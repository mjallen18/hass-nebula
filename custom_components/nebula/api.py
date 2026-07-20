"""Asynchronous client for Nebula's Prometheus `/metrics` endpoint.

Nebula exposes its stats via a standard Prometheus text-format endpoint
(configured in `nebula.yml` under the `stats:` block). We parse the text
ourselves rather than depend on `prometheus_client`, so the integration has
zero external Python dependencies and works on minimal HA installs.

The parser supports the Prometheus text format subset that Nebula emits:
counter / gauge / histogram / summary lines, with optional `{label="..."}`
blocks. Unknown metric types are still captured by name so the
`nebula.get_metrics` service can surface them.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import (
    LIGHTHOUSE_RX_PREFIX,
    LIGHTHOUSE_TX_PREFIX,
    METRIC_CERT_TTL,
    METRIC_HANDSHAKE_INITIATED,
    METRIC_HANDSHAKE_TIMED_OUT,
    METRIC_HOSTMAP_MAIN_HOSTS,
    METRIC_HOSTMAP_PENDING_HOSTS,
    METRIC_INFO,
    METRIC_PACKETS_LOST,
    MSG_RX_PREFIX,
    MSG_TX_PREFIX,
    INFO_LABEL_VERSION,
)

_LOGGER = logging.getLogger(__name__)

# A Prometheus exposition line looks like:
#   name{label1="v1",label2="v2"} 12.34 # optional comment
# or without labels:
#   name 12.34
# Lines starting with `#` are comments. TYPE / HELP lines are ignored here
# because we infer the value directly; type info is not needed for our
# read-only use case.
_LINE_RE = re.compile(
    r"""^(?P<name>[a-zA-Z_:][a-zA-Z0-9_:]*)  # metric name
        (?:\{(?P<labels>[^}]*)\})?            # optional label block
        \s+(?P<value>[-+]?(\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)  # value
    """,
    re.VERBOSE,
)
_LABEL_RE = re.compile(r"""(?P<k>[a-zA-Z_][a-zA-Z0-9_]*)="(?P<v>(?:\\.|[^"\\])*)\"""")


class NebulaAuthError(Exception):
    """Raised when the metrics endpoint requires auth we don't have."""


class NebulaEndpointError(Exception):
    """Raised on transport/parse failures talking to the metrics endpoint."""


@dataclass
class ParsedMetric:
    """A single sample parsed from the exposition document."""

    name: str
    labels: dict[str, str]
    value: float


@dataclass
class NebulaSnapshot:
    """Aggregated, integration-facing view of a metrics scrape.

    Every field is derived directly from metrics Nebula publishes; if a
    metric is missing (e.g. user disabled `message_metrics`), the field
    stays `None` so the corresponding entity can report `unknown`.
    """

    running: bool = True
    peer_count: int | None = None
    pending_handshakes: int | None = None
    cert_ttl: float | None = None
    handshakes_initiated: float | None = None
    handshakes_timed_out: float | None = None
    messages_tx: float | None = None
    messages_rx: float | None = None
    packets_lost: float | None = None
    version: str | None = None
    lighthouse_observable: bool = False
    lighthouse_activity: float = 0.0
    raw: dict[str, list[ParsedMetric]] = field(default_factory=dict)
    counters: dict[str, float] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)


def _parse_labels(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    labels: dict[str, str] = {}
    for m in _LABEL_RE.finditer(raw):
        # Unescape Prometheus label escapes: \\ -> \, \" -> ", \n -> newline.
        val = m.group("v").replace('\\"', '"').replace("\\\\", "\\").replace("\\n", "\n")
        labels[m.group("k")] = val
    return labels


def parse_prometheus(text: str) -> dict[str, list[ParsedMetric]]:
    """Parse a Prometheus text-format document into name -> samples.

    Histograms and summaries emit multiple samples per name (`_bucket`,
    `_count`, `_sum`); we keep them grouped under the base name but with the
    full sample name preserved on each ParsedMetric so callers can pick the
    series they want.
    """
    out: dict[str, list[ParsedMetric]] = {}
    for lineno, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _LINE_RE.match(line)
        if not m:
            _LOGGER.debug("Skipping unparseable metrics line %d: %s", lineno, line)
            continue
        name = m.group("name")
        labels = _parse_labels(m.group("labels"))
        try:
            value = float(m.group("value"))
        except ValueError:
            _LOGGER.debug("Skipping non-numeric value on line %d: %s", lineno, line)
            continue
        # Bucket/histogram samples carry the full name in the `name` group
        # (e.g. `foo_bucket`). Group under the leading identifier so callers
        # iterating by base name find them, but keep `name` as-is on the
        # sample for disambiguation.
        out.setdefault(name, []).append(ParsedMetric(name=name, labels=labels, value=value))
    return out


def _sum_prefix(parsed: dict[str, list[ParsedMetric]], prefix: str) -> float | None:
    """Sum values of every metric whose name starts with `prefix`.

    Returns `None` when no matching metric is present (i.e. the user did not
    enable that metric group in nebula.yml) so callers can distinguish
    "missing" from "zero".
    """
    total = 0.0
    found = False
    for name, samples in parsed.items():
        if name.startswith(prefix):
            found = True
            for s in samples:
                # Skip `_bucket` / `_count` / `_sum` derived samples — those
                # belong to histograms/summaries and would double-count.
                if name.endswith(("_bucket", "_count", "_sum")):
                    continue
                total += s.value
    return total if found else None


def _gauge_value(parsed: dict[str, list[ParsedMetric]], name: str) -> float | None:
    samples = parsed.get(name)
    if not samples:
        return None
    # Nebula emits single-sample gauges; take the first if multiple appear.
    return samples[0].value


def _counter_value(parsed: dict[str, list[ParsedMetric]], name: str) -> float | None:
    # Counters may be exposed as `name_total` (Prometheus >= 3 client
    # convention) — check both spellings.
    if name in parsed:
        return parsed[name][0].value
    legacy = f"{name}_total"
    if legacy in parsed:
        return parsed[legacy][0].value
    return None


def aggregate(parsed: dict[str, list[ParsedMetric]]) -> NebulaSnapshot:
    """Project a raw parse into the fields the integration exposes."""
    snap = NebulaSnapshot(running=True)
    snap.raw = parsed

    # Populate raw counter/gauge lookup for the get_metrics service.
    for name, samples in parsed.items():
        if name.endswith(("_bucket", "_count", "_sum")):
            continue
        # We don't trust TYPE lines (we skip them); treat anything ending in
        # _total as a counter, everything else as a gauge for the raw view.
        if name.endswith("_total") or name == "handshakes":
            snap.counters[name] = samples[0].value
        else:
            snap.gauges[name] = samples[0].value

    snap.peer_count = _gauge_value(parsed, METRIC_HOSTMAP_MAIN_HOSTS)
    snap.pending_handshakes = _gauge_value(parsed, METRIC_HOSTMAP_PENDING_HOSTS)
    snap.cert_ttl = _gauge_value(parsed, METRIC_CERT_TTL)
    snap.handshakes_initiated = _counter_value(parsed, METRIC_HANDSHAKE_INITIATED)
    snap.handshakes_timed_out = _counter_value(parsed, METRIC_HANDSHAKE_TIMED_OUT)
    snap.packets_lost = _counter_value(parsed, METRIC_PACKETS_LOST)
    snap.messages_tx = _sum_prefix(parsed, MSG_TX_PREFIX)
    snap.messages_rx = _sum_prefix(parsed, MSG_RX_PREFIX)

    # Lighthouse activity is "any lighthouse rx/tx counter is present AND
    # > 0". We capture the raw sum so the coordinator can compute deltas
    # between polls (a counter that never moves means we're not reaching
    # the lighthouse even if it's configured).
    lh_rx = _sum_prefix(parsed, LIGHTHOUSE_RX_PREFIX)
    lh_tx = _sum_prefix(parsed, LIGHTHOUSE_TX_PREFIX)
    if lh_rx is not None or lh_tx is not None:
        snap.lighthouse_observable = True
        snap.lighthouse_activity = (lh_rx or 0.0) + (lh_tx or 0.0)

    # Version from the `info` gauge labels.
    info = parsed.get(METRIC_INFO)
    if info:
        snap.version = info[0].labels.get(INFO_LABEL_VERSION)

    return snap


class NebulaMetricsClient:
    """Async client that fetches and parses the Nebula metrics endpoint."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        metrics_url: str,
        verify_tls: bool = True,
        timeout: float = 10.0,
    ) -> None:
        self._session = session
        self._metrics_url = metrics_url
        self._timeout = timeout
        self._connector_kwargs: dict[str, Any] = {}
        if metrics_url.lower().startswith("https://") and not verify_tls:
            # aiohttp uses ssl=False to disable verification entirely.
            self._connector_kwargs["ssl"] = False

    @property
    def metrics_url(self) -> str:
        return self._metrics_url

    async def async_fetch(self) -> NebulaSnapshot:
        """Fetch one scrape and return the aggregated snapshot.

        Raises:
            NebulaEndpointError: network failure or non-2xx response.
            NebulaAuthError: 401/403 from the endpoint.
        """
        try:
            async with asyncio.timeout(self._timeout):
                async with self._session.get(
                    self._metrics_url, **self._connector_kwargs
                ) as resp:
                    if resp.status in (401, 403):
                        raise NebulaAuthError(
                            f"metrics endpoint returned {resp.status}"
                        )
                    if resp.status != 200:
                        body = await resp.text()
                        raise NebulaEndpointError(
                            f"metrics endpoint returned {resp.status}: {body[:200]}"
                        )
                    text = await resp.text()
        except asyncio.TimeoutError as err:
            raise NebulaEndpointError(
                f"timed out fetching {self._metrics_url}"
            ) from err
        except aiohttp.ClientError as err:
            raise NebulaEndpointError(str(err)) from err

        parsed = parse_prometheus(text)
        if not parsed:
            # An empty 200 OK likely means we hit the wrong path or Nebula
            # started but hasn't emitted any metric yet. Treat as down so the
            # running binary_sensor flips off and the user notices.
            snap = NebulaSnapshot(running=False)
            snap.raw = {}
            return snap
        return aggregate(parsed)

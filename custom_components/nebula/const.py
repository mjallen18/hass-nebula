"""Constants for the Nebula VPN integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "nebula"

# Config entry fields
CONF_METRICS_URL: Final = "metrics_url"
CONF_VERIFY_TLS: Final = "verify_tls"

# Defaults
DEFAULT_NAME: Final = "Nebula"
DEFAULT_METRICS_URL: Final = "http://127.0.0.1:8080/metrics"
DEFAULT_SCAN_INTERVAL: Final = 30
DEFAULT_VERIFY_TLS: Final = True

# Service names
SERVICE_GET_METRICS: Final = "get_metrics"

# Nebula Prometheus metric names (after go-metrics-prometheus normalisation:
# "." -> "_", "-" -> "_"). We key on the normalised name.
METRIC_HOSTMAP_MAIN_HOSTS: Final = "hostmap_main_hosts"
METRIC_HOSTMAP_PENDING_HOSTS: Final = "hostmap_pending_hosts"
METRIC_CERT_TTL: Final = "certificate_ttl_seconds"
METRIC_HANDSHAKE_INITIATED: Final = "handshake_manager_initiated"
METRIC_HANDSHAKE_TIMED_OUT: Final = "handshake_manager_timed_out"
METRIC_PACKETS_LOST: Final = "network_packets_lost"

# Prefixes used to aggregate message counters.
MSG_TX_PREFIX: Final = "messages_tx_"
MSG_RX_PREFIX: Final = "messages_rx_"

# Prefixes used to detect lighthouse activity. The counters are only emitted
# when `lighthouse_metrics: true` is set in nebula.yml.
LIGHTHOUSE_RX_PREFIX: Final = "lighthouse_rx_"
LIGHTHOUSE_TX_PREFIX: Final = "lighthouse_tx_"

# The `info` gauge emitted by stats.go carries version/goversion/boringcrypto
# labels. We surface `version` as a sensor.
METRIC_INFO: Final = "info"
INFO_LABEL_VERSION: Final = "version"

# Coordinator data keys (the keys we stash in coordinator.data so the
# entity modules don't have to re-parse on every update).
DATA_RUNNING: Final = "running"
DATA_LIGHTHOUSE_ACTIVE: Final = "lighthouse_active"
DATA_LIGHTHOUSE_OBSERVABLE: Final = "lighthouse_observable"
DATA_PEER_COUNT: Final = "peer_count"
DATA_PENDING_HANDSHAKES: Final = "pending_handshakes"
DATA_CERT_TTL: Final = "cert_ttl"
DATA_HANDSHAKES_INITIATED: Final = "handshakes_initiated"
DATA_HANDSHAKES_TIMED_OUT: Final = "handshakes_timed_out"
DATA_MESSAGES_TX: Final = "messages_tx"
DATA_MESSAGES_RX: Final = "messages_rx"
DATA_PACKETS_LOST: Final = "packets_lost"
DATA_VERSION: Final = "version"
DATA_RAW_METRICS: Final = "raw_metrics"
DATA_RAW_COUNTERS: Final = "raw_counters"

# Platforms
PLATFORM_BINARY_SENSOR: Final = "binary_sensor"
PLATFORM_SENSOR: Final = "sensor"
PLATFORMS: Final = (PLATFORM_BINARY_SENSOR, PLATFORM_SENSOR)

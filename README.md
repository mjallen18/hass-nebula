# Nebula VPN for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration for
[Slack Nebula](https://github.com/slackhq/nebula) — a scalable overlay
networking tool. It scrapes Nebula's built-in Prometheus `/metrics` endpoint
and exposes the state of the tunnel as Home Assistant entities.

## Features

The integration reads the Prometheus stats endpoint that Nebula itself
exposes (configured via the `stats:` block in `nebula.yml`). No control
socket or SSH admin access is required — every entity below is derived
purely from metrics that Nebula publishes.

| Entity                                            | Source metric / derivation                        | Class        |
| ------------------------------------------------- | ------------------------------------------------ | ------------ |
| `binary_sensor.nebula_running`                    | `/metrics` endpoint responds                     | binary       |
| `binary_sensor.nebula_lighthouse_connected`       | lighthouse metric counters advancing between polls¹ | binary    |
| `sensor.nebula_peer_count`                        | `hostmap.main.hosts` gauge                       | measurement  |
| `sensor.nebula_pending_handshakes`                | `hostmap.pending.hosts` gauge                    | measurement  |
| `sensor.nebula_cert_ttl`                          | `certificate.ttl_seconds` gauge                  | duration     |
| `sensor.nebula_handshakes_initiated`              | `handshake_manager.initiated` counter            | total_increasing |
| `sensor.nebula_handshakes_timed_out`              | `handshake_manager.timed_out` counter            | total_increasing |
| `sensor.nebula_messages_tx`                       | sum of `messages.tx.*` counters                  | total_increasing |
| `sensor.nebula_messages_rx`                       | sum of `messages.rx.*` counters                  | total_increasing |
| `sensor.nebula_packets_lost`                      | `network.packets.lost` counter                   | total_increasing |
| `sensor.nebula_version`                           | `info` gauge labels                              | measurement  |

¹ Requires `lighthouse_metrics: true` in `nebula.yml`. If lighthouse metrics
are disabled the sensor reports `unknown` rather than guessing.

A `nebula.get_metrics` service is also registered: it returns the full
parsed Prometheus document as a response so advanced users can template
against any metric.

## Requirements

- A running Nebula instance with the `stats` block configured to expose a
  Prometheus endpoint. Minimum `nebula.yml` snippet:

  ```yaml
  stats:
    type: prometheus
    listen: 127.0.0.1:8080
    path: /metrics
    interval: 10s
    # message_metrics: true   # enables messages.tx/rx.* counters
    # lighthouse_metrics: true # enables lighthouse.rx/tx.* counters
  ```

- The Home Assistant process must be able to reach that HTTP endpoint. When
  Nebula runs as a companion add-on on HAOS, expose the listener on the
  add-on's container IP or via a port mapping.

## Installation

### HACS

1. Open HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://gitea.mjallen.dev/mjallen/hass-nebula` (category:
   Integration).
3. Install **Nebula VPN**.
4. Restart Home Assistant.
5. Settings → Devices & Services → Add Integration → **Nebula VPN**.
6. Enter the base URL of the Nebula stats endpoint
   (e.g. `http://127.0.0.1:8080/metrics`) and a friendly name.

### Manual

Copy the contents of `custom_components/nebula/` into your
`config/custom_components/nebula/` directory and restart Home Assistant.

## Configuration

The integration is configured entirely through the UI. Options:

| Field              | Default                              | Description                          |
| ------------------ | ------------------------------------ | ------------------------------------ |
| Name               | `Nebula`                             | Friendly name of the device.         |
| Metrics URL        | `http://127.0.0.1:8080/metrics`     | Full URL of Nebula's Prometheus endpoint. |
| Scan interval (s)  | `30`                                 | How often to poll the endpoint.      |
| Verify TLS         | `true`                               | TLS certificate verification (HTTPS). |

## Running Nebula on HAOS

Home Assistant OS is a locked-down appliance: a `custom_components`
integration cannot install or start the `nebula` binary. To actually bring
up the tunnel you need the companion add-on:

**[haos-nebula](https://gitea.mjallen.dev/mjallen/haos-nebula)** — runs
`nebula` inside a Home Assistant add-on container with `host_network` +
`CAP_NET_ADMIN` + `/dev/net/tun`, and exposes the Prometheus listener on
port 8080 so this integration can scrape it.

To generate a config for the add-on, use
[`nebula-tui`](https://gitea.mjallen.dev/mjallen/nix-config) (if you have
it) with the `export-haos` subcommand:

```bash
nebula-tui export-haos <hostname> -o /share/nebula/config.yml
```

See the [add-on README](https://gitea.mjallen.dev/mjallen/haos-nebula) for
full setup instructions.

## Why no per-peer sensors?

Nebula's public Prometheus metrics are aggregate — they do not break out
per-peer byte counters or per-peer tunnel state. Exposing per-peer
entities would require driving Nebula's interactive SSH admin shell, which
is fragile and not intended for programmatic use. This integration
intentionally sticks to the stable, documented Prometheus interface.

## License

MIT — see [LICENSE](LICENSE).

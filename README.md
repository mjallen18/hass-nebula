# Nebula VPN for Home Assistant

A [Home Assistant](https://www.home-assistant.io/) custom integration for
[Slack Nebula](https://github.com/slackhq/nebula) — a scalable overlay
networking tool. Exposes lighthouse connectivity, per-peer status, traffic
counters, and overall tunnel state as Home Assistant entities.

## Features

- **Service health** — `binary_sensor.nebula_running` reflects whether the
  control socket responds.
- **Lighthouse reachability** — `binary_sensor.nebula_lighthouse_connected`
  derived from reported lighthouse state.
- **Per-peer status** — one `binary_sensor.nebula_peer_<vpn_ip>` per known
  remote host, plus a `sensor.nebula_peer_count` aggregate.
- **Traffic stats** — `sensor.nebula_inbound` and `sensor.nebula_outbound`
  report bytes per second across the tunnel.
- **Services** — `nebula.list_hosts`, `nebula.host_info`, and
  `nebula.disconnect_peer` map to the Nebula control API.

## Requirements

- A running Nebula instance reachable by its control socket
  (configured in `nebula.yml` under `stats:` / `pki:` as appropriate for
  your version).
- The Home Assistant process must be able to read the Unix control socket
  file. On HAOS this means the Nebula process must run in a context that
  shares the socket path with the Home Assistant container — typically via
  a companion add-on (see *Running Nebula on HAOS* below).

## Installation

### HACS

1. Open HACS → Integrations → ⋮ → Custom repositories.
2. Add `https://gitea.mjallen.dev/mjallen/hass-nebula` (category:
   Integration).
3. Install **Nebula VPN**.
4. Restart Home Assistant.
5. Settings → Devices & Services → Add Integration → **Nebula VPN**.
6. Enter the path to the Nebula control socket (default
   `/var/run/nebula/control.sock`) and a friendly name.

### Manual

Copy the contents of `custom_components/nebula/` into your
`config/custom_components/nebula/` directory and restart Home Assistant.

## Configuration

The integration is configured entirely through the UI. Options:

| Field              | Default                          | Description                          |
| ------------------ | -------------------------------- | ------------------------------------ |
| Name               | `Nebula`                         | Friendly name of the device.         |
| Control socket     | `/var/run/nebula/control.sock`   | Unix socket path to `nebula-service`.|
| Scan interval (s)  | `30`                             | How often to poll the control API.   |

## Running Nebula on HAOS

Home Assistant OS is a locked-down appliance: a `custom_components`
integration cannot install or start the `nebula` binary. To actually bring
up the tunnel you need a companion add-on that runs `nebula-service`
inside a container and exposes the control socket on a path the Home
Assistant container can reach (for example via `/data` or a bind mount).

A matching add-on is tracked separately — once published, link it here.

## License

MIT — see [LICENSE](LICENSE).

# Nebula VPN

Exposes the state of a [Slack Nebula](https://github.com/slackhq/nebula)
overlay network to Home Assistant: lighthouse connectivity, peer status,
traffic counters, and tunnel up/down state.

Connects to an existing `nebula-service` instance via its Unix control
socket. To actually run Nebula on Home Assistant OS you need a companion
add-on (see the README for details).

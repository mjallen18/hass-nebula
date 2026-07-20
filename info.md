# Nebula VPN

Exposes the state of a [Slack Nebula](https://github.com/slackhq/nebula)
overlay network to Home Assistant by scraping Nebula's built-in Prometheus
`/metrics` endpoint. Provides tunnel up/down, lighthouse connectivity,
peer count, handshake counters, message counters, packet loss, and cert
TTL as entities.

To actually run Nebula on Home Assistant OS you need a companion add-on
(see the README for details).

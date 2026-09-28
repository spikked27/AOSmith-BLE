# Validation of development preview 0.1.0

September 28, 2026.

- Python 3.13.15; installed Home Assistant 2025.12.5 with its Bluetooth/USB dependencies.
- 27 passing tests: captured read packets, CRC, temperature encoding, synthetic
  HMAC fixture, fragmented notifications, unrelated response rejection, expired
  sessions, reconnect on dropped reads, serialized concurrent operations,
  successful write/readback, ignored writes, uncertain writes without replay,
  explicit enrollment, redacted diagnostics, HA entity properties and controls,
  existing/new pairing flows and enrollment retry behavior.
- Ruff lint and formatting checks passed.
- One upstream Home Assistant aiohttp deprecation warning during test import.
- Manual nRF Connect tests on HPS10-80H45DV confirmed wire-level auth, reads, and
  Heat Pump/Hybrid switching. They did not run this integration's Python code.

Still requires actual HA installation, BLE hardware/proxy tests, temperature
write verification, reconnect after radio timeout, multi-slot pairing validation,
and an internet-blocked endurance test. Simulation does not establish these.

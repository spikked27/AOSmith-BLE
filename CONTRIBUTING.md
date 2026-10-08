# Contributing

Use [Issues](https://github.com/spikked27/AOSmith-BLE/issues) for reproducible bugs,
model compatibility reports and feature requests. Include the heater model,
firmware and integration/Home Assistant versions. Redact personal information
from logs and diagnostics; never post PINs or pairing credentials.

For code changes, install `requirements-test.txt`, follow the Bluetooth/USB
requirements setup in `.github/workflows/tests.yml`, and run:

```sh
ruff check .
ruff format --check .
pytest -q
python scripts/build_release.py
```

Add focused regressions for protocol or lifecycle changes. Use captured, redacted
frames or a simulated peripheral; mark hardware assumptions explicitly. Keep
writes serialized, preserve original backups, and never replay a write to resolve
an ambiguous acknowledgement. Ordinary polling must not change heater settings.
The sole automatic-write exception is ClockGuard: a missed value-changing tariff
transition with fresh before/after evidence, verified device schedule and fresh
eligibility checks. Preserve its one-attempt-per-episode and 24-hour durable limits;
never use the non-ticking clock readback to trigger correction.

Pull requests should explain the user-facing change, validation and model coverage.
Do not include proprietary app binaries, raw private diagnostics or credentials.

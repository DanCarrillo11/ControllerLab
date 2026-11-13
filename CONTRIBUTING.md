# Contributing

Keep the interface and documentation in English. Preserve original measurements;
output transforms belong only to the optional emulation path. Do not auto-start
virtual devices, rumble or driver installers.

Install development dependencies without launching a driver installer:

```powershell
$env:VGAMEPAD_SKIP_VIGEMBUS_INSTALL = 'true'
python -m pip install -r requirements-build.txt
python tools/run_checks.py outputs/test-summary.json
```

Use `--demo`, `--render-demo`, `--page` and `--render-report` for background UI
checks. These modes do not create virtual output or access physical input.
`--virtual-check` is a separate explicit neutral-output check; record unavailable
hardware as unavailable rather than marking it passed.

Include controller model, connection, selected profile, app version, reproduction
steps and exact error in bug reports. Review copied diagnostics before sharing.
Do not commit personal reports or controller settings.

See docs/RELEASE_CHECKLIST.md for acceptance and docs/EMULATION.md for virtual-output
limits. Preserve artwork provenance, upstream files and third-party notices.

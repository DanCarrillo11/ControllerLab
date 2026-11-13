# Release candidate acceptance

Automated evidence is recorded in BUILD_INFO.json inside each package. A stable
1.0 needs the physical items below in addition to passing automated checks.

- [x] Guided checklist, raw and mapped observations, center measurement.
- [x] Visual PNG/HTML reports, JSON/CSV, stored trajectories.
- [x] Named presets, input capture, history search/rename/import/delete/restore.
- [x] Explicit Xbox 360/DS4 output integration and configurable transforms.
- [x] Neutral cleanup, no auto-start, source pinning and self-output filtering tests.
- [x] Native source-to-virtual report mapping verified with isolated API fakes.
- [x] Tray lifecycle, temporary game profiles, stop shortcut and first-run setup.
- [x] Native shortcut registration/message routing and process-path readback checked.
- [x] Successful native virtual target creation and removal on the local PC after
  driver repair; see [recorded evidence](validation/virtual-output-after-driver-repair.json).
- [ ] Game input and optional vibration forwarding verified physically.
- [ ] Wider USB/Bluetooth tests: Xbox, DualShock, Switch, generic pads and adapters.
- [ ] HidHide setup verified by the user for games that otherwise receive double input.

Physical evidence currently covers discovery and input readback from a DualSense,
plus neutral Xbox 360/DS4 virtual-target creation and removal on the local PC.
Forwarding physical input to a game and vibration remain unverified. Other
families have rendering and simulated-input coverage. Report untested or
unavailable functions as such; do not substitute an overlay for hardware evidence.

## Manual candidate test

1. Start without a controller, open history, connect and reconnect a device.
2. Run a guided test. Deliberately leave an input untouched and confirm it stays
   Not observed. Confirm vibration only if it was actually felt.
3. Create two profiles, assign different settings, switch and restart the app.
4. Record, rename, filter, export, delete and restore a report. Import its JSON.
5. Compare two reports; check that missing measurements remain missing.
6. On a working virtual bus, start each output type, test directions and triggers,
   then disconnect the input. Confirm the virtual device detaches and never
   becomes its own input. Exit/minimize behavior should match the documentation.
7. Test the extracted portable on another Windows x64 PC without Python.
8. Enable tray behavior, minimize/restore, close to tray and use Quit. Confirm
   output stays available while hidden and detaches on Quit.
9. Associate a game with a preset, open it, alt-tab and close it. Confirm temporary
   selection, manual-profile restoration and no automatic output restart.
10. Use the configured global stop shortcut while a game is focused. Test a
    conflicting shortcut and confirm the previous one remains available.
11. Open the setup assistant, map inputs and explicitly check virtual outputs.
    Skip/Finish should persist; closing an unfinished assistant may show it again.
12. Change the active profile from the controller summary. Confirm output stops
    on a profile change but stays active while navigating to sessions or settings.
13. Edit the final game rule and choose Save directly. Discard/Escape should
    restore drafts without hiding an embedded settings page. Test at 1080 × 730.

Keep reports labeled with their connection and selected profile.
Identical controllers may share a GUID. The app does not infer unique serial numbers.

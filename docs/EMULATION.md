# Virtual controller output

Controller Lab can transform a mapped Windows controller into one virtual Xbox
360 (XInput) or DualShock 4 output. This is an independently implemented input
bridge using [vgamepad](https://github.com/yannbouteiller/vgamepad), not a copy of
DS4Windows or x360ce. The same virtual-bus approach is documented by
[x360ce v4](https://www.x360ce.com/).

## Setup

1. Connect the input device to Windows and select it in Controller Lab.
2. If its inputs are not mapped, use **Controller options → Map inputs**. Listen captures
   raw axes/buttons/hats. Review direction and trigger range before saving.
3. Open **Emulation**, select Xbox 360 or DualShock 4, configure the output and
   optionally remap buttons. Save the configuration to the selected profile.
4. Press **Start emulation**, then select the virtual device in the game.
5. Keep Controller Lab open or minimized while playing. Stop before changing
   the input/profile. The app detaches its output on disconnect or exit.

The default global stop shortcut is **Ctrl+Alt+F11**. Configure it in
**Settings → General**. Stop emulation also appears beside the page title while output is active.
Optional game rules select presets but never start or restart output.
See the [desktop workflow guide](DESKTOP_WORKFLOW.md) for tray behavior, setup
and automatic profile selection.

Output deadzone, curve, sensitivity, inversion and remapping are separate from
diagnostic measurements. Original raw input remains available for testing.
Game vibration forwarding is optional and off by default. Enabling it requests
standard physical rumble; advanced haptics and adaptive triggers are not emulated.

## Driver requirements and actual evidence

The Windows implementation requires a working
[ViGEmBus](https://github.com/nefarius/ViGEmBus) installation. ViGEmBus has been
retired upstream; consult the upstream documentation for your Windows setup.
Controller Lab includes the user-space client library, not a driver installer.
It never installs, repairs or removes kernel drivers automatically.

The first local check returned **VIGEM_ERROR_BUS_NOT_FOUND** despite a running
ViGEmBus service. After the user repaired the driver using the official 1.22
installer, Windows reported the bus device as healthy and the same packaged
executable successfully created neutral Xbox 360 and DualShock 4 targets and
detached them. The driver file still reports 1.21.442.0. See the recorded
[post-repair check](validation/virtual-output-after-driver-repair.json).

This verifies native target creation and removal on this PC. It did not forward
physical inputs or request vibration, and does not verify game compatibility.
A registered/running service alone does not prove readiness; use the exact error
shown in Output status when reviewing the Windows driver.

The transformation, Xbox/DS4 button and axis reports, neutral-state cleanup,
source pinning and disconnect behavior are tested independently with fake sinks.
These tests and the neutral-target check do not replace physical input, game and
vibration tests.

An explicit optional check is available for developers:

```powershell
.\ControllerLab.exe --virtual-check virtual-output-check.json
```

It attempts neutral targets and detaches them without forwarding physical input
or requesting vibration. Exit code 2 means the driver/output check was unavailable.
Normal startup and demo/render modes never create virtual controllers.

## Double input and HidHide

Some games can read both the physical and virtual device. Use
[HidHide's own setup documentation](https://github.com/nefarius/HidHide) when
exclusive access is needed. Allow the ControllerLab executable to read the physical
device, then hide that physical device from other applications. Do not hide the
virtual output. The Emulation page can copy the exact executable path.
For source runs the allowlisted process is the Python executable.

Controller Lab only checks driver presence and opens documentation on demand;
it does not change HidHide's allowlist, device list or hiding state. Other mappers
and Steam Input can expose additional virtual devices; choose the intended source.

## Limits for this candidate

- One selected input and one virtual output at a time.
- Inputs must already be readable by Windows; this does not add native Wii
  Bluetooth or GameCube-adapter protocols.
- DS4 output includes ordinary buttons, axes, triggers, d-pad, PS and touchpad click.
  Motion, touch coordinates, audio, lightbar passthrough, macros and keyboard/mouse
  output are outside this candidate.
- A game must accept the chosen output type. Universal game compatibility is not
  claimed. Test your actual game and connection before relying on a saved preset.

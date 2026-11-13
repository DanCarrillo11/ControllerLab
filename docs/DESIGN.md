# Desktop interface

Controller Lab shares the dark Windows design used by UniversalSaveEditor and
SteamAchievementManager. The theme in `controller_lab/theme.py` uses a charcoal
canvas (`#171719`), neutral panels (`#242426`) and blue actions (`#087beb`). The
interface uses Segoe UI and Consolas with bundled fallback fonts.

## Controller workspace

- A full-width header carries the app identity, connection status, Settings and Help.
- The attached sidebar groups controller selection, testing and saved work.
- The detected controller, active profile and power share a summary panel. Device
  actions and the new-profile button sit beside the information they affect.
- The live controller sits beside button activity, trigger pressure and stick position.
  Blue highlights show current input in the original controller artwork.
- Emulation, guided tests, sessions and settings use the same panels and controls.
  Recording and emergency stop actions stay by the page title when available.

## Native motion

Page changes dissolve over 190 ms. Navigation selection and switches ease over
170–180 ms; disclosures use a 200 ms reveal. Button hover edges settle in 170 ms.
Visual tracks smooth over 95 ms, independently of their reported values. Button
and trigger artwork eases toward the latest input with a bounded 16 ms visual
timer. No animation delays polling, changes a saved report or starts output.

Animations are interruptible: repeated navigation discards obsolete snapshots,
repeated disclosure changes cancel the old target, and hidden views stop their
visual timers. Preview captures normally render settled states. The motion QA
tool explicitly enables animations with simulated inputs. Its timings describe
local offscreen painting, not physical input latency or every user's frame rate.

Settings → General → Reduce interface motion is persisted separately from device
profiles. It disables decorative transitions and smoothing. The UI remains fully
usable with keyboard navigation and without motion. General settings Save and
Discard stay outside its scrollable form.

The UI remains English and supports the existing 1080 × 730 minimum client area.
The power summary reserves space for complete status text.
App screenshots use simulated inputs and are not evidence of hardware testing.

## State and information

Mint denotes an available connection or active output, amber explicitly denotes
simulated input, and rose denotes an unavailable/lost connection. Stopped output
is neutral. These colors describe connection/output states, not hardware grades.
Text accompanies each state. The global Stop action stays beside the page title whenever
virtual output is active.

A reported zero trigger position appears as `0%`; absent/unmapped readings show
an em dash and a disabled progress track. Input loss clears the live summary
immediately. Compact progress tracks do not duplicate the numeric value or step
label already displayed beside them. The design requires no change to drivers,
emulation transformations, input assignments or stored profile formats.

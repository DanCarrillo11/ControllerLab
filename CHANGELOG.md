# Changelog

## 0.9.0 RC12 — PlayStation controller icon

- Use the supplied PlayStation controller photo with its cable and background
  removed for the application icon and README.

## 0.9.0 RC11 — interface aligned with the companion applications

- Use a full-width application header, an attached controller sidebar and blue
  actions on neutral dark surfaces, matching the other desktop projects.
- Group the controller, profile and power in one summary panel and place
  Settings and Help in the app header.
- Use the same palette in diagnostics, emulation, reports and controller artwork.

## 0.9.0 RC10 — text-only workspace navigation

- Remove icons from the sidebar's workspace navigation, including Settings.
- Align navigation labels to a consistent left inset without an unused icon slot.
- Retain selection, hover, keyboard focus and existing page actions.

## 0.9.0 RC9 — readable status and honest interaction cues

- Widen the power summary and allow word wrapping so Wired power and Not reported
  remain readable at the minimum window size and Windows display scaling.
- Present the sidebar's A closer look caption as plain text, without a card frame.
- Remove hover illumination from passive information cards. Buttons, navigation,
  switches and other real controls retain their existing interaction feedback.

## 0.9.0 RC8 — NeoViolet desktop design

- Recompose the workspace around an identity/navigation rail, contextual task
  header and independent controller, profile and power cards. Turn Overview
  into a large controller playground beside live activity, trigger and stick tiles.
- Add interruptible page dissolves, animated navigation selection, hover edges,
  pill switches, disclosure reveals and smooth visual input tracks. Timers stop
  when their views hide; actual input values and output handling remain immediate.
- Add a persisted Reduce interface motion preference and keep General settings
  Save/Discard controls outside the scrolling form.
- Visualize the physical-to-virtual signal path in Emulation. Animation denotes
  active forwarding only; stopped/demo output stays explicitly labeled.
- Adapt the owner's supplied NeoViolet reference into the native Qt workspace:
  near-black canvas, floating rounded panels, violet navigation, restrained
  violet/pink primary actions and soft cached ambient backgrounds.
- Bundle Plus Jakarta Sans and JetBrains Mono with their OFL licenses for a
  consistent interface that works offline, including in portable builds.
- Give the controller preview more room, keep the active profile and device
  options together, and present button activity and trigger values as compact
  readout cards. Distinguish left/right trigger accents.
- Display the existing controller artwork in lavender with pink active inputs;
  retain its source files, proportions, symbols and input assignments.
- Style dialogs, checkboxes, tabs, reports, plots, fields and menus consistently;
  preserve keyboard focus indicators and truthful connection/demo states.
- Retain all input, profile, session and virtual-output behavior. Review the
  nine workspaces at standard and minimum sizes and verify bundled fonts.

## 0.9.0 RC7 — diagnostic workspace design

- Unify the dark ink/navy palette, typography hierarchy, panel surfaces, button
  weights, keyboard focus and menu/dropdown indicators across the app.
- Compact the app header, add task icons to navigation and group diagnostic tabs
  in one segmented control while preserving their existing actions.
- Add distinct connection/output status chips with neutral, connected, simulated
  and error presentations. Status colors do not claim controller health.
- Frame the controller in a cached precision-grid stage without changing its
  artwork, proportions, input highlights or geometry.
- Add compact live trigger readouts beside button activity. Missing readings use
  an em dash and clear immediately on input loss rather than looking like zero.
- Align diagnostic plots, report exports and dialogs with the same palette.
- Bundle and verify interface glyph assets; review all workspaces at standard
  and minimum sizes with explicitly simulated inputs.

## 0.9.0 RC6 — create named configurations directly

- Add a visible plus action beside Active profile and New profile / Manage profiles
  actions inside its dropdown. Action entries never become a saved profile.
- Create and activate a named profile in one atomic write, copying the visible
  configuration, including unsaved emulation adjustments. Other presets stay separate.
- Validate empty, duplicate and overlong names; keep the creation dialog open for
  correction. Cancel, failed writes and controller changes do not create a preset.
- Stop output after a successful profile switch and retain saved selections across
  restarts. Recordings keep the profile identity they started with when switching.
- Verify the new profile dialog in the packaged app alongside the existing pages.

## 0.9.0 RC5 — transparent branding and detected-device thumbnails

- Render the selected joystick symbol from clean vector artwork to transparent
  PNG and Windows ICO assets, retaining its negative-space holes and lower gap.
- Prepare transparent light/dark README logo variants for GitHub themes.
- Show the detected controller's existing artwork in the sidebar and controller
  summary, including DualSense, DualShock, Xbox, Switch, Wii, GameCube and generic.
- Keep device identity thumbnails independent of a manually chosen testing overlay.
- Verify bundled icon transparency and device-thumbnail changes on selection.

## 0.9.0 RC4 — chosen joystick icon

- Replace the previous gamepad mark with the project owner's supplied white
  arcade joystick image, retaining the original design and black background.
- Use the chosen image for the window, tray, header, device-list icons and
  executable icon. Package the runtime PNG and seven Windows ICO sizes.
- Keep the uploaded source image and use reproducible format conversion only.
  Verify the runtime icon is bundled in the portable application.

## 0.9.0 RC3 — a clearer workspace

- Group primary tasks in the sidebar; keep live input, sticks, triggers and raw
  inputs together under Test controller, remembering the last diagnostic view.
- Bring Settings and Game profiles inside the main window. Group app preferences,
  controller settings and help into separate settings categories.
- Add a direct active-profile picker and contextual controller options. Switching
  profiles stops output; navigating between pages does not.
- Simplify Emulation around output selection, vibration and Start. Put tuning,
  remapping and connection help behind disclosure controls; keep Stop available
  across pages whenever output is active.
- Arrange game rules as a list and editor. Save includes the latest edited game
  without requiring a separate Add click. Discard restores saved values.
- Pause game detection while editing game profiles and ignore scans that finish
  after entering the editor. Keep session recording actions in their context.
- Improve connection-empty guidance, battery labeling and small-window layout.
- Extend packaged GUI checks to all nine workspace pages and add navigation,
  persistence, save/discard and active-output regression coverage.

## 0.9.0 RC2 — desktop workflow and game profiles

- Add a system tray menu with Open, Stop emulation and Quit. Minimize/close-to-tray
  are optional; normal close still detaches output and exits.
- Add a configurable global stop shortcut, Ctrl+Alt+F11 by default. Report key
  conflicts and preserve the old shortcut when a replacement cannot register.
- Add per-controller game rules using full executable paths. Read running games
  in the background, prefer the focused matching game, and retain that choice
  when alt-tabbing. Temporary selections never replace the saved manual profile.
- Restore the manual profile when the game closes. Manual profile selection
  pauses automation until matching games close or Game profiles is saved again.
- Stop output and finish recordings on automatic profile changes; output always
  needs an explicit Start and never resumes after the stop shortcut by itself.
- Add a four-step first-run assistant for connection, mapping, optional neutral
  virtual-output checks and next steps. It never installs or changes drivers.
- Add tests for profile lifecycle, stale background results, shortcut conflicts,
  native message handling, tray exit and setup. Include dialog renders in the
  frozen application checks and optional native desktop evidence in packages.

## 0.9.0 RC1 — guided diagnostics and optional virtual output

- Add a guided button/direction, stick, trigger, center and optional vibration
  checklist. Missing observations stay pending; vibration needs user confirmation.
- Store bounded stick trajectories and raw button edges. Export visual PNG/HTML
  reports alongside JSON/CSV, with missing measurements kept distinct from zero.
- Add named presets for mappings, overlays and emulation, preserving legacy defaults.
- Capture axes, buttons and hat directions with Listen before applying assignments.
- Add history search, naming, import, reversible deletion and chosen comparisons.
- Add a compatibility table, troubleshooting and copyable diagnostics.
- Implement explicit Xbox 360/DS4 output through vgamepad/ViGEmClient, configurable
  transforms/remapping and opt-in game vibration forwarding. No output on startup,
  no driver installation, cleanup on disconnect/exit and self-output filtering.
- Prepare Windows CI, artifact packaging, notices, issue reporting and acceptance docs.
- Verify neutral Xbox 360 and DualShock 4 target creation and removal using the
  packaged executable after the user repaired ViGEmBus. This resolves the earlier
  VIGEM_ERROR_BUS_NOT_FOUND result. Physical input forwarding, in-game behavior
  and vibration remain unverified.

## 0.1.5 — companion desktop workspace

- Match UniversalSaveEditor and Achievement Desk with neutral charcoal surfaces,
  blue actions, a compact sidebar and a selected-device summary.
- Give the controller preview the main canvas; move vibration controls into an
  inline drawer and group overlay selection, mapping and device details in Settings.
- Place left/right trigger traces side by side and compact the stick measurement
  controls. Add a persistent saved-session shortcut in the sidebar.
- Elide long names and held-button lists while preserving their full tooltip text.
- Clear power and input summaries on disconnection, and close the device's drawer.
- Update the plots, vector surface fills, dialogs and preview captures to the theme.
- Verify all pages at 1080 × 730 and 1280 × 840, including the vibration drawer,
  long device names, empty state and history without a connected controller.

## 0.1.4 — front-facing Xbox and consistent outline weights

- Replace the perspective Xbox view with front-facing Xbox One artwork and
  preserve its circular buttons and sticks. Update the neutral generic layout too.
- Normalize outline weights with screen-space strokes that stay steady when
  resizing. Strengthen the thin filled details in the DualShock source to match.
- Remove redundant offset shadow contours from the GameCube color artwork so
  its outlines do not appear doubled.
- Replace GameCube's abbreviated GCN label with the full two-line Nintendo
  GameCube vector wordmark, centered above Start/Pause.
- Capture gallery thumbnails at their final size so screenshot scaling does not
  introduce artificial differences in line weight.
- Add checks for resizing, Xbox proportions and the full GameCube wordmark.

## 0.1.3 — centered PlayStation symbols and overlay gallery

- Center the square, circle and cross within their face-button rings on both
  PlayStation views; optically align the triangle by its visual center.
- Separate the DualShock 4 symbols from their button rings so symbol adjustments
  preserve the original ring positions and controller body contours.
- Add regression checks for all eight PlayStation face symbols and DS4 rings.
- Include a seven-model screenshot gallery and an offscreen capture tool using
  explicitly simulated input. All seven models remain selectable in the app.

## 0.1.2 — tester-style vector overlays

- Replace product photographs with cyan line-art SVGs adapted from DualSense
  Tester, VSCView's Gamepad Asset Pack and credited community controller artwork.
- Illuminate individual button shapes, fill triggers by pressure, and move the
  actual vector stick caps using the reported axes.
- Keep aspect ratios and the original contour paths at all window sizes.
- Add a standard neutral vector layout for generic controllers.
- Bundle original/adapted SVG sources and all artwork license texts.
- Add checks for input highlight isolation, correct direction positions, stick
  motion, trigger fill and GameCube rear-control clipping.

## 0.1.1 — official controller artwork

- Replace the hand-painted controller bodies with unmodified photographs from
  Sony, Microsoft and Nintendo's official product pages.
- Fit photographs with their original proportions and align live button/stick
  highlights to the real controls. Retain the manufacturer's original image bytes.
- Use a neutral input view for unidentified generic controllers, which do not
  correspond to a single official hardware design.
- Include all images locally, with source links, ownership and checksums.
- Keep the existing input backend, measurements and session behavior.

## 0.1.0 — local preview

- Automatic device discovery and conservative family identification.
- Seven original controller schematics with automatic and manual selection.
- Live mapped/raw inputs, center and circle measurements, trigger traces.
- Explicit standard rumble tests; no automatic vibration on startup.
- App-local adapter assignments and deadzone previews.
- Local session history, previous-session comparison, JSON and CSV export.
- Background-only demo rendering and frozen-runtime input checks.

Physical evidence is currently limited to discovery and input readback from one
DualSense Wireless Controller. This preview is not a published stable release.

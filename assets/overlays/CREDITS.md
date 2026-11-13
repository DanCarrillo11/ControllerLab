# Controller overlay artwork

These are community vector overlays, not manufacturer photographs or official
manufacturer software. Controller Lab adds the local input renderer and theme.

| View | Original artwork / application | Author | Artwork license |
|---|---|---|---|
| DualSense and DualShock 4 | [DualSense Tester](https://github.com/daidr/dualsense-tester), `design/` | Xuezhou Dai (daidr), 2023 | MIT |
| Switch Pro | [Gamepad Asset Pack](https://github.com/AL2009man/Gamepad-Asset-Pack), originally made for [VSCView](https://github.com/Nielk1/VSCView) | Al. Lopez (AL2009man), 2024 | MIT |
| Front-facing Xbox One, generic standard layout and GameCube | [ControllerOverlays](https://github.com/datkat21/ControllerOverlays), `styles/xbox/xbox_one_black.svg` and `styles/gcn/gamecube_indigo.svg` | ControllerOverlays contributors | GPL-3.0 |
| GameCube wordmark lettering | [Nintendo GameCube Official Logo](https://commons.wikimedia.org/wiki/File:Nintendo_GameCube_Official_Logo.svg), lettering portion only | Nintendo; vector uploaded by JustDanPatrick | Public domain text logo (PD-textlogo), as recorded by Wikimedia Commons |
| Wii Remote base | [Wiimote 1 Player Icon](https://commons.wikimedia.org/wiki/File:Wiimote_1_Player_Icon.svg) | Alexanderpas, 2007 | CC-BY-SA-3.0 (selected from the author's offered licenses) |

The original SVG files are preserved in `upstream/`. Exact revisions, source links
and SHA-256 checksums are recorded in `sources.json`. License texts are in `licenses/`.
The adapted Xbox, generic and GameCube SVGs remain GPL-3.0, and the adapted Wii SVG remains
CC-BY-SA-3.0. These licenses apply to the respective artwork files; the application's
own code retains its separate MIT license.

Adaptations change presentation and control hooks: a consistent cyan outline
theme, removal of editor metadata and unused elements, individually mapped buttons,
and a neutral generic layout without the brand mark. The Wii base is extended with
directional regions and individual 1/2 controls. Original controller body contours
are preserved. PlayStation face symbols are translated to center them within the
button rings; triangles use optical centering. DualShock 4 compound paths are split
into rings and separate symbols without changing the ring geometry.
Outlines use non-scaling strokes; the DS4 source's thin filled ink receives a
lighter edge to match. Xbox artboard margins are cropped without distorting its
front-view geometry. GameCube's GCN placeholder is replaced with the full
two-line wordmark, recolored to the interface theme; the separate cube icon is omitted.
Redundant offset GameCube shadow contours are removed so each edge is inked once.
Neutral fills match the companion workspace's charcoal surface (#242426).
`tools/prepare_overlays.py` is the reproducible adaptation source.

Input rendering changes only visual states: button fills, trigger fill levels and
stick cap positions. It does not copy another application's device input code.
Product names identify controller families and do not imply endorsement.

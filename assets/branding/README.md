# Application icon

`joystick-source.png` is the original image supplied by the project owner for the
Controller Lab icon. Its SHA-256 is
`62d9bfbd7109621f1fd59f1e68f71f0778fcdfc391ef25861ff115e0d5837f5c`.

`joystick.svg` is a native vector reconstruction of the selected symbol, keeping
the round ball, plate, oval cutout, central notch and separate lower strip. It
provides clean transparent negative spaces without altering the archived upload.

`tools/build_assets.py` renders it as transparent `assets/app.png` and a seven-size
Windows `assets/app.ico`. `assets/app-dark.png` is the dark-color transparent
variant for a light README background. The README's picture element selects the
appropriate PNG for the reader's theme. There is no painted background rectangle.

Generated logo proposals and unsuccessful bitmap cutouts are not application
assets. Device thumbnails use the already-credited controller overlays rather
than this app logo; see `assets/overlays/CREDITS.md`.

"""Adapt reviewed third-party vector geometry for Controller Lab's outline theme.

Original files and their licenses stay alongside the generated SVG sources.
Only presentation and control IDs change; controller contours are not redrawn.
"""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from pathlib import Path
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET
from copy import deepcopy

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QGuiApplication
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1] / "assets" / "overlays"
NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", NS)
CYAN = "#22bfd4"
LINE_WIDTH = 1.5  # Logical screen pixels, independent of source units or transforms.

SPECS = {
    "dualsense": {"style": "stroke", "parts": {
        "a": "cross", "b": "circle", "x": "rect", "y": "triangle", "back": "create", "start": "options",
        "guide": "ps", "misc1": "mute", "touchpad": "touchpad", "dpup": "dpad-up", "dpdown": "dpad-down",
        "dpleft": "dpad-left", "dpright": "dpad-right", "leftshoulder": "l1", "rightshoulder": "r1",
        "lefttrigger": "l2", "righttrigger": "r2"},
        "sticks": {"left": "l3", "right": "r3"}, "remove": ["画板1", "t1", "t2"]},
    "playstation": {"style": "ink", "parts": {
        "a": "Active_Cross", "b": "Active_Circle", "x": "Active_Square", "y": "Active_Triangle",
        "back": "Active_Share", "start": "Active_Options", "guide": "Active_PS", "touchpad": "Active_TouchPad",
        "dpup": "Active_DPadTop", "dpdown": "Active_DPadBottom", "dpleft": "Active_DPadLeft", "dpright": "Active_DPadRight",
        "leftshoulder": "Active_L1", "rightshoulder": "Active_R1", "lefttrigger": "Active_LT", "righttrigger": "Active_RT"},
        "sticks": {"left": "Active_LS", "right": "Active_RS"}, "remove": ["DualShock", "TPPattern"]},
    "xbox": {"style": "outline", "parts": {"a": "Button_A", "b": "Button_B", "x": "Button_X", "y": "Button_Y",
        "back": "Button_Select", "start": "Button_Start", "guide": "Button_Home",
        "lefttrigger": "Button_L", "righttrigger": "Button_R", "leftshoulder": "Button_ZL", "rightshoulder": "Button_ZR",
        "dpup": "Dpad_Up", "dpdown": "Dpad_Down", "dpleft": "Dpad_Left", "dpright": "Dpad_Right"},
        "sticks": {"left": "Analog_Stick", "right": "Analog_C_Stick"}, "crop": "xbox_one_black"},
    "switch": {"style": "outline", "parts": {"a": "g10417", "b": "g10422", "x": "g10432", "y": "g10427",
        "back": "g1445", "start": "g1440", "guide": "g1458", "misc1": "g1451",
        "leftshoulder": "lab-lb", "rightshoulder": "lab-rb", "lefttrigger": "lab-lt", "righttrigger": "lab-rt",
        "dpup": "g1435", "dpdown": "g1435", "dpleft": "g1435", "dpright": "g1435"},
        "sticks": {"left": "g2489", "right": "g2495"}, "split_dpad": True},
    "generic": {"style": "outline", "parts": {"a": "g1171", "b": "g1178", "x": "g1185", "y": "g1192",
        "back": "g1197", "start": "g1202", "dpup": "g113765", "dpdown": "g113773", "dpleft": "g113777", "dpright": "g113769",
        "leftshoulder": "path382", "rightshoulder": "path384", "lefttrigger": "path6698", "righttrigger": "path6698-8"},
        "sticks": {"left": "g84240", "right": "g6335"}},
    "gamecube": {"style": "outline", "parts": {"a": "Button_A", "b": "Button_B", "x": "Button_X", "y": "Button_Y",
        "start": "Button_Start", "rightshoulder": "Button_Z", "leftshoulder": "Button_L", "lefttrigger": "Button_L", "righttrigger": "Button_R",
        "dpup": "Dpad_Up", "dpdown": "Dpad_Down", "dpleft": "Dpad_Left", "dpright": "Dpad_Right"},
        "sticks": {"left": "Analog_Stick", "right": "Analog_C_Stick"},
        "visible": {"lefttrigger": [0, 0, 1, .25], "righttrigger": [0, 0, 1, .25],
                    "leftshoulder": [0, 0, 1, .25]}},
    "wii": {"style": "outline", "parts": {"a": "path5097", "back": "path5099", "guide": "path5101", "start": "path5103",
        "x": "lab-one", "y": "lab-two", "dpup": "lab-up", "dpdown": "lab-down", "dpleft": "lab-left", "dpright": "lab-right"},
        "sticks": {}, "remove": ["text5135", "rect5075", "rect5077"]},
}

# A generic pad uses the standard controller geometry with the brand mark removed.
SPECS["generic"] = deepcopy(SPECS["xbox"])
SPECS["generic"]["parts"]["guide"] = "lab-generic-home"
# The GameCube color drawing pairs offset shadow and face contours. Keep the
# original face contour once, rather than turning both color edges into thick ink.
SPECS["gamecube"]["remove"] = ["GCN", "Vector"] + [
    "Vector_" + str(index) for index in (*range(3, 36, 2), 42, 44, 46, 48, 50, 51)
]

FACE_GLYPHS = {"a": "cross", "b": "circle", "x": "square", "y": "triangle"}


def split_subpaths(data):
    """Separate SVG subpaths while preserving their absolute starting positions.

    Only move commands change representation; curve/line geometry stays intact.
    The source DS4 combines each button ring and its glyph in one compound path.
    """
    tokens = list(re.finditer(r"[A-Za-z]|[-+]?(?:\d*\.\d+|\d+\.?\d*)(?:[eE][-+]?\d+)?", data))
    counts = {"M": 2, "L": 2, "H": 1, "V": 1, "C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}
    current = [0.0, 0.0]
    start = [0.0, 0.0]
    moves, command, i = [], None, 0
    while i < len(tokens):
        if tokens[i].group().isalpha():
            command = tokens[i].group()
            command_start = tokens[i].start()
            i += 1
            if command.upper() == "Z":
                current = start[:]
                continue
        upper = command.upper()
        count = counts[upper]
        values = [float(t.group()) for t in tokens[i:i + count]]
        old = current[:]
        if upper == "H":
            current[0] = values[0] + (old[0] if command.islower() else 0)
        elif upper == "V":
            current[1] = values[0] + (old[1] if command.islower() else 0)
        else:
            current = [values[-2] + (old[0] if command.islower() else 0),
                       values[-1] + (old[1] if command.islower() else 0)]
        if upper == "M":
            start = current[:]
            moves.append((command_start, tokens[i + 1].end(), start[:]))
            command = "l" if command.islower() else "L"
        i += count
    return [f"M{point[0]:.9f},{point[1]:.9f}" + data[end:(moves[index + 1][0] if index + 1 < len(moves) else len(data))]
            for index, (_, end, point) in enumerate(moves)]


def center_face_glyphs(tree, family, spec):
    """Center symbols independently of controller/button contours and font metrics."""
    if family not in ("dualsense", "playstation"):
        return
    ids = {node.get("id"): node for node in tree.iter() if node.get("id")}
    if family == "dualsense":
        glyphs = {"a": "lab-auto-0", "x": "lab-auto-1", "y": "lab-auto-2", "b": "lab-auto-3"}
    else:
        glyphs = {}
        for key, name in (("a", "Cross"), ("b", "Circle"), ("x", "Square"), ("y", "Triangle")):
            ring = ids[name]
            subpaths = split_subpaths(ring.get("d"))
            ring.set("d", " ".join(subpaths[:2]))
            glyph = ET.Element("{" + NS + "}path", ring.attrib.copy())
            glyph.set("id", "lab-glyph-" + FACE_GLYPHS[key])
            glyph.set("d", " ".join(subpaths[2:]))
            parent = next(parent for parent in tree.iter() if ring in list(parent))
            parent.insert(list(parent).index(ring) + 1, glyph)
            glyphs[key] = glyph.get("id")
        ids = {node.get("id"): node for node in tree.iter() if node.get("id")}
    renderer = QSvgRenderer(QByteArray(ET.tostring(tree)))
    for key, id in glyphs.items():
        target_id = spec["parts"][key]
        target = renderer.transformForElement(target_id).mapRect(renderer.boundsOnElement(target_id)).center()
        matrix = renderer.transformForElement(id)
        box = matrix.mapRect(renderer.boundsOnElement(id))
        center = box.center()
        if key == "y":
            # An upward triangle carries more visual weight along its lower edge.
            # Place its centroid at the button center rather than its bounding-box midpoint.
            center.setY(box.top() + box.height() * 2 / 3)
        inverse, ok = matrix.inverted()
        if not ok:
            raise ValueError(f"Non-invertible glyph transform: {family}/{id}")
        delta = inverse.map(target) - inverse.map(center)
        node = ids[id]
        parent = next(parent for parent in tree.iter() if node in list(parent))
        wrapper = ET.Element("{" + NS + "}g", id="lab-centered-" + FACE_GLYPHS[key],
                             transform=f"translate({delta.x():.9f},{delta.y():.9f})")
        index = list(parent).index(node)
        parent.remove(node)
        parent.insert(index, wrapper)
        wrapper.append(node)
    spec["glyphs"] = glyphs


def local(tag):
    return tag.rsplit("}", 1)[-1]


def style_of(node):
    return dict(part.split(":", 1) for part in node.get("style", "").split(";") if ":" in part)


def add_gamecube_wordmark(tree):
    """Use the actual two-line lettering, omitting the console's separate cube icon."""
    source = ET.parse(ROOT / "upstream" / "gamecube-wordmark.svg").getroot()
    leaves = []
    for index, node in enumerate(source.iter()):
        if local(node.tag) in ("path", "polygon", "rect", "polyline"):
            node.set("id", "lab-wordmark-" + str(index))
            leaves.append(node)
    probe = QSvgRenderer(QByteArray(ET.tostring(source)))
    group = ET.SubElement(tree, "{" + NS + "}g", id="lab-gamecube-wordmark",
                          transform="translate(1436.105,351.15) scale(0.3290395388) translate(-952.7,-114)")
    ET.SubElement(group, "{" + NS + "}title").text = "NINTENDO GAMECUBE"
    for node in leaves:
        box = probe.transformForElement(node.get("id")).mapRect(probe.boundsOnElement(node.get("id")))
        if box.left() < 900:
            continue
        letter = deepcopy(node)
        letter.attrib.pop("class", None)
        letter.attrib.pop("style", None)
        letter.set("fill", CYAN)
        letter.set("stroke", "none")
        group.append(letter)


def prepare(family, spec):
    path = ROOT / "upstream" / f"{'xbox' if family == 'generic' else family}.svg"
    raw = path.read_bytes()
    tree = ET.fromstring(raw)
    if not tree.get("viewBox"):
        tree.set("viewBox", f"-3 -3 {float(tree.get('width')) + 6} {float(tree.get('height')) + 6}")
    tree.set("width", "100%")
    tree.set("height", "100%")
    tree.set("preserveAspectRatio", "xMidYMid meet")
    # Remove editor metadata, inactive alternate layers and any external resources.
    for parent in list(tree.iter()):
        for node in list(parent):
            if (local(node.tag) in ("metadata", "namedview", "script", "foreignObject", "image", "use")
                    or ("}" in node.tag and not node.tag.startswith("{" + NS + "}"))
                    or node.get("id") in spec.get("remove", [])
                    or style_of(node).get("display") == "none"):
                parent.remove(node)
    if family == "wii":
        for key, x, y, w, h in (("up", 53.15, 63.78, 17.72, 30), ("down", 53.15, 93.78, 17.72, 30),
                                ("left", 31.89, 85.04, 30.12, 17.72), ("right", 62.01, 85.04, 30.12, 17.72)):
            ET.SubElement(tree, "{" + NS + "}rect", id="lab-" + key, x=str(x), y=str(y), width=str(w), height=str(h))
        for number, y in (("one", 355), ("two", 415)):
            ET.SubElement(tree, "{" + NS + "}circle", id="lab-" + number, cx="62", cy=str(y), r="15")
        for text, x, y in (("A", 62, 179), ("−", 26.57, 265), ("⌂", 62, 265), ("+", 97.44, 265), ("1", 62, 360), ("2", 62, 420)):
            e = ET.SubElement(tree, "{" + NS + "}text", x=str(x), y=str(y), **{"font-size": "12", "text-anchor": "middle"})
            e.text = text
    # Give every drawable a stable id for its ancestor transform and highlight layer.
    counter = 0
    for node in tree.iter():
        if local(node.tag) in ("path", "rect", "circle", "ellipse", "polygon", "polyline", "text") and not node.get("id"):
            node.set("id", f"lab-auto-{counter}")
            counter += 1
    # Move leaf transforms to wrappers so transformForElement includes the full scale.
    for parent in list(tree.iter()):
        for index, node in enumerate(list(parent)):
            if node.get("transform") and local(node.tag) not in ("g", "defs"):
                wrapper = ET.Element("{" + NS + "}g", transform=node.attrib.pop("transform"))
                parent.remove(node); parent.insert(index, wrapper); wrapper.append(node)
    probe = QSvgRenderer(QByteArray(ET.tostring(tree)))
    if not probe.isValid():
        raise ValueError(f"Invalid source artwork: {family}")
    if spec.get("crop"):
        box = probe.transformForElement(spec["crop"]).mapRect(probe.boundsOnElement(spec["crop"]))
        box = box.adjusted(-10, -10, 10, 10)
        tree.set("viewBox", f"{box.x()} {box.y()} {box.width()} {box.height()}")
        probe = QSvgRenderer(QByteArray(ET.tostring(tree)))
    if family == "generic":
        box = probe.transformForElement("Button_Home").mapRect(probe.boundsOnElement("Button_Home"))
        for parent in tree.iter():
            for child in list(parent):
                if child.get("id") == "Button_Home":
                    parent.remove(child)
        ET.SubElement(tree, "{" + NS + "}circle", id="lab-generic-home", cx=str(box.center().x()),
                      cy=str(box.center().y()), r=str(min(box.width(), box.height()) / 2))
    width = probe.viewBoxF().width()
    height = probe.viewBoxF().height()
    drawables = ("path", "rect", "circle", "ellipse", "polygon", "polyline", "line", "text", "tspan")
    for node in tree.iter():
        tag, original = local(node.tag), style_of(node)
        for key in list(node.attrib):
            if key.startswith("{") and key not in ("{http://www.w3.org/XML/1998/namespace}space",):
                del node.attrib[key]
            elif key.lower().startswith("on") or key in ("href", "style"):
                del node.attrib[key]
        if tag == "g":
            for key in ("fill", "stroke", "opacity", "fill-opacity", "stroke-width"):
                node.attrib.pop(key, None)
        if tag not in drawables:
            continue
        node.set("fill", "none")
        node.set("stroke", CYAN)
        node.set("stroke-width", str(LINE_WIDTH))
        node.set("vector-effect", "non-scaling-stroke")
        node.set("stroke-linejoin", "round")
        node.set("stroke-linecap", "round")
        node.set("stroke-opacity", "1")
        node.set("fill-opacity", "1")
        if spec["style"] == "outline" and family != "wii":
            node.set("fill", "#242426")
        if spec["style"] == "stroke":
            # Keep tiny speaker/glyph shapes filled; control outlines remain hollow.
            if original.get("fill") == "#f00" and not node.get("id", "").startswith(("l3", "r3")):
                node.set("fill", CYAN)
                node.set("stroke", "none")
        elif spec["style"] == "ink":
            if node.get("id", "").startswith("Active_"):
                if node.get("id") not in spec["sticks"].values():
                    node.set("stroke", "none")
            elif original.get("fill", "none") != "none":
                node.set("fill", CYAN)
                # This source encodes thin ink as filled ribbons. Their native
                # width contributes to the visible line, so use a lighter edge.
                node.set("stroke-width", "1.0")
        if tag in ("text", "tspan"):
            node.set("fill", CYAN);node.set("stroke", "none");node.set("font-family", "Segoe UI")
    # Select actual left/right sub-shapes from the existing bumper groups.
    ids = {node.get("id"): node for node in tree.iter() if node.get("id")}
    for group, prefix in (("g1756", "b"), ("g3215", "b"), ("g10592", "t")):
        if family not in ("xbox", "switch", "generic") or group not in ids:
            continue
        shapes = [n for n in ids[group].iter() if local(n.tag) in ("path", "rect", "circle")]
        if len(shapes) >= 2:
            shapes = sorted(shapes, key=lambda n: probe.transformForElement(n.get("id")).mapRect(probe.boundsOnElement(n.get("id"))).center().x())
            shapes[0].set("id", "lab-l" + prefix)
            shapes[-1].set("id", "lab-r" + prefix)
    if family == "gamecube":
        add_gamecube_wordmark(tree)
    center_face_glyphs(tree, family, spec)
    payload = ET.tostring(tree, encoding="utf-8", xml_declaration=True)
    renderer = QSvgRenderer(QByteArray(payload))
    for side, cap in spec["sticks"].items():
        if not renderer.elementExists(cap):
            raise ValueError(f"Missing {family} {side} stick: {cap}")
    for key in ("dpleft", "dpright"):
        if key not in spec["parts"]:break
    else:
        left, right = spec["parts"]["dpleft"], spec["parts"]["dpright"]
        def center(id):return renderer.transformForElement(id).mapRect(renderer.boundsOnElement(id)).center().x()
        if left != right and center(left) > center(right):
            spec["parts"]["dpleft"], spec["parts"]["dpright"] = right, left
    missing = [value for value in spec["parts"].values() if not renderer.elementExists(value)]
    if missing:
        raise ValueError(f"Missing {family} parts: {missing}")
    (ROOT / f"{family}.svg").write_bytes(payload)
    result = {k:v for k,v in spec.items() if k not in ("style", "remove", "crop")}
    result.update(file=f"{family}.svg", upstream_sha256=hashlib.sha256(raw).hexdigest(),
                  sha256=hashlib.sha256(payload).hexdigest(), viewbox=[renderer.viewBoxF().x(), renderer.viewBoxF().y(), width, height])
    return result


if __name__ == "__main__":
    application = QGuiApplication.instance() or QGuiApplication([])
    result = {name: prepare(name, spec) for name, spec in SPECS.items()}
    (ROOT / "layouts.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    source_file = ROOT / "sources.json"
    if source_file.exists():
        sources = json.loads(source_file.read_text(encoding="utf-8"))
        for name, spec in result.items():
            sources[name]["sha256"] = spec["sha256"]
            sources[name]["upstream_sha256"] = spec["upstream_sha256"]
            if spec.get("glyphs"):
                note = " PlayStation face glyphs are individually centered; triangles use optical centering."
                if note not in sources[name]["changes"]:
                    sources[name]["changes"] += note
        source_file.write_text(json.dumps(sources, indent=2), encoding="utf-8")
    print("Prepared", len(result), "vector controller overlays")

"""Local visual reports. User and imported text is always escaped."""
import base64
import math
from html import escape

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QPointF, QRectF
from PySide6.QtGui import QImage, QColor, QPainter, QPen, QFont, QTextDocument

from .model import button_names
from .theme import ACCENT_TEXT, BORDER, SURFACE, UI_FONT


def pct(value):
    return f"{value * 100:.2f}%" if isinstance(value, (float, int)) and math.isfinite(value) else "—"


def trail_image(points):
    image = QImage(240, 240, QImage.Format.Format_ARGB32)
    image.fill(QColor(SURFACE))
    p = QPainter(image)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor(BORDER), 1))
    p.drawEllipse(QRectF(20, 20, 200, 200))
    p.drawLine(20, 120, 220, 120)
    p.drawLine(120, 20, 120, 220)
    p.setPen(QPen(QColor(ACCENT_TEXT), 2))
    for x, y in points[-900:]:
        p.drawPoint(QPointF(120 + max(-1, min(1, x)) * 100, 120 + max(-1, min(1, y)) * 100))
    p.end()
    data = QByteArray()
    buffer = QBuffer(data)
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return base64.b64encode(bytes(data)).decode("ascii")


def table(rows):
    return '<table width="100%" cellspacing="0" cellpadding="8">' + "".join(
        '<tr>' + "".join('<td style="border-bottom:1px solid #3a3a3f">' + escape(str(cell)) + '</td>' for cell in row) + '</tr>' for row in rows) + '</table>'


def report_html(report):
    device = report["device"]
    title = report.get("name") or device["name"]
    parts = ['<html><head><meta charset="utf-8"><style>body{font-family:"Segoe UI",sans-serif;background:#242426;color:#f5f5f7;font-size:13px}h1{font-size:22px}h2{font-size:17px;color:#93c5ff}p{color:#b6b6be}td{vertical-align:top}th{text-align:left}</style></head><body>',
             '<h1>' + escape(str(title)) + '</h1>',
             '<p>' + escape(device["name"]) + '<br>Profile: ' + escape(str(report.get("profile_name", "Default"))) + '<br>' + escape(report["created"]) + '</p>',
             '<p>Duration: ' + f"{report['duration_seconds']:.1f} seconds" + ' · Samples: ' + str(report["sample_count"]) + '</p>',
             '<h2>Stick measurements</h2><table width="100%"><tr>']
    for side in ("left", "right"):
        trail = report.get("stick_trails", {}).get(side, [])
        parts.append('<td width="50%"><b>' + side.title() + ' stick</b><br><img width="150" height="150" src="data:image/png;base64,' + trail_image(trail) + '"></td>')
    parts.append('</tr></table>')
    rows = [("Measurement", "Left", "Right")]
    metrics = (("samples", "Recorded samples"), ("coverage", "Circle coverage"), ("peak_radius", "Peak radius"),
               ("radial_deviation", "Radial deviation"), ("mean_radius", "Center mean offset"), ("max_radius", "Center peak offset"), ("jitter", "Center jitter"))
    for key, title in metrics:
        values = []
        for side in ("left", "right"):
            stats = report[side + "_stick"] if key in ("samples", "coverage", "peak_radius", "radial_deviation") else report.get("rest_measurements", {}).get(side, {})
            values.append(str(stats.get(key, 0)) if key == "samples" else pct(stats.get(key)) if stats.get("samples", 1) else "Not measured")
        rows.append((title, *values))
    parts.append(table(rows))
    parts.append('<p>Plots contain the last recorded positions. Missing measurements remain unmeasured.</p><h2>Triggers</h2>')
    parts.append(table([(key.replace("trigger", " trigger").title(), pct(report["triggers"][key]["min"]), pct(report["triggers"][key]["max"]))
                        if key in report["triggers"] else (key.replace("trigger", " trigger").title(), "Not mapped / not measured", "—") for key in ("lefttrigger", "righttrigger")]))
    names = button_names(device.get("family", "generic"))
    guided = report.get("guided", {}) if isinstance(report.get("guided"), dict) else {}
    parts.append('<h2>Buttons and directions</h2>')
    buttons = guided.get("buttons", [])
    if isinstance(buttons, list) and buttons:
        parts.append(table([(str(b.get("name", b.get("key", ""))), "Observed" if b.get("observed") is True else "Not observed") for b in buttons if isinstance(b, dict)]))
    else:
        parts.append(table([(names.get(key, key), count) for key, count in report["button_presses"].items()]) or '<p>No button presses recorded.</p>')
    if report.get("raw_button_presses"):
        parts.append('<h2>Raw button counts</h2>' + table([("Button " + key, count) for key, count in report["raw_button_presses"].items()]))
    parts.append('<h2>Vibration</h2><p>' + escape(str(guided.get("vibration", report.get("vibration_evidence", "Not tested")))) + '</p>')
    if report.get("demo"):
        parts.append('<p><b>DEMO · Simulated input. This is not a physical hardware test.</b></p>')
    parts.append('<p>Observed input measurements, not a hardware health certification. Circle deviation depends on the stick gate and test movement. Unobserved controls are not automatically faulty.</p></body></html>')
    return "".join(parts)


def export_png(report, path):
    document = QTextDocument()
    document.setDefaultFont(QFont(UI_FONT, 10))
    document.setHtml(report_html(report))
    document.setTextWidth(1000)
    height = math.ceil(document.size().height()) + 48
    if height > 16000:
        raise ValueError("This report is too long for an image. Export HTML or JSON instead.")
    image = QImage(1048, height, QImage.Format.Format_ARGB32)
    image.fill(QColor(SURFACE))
    painter = QPainter(image)
    painter.translate(24, 24)
    document.drawContents(painter)
    painter.end()
    if not image.save(str(path), "PNG"):
        raise OSError("The report image could not be saved.")


def comparison_rows(first, second):
    rows = [("Metric", first.get("name") or first["device"]["name"], second.get("name") or second["device"]["name"])]
    for side in ("left", "right"):
        for key, title in (("coverage", "circle coverage"), ("peak_radius", "peak radius"), ("radial_deviation", "radial deviation")):
            rows.append((side.title() + " " + title,
                         pct(first[side + "_stick"].get(key)) if first[side + "_stick"]["samples"] else "Not measured",
                         pct(second[side + "_stick"].get(key)) if second[side + "_stick"]["samples"] else "Not measured"))
        for key, title in (("mean_radius", "center offset"), ("jitter", "center jitter")):
            rows.append((side.title() + " " + title, pct(first.get("rest_measurements", {}).get(side, {}).get(key)), pct(second.get("rest_measurements", {}).get(side, {}).get(key))))
    return rows

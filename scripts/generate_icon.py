"""Generates multi-resolution application icons for Instagram & YouTube Video Downloader Pro."""

from pathlib import Path
from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import (
    QImage,
    QPainter,
    QPainterPath,
    QLinearGradient,
    QColor,
    QPen,
    QBrush,
    QPolygonF,
)


def create_icon_image(size: int = 256) -> QImage:
    """Renders a modern Instagram/YouTube styled gradient icon with download glyph."""
    img = QImage(size, size, QImage.Format.Format_ARGB32_Premultiplied)
    img.fill(Qt.GlobalColor.transparent)

    painter = QPainter(img)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

    scale = size / 256.0

    # Background rounded rectangle
    margin = 12 * scale
    radius = 48 * scale
    rect = QRectF(margin, margin, size - 2 * margin, size - 2 * margin)

    # Instagram + YouTube gradient (Purple -> Pink/Red -> Amber)
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#833AB4"))   # Instagram Purple
    gradient.setColorAt(0.35, QColor("#FD1D1D"))  # Instagram Red
    gradient.setColorAt(0.70, QColor("#E62117"))  # YouTube Red
    gradient.setColorAt(1.0, QColor("#FCB045"))   # Instagram Yellow/Orange

    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawRoundedRect(rect, radius, radius)

    # Subtle inner border/ring
    border_pen = QPen(QColor(255, 255, 255, 60))
    border_pen.setWidthF(3 * scale)
    painter.setPen(border_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(rect, radius, radius)

    # Download arrow & tray in crisp white
    arrow_brush = QBrush(QColor(255, 255, 255))
    painter.setBrush(arrow_brush)
    painter.setPen(Qt.PenStyle.NoPen)

    # Arrow stem (vertical bar)
    stem_w = 26 * scale
    stem_h = 58 * scale
    stem_x = (size - stem_w) / 2
    stem_y = 66 * scale
    painter.drawRoundedRect(QRectF(stem_x, stem_y, stem_w, stem_h), 4 * scale, 4 * scale)

    # Arrow head (triangle)
    head_poly = QPolygonF([
        QPointF(size / 2 - 46 * scale, 116 * scale),
        QPointF(size / 2 + 46 * scale, 116 * scale),
        QPointF(size / 2, 160 * scale),
    ])
    painter.drawPolygon(head_poly)

    # Tray / base bracket
    tray_pen = QPen(QColor(255, 255, 255))
    tray_pen.setWidthF(16 * scale)
    tray_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    tray_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(tray_pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    tray_path = QPainterPath()
    tray_y = 175 * scale
    tray_left = 68 * scale
    tray_right = size - 68 * scale
    tray_h = 24 * scale

    tray_path.moveTo(tray_left, tray_y)
    tray_path.lineTo(tray_left, tray_y + tray_h)
    tray_path.lineTo(tray_right, tray_y + tray_h)
    tray_path.lineTo(tray_right, tray_y)
    painter.drawPath(tray_path)

    painter.end()
    return img


def generate_all_icons():
    assets_dir = Path(__file__).resolve().parent.parent / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)

    img_256 = create_icon_image(256)

    # Save PNG
    png_path = assets_dir / "app_icon.png"
    img_256.save(str(png_path), "PNG")
    print(f"Generated {png_path} ({img_256.width()}x{img_256.height()})")

    # Save multi-size ICO
    ico_path = assets_dir / "app_icon.ico"
    # Qt writes .ico directly
    img_256.save(str(ico_path), "ICO")
    print(f"Generated {ico_path}")


if __name__ == "__main__":
    generate_all_icons()

"""Generátor ikony aplikace pro macOS.

Vykreslí do PNG zaoblený čtvercový badge (~iOS/macOS styl) s motivem
sloupcového grafu známek A→F. Soubor uloží do
`src/softwaretestingklasifikator/resources/icon.png`.

Spuštění:
    python tools/generate_icon.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPixmap,
)
from PySide6.QtWidgets import QApplication

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_PATH = REPO_ROOT / "src" / "softwaretestingklasifikator" / "resources" / "icon.png"

# Paleta známek (z theme.py — zde duplikováno, ať skript nezávisí na zbytku
# kódu a šel spustit i bez plné instalace).
GRADE_COLORS = [
    QColor(130, 200, 80),    # A
    QColor(180, 215, 85),    # B
    QColor(220, 220, 90),    # C
    QColor(245, 220, 95),    # D
    QColor(250, 215, 110),   # E
    QColor(204, 70, 70),     # F
]
BAR_HEIGHTS = [0.95, 0.78, 0.55, 0.36, 0.45, 0.85]  # vizuální motiv distribuce


def render_icon(size: int) -> QPixmap:
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pix)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    # Zaoblené pozadí (macOS ~22 % rohového rádia)
    radius = size * 0.225
    bg = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    bg.setColorAt(0.0, QColor(72, 130, 198))
    bg.setColorAt(1.0, QColor(28, 70, 138))
    painter.setBrush(QBrush(bg))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    # Vrchní jemný highlight (3D efekt)
    highlight = QLinearGradient(QPointF(0, 0), QPointF(0, size * 0.5))
    highlight.setColorAt(0.0, QColor(255, 255, 255, 60))
    highlight.setColorAt(1.0, QColor(255, 255, 255, 0))
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.setClipPath(path)
    painter.setBrush(QBrush(highlight))
    painter.drawRect(QRectF(0, 0, size, size * 0.5))
    painter.setClipping(False)

    # Sloupcový graf — 6 sloupců A..F
    n = len(GRADE_COLORS)
    chart_x = size * 0.16
    chart_y = size * 0.20
    chart_w = size * 0.68
    chart_h = size * 0.55

    slot_w = chart_w / n
    bar_w = slot_w * 0.62
    bar_radius = max(2, int(size * 0.012))

    # Stín pod sloupci
    shadow_color = QColor(0, 0, 0, 60)

    for i, (color, h_ratio) in enumerate(zip(GRADE_COLORS, BAR_HEIGHTS, strict=True)):
        bar_h = chart_h * h_ratio
        x = chart_x + i * slot_w + (slot_w - bar_w) / 2
        y = chart_y + chart_h - bar_h

        # Stín
        painter.setBrush(QBrush(shadow_color))
        shadow_rect = QRectF(x + size * 0.005, y + size * 0.008, bar_w, bar_h)
        painter.drawRoundedRect(shadow_rect, bar_radius, bar_radius)

        # Sloupec
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(QRectF(x, y, bar_w, bar_h), bar_radius, bar_radius)

    # Spodní baseline (jemná bílá linka)
    baseline_y = chart_y + chart_h + size * 0.005
    painter.setPen(QColor(255, 255, 255, 90))
    painter.drawLine(
        int(chart_x), int(baseline_y),
        int(chart_x + chart_w), int(baseline_y),
    )

    # Popisek vespod
    font = QFont("Helvetica")
    font.setBold(True)
    font.setPointSize(int(size * 0.072))
    painter.setFont(font)
    painter.setPen(QColor(255, 255, 255, 230))
    painter.drawText(
        QRectF(0, size * 0.79, size, size * 0.18),
        int(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop),
        "AP4TS",
    )

    painter.end()
    return pix


def main() -> int:
    QApplication.instance() or QApplication([])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pix = render_icon(1024)
    if not pix.save(str(OUT_PATH), "PNG"):
        print(f"Uložení selhalo: {OUT_PATH}", file=sys.stderr)
        return 1
    print(f"OK: {OUT_PATH} ({pix.width()}x{pix.height()})")

    # Také menší 256x256 jako fallback (rychlejší načtení).
    small = render_icon(256)
    small_path = OUT_PATH.with_name("icon-256.png")
    small.save(str(small_path), "PNG")
    print(f"OK: {small_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

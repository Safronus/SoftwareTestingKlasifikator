"""Jednoduchý sloupcový graf rozložení známek (kreslený přes QPainter)."""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QSizePolicy, QWidget

from softwaretestingklasifikator.domain.stats import GRADE_ORDER
from softwaretestingklasifikator.ui.theme import GRADE_BG


class GradeChart(QWidget):
    """Sloupcový graf počtů známek (A–F).

    Bary jsou barevně laděné podle palety známek. Nad každým barem se zobrazí
    počet, pod ním písmeno známky. Osa Y popisek nemá.
    """

    LABEL_TOP_H = 16     # výška místa pro počet (nad barem)
    LABEL_BOTTOM_H = 18  # výška místa pro písmeno (pod barem)
    MARGIN = 6           # vnější margin
    MIN_BAR_HEIGHT = 2   # vždy alespoň pár pixelů, ať jdou nulové bary znát

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._counts: dict[str, int] = {g: 0 for g in GRADE_ORDER}
        self.setMinimumHeight(160)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

    def set_counts(self, counts: dict[str, int]) -> None:
        self._counts = {g: int(counts.get(g, 0)) for g in GRADE_ORDER}
        self.update()

    def sizeHint(self):  # noqa: N802
        return self.minimumSizeHint().expandedTo(self.size())

    def minimumSizeHint(self):  # noqa: N802
        from PySide6.QtCore import QSize
        return QSize(220, 160)

    def paintEvent(self, event) -> None:  # noqa: D401, N802
        painter = QPainter(self)
        try:
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            self._paint(painter)
        finally:
            painter.end()

    def _paint(self, painter: QPainter) -> None:
        # Známky budeme zobrazovat A → F (zleva doprava).
        grades = list(reversed(GRADE_ORDER))  # GRADE_ORDER má F první
        n = len(grades)
        if n == 0:
            return

        w = self.width()
        h = self.height()
        max_count = max(self._counts.values()) if self._counts else 0
        max_count = max(max_count, 1)

        bar_area_top = self.MARGIN + self.LABEL_TOP_H
        bar_area_bottom = h - self.MARGIN - self.LABEL_BOTTOM_H
        bar_area_h = max(0, bar_area_bottom - bar_area_top)

        slot_w = (w - 2 * self.MARGIN) / n
        bar_w = max(8.0, slot_w * 0.62)

        count_font = QFont(painter.font())
        count_font.setBold(True)
        count_font.setPointSize(max(8, count_font.pointSize()))

        letter_font = QFont(painter.font())
        letter_font.setBold(True)
        letter_font.setPointSize(max(9, letter_font.pointSize() + 1))

        text_color = QColor(245, 245, 245)  # bílý popisek na typicky tmavém docku

        for i, grade in enumerate(grades):
            count = self._counts.get(grade, 0)
            ratio = count / max_count if max_count > 0 else 0.0
            bar_h = (
                self.MIN_BAR_HEIGHT
                if count == 0
                else max(self.MIN_BAR_HEIGHT, int(bar_area_h * ratio))
            )

            slot_x = self.MARGIN + i * slot_w
            x = int(slot_x + (slot_w - bar_w) / 2)
            y = int(bar_area_bottom - bar_h)
            rect = QRect(x, y, int(bar_w), int(bar_h))

            bg = GRADE_BG.get(grade, QColor(120, 120, 120))
            painter.fillRect(rect, bg)
            painter.setPen(QPen(QColor(0, 0, 0, 60)))
            painter.drawRect(rect)

            # Počet nad barem
            painter.setFont(count_font)
            painter.setPen(text_color)
            count_rect = QRect(
                int(slot_x), self.MARGIN, int(slot_w), self.LABEL_TOP_H
            )
            painter.drawText(
                count_rect, Qt.AlignmentFlag.AlignCenter, str(count)
            )

            # Písmeno pod barem — světlý text, ať je vidět i na tmavém docku.
            painter.setFont(letter_font)
            painter.setPen(text_color)
            letter_rect = QRect(
                int(slot_x),
                bar_area_bottom + 2,
                int(slot_w),
                self.LABEL_BOTTOM_H,
            )
            painter.drawText(
                letter_rect, Qt.AlignmentFlag.AlignCenter, grade
            )

from pathlib import Path
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen
from PyQt6.QtCore import Qt, QRectF, QPointF
import sys

app = QApplication.instance() or QApplication(sys.argv)

# Test full body with glasses
full_path = Path("rat/assets/rat_mascot_cutout.png")
pm_full = QPixmap(str(full_path)).scaled(124, 124, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

canvas = QPixmap(146, 146)
canvas.fill(Qt.GlobalColor.transparent)
p = QPainter(canvas)
p.setRenderHint(QPainter.RenderHint.Antialiasing)

pm_w = pm_full.width()
pm_h = pm_full.height()
draw_x = (146 - pm_w) // 2
draw_y = (146 - pm_h) // 2

p.drawPixmap(draw_x, draw_y, pm_full)

# Full body eye coordinates:
lx = draw_x + int(pm_w * 0.14)
ly = draw_y + int(pm_h * 0.15)
lw = int(pm_w * 0.14)
lh = int(pm_h * 0.22)

rx = draw_x + int(pm_w * 0.33)
ry = draw_y + int(pm_h * 0.20)
rw = int(pm_w * 0.22)
rh = int(pm_h * 0.22)

pen_frame = QPen(QColor("#1F1A16"), 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
p.setPen(pen_frame)
p.setBrush(QColor(255, 255, 255, 40))
p.drawEllipse(QRectF(lx, ly, lw, lh))
p.drawEllipse(QRectF(rx, ry, rw, rh))

bridge_y = ly + lh * 0.60
p.drawLine(QPointF(lx + lw, bridge_y), QPointF(rx + 1, ry + rh * 0.50))
p.drawLine(QPointF(rx + rw, ry + rh * 0.44), QPointF(draw_x + int(pm_w * 0.62), ry + int(rh * 0.20)))

pen_sheen = QPen(QColor(255, 255, 255, 220), 1.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
p.setPen(pen_sheen)
p.drawLine(QPointF(rx + rw * 0.44, ry + rh * 0.22), QPointF(rx + rw * 0.28, ry + rh * 0.56))
p.drawLine(QPointF(rx + rw * 0.60, ry + rh * 0.22), QPointF(rx + rw * 0.44, ry + rh * 0.56))

p.end()
canvas.save("scratch/test_full_glasses.png")
print("Saved full body glasses")

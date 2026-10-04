import os
import sys
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6.QtGui import QPainter, QPixmap, QColor, QPen, QFont
from PyQt6.QtCore import Qt, QRectF, QPointF

app = QApplication.instance() or QApplication(sys.argv)

mascot_bust = Path("rat/assets/rat_mascot_bust.png")
pm = QPixmap(str(mascot_bust)).scaled(124, 124, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

# Target image 146x146 (exact widget dimensions)
canvas = QPixmap(146, 146)
canvas.fill(Qt.GlobalColor.transparent)

p = QPainter(canvas)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

pm_w = pm.width()
pm_h = pm.height()
draw_x = (146 - pm_w) // 2
draw_y = (146 - pm_h) // 2

pivot_x = draw_x + pm_w / 2
pivot_y = draw_y + pm_h * 0.95

# Test with 10 degree tilt (speaking / reasoning)
p.save()
p.translate(pivot_x, pivot_y)
p.rotate(10.0)
p.translate(-pivot_x, -pivot_y)

p.drawPixmap(draw_x, draw_y, pm)

# Left eye (angled oval)
lx = draw_x + int(pm_w * 0.15)
ly = draw_y + int(pm_h * 0.24)
lw = int(pm_w * 0.24)
lh = int(pm_h * 0.36)

# Right eye (large round cartoon eye)
rx = draw_x + int(pm_w * 0.43)
ry = draw_y + int(pm_h * 0.30)
rw = int(pm_w * 0.36)
rh = int(pm_h * 0.38)

# Frame with ink pen
pen_frame = QPen(QColor("#1F1A16"), 2.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
p.setPen(pen_frame)
p.setBrush(QColor(255, 255, 255, 40))
p.drawEllipse(QRectF(lx, ly, lw, lh))
p.drawEllipse(QRectF(rx, ry, rw, rh))

# Bridge
bridge_y = ly + lh * 0.58
p.drawLine(QPointF(lx + lw, bridge_y), QPointF(rx + 1, ry + rh * 0.52))

# Temple
p.drawLine(QPointF(rx + rw, ry + rh * 0.46), QPointF(draw_x + pm_w * 0.88, ry + rh * 0.32))

# White sheens //
pen_sheen = QPen(QColor(255, 255, 255, 225), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
p.setPen(pen_sheen)
p.drawLine(QPointF(rx + rw * 0.44, ry + rh * 0.22), QPointF(rx + rw * 0.28, ry + rh * 0.56))
p.drawLine(QPointF(rx + rw * 0.60, ry + rh * 0.22), QPointF(rx + rw * 0.44, ry + rh * 0.56))

p.restore()
p.end()

out_path = Path("scratch/test_mascot_with_glasses.png")
out_path.parent.mkdir(exist_ok=True, parents=True)
canvas.save(str(out_path))
print("Saved to", out_path)

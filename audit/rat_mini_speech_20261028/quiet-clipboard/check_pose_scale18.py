from pathlib import Path
from PyQt6.QtCore import QUrl,QRectF
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQml import QQmlEngine,QQmlComponent
from rat.ui.mini_placement import LOOK_WIDTH,LOOK_HEIGHT,LOOK_OPTICAL_HEIGHT
app=QGuiApplication([]);engine=QQmlEngine()
component=QQmlComponent(engine,QUrl.fromLocalFile(str(Path('rat/ui/quick/MascotPose.qml').resolve())))
for name,bounds in [('rat_mascot_cutout.png',QRectF(2/419,2/445,417/419,441/445)),('rat_look_idle_seated_v1.png',QRectF(.08,.06,.86,.88)),('rat_look_error_seated_v1.png',QRectF(.04,.06,.92,.87))]:
 pose=component.createWithInitialProperties(dict(width=LOOK_WIDTH,height=LOOK_HEIGHT,opticalHeight=LOOK_OPTICAL_HEIGHT,inkBounds=bounds,source=QUrl.fromLocalFile(str(Path('rat/assets',name).resolve()))))
 assert pose is not None, [e.toString() for e in component.errors()]
 for _ in range(20):app.processEvents()
 rect=pose.property('visualBounds')
 assert abs(rect.height()-LOOK_OPTICAL_HEIGHT)<.1,(name,rect.height())
 print(name, 'visible height',rect.height(),'visible width',rect.width())
 pose.deleteLater();app.processEvents()

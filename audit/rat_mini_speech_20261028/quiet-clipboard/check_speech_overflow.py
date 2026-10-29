from pathlib import Path
from PyQt6.QtCore import QObject,QUrl
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtQuick import QQuickItem
from PyQt6.QtQml import QQmlComponent,QQmlEngine,QQmlExpression
app=QGuiApplication([]); engine=QQmlEngine(); component=QQmlComponent(engine,QUrl.fromLocalFile(str(Path('rat/ui/quick/SpeechBubble.qml').resolve())))
bubble=component.createWithInitialProperties(dict(text='A long reading paragraph. '*100,maximumWidth=220,maximumHeight=120,placedWidth=220,placedHeight=120))
assert bubble is not None, [e.toString() for e in component.errors()]
for _ in range(10): app.processEvents()
assert bubble.property('overflowing') and bubble.property('moreBelow')
bar=bubble.findChild(QObject,'speechScrollBar')
assert QQmlExpression(engine.rootContext(),bar,'policy === 2').evaluate()[0]
speech=bubble.findChild(QQuickItem,'speechText');scroll=bubble.findChild(QQuickItem,'speechViewport')
scroll.setProperty('contentY',scroll.property('contentHeight')-scroll.property('height'))
for _ in range(5):app.processEvents()
assert not bubble.property('moreBelow')
bubble.setProperty('text','Xin chào.')
for _ in range(10):app.processEvents()
assert not bubble.property('overflowing') and not bubble.property('moreBelow')
assert speech.property('contentHeight') < 25
print('PASS: overflow thumb persistent, continuation fades only before end, short speech stays one line')

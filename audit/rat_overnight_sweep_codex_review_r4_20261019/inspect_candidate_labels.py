"""Capture actual button geometry/text in isolated offscreen renderers."""
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication, QPushButton, QStyle, QStyleOptionButton
from PyQt6.QtTest import QTest
from rat.kernel.contracts import Artifact
from rat.kernel.view_spec import StandardViewProvider
from rat.ui.view_renderer import QtViewRenderer

app = QApplication([])
out = Path(__file__).resolve().parent
rows = []
for width in (420, 620):
    choices = [dict(name="League of Legends", path=p, bundle_id="com.fixture.league", version="1.0")
               for p in ("/Applications/League of Legends.app", "/Applications/League of Legends copy.app")]
    art = Artifact("geometry-choice", "input_request", payload=dict(operation_name="open_application",
        missing_fields=[], candidate_choices=choices, supplied_inputs={"name":"Liên Minh"}, prompt="Choose installation"))
    ren = QtViewRenderer(StandardViewProvider().provide_view(art), art)
    ren.setFixedWidth(width)
    ren.show()
    for _ in range(5):
        app.processEvents()
        QTest.qWait(10)
    ren.grab().save(str(out / f"candidate_labels_{width}.png"))
    data=[]
    for b in ren.findChildren(QPushButton):
        if b.objectName() != "CandidateBtn":
            continue
        opt=QStyleOptionButton(); b.initStyleOption(opt)
        rect=b.style().subElementRect(QStyle.SubElement.SE_PushButtonContents,opt,b)
        prefix=""
        for char in b.text():
            if b.fontMetrics().horizontalAdvance(prefix+char)>rect.width():
                break
            prefix+=char
        data.append(dict(text=b.text(),button_width=b.width(),content_width=rect.width(),
                         text_width=b.fontMetrics().horizontalAdvance(b.text()),readable_prefix=prefix,
                         parent_width=b.parentWidget().width()))
    rows.append(dict(renderer_width=ren.width(),buttons=data))
    ren.close();ren.deleteLater();app.processEvents()
(out / "candidate_geometry.json").write_text(json.dumps(rows,indent=2)+"\n")
print(json.dumps(rows,indent=2))

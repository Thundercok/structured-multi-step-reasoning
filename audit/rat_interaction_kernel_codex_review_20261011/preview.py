"""Preview actual inline components on explicitly artificial birth data; no model calls."""
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from rat.kernel import ActionDispatcher, ArtifactStore
from rat.kernel.capabilities import build_default_registry
from rat.kernel.view_spec import StandardViewProvider
from rat.ui.view_renderer import QtViewRenderer

app = QApplication.instance() or QApplication([])
root = Path(__file__).resolve().parent
registry = build_default_registry()
dispatcher = ActionDispatcher(registry, ArtifactStore())
birth = dict(name='Ví dụ minh họa', date='2000-06-15', time='09:30', place='Hồ Chí Minh',
             latitude=10.8231, longitude=106.6297, timezone='Asia/Ho_Chi_Minh')
chart = dispatcher.execute_operation('create_natal_chart', birth).artifact
pending = dispatcher.execute_operation('create_natal_chart', {}).artifact
for artifact, name, height in [(chart, 'inline_natal_fixture', 650), (pending, 'inline_birth_fixture', 330)]:
    renderer = QtViewRenderer(StandardViewProvider(registry).provide_view(artifact), artifact)
    renderer.resize(620, height)
    renderer.show()
    app.processEvents()
    assert renderer.grab().save(str(root / (name + '.png')))
    renderer.close()
print('Saved fixture previews only; no personal chart or measured model output.')

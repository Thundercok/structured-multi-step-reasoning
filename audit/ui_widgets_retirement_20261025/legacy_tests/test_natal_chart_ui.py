"""Form state, real exports and keyboard/pointer interactions on the atlas."""
from unittest.mock import patch
import pytest
pytest.importorskip('swisseph')
from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication
from rat.astrology.svg import planet_targets
from rat.ui.natal_chart import NatalChartWindow


@pytest.fixture
def window():
    app = QApplication.instance() or QApplication([])
    widget = NatalChartWindow()
    widget.show()
    app.processEvents()
    yield widget
    widget.close()
    app.processEvents()


def test_sample_form_and_real_exports(window, tmp_path):
    assert window.chart and window.planet_table.rowCount() == 14
    assert window.house_table.rowCount() == 17
    assert 'Ví dụ minh họa' in window.sample_note.text()
    for ext in ('svg', 'png', 'pdf'):
        file = tmp_path / ('chart.' + ext)
        window.export_to(file)
        assert file.stat().st_size > 1000
    assert (tmp_path / 'chart.pdf').read_bytes().startswith(b'%PDF')


def test_unknown_time_and_invalid_place_do_not_display_new_fake_houses(window):
    window.unknown_time.setChecked(True)
    window.generate_chart()
    assert not window.chart.angles and window.house_table.rowCount() == 0
    assert not window.time_input.isEnabled()
    window.place_input.setEditText('An unresolved city')
    window.generate_chart()
    assert 'Tìm thành phố' in window.form_status.text()
    assert not window.btn_export.isEnabled()


def test_edit_is_stale_until_recalculated_and_entered_city_can_be_manual(window):
    before = window.chart
    window.name_input.setText('My chart')
    assert window.chart is before and not window.btn_export.isEnabled()
    window.place_input.setEditText('Manual coordinates')
    window.advanced_btn.setChecked(True)
    window.generate_chart()
    assert window.chart.birth.name == 'My chart'
    assert window.chart.birth.place == 'Manual coordinates'
    assert window.btn_export.isEnabled()


def test_wheel_selection_by_keyboard_and_click(window):
    canvas = window.canvas
    canvas.setFocus()
    QTest.keyClick(canvas, Qt.Key.Key_Right)
    assert canvas.selected == 'sun'
    QTest.keyClick(canvas, Qt.Key.Key_Right)
    assert canvas.selected == 'moon'
    assert 'Mặt Trăng' in window.details.toPlainText()
    x, y = planet_targets(window.chart)['mars']
    bounds = canvas._bounds()
    QTest.mouseClick(canvas, Qt.MouseButton.LeftButton, pos=QPoint(int(bounds.x() + x * bounds.width() / 900), int(bounds.y() + y * bounds.height() / 900)))
    assert canvas.selected == 'mars' and 'Sao Hỏa' in window.details.toPlainText()
    window.select_point('ASC')
    assert 'Cung Mọc' in window.details.toPlainText()
    window.select_aspect(0, 0)
    assert 'Orb' in window.details.toPlainText()


def test_profile_round_trip_recomputes_instead_of_trusting_imported_positions(window, tmp_path):
    file = tmp_path / 'birth.json'
    with patch('rat.ui.natal_chart.QFileDialog.getSaveFileName', return_value=(str(file), 'Hồ sơ lá số (*.json)')):
        window.save_profile()
    window.name_input.setText('Changed')
    with patch('rat.ui.natal_chart.QFileDialog.getOpenFileName', return_value=(str(file), 'Hồ sơ lá số (*.json)')):
        window.open_profile()
    assert window.chart.birth.name == 'Ví dụ minh họa'
    assert window.chart.positions[0].longitude > 80


def test_interpretation_request_keeps_raw_chart_out_of_chat_text(window):
    captured = []
    window.ask_assistant.connect(lambda prompt, chart: captured.append((prompt, chart)))
    window._ask()
    prompt, chart = captured[0]
    assert 'Ví dụ minh họa' in prompt and 'longitude' not in prompt
    assert chart == window.chart.to_dict()

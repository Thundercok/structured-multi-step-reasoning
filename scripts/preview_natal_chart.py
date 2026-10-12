"""Render a labeled sample atlas and its real vector/raster/PDF exports."""
import argparse
import json
from pathlib import Path
from PyQt6.QtWidgets import QApplication
from rat.ui.natal_chart import NatalChartWindow


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    app = QApplication.instance() or QApplication([])
    window = NatalChartWindow()
    window.show()
    app.processEvents()
    if window.chart is None:
        raise RuntimeError(window.form_status.text())
    window.grab().save(str(args.output / 'atlas.png'))
    window.canvas.select('moon')
    app.processEvents()
    window.grab().save(str(args.output / 'moon_detail.png'))
    for extension in ('svg', 'png', 'pdf'):
        window.export_to(args.output / ('sample.' + extension))
    (args.output / 'sample_chart.json').write_text(json.dumps(window.chart.to_dict(), ensure_ascii=False, indent=2) + '\n')
    window.resize(1080, 730)
    app.processEvents()
    window.grab().save(str(args.output / 'compact.png'))
    print(json.dumps({'size': [window.width(), window.height()], 'points': len(window.chart.positions), 'aspects': len(window.chart.aspects), 'utc': window.chart.utc_datetime, 'status': 'sample_calculated_not_personal_data'}))
    window.close()


if __name__ == '__main__':
    main()

"""Render observed tool data; no calculation, file IO or inference."""
import sys
from urllib.parse import quote

from rat.astrology.chart import NatalChart
from rat.astrology.svg import render_wheel


def reading_profile_view(result):
    chart = NatalChart.from_dict(result['chart'])
    # Qt SVG treats a CSS fallback list as one missing font family.
    svg = render_wheel(chart).replace(
        'font-family="Arial, DejaVu Sans, sans-serif"',
        'font-family="Helvetica Neue"' if sys.platform == 'darwin' else 'font-family="sans-serif"',
    )
    return {k: v for k, v in result.items() if k != 'chart'} | {
        'wheel': 'data:image/svg+xml;charset=utf-8,' + quote(svg, safe=''),
    }

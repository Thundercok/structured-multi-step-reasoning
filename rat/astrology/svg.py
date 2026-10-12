"""Vector natal wheel. Every tick/aspect uses calculated, undisplaced longitude.

Only glyph labels move to avoid collisions; leader lines retain exact positions.
No Qt dependency, so exports and runtime tools also work headlessly.
"""
from __future__ import annotations
from html import escape
import json
import math

from rat.astrology.chart import NatalChart, SIGNS, degree_text, point_map

ELEMENT_COLORS = {"Lửa": "#b7735a", "Đất": "#738669", "Khí": "#718ca3", "Nước": "#9481ae"}
INK, MUTED, GOLD = "#30363e", "#777c82", "#b29661"
VIEW_SIZE = 900


def wheel_point(longitude, radius, ascendant):
    angle = math.radians(180 + longitude - ascendant)
    return 450 + radius * math.cos(angle), 450 - radius * math.sin(angle)


def label_longitudes(positions, separation=7.0):
    """Cut at the largest gap, then place labels without breaking circular order."""
    if not positions:
        return {}
    ordered = sorted(positions, key=lambda p: p.longitude)
    gaps = [(ordered[(i + 1) % len(ordered)].longitude - p.longitude) % 360 for i, p in enumerate(ordered)]
    cut = (max(range(len(gaps)), key=lambda i: gaps[i]) + 1) % len(ordered)
    ordered = ordered[cut:] + ordered[:cut]
    values = [ordered[0].longitude]
    for p in ordered[1:]:
        value = p.longitude
        while value < values[-1]:
            value += 360
        values.append(value)
    # Isotonic regression of (longitude - index*separation), using pooled
    # adjacent violators, exactly centers crowded labels with bounded spacing.
    blocks = []
    for i, value in enumerate(values):
        blocks.append([i, i, value - i * separation, 1])
        while len(blocks) > 1 and blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]:
            right, left = blocks.pop(), blocks.pop()
            blocks.append([left[0], right[1], left[2] + right[2], left[3] + right[3]])
    placed = [0.0] * len(values)
    for start, end, total, count in blocks:
        for i in range(start, end + 1):
            placed[i] = total / count + i * separation
    return {p.id: value % 360 for p, value in zip(ordered, placed)}


def planet_targets(chart):
    asc = chart.angles.get("ASC", 0)
    return {key: wheel_point(value, 336, asc) for key, value in label_longitudes(chart.positions).items()}


def render_wheel(chart: NatalChart, *, selected=None, show_aspects=True, major_only=True) -> str:
    asc = chart.angles.get("ASC", 0)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="900" height="900" viewBox="0 0 900 900" role="img" aria-label="Lá số {escape(chart.birth.name, quote=True)}">',
             '<title>Lá số chiêm tinh cá nhân</title>',
             '<desc>Hành tinh, các nhà và góc chiếu theo dữ liệu sinh. Chữ hành tinh được giãn để tránh trùng; vạch chỉ vị trí chính xác.</desc>',
             f'<metadata>{escape(json.dumps(chart.to_dict(), ensure_ascii=False))}</metadata>',
             '<rect width="900" height="900" fill="#fcfaf6"/>']
    def line(p1, p2, color, width=1, opacity=1, dash=""):
        parts.append(f'<line x1="{p1[0]:.3f}" y1="{p1[1]:.3f}" x2="{p2[0]:.3f}" y2="{p2[1]:.3f}" stroke="{color}" stroke-width="{width}" opacity="{opacity}"' + (f' stroke-dasharray="{dash}"' if dash else '') + '/>')
    def circle(x, y, radius, color, stroke="none", width=1):
        parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{radius}" fill="{color}" stroke="{stroke}" stroke-width="{width}"/>')
    def text(x, y, value, size=16, color=INK, weight=400):
        parts.append(f'<text x="{x:.3f}" y="{y:.3f}" text-anchor="middle" font-family="Arial, DejaVu Sans, sans-serif" font-size="{size}" font-weight="{weight}" fill="{color}">{escape(str(value))}</text>')
    circle(450, 450, 433, "#f7f2e9", "#ddd3c1")
    circle(450, 450, 370, "#fcfaf6", "#ddd3c1")
    for i, (name, glyph, element, _) in enumerate(SIGNS):
        color = ELEMENT_COLORS[element]
        coordinates = [wheel_point(i * 30 + d, 429, asc) for d in range(0, 31, 3)]
        coordinates += [wheel_point(i * 30 + d, 374, asc) for d in range(30, -1, -3)]
        path = 'M ' + ' L '.join(f'{x:.3f} {y:.3f}' for x, y in coordinates) + ' Z'
        parts.append(f'<path d="{path}" fill="{color}" fill-opacity="0.09"/>')
        line(wheel_point(i * 30, 372, asc), wheel_point(i * 30, 432, asc), "#d7cbb7")
        x, y = wheel_point(i * 30 + 15, 405, asc)
        text(x, y + 9, glyph, 37, color)
        x, y = wheel_point(i * 30 + 15, 383, asc)
        text(x, y + 4, name, 12, color)
    for deg in range(360):
        inner = 361 if deg % 10 == 0 else 366 if deg % 5 == 0 else 369
        line(wheel_point(deg, inner, asc), wheel_point(deg, 373, asc), GOLD, 0.8)
    circle(450, 450, 304, "none", "#e1d9cb")
    circle(450, 450, 245, "none", "#e1d9cb")
    for i, cusp in enumerate(chart.cusps):
        line(wheel_point(cusp, 245, asc), wheel_point(cusp, 304, asc), "#b5aa98", 1.5 if i % 3 == 0 else 0.8)
        width = (chart.cusps[(i + 1) % 12] - cusp) % 360
        x, y = wheel_point(cusp + width / 2, 276, asc)
        text(x, y + 4, i + 1, 13, MUTED)
    positions = point_map(chart)
    if show_aspects:
        for aspect in reversed(chart.aspects):
            if major_only and aspect.kind == "quincunx":
                continue
            related = selected in (aspect.first, aspect.second)
            opacity = 0.85 if related else 0.12 if selected else 0.6
            if aspect.kind == "conjunction":
                continue
            line(wheel_point(positions[aspect.first].longitude, 242, asc),
                 wheel_point(positions[aspect.second].longitude, 242, asc),
                 aspect.color, 1.8 if related else 1.3, opacity, "4 4" if aspect.kind in ("sextile", "quincunx") else "")
    labels = label_longitudes(chart.positions)
    for p in chart.positions:
        color = ELEMENT_COLORS[SIGNS[p.sign_index][2]]
        tick = wheel_point(p.longitude, 310, asc)
        label = wheel_point(labels[p.id], 336, asc)
        line(wheel_point(p.longitude, 303, asc), tick, color, 1.5)
        line(tick, wheel_point(labels[p.id], 322, asc), "#b8afa1", 0.7)
        circle(*tick, 2.5, color)
        if p.id == selected:
            circle(*label, 22, "#f0e5d0", GOLD)
        text(label[0], label[1] + 8, p.glyph, 30, color, 500)
        x, y = wheel_point(labels[p.id], 357, asc)
        # Full sign is available in the table/tooltip; label preserves actual degrees.
        rounded = int(round(p.degree * 60))
        text(x, y + 4, f"{rounded // 60:02d}°{rounded % 60:02d}′" + (" ℞" if p.retrograde else ""), 12, INK)
    for key in ("ASC", "MC", "DSC", "IC"):
        if key not in chart.angles:
            continue
        longitude = chart.angles[key]
        line(wheel_point(longitude, 245, asc), wheel_point(longitude, 432, asc), GOLD, 1.6)
        x, y = wheel_point(longitude, 446, asc)
        text(x, y + 4, key, 11, "#8a6b38", 700)
    if not chart.birth.time_known:
        text(450, 450, "CHƯA BIẾT GIỜ SINH", 14, MUTED, 600)
        text(450, 471, "Không tính Cung Mọc và nhà", 12, MUTED)
    parts.append('</svg>')
    return ''.join(parts)


def render_poster(chart: NatalChart, **options) -> str:
    wheel = render_wheel(chart, **options)
    inner = wheel[wheel.index('>') + 1:wheel.rindex('</svg>')]
    headline = escape(chart.birth.name or "Lá số cá nhân")
    subtitle = escape(f"{chart.birth.date} · {chart.birth.time if chart.birth.time_known else 'Chưa biết giờ'} · {chart.birth.place}")
    mode = escape(f"{chart.birth.timezone} · {'Tropical' if chart.birth.zodiac == 'tropical' else 'Sidereal · Lahiri'} · {chart.birth.house_system if chart.cusps else 'Không tính nhà'}")
    rows = []
    for i, p in enumerate(chart.positions):
        x, y = 70 + (i // 7) * 440, 1090 + (i % 7) * 26
        value = escape(f"{p.glyph}  {p.name.split(' (')[0]}   {degree_text(p.longitude)}" + (f"  · Nhà {p.house}" if p.house else "") + (" ℞" if p.retrograde else ""))
        rows.append(f'<text x="{x}" y="{y}" font-size="13" fill="{INK}">{value}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1330" viewBox="0 0 1000 1330" font-family="Arial, DejaVu Sans, sans-serif">'
            '<rect width="1000" height="1330" fill="#fcfaf6"/>'
            '<text x="70" y="45" font-size="12" letter-spacing="4" fill="#997e4e">RAT / NATAL ATLAS</text>'
            f'<text x="70" y="96" font-size="38" fill="{INK}">{headline}</text>'
            f'<text x="70" y="125" font-size="15" fill="{MUTED}">{subtitle}</text>'
            f'<text x="70" y="151" font-size="12" fill="{MUTED}">{mode}</text>'
            f'<g transform="translate(50 165)">{inner}</g>' + ''.join(rows) +
            f'<text x="70" y="1310" font-size="11" fill="{MUTED}">Vị trí thiên thể được tính từ dữ liệu sinh · Giờ UTC {escape(chart.utc_datetime)}</text></svg>')

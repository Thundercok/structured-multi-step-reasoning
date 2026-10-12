"""Astronomical reference, historical civil-time and house-boundary checks."""
from dataclasses import replace
from datetime import datetime
import xml.etree.ElementTree as ET
import pytest
pytest.importorskip('swisseph')
from rat.astrology.chart import BirthData, ChartError, angular_distance, calculate_aspects, calculate_chart, degree_text, house_for, interpretation_context, resolve_local_time
from rat.astrology.svg import label_longitudes, render_poster

BIRTH = BirthData('Reference', '2000-06-15', '09:30', 'HCM', 10.8231, 106.6297, 'Asia/Ho_Chi_Minh')


def test_against_saved_nasa_horizons_observer_ecliptic_reference():
    # Quantity 31, geocenter 500@399, UTC 2000-06-15 02:30. Raw API
    # responses and exact requests: audit/natal_horizons_reference_20261011.
    # Three bodies at one epoch, not a global accuracy certification.
    reference = {'sun': 84.3021485, 'moon': 244.1346105, 'mars': 89.0485508}
    chart = calculate_chart(BIRTH)
    assert chart.utc_datetime == '2000-06-15T02:30:00+00:00'
    for key, longitude in reference.items():
        point = next(p for p in chart.positions if p.id == key)
        assert angular_distance(point.longitude, longitude) * 3600 < 5
        assert point.ephemeris == 'swiss'


def test_same_instant_different_civil_zone_gives_same_chart():
    a = calculate_chart(BIRTH)
    b = calculate_chart(replace(BIRTH, time='02:30', timezone='UTC'))
    assert a.positions == b.positions and a.cusps == b.cusps


def test_dst_gap_and_fold_are_not_silently_guessed():
    with pytest.raises(ChartError, match='không tồn tại'):
        resolve_local_time(datetime(2020, 3, 8, 2, 30), 'America/New_York')
    with pytest.raises(ChartError, match='hai lần'):
        resolve_local_time(datetime(2020, 11, 1, 1, 30), 'America/New_York')
    early = resolve_local_time(datetime(2020, 11, 1, 1, 30), 'America/New_York', 0)
    late = resolve_local_time(datetime(2020, 11, 1, 1, 30), 'America/New_York', 1)
    assert late.timestamp() - early.timestamp() == 3600


def test_unknown_time_excludes_all_angles_and_houses():
    chart = calculate_chart(replace(BIRTH, time_known=False))
    assert not chart.cusps and not chart.angles and chart.notices
    assert all(p.house is None for p in chart.positions)
    assert next(p for p in chart.positions if p.id == 'moon').day_range is not None


def test_polar_placidus_does_not_silently_become_porphyry():
    with pytest.raises(ChartError, match='Whole Sign'):
        calculate_chart(replace(BIRTH, latitude=78))
    chart = calculate_chart(replace(BIRTH, latitude=78, house_system='W'))
    assert len(chart.cusps) == 12 and all(abs(cusp % 30) < 1e-8 for cusp in chart.cusps)


def test_longitude_house_wrap_and_exact_cusp_boundary():
    cusps = [(350 + i * 30) % 360 for i in range(12)]
    assert house_for(0, cusps) == 1
    assert house_for(20, cusps) == 2
    assert house_for(349.999, cusps) == 12
    assert degree_text(29.99999) == '00°00′ Kim Ngưu'
    assert degree_text(359.99999) == '00°00′ Bạch Dương'


def test_sidereal_mode_does_not_leak_into_next_tropical_calculation():
    tropical = calculate_chart(BIRTH)
    sidereal = calculate_chart(replace(BIRTH, zodiac='sidereal_lahiri'))
    again = calculate_chart(BIRTH)
    assert tropical.positions == again.positions
    assert 23 < (tropical.positions[0].longitude - sidereal.positions[0].longitude) % 360 < 25


def test_aspect_orb_filter_and_distribution_use_actual_points():
    broad = calculate_chart(BIRTH)
    narrow = calculate_chart(replace(BIRTH, max_orb=1))
    assert len(narrow.aspects) < len(broad.aspects)
    assert all(a.orb <= 1 for a in narrow.aspects)
    assert sum(broad.elements.values()) == sum(broad.modalities.values()) == 10
    nodes = [p for p in broad.positions if p.id in ('north_node', 'south_node')]
    assert angular_distance(*[p.longitude for p in nodes]) == pytest.approx(180)
    assert any(a.second in ('ASC', 'MC') for a in broad.aspects)
    assert all(a.applying is None for a in broad.aspects if a.second in ('ASC', 'MC'))


def test_exact_longitudes_survive_collision_layout_and_svg_escapes_names():
    chart = calculate_chart(replace(BIRTH, name='<Ada & Lin>'))
    original = [p.longitude for p in chart.positions]
    labels = sorted(label_longitudes(chart.positions).values())
    distances = [(labels[(i + 1) % len(labels)] - value) % 360 for i, value in enumerate(labels)]
    assert min(distances) > 6.99
    assert [p.longitude for p in chart.positions] == original
    svg = render_poster(chart)
    ET.fromstring(svg)
    assert '&lt;Ada &amp; Lin&gt;' in svg


def test_missing_main_ephemeris_is_an_error(tmp_path, monkeypatch):
    import swisseph as swe
    import rat.astrology.chart as module
    swe.close()
    monkeypatch.setattr(module, 'EPHEMERIS_PATH', tmp_path)
    with pytest.raises(ChartError, match='Thiếu tệp'):
        calculate_chart(BIRTH)
    swe.close()


def test_inference_context_preserves_calculation_and_unknown_time_limits():
    import json
    chart = calculate_chart(replace(BIRTH, time_known=False))
    full = chart.to_dict()
    compact = interpretation_context(chart)
    points = [dict(zip(compact['points']['columns'], row)) for row in compact['points']['rows']]
    assert [p['longitude'] for p in points] == [p.longitude for p in chart.positions]
    assert next(p for p in points if p['id'] == 'moon')['day_range'] == chart.positions[1].day_range
    assert compact['house_cusps'] == [] and compact['angles'] == {}
    assert compact['notices'] == chart.notices and compact['birth']['time_known'] is False
    assert len(json.dumps(compact)) < len(json.dumps(full)) * .7
    assert chart.to_dict() == full  # Formatting never mutates the actual source.


def test_imported_compact_iso_strings_cannot_change_date_or_time_in_form():
    for changes in ({'date': '20000615'}, {'time': '0930'}):
        with pytest.raises(ChartError, match='YYYY-MM-DD'):
            calculate_chart(replace(BIRTH, **changes))


def test_applying_is_instantaneous_even_when_exact_aspect_is_seconds_away():
    chart = calculate_chart(BIRTH)
    first = replace(chart.positions[0], longitude=0, speed=0)
    approaching = replace(chart.positions[1], longitude=60 - .000001, speed=1)
    leaving = replace(approaching, longitude=60 + .000001)
    aspect = next(a for a in calculate_aspects([first, approaching], 4) if a.kind == 'sextile')
    assert aspect.applying is True  # Exact in .0864 seconds, still approaching now.
    aspect = next(a for a in calculate_aspects([first, leaving], 4) if a.kind == 'sextile')
    assert aspect.applying is False


def test_north_and_south_vietnam_do_not_share_a_guessed_historical_offset():
    from rat.astrology.places import PRESETS
    hanoi = next(p for p in PRESETS if p.name.startswith('Hà Nội'))
    north = calculate_chart(replace(BIRTH, date='1973-06-15', place=hanoi.name,
                                     latitude=hanoi.latitude, longitude=hanoi.longitude, timezone=hanoi.timezone))
    south = calculate_chart(replace(BIRTH, date='1973-06-15'))
    assert north.utc_datetime == '1973-06-15T02:30:00+00:00'
    assert south.utc_datetime == '1973-06-15T01:30:00+00:00'
    early = calculate_chart(replace(BIRTH, date='1950-06-15'))
    assert any('1970' in notice for notice in early.notices)

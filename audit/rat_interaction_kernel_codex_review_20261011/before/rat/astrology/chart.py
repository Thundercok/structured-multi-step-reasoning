"""Geocentric apparent natal positions with explicit time and ephemeris provenance.

Angles and house placement use ecliptic longitude. Interpretation is kept out of
the astronomical calculation layer. Swiss Ephemeris has process-global settings;
all access is serialized, including sidereal mode and ephemeris path.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import math
import re
from pathlib import Path
from threading import RLock
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

EPHEMERIS_PATH = Path(__file__).parent / "ephemeris"
_LOCK = RLock()
SIGNS = (
    ("Bạch Dương", "♈", "Lửa", "Tiên phong"),
    ("Kim Ngưu", "♉", "Đất", "Kiên định"),
    ("Song Tử", "♊", "Khí", "Linh hoạt"),
    ("Cự Giải", "♋", "Nước", "Tiên phong"),
    ("Sư Tử", "♌", "Lửa", "Kiên định"),
    ("Xử Nữ", "♍", "Đất", "Linh hoạt"),
    ("Thiên Bình", "♎", "Khí", "Tiên phong"),
    ("Bọ Cạp", "♏", "Nước", "Kiên định"),
    ("Nhân Mã", "♐", "Lửa", "Linh hoạt"),
    ("Ma Kết", "♑", "Đất", "Tiên phong"),
    ("Bảo Bình", "♒", "Khí", "Kiên định"),
    ("Song Ngư", "♓", "Nước", "Linh hoạt"),
)
HOUSE_SYSTEMS = {"P": "Placidus", "W": "Whole Sign", "E": "Equal House", "K": "Koch", "O": "Porphyry", "R": "Regiomontanus"}
BODIES = (
    ("sun", "Mặt Trời", "☉", 0), ("moon", "Mặt Trăng", "☽", 1),
    ("mercury", "Sao Thủy", "☿", 2), ("venus", "Sao Kim", "♀", 3),
    ("mars", "Sao Hỏa", "♂", 4), ("jupiter", "Sao Mộc", "♃", 5),
    ("saturn", "Sao Thổ", "♄", 6), ("uranus", "Thiên Vương", "♅", 7),
    ("neptune", "Hải Vương", "♆", 8), ("pluto", "Diêm Vương", "♇", 9),
    ("north_node", "Nút Bắc (thật)", "☊", 11),
    ("lilith", "Lilith (viễn điểm trung bình)", "⚸", 12),
    ("chiron", "Chiron", "⚷", 15),
)
ASPECT_TYPES = (
    ("conjunction", "Trùng tụ", "☌", 0, 8, "#956337"),
    ("sextile", "Lục hợp", "⚹", 60, 4, "#438d86"),
    ("square", "Vuông", "□", 90, 6, "#bb6575"),
    ("trine", "Tam hợp", "△", 120, 6, "#577eaa"),
    ("quincunx", "Quincunx", "⚻", 150, 2, "#91946b"),
    ("opposition", "Đối đỉnh", "☍", 180, 8, "#bb6575"),
)


class ChartError(ValueError):
    pass


@dataclass(frozen=True)
class BirthData:
    name: str
    date: str  # Gregorian YYYY-MM-DD
    time: str  # local wall-clock HH:MM[:SS]
    place: str
    latitude: float
    longitude: float
    timezone: str  # IANA, never a guessed fixed UTC offset
    time_known: bool = True
    fold: int | None = None
    house_system: str = "P"
    zodiac: str = "tropical"
    max_orb: float = 8.0


@dataclass(frozen=True)
class Position:
    id: str
    name: str
    glyph: str
    longitude: float
    latitude: float
    distance_au: float
    speed: float
    retrograde: bool
    sign: str
    sign_index: int
    degree: float
    house: int | None
    ephemeris: str
    flags: int
    day_range: tuple[float, float] | None = None


@dataclass(frozen=True)
class Aspect:
    first: str
    second: str
    kind: str
    name: str
    glyph: str
    exact_angle: float
    separation: float
    orb: float
    max_orb: float
    applying: bool | None
    color: str


@dataclass
class NatalChart:
    birth: BirthData
    local_datetime: str
    utc_datetime: str
    julian_day_ut: float
    positions: list[Position]
    cusps: list[float]
    angles: dict[str, float]
    aspects: list[Aspect]
    elements: dict[str, int]
    modalities: dict[str, int]
    provenance: dict
    notices: list[str] = field(default_factory=list)

    def to_dict(self):
        return asdict(self)


def resolve_local_time(naive: datetime, zone_name: str, fold: int | None = None) -> datetime:
    """Round-trip to reject DST gaps and require a choice for repeated times."""
    try:
        zone = ZoneInfo(zone_name)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ChartError("Múi giờ không hợp lệ. Dùng tên IANA, ví dụ Asia/Ho_Chi_Minh.") from exc
    candidates = []
    for variant in (0, 1):
        aware = naive.replace(tzinfo=zone, fold=variant)
        back = aware.astimezone(timezone.utc).astimezone(zone)
        if back.replace(tzinfo=None) == naive and not any(c.utcoffset() == aware.utcoffset() for c in candidates):
            candidates.append(aware)
    if not candidates:
        raise ChartError("Giờ này không tồn tại do chuyển giờ mùa hè. Kiểm tra lại giờ sinh.")
    if len(candidates) == 2:
        if fold not in (0, 1):
            raise ChartError("Giờ này xuất hiện hai lần do chuyển giờ mùa hè. Chọn lần đầu hoặc lần sau trong mục Nâng cao.")
        return next(c for c in candidates if c.fold == fold)
    return candidates[0]


def angular_distance(a: float, b: float) -> float:
    return abs((a - b + 180) % 360 - 180)


def house_for(longitude: float, cusps: list[float]) -> int | None:
    for i, cusp in enumerate(cusps):
        width = (cusps[(i + 1) % 12] - cusp) % 360
        if (longitude - cusp) % 360 < width:
            return i + 1
    return None


def degree_text(longitude: float, *, seconds: bool = False) -> str:
    # Round within the sign without accidentally displaying 30° of the old sign.
    units = int(round((longitude % 360) * (3600 if seconds else 60))) % (360 * (3600 if seconds else 60))
    sign, rest = divmod(units, 30 * (3600 if seconds else 60))
    if seconds:
        degrees, rest = divmod(rest, 3600)
        minutes, secs = divmod(rest, 60)
        return f"{degrees:02d}°{minutes:02d}′{secs:02d}″ {SIGNS[sign][0]}"
    degrees, minutes = divmod(rest, 60)
    return f"{degrees:02d}°{minutes:02d}′ {SIGNS[sign][0]}"


def calculate_aspects(positions: list[Position], max_orb: float) -> list[Aspect]:
    aspects = []
    # South Node is the exact opposite of North Node; don't duplicate every aspect.
    points = [p for p in positions if p.id != "south_node"]
    for i, first in enumerate(points):
        for second in points[i + 1:]:
            if first.ephemeris == second.ephemeris == "axis_geometry":
                continue
            separation = angular_distance(first.longitude, second.longitude)
            for kind, name, glyph, angle, default_orb, color in ASPECT_TYPES:
                limit = min(max_orb, default_orb)
                orb = abs(separation - angle)
                if orb <= limit:
                    signed_distance = (second.longitude - first.longitude + 180) % 360 - 180
                    separation_speed = (second.speed - first.speed) * (1 if signed_distance > 0 else -1)
                    orb_speed = separation_speed * (1 if separation > angle else -1)
                    # The derivative describes motion *at* birth. A finite
                    # one-minute step can cross an exact aspect and mislabel it.
                    applying = (orb_speed < 0 if abs(orb_speed) > 1e-12 else None) if orb > 1e-8 and "axis_geometry" not in (first.ephemeris, second.ephemeris) else None
                    aspects.append(Aspect(first.id, second.id, kind, name, glyph, angle,
                                          separation, orb, limit, applying, color))
    return sorted(aspects, key=lambda a: a.orb)


def axis_positions(angles, cusps):
    names = {"ASC": "Cung Mọc · ASC", "MC": "Thiên Đỉnh · MC", "DSC": "Điểm Lặn · DSC", "IC": "Thiên Đế · IC", "Vertex": "Vertex"}
    return [Position(key, names[key], key, longitude, 0, 0, 0, False,
                     SIGNS[int(longitude // 30)][0], int(longitude // 30), longitude % 30,
                     house_for(longitude, cusps) if cusps else None, "axis_geometry", 0)
            for key, longitude in angles.items()]


def point_map(chart):
    return {p.id: p for p in chart.positions + axis_positions(chart.angles, chart.cusps)}


def interpretation_context(chart):
    """Compact calculated data for inference; keep full precision and uncertainty.

    Explicit table columns remove repeated keys, glyph/style information and
    export-only fields. The full chart remains in UI sources and raw tool traces.
    This formats observations; it does not generate an interpretation or verdict.
    """
    data = chart.to_dict() if isinstance(chart, NatalChart) else chart
    point_columns = ('id', 'name', 'longitude', 'latitude', 'speed', 'retrograde', 'house', 'day_range')
    aspect_columns = ('first', 'second', 'kind', 'exact_angle', 'separation', 'orb', 'max_orb', 'applying')
    return {
        'schema': 'rat-natal-interpretation-v1',
        'units': 'angles in degrees; planetary speed in degrees/day; applying is instantaneous or null',
        'birth': data['birth'], 'utc_datetime': data['utc_datetime'],
        'points': {'columns': point_columns, 'rows': [[p.get(k) for k in point_columns] for p in data['positions']]},
        'house_cusps': data['cusps'], 'angles': data['angles'],
        'aspects': {'columns': aspect_columns, 'rows': [[a[k] for k in aspect_columns] for a in data['aspects']]},
        'elements': data['elements'], 'modalities': data['modalities'],
        'provenance': data['provenance'], 'notices': data['notices'],
    }


def calculate_chart(birth: BirthData) -> NatalChart:
    if (not isinstance(birth, BirthData) or type(birth.time_known) is not bool
            or (birth.fold is not None and (type(birth.fold) is not int or birth.fold not in (0, 1)))
            or any(type(value) not in (int, float) for value in (birth.latitude, birth.longitude, birth.max_orb))):
        raise ChartError("Dữ liệu sinh không đúng định dạng.")
    if any(not isinstance(value, str) or len(value) > limit for value, limit in
           ((birth.name, 100), (birth.place, 200), (birth.date, 10), (birth.time, 8), (birth.timezone, 80))):
        raise ChartError("Tên, ngày, giờ hoặc nơi sinh không đúng định dạng.")
    if (not math.isfinite(birth.latitude) or not math.isfinite(birth.longitude)
            or not -89.9 <= birth.latitude <= 89.9 or not -180 <= birth.longitude <= 180):
        raise ChartError("Tọa độ không hợp lệ: vĩ độ từ −89.9 đến 89.9, kinh độ từ −180 đến 180.")
    if birth.house_system not in HOUSE_SYSTEMS or birth.zodiac not in ("tropical", "sidereal_lahiri"):
        raise ChartError("Hệ nhà hoặc hệ hoàng đạo không được hỗ trợ.")
    if not math.isfinite(birth.max_orb) or not 0.1 <= birth.max_orb <= 10:
        raise ChartError("Orb tối đa phải nằm trong khoảng 0.1°–10°.")
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', birth.date) or not re.fullmatch(r'\d{2}:\d{2}(?::\d{2})?', birth.time):
        raise ChartError("Ngày phải có dạng YYYY-MM-DD và giờ dạng HH:MM hoặc HH:MM:SS.")
    try:
        naive = datetime.fromisoformat(birth.date + "T" + (birth.time if birth.time_known else "12:00"))
    except ValueError as exc:
        raise ChartError("Ngày hoặc giờ sinh không hợp lệ.") from exc
    if naive.tzinfo or not 1800 <= naive.year <= 2399:
        raise ChartError("Nhập giờ địa phương và năm trong khoảng 1800–2399.")
    local = resolve_local_time(naive, birth.timezone, birth.fold)
    utc = local.astimezone(timezone.utc)
    try:
        import swisseph as swe
    except ImportError as exc:
        raise ChartError("Chưa cài bộ tính thiên thể. Cài requirements-astrology.txt rồi mở lại RAT.") from exc
    notices, positions = [], []
    if local.year < 1970:
        notices.append("Sinh trước 1970: kiểm chứng giờ dân sự theo lịch sử địa phương; dữ liệu IANA trước mốc này có giới hạn và khác biệt vùng.")
    with _LOCK:
        swe.set_ephe_path(str(EPHEMERIS_PATH))
        swe.set_sid_mode(swe.SIDM_LAHIRI)
        flags = swe.FLG_SWIEPH | swe.FLG_SPEED
        house_flags = 0
        if birth.zodiac == "sidereal_lahiri":
            flags |= swe.FLG_SIDEREAL
            house_flags = swe.FLG_SIDEREAL
        def jd_at(dt):
            dt = dt.astimezone(timezone.utc)
            return swe.julday(dt.year, dt.month, dt.day, dt.hour + dt.minute / 60 + (dt.second + dt.microsecond / 1e6) / 3600)
        jd = jd_at(utc)
        cusps, angles = [], {}
        if birth.time_known:
            try:
                houses, ascmc = swe.houses_ex(jd, birth.latitude, birth.longitude,
                                             birth.house_system.encode("ascii"), house_flags)
            except swe.Error as exc:
                raise ChartError("Không tính được hệ nhà này tại vĩ độ đã chọn. Thử Whole Sign hoặc Equal House.") from exc
            cusps = list(houses)
            angles = {"ASC": ascmc[0], "MC": ascmc[1], "DSC": (ascmc[0] + 180) % 360, "IC": (ascmc[1] + 180) % 360, "Vertex": ascmc[3]}
        else:
            notices.append("Chưa biết giờ sinh: vị trí tạm tính lúc 12:00 địa phương; không hiển thị Cung Mọc, MC hay nhà. Khoảng chuyển động trong ngày chỉ là ước tính tại hai đầu ngày.")
        for key, name, glyph, body_id in BODIES:
            try:
                xx, returned = swe.calc_ut(jd, body_id, flags)
            except swe.Error as exc:
                if key == "chiron":
                    notices.append("Không có dữ liệu Chiron cho ngày này; điểm này được bỏ qua.")
                    continue
                raise ChartError(f"Không tính được {name}: {exc}") from exc
            engine = "swiss" if returned & swe.FLG_SWIEPH else "moshier" if returned & swe.FLG_MOSEPH else "analytical"
            # Never silently downgrade the main planetary ephemeris.
            if body_id <= 9 and engine != "swiss":
                raise ChartError("Thiếu tệp thiên văn chính xác cho ngày này. Kiểm tra thư mục rat/astrology/ephemeris.")
            longitude = xx[0] % 360
            sign_index = int(longitude // 30)
            day_range = None
            if not birth.time_known:
                midnight = naive.replace(hour=0, minute=0, second=0)
                start = resolve_local_time(midnight, birth.timezone, birth.fold)
                end = resolve_local_time(midnight + timedelta(days=1), birth.timezone, birth.fold)
                day_range = tuple(swe.calc_ut(jd_at(dt), body_id, flags)[0][0] % 360 for dt in (start, end))
            positions.append(Position(key, name, glyph, longitude, xx[1], xx[2], xx[3], xx[3] < 0,
                                      SIGNS[sign_index][0], sign_index, longitude % 30,
                                      house_for(longitude, cusps) if cusps else None, engine, returned, day_range))
        north = next(p for p in positions if p.id == "north_node")
        south = (north.longitude + 180) % 360
        positions.append(Position("south_node", "Nút Nam (thật)", "☋", south, -north.latitude,
                                  north.distance_au, north.speed, north.retrograde, SIGNS[int(south // 30)][0],
                                  int(south // 30), south % 30, house_for(south, cusps) if cusps else None, "derived_opposite_north_node", north.flags))
        ayanamsa = swe.get_ayanamsa_ut(jd) if house_flags else None
    elements = {key: 0 for key in ("Lửa", "Đất", "Khí", "Nước")}
    modalities = {key: 0 for key in ("Tiên phong", "Kiên định", "Linh hoạt")}
    for p in positions[:10]:
        elements[SIGNS[p.sign_index][2]] += 1
        modalities[SIGNS[p.sign_index][3]] += 1
    aspect_points = positions + [p for p in axis_positions(angles, cusps) if p.id in ("ASC", "MC")]
    return NatalChart(birth, local.isoformat(), utc.isoformat(), jd, positions, cusps, angles,
                      calculate_aspects(aspect_points, birth.max_orb), elements, modalities,
                      {"engine_version": swe.version, "calendar": "proleptic Gregorian",
                       "coordinates": "apparent geocentric ecliptic, equinox of date",
                       "time_standard": "UTC passed to calc_ut; library handles delta T",
                       "timezone_source": "IANA zoneinfo historical offsets",
                       "house_assignment": "ecliptic longitude against cusps",
                       "ayanamsa_degrees": ayanamsa, "aspect_rule": "min(user maximum, per-aspect default)",
                       "element_count": "10 planets, equal weights; nodes/asteroids excluded"}, notices)

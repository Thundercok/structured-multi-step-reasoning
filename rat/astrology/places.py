"""Explicit location search; only the typed place is sent to the geocoder."""
from dataclasses import dataclass
from functools import lru_cache
import json
import unicodedata
import urllib.parse
import urllib.request


@dataclass(frozen=True)
class Place:
    name: str
    latitude: float
    longitude: float
    timezone: str


PRESETS = (
    Place("TP. Hồ Chí Minh, Việt Nam", 10.8231, 106.6297, "Asia/Ho_Chi_Minh"),
    # tzdb/asia assigns northern Vietnam to Bangkok since its 1970 cutoff.
    # Ho_Chi_Minh differs by an hour in 1970–1975; see docs/natal_chart.md.
    Place("Hà Nội, Việt Nam", 21.0245, 105.8412, "Asia/Bangkok"),
    Place("Đà Nẵng, Việt Nam", 16.0678, 108.2208, "Asia/Ho_Chi_Minh"),
    Place("Huế, Việt Nam", 16.4637, 107.5909, "Asia/Ho_Chi_Minh"),
    Place("Cần Thơ, Việt Nam", 10.0371, 105.7883, "Asia/Ho_Chi_Minh"),
    Place("New York, Hoa Kỳ", 40.7143, -74.0060, "America/New_York"),
    Place("London, Anh", 51.5085, -0.1257, "Europe/London"),
    Place("Paris, Pháp", 48.8534, 2.3488, "Europe/Paris"),
    Place("Tokyo, Nhật Bản", 35.6895, 139.6917, "Asia/Tokyo"),
    Place("Sydney, Úc", -33.8679, 151.2073, "Australia/Sydney"),
)


def geocoding_query(query: str) -> str:
    """GeoNames searches Latin city names reliably without diacritics.

    Preserve spaces (Da Lat is not Dalat) and leave non-Latin scripts intact.
    The displayed city/returned coordinates still come from the service.
    """
    letters = [c for c in query if unicodedata.category(c).startswith('L')]
    if any(not unicodedata.name(c, '').startswith('LATIN') for c in letters):
        return query
    decomposed = unicodedata.normalize('NFKD', query)
    return ''.join(c for c in decomposed if not unicodedata.combining(c)).translate(str.maketrans({'Đ': 'D', 'đ': 'd', 'Ð': 'D', 'ð': 'd'}))


@lru_cache(maxsize=64)
def search_places(query: str) -> tuple[Place, ...]:
    query = query.strip()
    if not 2 <= len(query) <= 200:
        raise ValueError("Nhập tên thành phố từ 2 ký tự.")
    url = "https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(
        {"name": geocoding_query(query), "count": 8, "language": "vi", "format": "json"})
    request = urllib.request.Request(url, headers={"User-Agent": "RAT-Natal/1.0 (local desktop city search)"})
    with urllib.request.urlopen(request, timeout=10) as response:
        payload = json.loads(response.read(256_000))
    if payload.get("error"):
        raise ValueError(payload.get("reason", "Không tìm được địa điểm."))
    results = []
    for item in payload.get("results", []):
        if all(key in item for key in ("name", "latitude", "longitude", "timezone")):
            label = ", ".join(dict.fromkeys(str(item[key]) for key in ("name", "admin1", "country") if item.get(key)))
            results.append(Place(label, float(item["latitude"]), float(item["longitude"]), item["timezone"]))
    return tuple(results)

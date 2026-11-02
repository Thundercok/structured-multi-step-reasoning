"""Location-query regression and candidate preservation, independent of Qt."""
from io import BytesIO
import json
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

from rat.astrology.places import geocoding_query, search_places


def test_latin_diacritics_preserve_spaces_and_non_latin_scripts():
    # Actual API failure: Đà Lạt matched an unrelated place, while Da Lat worked.
    # Joining the words into Dalat instead matched towns in other countries.
    assert geocoding_query('Đà Lạt') == 'Da Lat'
    assert geocoding_query('München') == 'Munchen'
    assert geocoding_query('東京都') == '東京都'
    assert geocoding_query('Москва') == 'Москва'


def test_lookup_sends_only_place_query_and_keeps_all_candidates():
    search_places.cache_clear()
    payload = {'results': [
        {'name': 'Ðà Lạt', 'latitude': 11.94646, 'longitude': 108.44193,
         'timezone': 'Asia/Ho_Chi_Minh', 'country': 'Việt Nam'},
        {'name': 'Other place', 'latitude': 2.6, 'longitude': 112,
         'timezone': 'Asia/Kuching', 'country': 'Malaysia'},
    ]}
    with patch('urllib.request.urlopen', return_value=BytesIO(json.dumps(payload).encode())) as request:
        places = search_places('Đà Lạt')
    query = parse_qs(urlsplit(request.call_args.args[0].full_url).query)
    assert query == {'name': ['Da Lat'], 'count': ['8'], 'language': ['vi'], 'format': ['json']}
    assert len(places) == 2 and places[0].timezone == 'Asia/Ho_Chi_Minh'
    assert places[1].name == 'Other place, Malaysia'
    search_places.cache_clear()

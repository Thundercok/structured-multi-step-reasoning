# RAT Natal Atlas

Open **✧ Lá số** in RAT's expanded navigation, **Bản đồ sao cá nhân** in the
menu bar, or run the independent window:

```bash
python -m pip install -r requirements-astrology.txt
python -m rat.astrology
```

Inside the main RAT assistant, clicking **✧ Lá số** or asking naturally enters the shared interaction kernel workflow inline within the conversational surface (asking for missing birth data via `InputRequest` and rendering the chart artifact inline). The independent standalone window via `python -m rat.astrology` remains available for standalone desktop viewing.
The independent window needs PyQt6 and the optional astrology binding. It does
not initialize file indexing, a resident daemon, Qt research experiments or an
AI model. The first view is clearly labeled sample data, not the user's chart.
The PyInstaller specification includes the chart module, Qt SVG component and
ephemeris directory. Install the optional requirement in the build environment
before packaging. The frozen app/DMG has not been rebuilt in this change.

## Inline RAT workflow

The main assistant uses the shared interaction surface rather than opening the
standalone atlas. Request a chart or choose **✧ Lá số**. Only missing inputs are
shown; no example birth date is used as personal data. The date field accepts
`DD/MM/YYYY` and `YYYY-MM-DD`. If birth time is unknown, uncheck **Biết giờ sinh**;
houses and angles are omitted and the calculated uncertainty remains visible.

Select an actual place candidate when ambiguous. If geocoding is unavailable,
enter known latitude, longitude and an IANA timezone. Repeated DST hours offer
an explicit first/second occurrence choice. These inputs resume the same pending
operation and survive progress updates.

**Đổi giờ sinh** opens a small inline editor; **Áp dụng** recalculates the same
chart with a new revision. SVG/PNG/PDF export asks where to save and leaves the
chart intact. Drawing uses observed chart data without recalculation. Expand
planet, house and aspect tables to see every row; selecting a point on the wheel
shows its precise position. Previous results can be inspected by ID/revision
through the registered `inspect_artifact` operation.

Direct actions run on a worker. Invalid input remains visible for correction;
a conversation reset rejects late results from the old generation. The standard
view provider and registered domain drawings use shared contracts. AI-generated
views/code remain future work. This software behavior is covered by fixture
regressions, not a measured improvement in live-model task quality.

## Standalone atlas

Enter a name, Gregorian birth date, **local** birth time and place. Choose a
preset city or type a city and press **Tìm thành phố khác**, then select the
correct result. Search uses Open-Meteo/GeoNames; only the place query leaves the
machine. Latin-script queries omit diacritics but preserve word boundaries;
non-Latin scripts remain unchanged. The live Đà Lạt regression and raw responses
are in `audit/natal_place_lookup_20261011/`. Birth details are not sent to that
service. A network failure leaves
presets and manual coordinates usable. Advanced settings allow exact coordinates,
IANA timezone, the repeated-DST-hour choice, zodiac and orb maximum. City
coordinates are reference points; historical boundaries/zone names should be
checked for old births. `zoneinfo` applies the historical offsets in the chosen
zone, rather than today's fixed UTC offset.
The Hà Nội preset uses `Asia/Bangkok`, the tzdb zone for northern Vietnam since
1970. `Asia/Ho_Chi_Minh` covers the southern transition from UTC+8 to UTC+7 in
June 1975; using it for Hà Nội in 1970–1975 would shift the chart by one hour.
The [IANA source](https://data.iana.org/time-zones/tzdb/asia) explicitly directs
pre-1970 Hanoi history to its separate `backzone` data, which is not bundled here.
Births before 1970 display a civil-time uncertainty notice; selecting a modern
geocoder timezone is not archival verification of every city's earlier clocks.

Select a planet on the wheel, use left/right keys, or choose a table row. The
detail panel gives degrees/minutes/seconds, latitude, daily angular speed,
retrograde status, house and aspects. Tables include 10 planets, true North/South
Nodes, mean-apogee Lilith and Chiron (when data is available); the 12 cusps plus
ASC, MC, DSC, IC and Vertex; and aspect separations, orbs and instantaneous
applying/separating status. Whole Sign may place MC away from the tenth cusp.
Aspects also include ASC and MC; their instantaneous applying/separating status
is deliberately unspecified. Click an axis row in the house table for its data.
Trine/sextile/square/opposition/quincunx appear as named rows, so color alone is
never necessary. Conjunctions are in the table but omitted from the inner chords.
South Node aspects are omitted as exact duplicates of the opposite North Node.

The **chưa biết giờ sinh** mode uses local noon as an explicitly provisional
planetary epoch and removes all houses/axes. Positions at the two day endpoints
give a rough movement indication, not a rigorous interval extremum computation.
Moon positions/aspects in that mode are provisional. A DST gap is rejected;
a repeated time requires choosing first/second occurrence. Placidus/Koch failures
at polar latitudes are reported, not silently replaced by another house system.

Changes mark the displayed chart stale and disable export/AI interpretation
until **Lập lá số** recomputes it. Save/Open stores birth inputs in a chosen JSON
file; imported astronomical positions are never trusted. SVG retains vector
geometry and calculation metadata; PNG is 2000×2660; PDF is vector. Profiles are
saved only on an explicit Save, not automatically. Exported charts contain birth
information. The integrated **Hỏi Chuột** button sends calculated positions to
RAT's configured model for requested symbolic interpretation; calculation itself
is deterministic and remains available without a model.
Chat also exposes a place-lookup tool, so the model can retrieve coordinates and
timezones before proposing a chart. It receives all matching candidates instead
of a silently selected city. The interpretation input uses explicit table columns
to remove repeated field names and export styling: the sample is 4,569 characters
instead of 10,932. Calculated longitudes, aspect values, time uncertainty and
provenance retain full precision; the full chart remains in UI sources and raw
tool results. This reduces context pressure without supplying canned readings.
The chat displays a short interpretation request; the calculated chart travels
as source data, so JSON fields do not fill the user's conversation. That source
remains available to follow-up questions.

## Calculation conventions and limits

- Bundled planetary/lunar/main-asteroid data supports 1800–2399 CE. Manifest
  records upstream URLs, sizes and SHA-256 hashes. Main planetary calculations
  reject an effective Moshier fallback if the files are missing.
- Geocentric apparent ecliptic longitude/latitude, equinox of date; UTC to
  `calc_ut`, with library delta-T handling. Civil-time uncertainty and the
  UTC/UT1 distinction limit what printed seconds can imply.
- Tropical, or sidereal Lahiri. Sidereal globals and ephemeris globals are
  serialized under a lock, including across chart requests.
- Placidus, Whole Sign, Equal, Koch, Porphyry and Regiomontanus. House assignment
  compares **ecliptic longitude** against cusp intervals; this is not the
  alternative mundane placement calculated with planetary latitude.
- Aspect thresholds: conjunction/opposition 8°, square/trine 6°, sextile 4°,
  quincunx 2°, each capped by the chosen user maximum. Element/modalities counts
  use the 10 planets with equal weights, excluding nodes/asteroids/axes.
  ASC/MC aspects are included, but trivial axis-to-axis geometry is excluded.
- Labels move only to avoid collision. Exact ticks, leader-line endpoints,
  aspect lines and tables retain the calculated longitude.
- No AI or canned personality reading is mixed into the position calculations.
  The requested model interpretation is identified separately from these data.

The raw [NASA Horizons comparison](../audit/natal_horizons_reference_20261011/comparison.json)
checks Sun, Moon and Mars at one sample epoch. All three differ by less than
0.1 arcsecond in apparent ecliptic longitude. The offline regression tolerance
is 5 arcseconds to allow reference-model/convention differences. This limited
check is not a universal accuracy certification or an endorsement.

## Component and accessibility notes

The atlas extends RAT's paper/ink/gold palette with restrained element colors.
Form controls have focus outlines, labels/accessibility names, visible error
states and a clear primary action. The canvas has keyboard point selection and
an accessible description; exact data is also available as table text. Small
window sizes preserve scrolling rather than hiding advanced settings. The native
window supports saved profiles and explicit empty/error/stale states. The optional
city lookup runs on a Qt worker; local calculations and vector rendering are fast
and do not invoke inference. Profile name/place are escaped in SVG/HTML.

## Dependency licensing

The optional `pyswisseph` binding uses AGPL-3.0. Upstream ephemeris files retain
their [copyright/license notice](../rat/astrology/ephemeris/LICENSE). The upstream
dual-license terms require a choice before distribution or public hosting:
AGPL-compatible project distribution or an appropriate professional license.
This change does not relicense the repository or buy such a license. Local
implementation/testing is complete; public distribution needs that license
decision. Open-Meteo/GeoNames attribution is visible in the form; consult the
service terms for commercial use.

Primary documentation: [ephemeris API](https://www.astro.com/swisseph/swephprg.htm),
[Python binding](https://pypi.org/project/pyswisseph/),
[NASA Horizons quantity 31](https://ssd.jpl.nasa.gov/horizons/manual.html),
[city lookup](https://open-meteo.com/en/docs/geocoding-api).

For a reproducible, clearly labeled sample preview and all exports:

```bash
QT_QPA_PLATFORM=offscreen python -m scripts.preview_natal_chart --output audit/NEW_ATLAS_PREVIEW
```

This desktop demonstration does not change the NCKH Stage 0 gate or supply
evidence about language-model quality.

"""Read-only macOS application catalog. Discovery is explicit, outside typing.

Only bundle metadata is read. This module never launches applications, searches
personal documents, imports AppKit/Qt, or calls a model. Catalog identity is not
a code-signature/security attestation; a future launcher must revalidate targets.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import plistlib
import re
import sys
import unicodedata
from xml.parsers.expat import ExpatError


def _default_catalog_cache_path() -> Path:
    state_dir = os.environ.get("RAT_STATE_DIR")
    if state_dir:
        return Path(state_dir).expanduser() / "app_catalog_cache.json"
    rat_dir = Path.home() / ".rat"
    try:
        if rat_dir.is_dir() and os.access(str(rat_dir), os.W_OK):
            return rat_dir / "app_catalog_cache.json"
    except Exception:
        pass
    return Path("/tmp/rat_app_catalog_cache.json")


def name_key(text):
    value = unicodedata.normalize('NFD', text.casefold()).replace('đ', 'd')
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[^\W_]+', value))


DEFAULT_ALIASES = {'league of legends': ('Liên Minh Huyền Thoại', 'Liên Minh', 'LoL')}

# Resolve purposes against installed bundle identities, never invented app paths.
# Kept separate from cached names so vocabulary updates apply to warm catalogs.
FUNCTIONAL_APPS = {
    'tính toán': ('com.apple.calculator',),
    'máy tính': ('com.apple.calculator',),
    'trình duyệt': ('com.apple.safari', 'com.google.chrome', 'org.mozilla.firefox', 'com.microsoft.edgemac'),
    'lướt web': ('com.apple.safari', 'com.google.chrome', 'org.mozilla.firefox', 'com.microsoft.edgemac'),
    'gõ code': ('com.microsoft.vscode', 'com.apple.dt.xcode', 'com.todesktop.230313mzl4w4u92'),
    'viết code': ('com.microsoft.vscode', 'com.apple.dt.xcode', 'com.todesktop.230313mzl4w4u92'),
    'soạn thảo': ('com.apple.iwork.pages', 'com.microsoft.word', 'com.apple.textedit'),
    'ghi chú': ('com.apple.notes',),
}
_FUNCTIONAL_IDS = {name_key(purpose): ids for purpose, ids in FUNCTIONAL_APPS.items()}


def functional_app_ids(query: str) -> tuple[str, ...]:
    key = name_key(query)
    for prefix in ('cai app ', 'cai ung dung ', 'app ', 'ung dung ', 'cai '):
        if key.startswith(prefix):
            key = key[len(prefix):]
            break
    return _FUNCTIONAL_IDS.get(key, ())


@dataclass(frozen=True)
class Application:
    resource_id: str
    path: str
    name: str
    bundle_id: str
    version: str
    names: tuple[str, ...]


def revalidate_application_bundle(
    bundle_path: str | Path,
    *,
    expected_bundle_id: str | None = None,
    aliases=None,
) -> Application:
    """Revalidate an .app bundle on disk without executing or launching anything.

    Checks resolved .app directory, Contents/Info.plist (<= 1 MiB), CFBundleIdentifier,
    and Contents/MacOS/<CFBundleExecutable> regular file existence.
    """
    mapping = {
        name_key(key): (value,) if isinstance(value, str) else tuple(value)
        for key, value in (DEFAULT_ALIASES if aliases is None else aliases).items()
    }
    entry = Path(bundle_path).expanduser()
    if entry.suffix.casefold() != '.app':
        raise ValueError('invalid_application_bundle_suffix')
    path = entry.resolve(strict=True)
    if not path.is_dir() or path.suffix.casefold() != '.app':
        raise ValueError('invalid_application_bundle_dir')
    info = path / 'Contents' / 'Info.plist'
    if not info.is_file():
        raise ValueError('missing_info_plist')
    if info.stat().st_size > 1024 * 1024:
        raise ValueError('oversize_app_metadata')
    with info.open('rb') as stream:
        data = plistlib.load(stream)
    if not isinstance(data, dict):
        raise ValueError('invalid_info_plist')
    bundle_id = data.get('CFBundleIdentifier')
    executable = data.get('CFBundleExecutable')
    if not isinstance(bundle_id, str) or not bundle_id.strip():
        raise ValueError('missing_bundle_id')
    if expected_bundle_id is not None and bundle_id != expected_bundle_id:
        raise ValueError('bundle_id_mismatch')
    if (
        not isinstance(executable, str)
        or not executable.strip()
        or Path(executable).name != executable
        or not (path / 'Contents' / 'MacOS' / executable).is_file()
    ):
        raise ValueError('missing_bundle_executable')
    name = data.get('CFBundleDisplayName') or data.get('CFBundleName') or path.stem
    if not isinstance(name, str) or not name.strip():
        raise ValueError('invalid_app_name')
    names = {name_key(name), name_key(path.stem), name_key(bundle_id)}
    for key in tuple(names):
        names.update(name_key(alias) for alias in mapping.get(key, ()))
    return Application(
        'app:' + hashlib.sha256(str(path).encode()).hexdigest()[:24],
        str(path),
        name,
        bundle_id,
        str(data.get('CFBundleShortVersionString') or data.get('CFBundleVersion') or ''),
        tuple(sorted(n for n in names if n)),
    )


@dataclass(frozen=True)
class ApplicationCatalog:
    applications: tuple[Application, ...] = ()
    issues: tuple[str, ...] = ()

    @classmethod
    def scan(
        cls,
        roots=None,
        *,
        aliases=None,
        max_entries=20000,
        max_depth=2,
        use_cache: bool = True,
        cache_path: str | Path | None = None,
    ):
        """Bounded metadata scan; retain separate installations of one bundle ID.

        If use_cache is True and aliases is None, checks directory mtimes against
        cached metadata to achieve instant (< 2ms) startup.
        """
        if max_entries < 1 or max_depth < 0:
            raise ValueError('invalid_app_catalog_budget')
        is_default_scan = (roots is None and aliases is None and max_entries == 20000 and max_depth == 2)
        should_cache = (use_cache and cache_path is not None) or (use_cache and is_default_scan)

        if roots is None:
            if sys.platform != 'darwin':
                return cls(issues=('application_catalog_platform_unsupported',))
            roots = ('/Applications', '/System/Applications', Path.home() / 'Applications')

        resolved_roots = [Path(root).expanduser() for root in roots]
        target_cache = Path(cache_path) if cache_path else _default_catalog_cache_path()

        # Fast cache path: verify directory mtimes
        if should_cache:
            try:
                if target_cache.is_file():
                    with target_cache.open('r', encoding='utf-8') as f:
                        cache_data = json.load(f)
                    if isinstance(cache_data, dict) and cache_data.get('schema_version') == 1:
                        cached_mtimes = cache_data.get('roots_mtimes', {})
                        valid = True
                        for r in resolved_roots:
                            if r.is_dir():
                                mtime = r.stat().st_mtime_ns
                                if cached_mtimes.get(str(r)) != mtime:
                                    valid = False
                                    break
                            elif str(r) in cached_mtimes:
                                valid = False
                                break
                        if valid and 'apps' in cache_data:
                            cached_apps = [
                                Application(
                                    item['resource_id'],
                                    item['path'],
                                    item['name'],
                                    item['bundle_id'],
                                    item['version'],
                                    tuple(item.get('names', ())),
                                )
                                for item in cache_data['apps']
                            ]
                            cached_issues = tuple(cache_data.get('issues', ()))
                            return cls(tuple(cached_apps), cached_issues)
            except Exception:
                pass

        apps, issues, seen, inspected = [], set(), set(), 0
        pending = [(r, 0) for r in resolved_roots]
        while pending:
            directory, depth = pending.pop()
            try:
                entries = sorted(islice(directory.iterdir(), max_entries - inspected + 1),
                                 key=lambda p: p.name.casefold())
            except OSError:
                issues.add('application_root_unavailable')
                continue
            for entry in entries:
                inspected += 1
                if inspected > max_entries:
                    issues.add('application_catalog_scan_limit')
                    return cls(tuple(sorted(apps, key=lambda a: (a.name, a.path))), tuple(sorted(issues)))
                if entry.name.startswith('.'):
                    continue
                if entry.suffix.casefold() != '.app':
                    if depth < max_depth and not entry.is_symlink() and entry.is_dir():
                        pending.append((entry, depth + 1))
                    continue
                try:
                    app = revalidate_application_bundle(entry, aliases=aliases)
                    if app.path in seen:
                        continue
                    apps.append(app)
                    seen.add(app.path)
                except (OSError, ValueError, TypeError, AttributeError, ExpatError, plistlib.InvalidFileException):
                    issues.add('invalid_application_bundle')

        catalog_result = cls(tuple(sorted(apps, key=lambda a: (a.name, a.path))), tuple(sorted(issues)))

        # Save to cache atomically
        if should_cache:
            try:
                target_cache.parent.mkdir(parents=True, exist_ok=True)
                current_mtimes = {}
                for r in resolved_roots:
                    if r.is_dir():
                        current_mtimes[str(r)] = r.stat().st_mtime_ns
                cache_payload = {
                    'schema_version': 1,
                    'roots_mtimes': current_mtimes,
                    'apps': [
                        {
                            'resource_id': a.resource_id,
                            'path': a.path,
                            'name': a.name,
                            'bundle_id': a.bundle_id,
                            'version': a.version,
                            'names': list(a.names),
                        }
                        for a in catalog_result.applications
                    ],
                    'issues': list(catalog_result.issues),
                }
                tmp_cache = target_cache.with_name(f"{target_cache.name}.tmp.{os.getpid()}")
                with tmp_cache.open('w', encoding='utf-8') as f:
                    json.dump(cache_payload, f)
                tmp_cache.replace(target_cache)
            except Exception:
                pass

        return catalog_result

    def search(self, query, *, limit=10):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid_app_search_limit')
        key = name_key(query)
        if not key:
            return ()
        matches = []
        functional_ids = functional_app_ids(query)
        for app in self.applications:
            quality = min((0 if key == name else 1 if name.startswith(key)
                           else 2 if all(word in name.split() for word in key.split()) else 3)
                          for name in app.names)
            if app.bundle_id.casefold() in functional_ids:
                quality = min(quality, 2)
            if quality < 3 and (Path(app.path) / 'Contents' / 'Info.plist').is_file():
                matches.append((quality, app.name.casefold(), app.path, app))
        return tuple(item[-1] for item in sorted(matches)[:limit])

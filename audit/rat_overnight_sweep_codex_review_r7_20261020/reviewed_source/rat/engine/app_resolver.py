"""Read-only macOS application catalog. Discovery is explicit, outside typing.

Only bundle metadata is read. This module never launches applications, searches
personal documents, imports AppKit/Qt, or calls a model. Catalog identity is not
a code-signature/security attestation; a future launcher must revalidate targets.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from itertools import islice
from pathlib import Path
import plistlib
import re
import sys
import unicodedata
from xml.parsers.expat import ExpatError


def name_key(text):
    value = unicodedata.normalize('NFD', text.casefold()).replace('đ', 'd')
    value = ''.join(c for c in value if not unicodedata.combining(c))
    return ' '.join(re.findall(r'[^\W_]+', value))


DEFAULT_ALIASES = {'league of legends': ('Liên Minh Huyền Thoại', 'Liên Minh', 'LoL')}


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
    def scan(cls, roots=None, *, aliases=None, max_entries=20000, max_depth=2):
        """Bounded metadata scan; retain separate installations of one bundle ID."""
        if max_entries < 1 or max_depth < 0:
            raise ValueError('invalid_app_catalog_budget')
        if roots is None:
            if sys.platform != 'darwin':
                return cls(issues=('application_catalog_platform_unsupported',))
            roots = ('/Applications', '/System/Applications', Path.home() / 'Applications')
        apps, issues, seen, inspected = [], set(), set(), 0
        pending = [(Path(root).expanduser(), 0) for root in roots]
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
        return cls(tuple(sorted(apps, key=lambda a: (a.name, a.path))), tuple(sorted(issues)))

    def search(self, query, *, limit=10):
        if type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError('invalid_app_search_limit')
        key = name_key(query)
        if not key:
            return ()
        matches = []
        for app in self.applications:
            quality = min((0 if key == name else 1 if name.startswith(key)
                           else 2 if all(word in name.split() for word in key.split()) else 3)
                          for name in app.names)
            if quality < 3 and (Path(app.path) / 'Contents' / 'Info.plist').is_file():
                matches.append((quality, app.name.casefold(), app.path, app))
        return tuple(item[-1] for item in sorted(matches)[:limit])

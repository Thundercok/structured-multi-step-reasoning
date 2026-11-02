"""Bounded, nonrecursive folder plans and journalled exclusive moves.

No Qt or model dependency. The capability layer supplies scoped roots and a
pinned, explicit approval. Files are never deleted or overwritten.
"""
from __future__ import annotations
import ctypes
import errno
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import threading
import time
from uuid import uuid4

_LOCK = threading.Lock()
MAX_FILES, MAX_SCAN = 100, 1000
GROUPS = {'Documents': '.pdf .txt .md .doc .docx .xls .xlsx .ppt .pptx .csv .rtf .odt',
          'Images': '.png .jpg .jpeg .gif .webp .heic .tiff .bmp .svg',
          'Archives': '.zip .tar .gz .7z .rar', 'Audio': '.mp3 .wav .m4a .flac',
          'Video': '.mov .mp4 .mkv .avi'}


def identity(info):
    return [info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns]


def digest(plan):
    return hashlib.sha256(json.dumps({k: v for k, v in plan.items() if k != 'digest'},
        sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest()


def exclusive_move(srcfd, src, dstfd, dst):
    """Darwin renameatx_np(RENAME_EXCL); deliberately no unsafe rename fallback."""
    if sys.platform != 'darwin':
        raise OSError(errno.ENOTSUP, 'organization_requires_macos')
    libc = ctypes.CDLL(None, use_errno=True)
    call = libc.renameatx_np
    call.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    call.restype = ctypes.c_int
    if call(srcfd, os.fsencode(src), dstfd, os.fsencode(dst), 0x00000004):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code))


def directory(path, *, dir_fd=None):
    return os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=dir_fd)


def regular(fd, name):
    info = os.stat(name, dir_fd=fd, follow_symlinks=False)
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('not_regular_file')
    return identity(info)


class FolderOrganizer:
    def __init__(self, scopes, journal_directory):
        self.scopes, self.journals = scopes, Path(journal_directory)

    def root(self, raw):
        raw = Path(raw).expanduser()
        if raw.is_symlink():
            raise ValueError('organization_symlink_folder')
        path = raw.resolve(strict=True)
        if not any(path == root or path.is_relative_to(root) for root in self.scopes.roots):
            raise ValueError('organization_folder_outside_scope: Chọn thư mục trong phạm vi Cài đặt.')
        if not path.is_dir():
            raise ValueError('organization_not_folder')
        return path

    def plan(self, raw, rule='type', cancel=lambda: False):
        root = self.root(raw)
        if rule not in ('type', 'month'):
            raise ValueError('organization_unknown_rule')
        fd = directory(root)
        moves, skipped, scanned = [], {}, 0
        try:
            root_id = identity(os.fstat(fd))[:2]
            # Streaming enumeration is bounded even for huge Downloads folders.
            with os.scandir(fd) as entries:
                for entry in entries:
                    if cancel() or scanned >= MAX_SCAN or len(moves) >= MAX_FILES:
                        break
                    scanned += 1
                    reason = None
                    if entry.name.startswith('.'):
                        reason = 'hidden'
                    elif not entry.is_file(follow_symlinks=False):
                        reason = 'folder_or_link'
                    if reason:
                        skipped[reason] = skipped.get(reason, 0) + 1
                        continue
                    info = entry.stat(follow_symlinks=False)
                    suffix = Path(entry.name).suffix.lower()
                    group = (time.strftime('%Y-%m', time.localtime(info.st_mtime)) if rule == 'month' else
                        next((name for name, extensions in GROUPS.items() if suffix in extensions.split()), 'Other'))
                    # A destination link is never followed, even during preview.
                    try:
                        groupfd = directory(group, dir_fd=fd)
                    except FileNotFoundError:
                        groupfd = None
                    except OSError:
                        skipped['unsafe_destination'] = skipped.get('unsafe_destination', 0) + 1
                        continue
                    if groupfd is not None:
                        try:
                            try:
                                os.stat(entry.name, dir_fd=groupfd, follow_symlinks=False)
                                skipped['name_conflict'] = skipped.get('name_conflict', 0) + 1
                                continue
                            except FileNotFoundError:
                                pass
                        finally:
                            os.close(groupfd)
                    moves.append({'name': entry.name, 'group': group, 'identity': identity(info)})
        finally:
            os.close(fd)
        result = {'plan_id': uuid4().hex, 'root': str(root), 'root_identity': root_id,
            'scope_version': self.scopes.version, 'rule': rule, 'created_at': time.time(),
            'moves': sorted(moves, key=lambda m: m['name'].casefold()), 'skipped': skipped,
            'scanned': scanned, 'limited': scanned >= MAX_SCAN or len(moves) >= MAX_FILES,
            'status': 'preview'}
        result['digest'] = digest(result)
        return result

    def _path(self, tx):
        if len(tx) != 32 or any(c not in '0123456789abcdef' for c in tx):
            raise ValueError('organization_invalid_transaction')
        return self.journals / (tx + '.json')

    def _save(self, journal):
        self.journals.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = self._path(journal['transaction_id'])
        temporary = target.with_suffix('.pending')
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(journal, stream, ensure_ascii=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            parentfd = directory(self.journals)
            try:
                os.fsync(parentfd)
            finally:
                os.close(parentfd)
        finally:
            temporary.unlink(missing_ok=True)

    def read(self, tx):
        return json.loads(self._path(tx).read_text())

    def latest(self):
        if not self.journals.exists():
            return {'status': 'empty', 'entries': [], 'transaction_id': ''}
        files = list(self.journals.glob('*.json'))
        if not files:
            return {'status': 'empty', 'entries': [], 'transaction_id': ''}
        return json.loads(max(files, key=lambda p: p.stat().st_mtime_ns).read_text())

    def _open_root(self, plan):
        if plan['scope_version'] != self.scopes.version:
            raise ValueError('organization_scope_changed')
        fd = directory(self.root(plan['root']))
        if identity(os.fstat(fd))[:2] != plan['root_identity']:
            os.close(fd)
            raise ValueError('organization_folder_changed')
        return fd

    @staticmethod
    def _group(rootfd, group, create=False):
        if '/' in group or group in ('', '.', '..'):
            raise ValueError('organization_invalid_group')
        if create:
            try:
                os.mkdir(group, mode=0o755, dir_fd=rootfd)
            except FileExistsError:
                pass
        fd = directory(group, dir_fd=rootfd)
        if os.fstat(fd).st_dev != os.fstat(rootfd).st_dev:
            os.close(fd)
            raise ValueError('organization_cross_volume')
        return fd

    def apply(self, plan, cancel=lambda: False):
        if digest(plan) != plan['digest'] or time.time() - plan['created_at'] > 1800:
            raise ValueError('organization_stale_preview')
        with _LOCK:
            # One transaction per immutable plan; retry never executes it twice.
            tx = plan['plan_id']
            if self._path(tx).exists():
                return self.read(tx)
            fd = self._open_root(plan)
            journal = {'transaction_id': tx, 'plan': plan, 'entries': [], 'created_at': time.time(), 'status': 'applying'}
            try:
                self._save(journal)
                for move in plan['moves']:
                    if cancel():
                        break
                    item = dict(move, state='skipped')
                    journal['entries'].append(item)
                    groupfd = None
                    try:
                        if '/' in move['name'] or move['name'] in ('', '.', '..'):
                            raise ValueError('organization_invalid_name')
                        if regular(fd, move['name']) != move['identity']:
                            raise ValueError('source_changed')
                        groupfd = self._group(fd, move['group'], create=True)
                        item['state'] = 'move_pending'
                        self._save(journal)  # durable intent precedes mutation
                        exclusive_move(fd, move['name'], groupfd, move['name'])
                        item['state'] = 'moved'
                        if regular(groupfd, move['name']) != move['identity']:
                            # Concurrent replacement: restore exclusively if possible.
                            item['state'] = 'identity_conflict'
                            exclusive_move(groupfd, move['name'], fd, move['name'])
                            item['state'] = 'restored_conflict'
                    except (OSError, ValueError) as error:
                        if item['state'] == 'move_pending':
                            item['state'] = 'skipped'
                        item['reason'] = type(error).__name__ + ':' + str(getattr(error, 'errno', '') or error)
                    finally:
                        if groupfd is not None:
                            os.close(groupfd)
                    self._save(journal)
                journal['status'] = 'partial' if cancel() or any(x['state'] != 'moved' for x in journal['entries']) else 'applied'
                journal['finished_at'] = time.time()
                self._save(journal)
                return journal
            finally:
                os.close(fd)

    def undo(self, tx, cancel=lambda: False):
        with _LOCK:
            journal = self.read(tx)
            fd = self._open_root(journal['plan'])
            try:
                for item in reversed(journal['entries']):
                    if cancel():
                        break
                    if item['state'] not in ('moved', 'move_pending', 'undo_pending', 'undo_conflict'):
                        continue
                    groupfd = None
                    try:
                        groupfd = self._group(fd, item['group'])
                        if item['state'] in ('undo_pending', 'move_pending'):
                            # Recover interrupted rename, retaining uncertainty if ambiguous.
                            try:
                                original_matches = regular(fd, item['name']) == item['identity']
                            except (OSError, ValueError):
                                original_matches = False
                            try:
                                destination_exists = os.stat(item['name'], dir_fd=groupfd, follow_symlinks=False) is not None
                            except FileNotFoundError:
                                destination_exists = False
                            if original_matches and not destination_exists:
                                item['state'] = 'undone'
                                self._save(journal)
                                continue
                        if regular(groupfd, item['name']) != item['identity']:
                            raise ValueError('destination_changed')
                        item['state'] = 'undo_pending'
                        self._save(journal)
                        exclusive_move(groupfd, item['name'], fd, item['name'])
                        item['state'] = 'undone'
                        if regular(fd, item['name']) != item['identity']:
                            item['state'] = 'identity_conflict'
                            exclusive_move(fd, item['name'], groupfd, item['name'])
                            raise ValueError('concurrent_destination_replacement')
                    except (OSError, ValueError) as error:
                        item['state'] = 'undo_conflict'
                        item['reason'] = type(error).__name__ + ':' + str(getattr(error, 'errno', '') or error)
                    finally:
                        if groupfd is not None:
                            os.close(groupfd)
                    self._save(journal)
                journal['status'] = 'undo_partial' if any(x['state'] in ('moved','move_pending','undo_pending','undo_conflict','identity_conflict') for x in journal['entries']) else 'undone'
                self._save(journal)
                return journal
            finally:
                os.close(fd)

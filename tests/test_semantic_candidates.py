"""The index must reach a person's documents, not the text files inside their code repositories."""
import os
from pathlib import Path

from rat.engine import semantic_index
from rat.engine.semantic_index import candidate_files


def write(path, text='nội dung', mtime=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return str(path)


def names(paths):
    return [Path(p).name for p in paths]


def never_stop():
    return False


def test_repository_inside_a_chosen_folder_is_skipped(tmp_path):
    keep = write(tmp_path / 'Documents/hop_dong.pdf')
    (tmp_path / 'Documents/project/.git').mkdir(parents=True)
    write(tmp_path / 'Documents/project/data/notes.txt')
    write(tmp_path / 'Documents/project/paper.pdf')
    assert candidate_files([tmp_path / 'Documents'], never_stop) == [keep]


def test_git_worktree_marker_file_also_counts_as_a_repository(tmp_path):
    keep = write(tmp_path / 'Documents/bao_cao.docx')
    write(tmp_path / 'Documents/worktree/.git', 'gitdir: elsewhere')
    write(tmp_path / 'Documents/worktree/readme.md')
    assert candidate_files([tmp_path / 'Documents'], never_stop) == [keep]


def test_repository_chosen_as_the_root_stays_indexed(tmp_path):
    (tmp_path / 'project/.git').mkdir(parents=True)
    keep = write(tmp_path / 'project/paper.pdf')
    assert candidate_files([tmp_path / 'project'], never_stop) == [keep]


def test_older_documents_come_before_newer_plain_text(tmp_path):
    write(tmp_path / 'new_note.txt', mtime=2_000_000)
    write(tmp_path / 'old_paper.pdf', mtime=1_000_000)
    write(tmp_path / 'older_slides.pptx', mtime=500_000)
    write(tmp_path / 'new_scan.pdf', mtime=1_500_000)
    assert names(candidate_files([tmp_path], never_stop)) == [
        'new_scan.pdf', 'old_paper.pdf', 'older_slides.pptx', 'new_note.txt']


def test_file_limit_cannot_push_documents_out(tmp_path, monkeypatch):
    monkeypatch.setattr(semantic_index, 'MAX_FILES', 2)
    for index in range(4):
        write(tmp_path / f'note_{index}.txt', mtime=2_000_000 + index)
    write(tmp_path / 'old_paper.pdf', mtime=1_000_000)
    assert 'old_paper.pdf' in names(candidate_files([tmp_path], never_stop))


def test_stopping_during_the_walk_returns_nothing(tmp_path):
    write(tmp_path / 'paper.pdf')
    assert candidate_files([tmp_path], lambda: True) == []

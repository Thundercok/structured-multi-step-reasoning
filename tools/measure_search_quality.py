"""Measure whether meaning search puts the right file near the top, on a person's real files.

The questions name real files, so they live outside the repo:

    ~/.rat/search_quality.json   [{"query": "...", "expect": ["part of a file name"], "source": "user"}]

    python tools/measure_search_quality.py --build     index the configured folders first (slow)
    python tools/measure_search_quality.py             score the questions against the index
    python tools/measure_search_quality.py --db PATH   use another index

A question counts for its "source" separately: questions written by someone who has just read the
file reuse its words and score higher than what a person really types.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def state_directory():
    return Path(os.environ.get('RAT_STATE_DIR') or Path.home() / '.rat')


def rank_of(expected, paths):
    """1-based position of the first file whose name contains an expected part, or None."""
    wanted = [part.casefold() for part in expected]
    for position, path in enumerate(paths, 1):
        name = Path(path).name.casefold()
        if any(part in name for part in wanted):
            return position
    return None


def unique_files(rows):
    """Search returns one row per matching chunk; a person sees each file once."""
    return list(dict.fromkeys(row['file_path'] for row in rows))


def summarize(ranks):
    total = len(ranks)
    return {
        'questions': total,
        'top_1': sum(rank == 1 for rank in ranks),
        'top_3': sum(rank is not None and rank <= 3 for rank in ranks),
        'not_found': sum(rank is None for rank in ranks),
        'mean_reciprocal_rank': round(sum(1 / rank for rank in ranks if rank) / total, 3) if total else 0.0,
    }


def score(cases, search):
    """Rank each question and summarize per source, plus everything together as 'all'."""
    lines, by_source = [], collections.defaultdict(list)
    for case in cases:
        paths = unique_files(search(case['query']))
        rank = rank_of(case['expect'], paths)
        by_source[case.get('source', 'unknown')].append(rank)
        by_source['all'].append(rank)
        lines.append({'query': case['query'], 'rank': rank, 'top': [Path(p).name for p in paths[:3]],
                      'source': case.get('source', 'unknown')})
    return lines, {source: summarize(ranks) for source, ranks in by_source.items()}


def build_index(index, roots):
    index.start(roots)
    while index._thread and index._thread.is_alive():
        time.sleep(30)
        print(index.progress(), flush=True)
    print('Indexed', index.count(), 'chunks', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--db', type=Path, default=None, help='index file, default the app index')
    parser.add_argument('--questions', type=Path, default=None, help='default ~/.rat/search_quality.json')
    parser.add_argument('--build', action='store_true', help='index the configured folders into --db first')
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    from rat.engine.semantic_index import SemanticIndex
    index = SemanticIndex(args.db or state_directory() / 'semantic-index.sqlite')
    if args.build:
        from rat.config import config
        build_index(index, config.indexed_directories)

    questions = args.questions or state_directory() / 'search_quality.json'
    if not questions.exists():
        print(f'No questions at {questions}')
        return 0
    lines, summary = score(json.loads(questions.read_text(encoding='utf-8')), index.search)
    for line in lines:
        rank = line['rank'] or '-'
        print(f"{rank!s:>2}  [{line['source']}] {line['query']}\n      {' | '.join(line['top']) or '(no results)'}")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    sys.exit(main())

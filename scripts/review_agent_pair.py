"""Import explicit human ratings after verifying preserved paired artifacts."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from rat.engine.paired_continuation import canonical_bytes


def reviewed_row(bundle, ratings):
    pair_bytes = (bundle / 'pair.json').read_bytes()
    row = json.loads((bundle / 'pending_row.json').read_text())
    pair = json.loads(pair_bytes)
    digest = hashlib.sha256(pair_bytes).hexdigest()
    if digest != row['pair_trace_sha256'] or digest != ratings.get('pair_trace_sha256'):
        raise ValueError('Ratings must match the preserved raw pair hash')
    if row['evidence'] != 'measured_paired_continuation':
        raise ValueError('Synthetic smoke pairs cannot become measured outcomes')
    if pair['stop']['error'] or pair['continue']['error']:
        raise ValueError('Record execution failures separately; do not fit them as completed branch outcomes')
    for key in ('reviewer', 'rubric', 'notes'):
        if not isinstance(ratings.get(key), str) or not ratings[key].strip():
            raise ValueError('Human reviewer, rubric and notes are required')
    for key in ('stop_quality', 'continue_quality'):
        value = ratings.get(key)
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError('Explicit human ratings must be finite values in [0,1]')
    stop, continued = pair['stop']['total_tokens'], pair['continue']['total_tokens']
    if (row['stop_tokens'], row['continue_tokens'], row['delta_tokens']) != (stop, continued, continued - stop):
        raise ValueError('Row token costs differ from the branch artifacts')
    return {**row, 'reviewed': True, 'quality_gain': ratings['continue_quality'] - ratings['stop_quality'],
            'review': ratings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--ratings', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    row = reviewed_row(args.bundle, json.loads(args.ratings.read_text()))
    with args.output.open('xb') as stream:
        stream.write(canonical_bytes(row))


if __name__ == '__main__':
    main()

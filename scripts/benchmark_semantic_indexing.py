"""Benchmark first-run indexing on a real folder with >= 2k mixed files."""
import os
import resource
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rat.engine.semantic_index import SemanticIndex, candidate_files

def run_benchmark():
    roots = [
        os.path.expanduser('~/Downloads'),
        str(Path(__file__).resolve().parents[1])  # multi-step-structured-reasoning repo
    ]
    
    # 1. Count candidate files
    t_scan_start = time.time()
    candidates = candidate_files(roots, lambda: False)
    scan_time = time.time() - t_scan_start
    ext_counts = Counter(Path(p).suffix.lower() for p in candidates)
    
    print(f"=== Benchmark: First-Run Indexing ===")
    print(f"Roots: {roots}")
    print(f"Total candidate files found: {len(candidates)} (scanned in {scan_time:.2f}s)")
    print(f"File breakdown: {dict(ext_counts)}")
    
    if len(candidates) < 2000:
        print(f"WARNING: Found {len(candidates)} files, expected >= 2000.")
    
    # 2. Setup isolated database in tmp
    tmp_dir = tempfile.mkdtemp(prefix='rat-bench-')
    db_path = Path(tmp_dir) / 'test-index.sqlite'
    os.environ['RAT_MINI_STATE_DIR'] = tmp_dir
    
    index = SemanticIndex(db_path)
    
    # Measure baseline RSS
    rusage = resource.getrusage(resource.RUSAGE_SELF)
    # On macOS ru_maxrss is in bytes
    baseline_rss_mb = rusage.ru_maxrss / (1024 * 1024) if sys.platform == 'darwin' else rusage.ru_maxrss / 1024
    print(f"Baseline RSS: {baseline_rss_mb:.1f} MB")
    
    # 3. Start background indexing
    t0 = time.time()
    started = index.start(roots)
    assert started, "Failed to start indexing"
    
    # 4. Measure UI responsiveness (simulate UI loop measuring jitter)
    jitter_samples = []
    max_jitter_ms = 0.0
    queries_tested = 0
    query_latencies = []
    
    target_interval = 0.05  # 50ms tick
    last_tick = time.time()
    
    print("Indexing in progress...")
    while True:
        prog = index.progress()
        now = time.time()
        elapsed_tick = now - last_tick
        jitter_ms = abs(elapsed_tick - target_interval) * 1000.0
        jitter_samples.append(jitter_ms)
        if jitter_ms > max_jitter_ms:
            max_jitter_ms = jitter_ms
        last_tick = now
        
        # Every 10 seconds, test a search query to verify query non-interference & latency
        if int(now - t0) > 0 and int(now - t0) % 15 == 0 and queries_tested < int(now - t0) // 15:
            queries_tested += 1
            t_q0 = time.time()
            try:
                hits = index.search("attention mechanism paper")
                q_dur_ms = (time.time() - t_q0) * 1000.0
                query_latencies.append(q_dur_ms)
                print(f"  [Active query test #{queries_tested}] Latency: {q_dur_ms:.1f} ms, Hits: {len(hits)}")
            except Exception as e:
                print(f"  [Active query test #{queries_tested}] Failed: {e}")
        
        if prog['state'] in ('ready', 'unavailable'):
            break
        
        time.sleep(target_interval)
    
    total_time = time.time() - t0
    rusage_end = resource.getrusage(resource.RUSAGE_SELF)
    peak_rss_mb = rusage_end.ru_maxrss / (1024 * 1024) if sys.platform == 'darwin' else rusage_end.ru_maxrss / 1024
    
    avg_jitter_ms = sum(jitter_samples) / len(jitter_samples) if jitter_samples else 0.0
    indexed_count = index.count()
    
    print("\n=== Results ===")
    print(f"Files Indexed: {indexed_count} / {len(candidates)}")
    print(f"Total Time: {total_time:.2f} s ({total_time/indexed_count*1000:.1f} ms/file)")
    print(f"Peak RSS: {peak_rss_mb:.1f} MB (Delta: +{peak_rss_mb - baseline_rss_mb:.1f} MB)")
    print(f"UI Loop Avg Jitter: {avg_jitter_ms:.2f} ms")
    print(f"UI Loop Max Jitter: {max_jitter_ms:.2f} ms")
    if query_latencies:
        print(f"Concurrent Query Avg Latency: {sum(query_latencies)/len(query_latencies):.1f} ms")
    
    # Clean up
    import shutil
    shutil.rmtree(tmp_dir, ignore_errors=True)
    return {
        'files_indexed': indexed_count,
        'total_time_s': total_time,
        'peak_rss_mb': peak_rss_mb,
        'avg_jitter_ms': avg_jitter_ms,
        'max_jitter_ms': max_jitter_ms,
    }

if __name__ == '__main__':
    run_benchmark()

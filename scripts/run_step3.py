import time
import mlx_lm
from reasoning_strategies import run_python_sandboxed

REPO = "mlx-community/Qwen2.5-0.5B-Instruct-4bit"

print(f"=== STEP 3: PAL SUBPROCESS ISOLATION IN LOADED MLX PROCESS ===")
print(f"Loading {REPO} into process memory...")
model, tokenizer = mlx_lm.load(REPO)
print("Model loaded. MLX Metal device initialized.")

# Case 1: Valid Python code
valid_code = """
total_boxes = 24 * 18 + 15 * 25 + 30 * 12
result = total_boxes
"""
print("\n--- 1. Testing valid PAL code ---")
t0 = time.perf_counter()
ok1, res1 = run_python_sandboxed(valid_code, timeout=5.0)
elapsed1 = (time.perf_counter() - t0) * 1000.0

print(f"Valid Code Result: ok={ok1}, result={res1!r}")
print(f"Valid Code Elapsed Time: {elapsed1:.2f} ms")
assert ok1 and res1 == "1167", f"Expected ok=True and '1167', got ok={ok1}, res={res1!r}"

# Case 2: Infinite loop code
loop_code = """
while True:
    pass
"""
print("\n--- 2. Testing infinite loop (timeout=2.0s) ---")
timeout_setting = 2.0
t0 = time.perf_counter()
ok2, res2 = run_python_sandboxed(loop_code, timeout=timeout_setting)
elapsed2 = time.perf_counter() - t0

print(f"Loop Code Result: ok={ok2}, result={res2!r}")
print(f"Loop Code Elapsed Time: {elapsed2:.3f} s (timeout limit: {timeout_setting}s)")
assert not ok2 and res2 == "timeout", f"Expected ok=False and 'timeout', got ok={ok2}, res={res2!r}"
assert elapsed2 < (timeout_setting + 1.5), f"Process hung longer than timeout limit! Elapsed: {elapsed2:.3f}s"
print("\n=== STEP 3 VERIFICATION PASSED: No hang between MLX and PAL subprocess ===")

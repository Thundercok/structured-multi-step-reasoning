"""The latency check must flag real slowdowns and ignore noise on small numbers."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    'measure_desk_latency', Path(__file__).resolve().parents[1] / 'tools/measure_desk_latency.py')
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def step(ms):
    return {'median_ms': ms, 'worst_ms': ms, 'runs': 1}


def test_real_slowdown_is_flagged():
    assert tool.regressions({'enter': step(40.0)}, {'enter': step(80.0)}) == ['enter']


def test_noise_on_a_small_number_is_ignored():
    assert tool.regressions({'enter': step(4.0)}, {'enter': step(9.0)}) == []


def test_small_rise_on_a_large_number_is_ignored():
    assert tool.regressions({'enter': step(100.0)}, {'enter': step(140.0)}) == []


def test_new_step_without_a_baseline_is_not_a_regression():
    assert tool.regressions({}, {'enter': step(500.0)}) == []

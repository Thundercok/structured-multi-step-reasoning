import pytest

from scripts.cot_restart_rescue_diagnostics import clopper_pearson


def test_cp_zero_and_all_successes_have_exact_one_sided_boundaries():
    assert clopper_pearson(0, 5) == pytest.approx([0, 1-.025**(1/5)])
    assert clopper_pearson(7, 7) == pytest.approx([.025**(1/7), 1])
    lo, hi = clopper_pearson(3, 5)
    assert (lo, hi) == pytest.approx((.1466328, .947255), abs=1e-6)


def test_cp_invalid_counts_and_symmetry():
    a, b = clopper_pearson(2, 7), clopper_pearson(5, 7)
    assert a == pytest.approx([1-b[1], 1-b[0]])
    with pytest.raises(ValueError, match="invalid"):
        clopper_pearson(1, 0)
    with pytest.raises(ValueError, match="invalid"):
        clopper_pearson(8, 7)

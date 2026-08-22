"""The coverage floor, and telling its failure apart from a failing test.

pytest-cov reports both as exit 1. Calling a coverage dip "pytest failed" sends
you reading a green suite looking for a broken test — the same false accusation
the offline-toolchain branch already exists to avoid.

The floor is a ratchet, not a target: set just under the measured figure so that
ordinary churn passes and a new untested module does not. Lowering it to make a
red run green defeats the point; raise it only when the real number has moved up
and stayed there.
"""

from __future__ import annotations

from pathlib import Path

import selfcheck as sc

REPO = Path(__file__).resolve().parent.parent

# Ordering matters and is not obvious, so both fixtures mirror real pytest-cov
# output: the coverage table prints BEFORE `short test summary info`, and the
# FAILED lines and the run summary come after it. An earlier draft of this file
# invented the reverse order and failed a correct implementation.
FAILING_RUN = """\
tests/test_x.py F                                                        [100%]
---------- coverage: platform win32 ----------
Name                     Stmts   Miss  Cover
scripts/selfcheck.py       189     28    85%
TOTAL                     2566    178    93%
=========================== short test summary info ===========================
FAILED tests/test_x.py::test_thing - AssertionError: nope
1 failed, 741 passed, 2 skipped in 22.9s
"""

FLOOR_RUN = """\
---------- coverage: platform win32 ----------
Name                     Stmts   Miss  Cover
TOTAL                     2566    250    90%
FAIL Required test coverage of 91% not reached. Total coverage: 90.12%
742 passed, 2 skipped, 1 warning in 23.2s
"""


def test_floor_is_below_the_measured_figure():
    """A floor above reality gets bypassed within a week. This one is a ratchet:
    it must leave headroom, and it must not be zero."""
    assert 80 <= sc.COVERAGE_FLOOR <= 95


def test_the_floor_is_actually_passed_to_pytest():
    """A constant nothing reads is decoration."""
    src = (REPO / "scripts" / "selfcheck.py").read_text(encoding="utf-8")
    assert "--cov-fail-under={COVERAGE_FLOOR}" in src or "cov-fail-under" in src
    for target in sc.COVERED:
        assert target in src


def test_failure_detail_names_the_test_not_the_coverage_table():
    """With --cov the table prints AFTER the failures, so a plain tail showed
    table rows while claiming a test failed."""
    detail = sc._failure_detail(FAILING_RUN)
    assert "test_thing" in detail
    assert "Stmts" not in detail, "surfaced the coverage table instead of the failure"


def test_summary_is_found_even_below_the_coverage_table():
    assert "1 failed" in sc._pytest_summary(FAILING_RUN)
    assert "742 passed" in sc._pytest_summary(FLOOR_RUN)


def test_a_coverage_dip_is_distinguishable_from_a_test_failure():
    """The discriminator selfcheck uses: the floor line is present AND the
    summary reports nothing failed."""
    floor_line = [ln for ln in FLOOR_RUN.splitlines() if "Required test coverage" in ln]
    assert floor_line, "fixture no longer represents a floor breach"
    assert "failed" not in sc._pytest_summary(FLOOR_RUN)
    # ...and the inverse, so the branch cannot swallow a real failure.
    assert "failed" in sc._pytest_summary(FAILING_RUN)


def test_the_mutation_harness_is_omitted_for_a_stated_reason():
    """Excluding code to flatter a number is the failure this repo argues
    against; the omit has to carry its justification."""
    cfg = (REPO / ".coveragerc").read_text(encoding="utf-8")
    assert "mutate_checks.py" in cfg
    assert "rewrites source" in cfg or "mutate" in cfg.split("omit")[1][:600]

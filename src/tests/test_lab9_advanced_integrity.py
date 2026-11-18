"""M7 regressions for reports that look green after evidence is altered."""

import copy

import pytest

from lab9.gate import integrity_check

pytestmark = pytest.mark.student


@pytest.fixture
def evidence():
    rows = [{"item_id": item, "seed": seed, "pass_rate": True, "slices": ["money_movement"]}
            for item in ("E-001", "E-002") for seed in (11, 22)]
    report = {"manifest": {"eval_set_sha": "same", "items": 2, "seeds": [11, 22]},
              "rows": rows, "metrics": {"pass_rate": 1.0}, "evaluator_failures": []}
    spec = {"eval_set_version": "v2", "metrics": [
        {"id": "pass_rate", "blocking": True, "threshold": {"min": 0.8, "no_significant_drop": True}}],
        "slices": [{"name": "money_movement", "metric": "pass_rate", "min": 0.9,
                    "blocking": True, "no_significant_drop": True}]}
    return report, spec


@pytest.mark.parametrize("attack", ["duplicate", "evaluator_error", "slice_relabel", "fake_aggregate", "seed_selection"])
def test_integrity_rejects_green_looking_tampered_reports(evidence, attack):
    base, spec = evidence
    pr = copy.deepcopy(base)
    if attack == "duplicate":
        pr["rows"][-1] = copy.deepcopy(pr["rows"][0])  # Same row count, missing one pair.
    elif attack == "evaluator_error":
        pr["evaluator_failures"] = ["grader crashed despite all reported scores being green"]
    elif attack == "slice_relabel":
        for row in pr["rows"]:
            row["slices"] = []
    elif attack == "fake_aggregate":
        pr["rows"][0]["pass_rate"] = False  # The aggregate falsely stays 1.0.
    else:
        pr["manifest"]["seeds"] = [11]
        pr["rows"] = [r for r in pr["rows"] if r["seed"] == 11]
    assert integrity_check(pr, base, spec)


@pytest.mark.parametrize("value", [None, float("nan"), float("inf")])
def test_integrity_rejects_invalid_row_values(evidence, value):
    base, spec = evidence
    pr = copy.deepcopy(base)
    pr["rows"][0]["pass_rate"] = value
    assert integrity_check(pr, base, spec)


@pytest.mark.parametrize("change", ["blocking", "metric", "threshold", "ci", "slice", "slice_floor", "slice_ci"])
def test_ratchet_catches_removed_controls(evidence, change):
    report, base_spec = evidence
    spec = copy.deepcopy(base_spec)
    if change == "blocking":
        spec["metrics"][0]["blocking"] = False
    elif change == "metric":
        spec["metrics"] = []
    elif change == "threshold":
        spec["metrics"][0]["threshold"].pop("min")
    elif change == "ci":
        spec["metrics"][0]["threshold"].pop("no_significant_drop")
    elif change == "slice":
        spec["slices"] = []
    elif change == "slice_floor":
        spec["slices"][0]["min"] = 0.5
    else:
        spec["slices"][0]["no_significant_drop"] = False
    assert integrity_check(report, report, spec, base_spec)


def test_ratchet_allows_stricter_spec_and_same_report(evidence):
    report, base_spec = evidence
    spec = copy.deepcopy(base_spec)
    spec["metrics"][0]["threshold"]["min"] = 0.9
    assert integrity_check(report, report, spec, base_spec) == []

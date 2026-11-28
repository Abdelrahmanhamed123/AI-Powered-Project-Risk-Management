"""Unit tests - Dependency & Workload Service (FR9-FR12). Docstring = FR | description | input | expected."""
from unittest.mock import MagicMock
import pytest
from service import (DependencyService, DependencyValidator, ImpactCalculator, WorkloadService,
                     CapacityPolicy, CriticalPathAnalyzer, DependencyError, has_cycle, VALIDATED)

PID = "p1"

def dep_svc(existing=()):
    repo = MagicMock(); repo.find_by_project.return_value = list(existing)
    repo.save.side_effect = lambda d: d
    return DependencyService(repo, DependencyValidator()), repo

def d(a, b, t="FINISH_TO_START"): return {"pred": a, "succ": b, "type": t}

def test_DW01_create_dependency_success():
    """FR9.1 | Create dependency | T1 -> T2, FINISH_TO_START | Saved with status VALIDATED"""
    svc, repo = dep_svc()
    r = svc.create_dependency(PID, "T1", "T2")
    assert r["status"] == VALIDATED and r["pred"] == "T1" and r["succ"] == "T2"
    repo.save.assert_called_once()

def test_DW02_create_dependency_self_reference_rejected():
    """FR9.1 | Dependency of a task on itself | T1 -> T1 | DependencyError, not saved"""
    svc, repo = dep_svc()
    with pytest.raises(DependencyError):
        svc.create_dependency(PID, "T1", "T1")
    repo.save.assert_not_called()

def test_DW03_create_dependency_duplicate_rejected():
    """FR9.1 | Duplicate dependency | T1 -> T2 twice | DependencyError"""
    svc, repo = dep_svc([d("T1", "T2")])
    with pytest.raises(DependencyError):
        svc.create_dependency(PID, "T1", "T2")
    repo.save.assert_not_called()

def test_DW04_validate_dependency_rejects_cycle():
    """FR9.2 | Validate: new edge closes a cycle | existing T1->T2->T3, add T3->T1 | DependencyError, not saved"""
    svc, repo = dep_svc([d("T1", "T2"), d("T2", "T3")])
    with pytest.raises(DependencyError):
        svc.create_dependency(PID, "T3", "T1")
    repo.save.assert_not_called()

def test_DW05_validate_project_graph_valid_and_invalid():
    """FR9.2 | Validate whole project graph | acyclic and cyclic graphs | valid True / False"""
    ok, _ = dep_svc([d("A", "B"), d("B", "C")])
    bad, _ = dep_svc([d("A", "B"), d("B", "A")])
    assert ok.validate(PID) == {"valid": True, "dependency_count": 2}
    assert bad.validate(PID)["valid"] is False

def test_DW06_calculate_impact_ripple():
    """FR10.1 | Calculate dependency impact | T1 delayed 2.5 days; T1->T2->T3, T1->T4 | T2, T3, T4 delayed 2.5; T1 not included"""
    imp = ImpactCalculator().calculate([("T1", "T2"), ("T2", "T3"), ("T1", "T4"), ("X", "Y")], "T1", 2.5)
    assert imp == {"T2": 2.5, "T3": 2.5, "T4": 2.5}

def test_DW07_calculate_impact_no_successors():
    """FR10.1 | Impact of a last task | T3 has no successors | Empty result"""
    assert ImpactCalculator().calculate([("T1", "T2")], "T2", 3) == {}

def test_DW08_display_impact_sorted():
    """FR10.2 | Display dependency impact | impact of 3 tasks | List sorted by task with delay_days"""
    out = ImpactCalculator().display({"T3": 1, "T1": 2})
    assert out == [{"task": "T1", "delay_days": 2}, {"task": "T3", "delay_days": 1}]

def test_DW09_calculate_workload_utilization():
    """FR11.1 | Calculate team workload | Ali 30h+10h, Sara 20h, capacity 40h | Ali 100%, Sara 50%"""
    snap = WorkloadService(CapacityPolicy()).calculate([("Ali", 30), ("Ali", 10), ("Sara", 20)], 40)
    assert snap["Ali"]["utilization_percent"] == 100.0 and snap["Sara"]["utilization_percent"] == 50.0

def test_DW10_identify_bottleneck():
    """FR11.2 | Identify bottleneck | Ali 50h, Sara 20h, capacity 40h | Only Ali is a bottleneck"""
    svc = WorkloadService(CapacityPolicy())
    snap = svc.calculate([("Ali", 50), ("Sara", 20)], 40)
    assert svc.find_bottlenecks(snap, 40) == ["Ali"]

def test_DW11_exactly_at_capacity_not_bottleneck():
    """FR11.2 | User exactly at capacity | 40h of 40h | Not a bottleneck"""
    svc = WorkloadService(CapacityPolicy())
    assert svc.find_bottlenecks(svc.calculate([("Ali", 40)], 40), 40) == []

def test_DW12_capacity_policy_is_replaceable_mock():
    """FR11.2 | Custom capacity policy (mock) | policy always True | All users flagged"""
    policy = MagicMock(); policy.is_over_capacity.return_value = True
    svc = WorkloadService(policy)
    assert svc.find_bottlenecks({"A": {"assigned_hours": 1}, "B": {"assigned_hours": 2}}, 40) == ["A", "B"]

DUR = {"A": 3, "B": 2, "C": 4, "D": 1}
EDGES = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]

def test_DW13_calculate_critical_path():
    """FR12.1 | Calculate critical path | A3,B2,C4,D1; A->B,A->C,B->D,C->D | Duration 8; critical A, C, D"""
    r = CriticalPathAnalyzer().calculate(DUR, EDGES)
    assert r["project_duration"] == 8 and r["critical_tasks"] == ["A", "C", "D"]
    assert r["float"]["B"] == 2

def test_DW14_critical_path_cycle_rejected():
    """FR12.1 | Critical path on cyclic graph | A->B, B->A | DependencyError"""
    with pytest.raises(DependencyError):
        CriticalPathAnalyzer().calculate({"A": 1, "B": 1}, [("A", "B"), ("B", "A")])

def test_DW15_highlight_critical_tasks():
    """FR12.2 | Highlight critical tasks | result of TC DW13 | B not critical (float 2), A, C, D critical"""
    an = CriticalPathAnalyzer(); view = an.highlight(an.calculate(DUR, EDGES))
    flags = {v["task"]: v["critical"] for v in view}
    assert flags == {"A": True, "B": False, "C": True, "D": True}

def test_DW16_has_cycle_helper():
    """FR9.2 | Cycle detector | chain vs loop | False / True"""
    assert has_cycle([("A", "B"), ("B", "C")]) is False and has_cycle([("A", "B"), ("B", "A")]) is True

"""Unit tests - Risk Mitigation & Reporting Service (FR17-FR20). Docstring = FR | description | input | expected."""
from datetime import date
from unittest.mock import MagicMock
import pytest
from service import (Recommendation, RecommendationService, SimulationService, NotificationService,
                     AnomalyDetectionService, DashboardService, ReportService, NotFoundError,
                     PROPOSED, ACCEPTED, REJECTED, APPLIED)

def rec_svc(level, ctx):
    risk, tasks, repo = MagicMock(), MagicMock(), MagicMock()
    risk.get_task_prediction.return_value = {"risk_level": level, "delay_probability": 0.78}
    tasks.get_task_context.return_value = ctx; repo.save.side_effect = lambda r: r
    return RecommendationService(risk, tasks, repo), repo

def test_RR01_generate_recommendation_remove_blocker():
    """FR17.1 | Generate recommendation | HIGH risk, active blocker | REMOVE_BLOCKER, status PROPOSED, saved"""
    svc, repo = rec_svc("HIGH", {"has_active_blocker": True})
    r = svc.generate("t1")
    assert r.type == "REMOVE_BLOCKER" and r.status == PROPOSED and r.expected_risk_reduction == 0.18
    repo.save.assert_called_once()

@pytest.mark.parametrize("level,ctx,typ", [("HIGH", {"assignee_overloaded": True}, "REASSIGN_TASK"),
                                           ("MEDIUM", {}, "ADD_RESOURCES"), ("LOW", {"has_active_blocker": True}, "MONITOR")])
def test_RR02_generate_recommendation_other_types(level, ctx, typ):
    """FR17.1 | Generate other recommendation types | overloaded / no cause / LOW risk | REASSIGN_TASK / ADD_RESOURCES / MONITOR"""
    assert rec_svc(level, ctx)[0].generate("t1").type == typ

def test_RR03_record_decision_accept_then_apply():
    """FR17.2 | Record decision ACCEPT | PROPOSED recommendation | ACCEPTED, then APPLIED"""
    svc, repo = rec_svc("HIGH", {}); r = Recommendation("t1", "REMOVE_BLOCKER", 0.18); repo.find_by_id.return_value = r
    assert svc.record_decision(r.id, "ACCEPT").status == ACCEPTED
    r.apply(); assert r.status == APPLIED

def test_RR04_record_decision_reject():
    """FR17.2 | Record decision REJECT | PROPOSED recommendation | REJECTED"""
    svc, repo = rec_svc("HIGH", {}); r = Recommendation("t1", "X", 0.1); repo.find_by_id.return_value = r
    assert svc.record_decision(r.id, "REJECT").status == REJECTED

def test_RR05_record_decision_invalid_cases():
    """FR17.2 | Invalid decisions | unknown id; second decision; apply while PROPOSED; bad word | NotFoundError / ValueError"""
    svc, repo = rec_svc("HIGH", {}); repo.find_by_id.return_value = None
    with pytest.raises(NotFoundError): svc.record_decision("x", "ACCEPT")
    r = Recommendation("t1", "X", 0.1); repo.find_by_id.return_value = r
    with pytest.raises(ValueError): svc.record_decision(r.id, "MAYBE")
    svc.record_decision(r.id, "ACCEPT")
    with pytest.raises(ValueError): svc.record_decision(r.id, "REJECT")
    with pytest.raises(ValueError): Recommendation("t", "X", 0).apply()

def sim(baseline=0.6):
    risk, repo = MagicMock(), MagicMock()
    risk.get_task_prediction.return_value = {"risk_score": baseline}
    return SimulationService(risk, repo), repo

def test_RR06_define_scenario():
    """FR18.1 | Define what-if scenario | one change: effort 10h -> 5h | Scenario created"""
    svc, _ = sim()
    s = svc.define_scenario("p1", [{"task_id": "t1", "original": 10, "proposed": 5}])
    assert s["project_id"] == "p1" and len(s["changes"]) == 1

def test_RR07_define_scenario_invalid():
    """FR18.1 | Define invalid scenario | no changes; effort 0 | ValueError"""
    svc, _ = sim()
    with pytest.raises(ValueError): svc.define_scenario("p1", [])
    with pytest.raises(ValueError): svc.define_scenario("p1", [{"task_id": "t", "original": 0, "proposed": 5}])

def test_RR08_estimate_scenario_impact():
    """FR18.2 | Estimate scenario impact | baseline risk 0.6, effort 10h -> 5h | simulated 0.3, delta -0.3, result saved"""
    svc, repo = sim(0.6)
    r = svc.estimate_impact({"project_id": "p1", "changes": [{"task_id": "t1", "original": 10, "proposed": 5}]})
    assert r[0]["simulated_risk"] == 0.3 and r[0]["risk_delta"] == -0.3; repo.save.assert_called_once()

def test_RR09_estimate_impact_is_capped_at_1():
    """FR18.2 | Estimate impact above 1 | baseline 0.8, effort x3 | simulated risk capped at 1.0"""
    svc, _ = sim(0.8)
    r = svc.estimate_impact({"project_id": "p1", "changes": [{"task_id": "t1", "original": 5, "proposed": 15}]})
    assert r[0]["simulated_risk"] == 1.0

def detector(progress):
    tasks, anomalies, notifier = MagicMock(), MagicMock(), MagicMock()
    tasks.get_progress.return_value = progress
    return AnomalyDetectionService(tasks, anomalies, notifier), anomalies, notifier

def test_RR10_detect_anomaly_severity():
    """FR19.1 | Detect anomalies | 3 tasks behind by 10 / 30 / 50 points | 2 anomalies: MEDIUM (30) and HIGH (50), both saved"""
    svc, anomalies, _ = detector([{"task_id": "a", "expected_progress": 50, "progress": 40},
                                  {"task_id": "b", "expected_progress": 60, "progress": 30},
                                  {"task_id": "c", "expected_progress": 70, "progress": 20}])
    out = svc.detect("p1")
    assert [(o["task_id"], o["severity"]) for o in out] == [("b", "MEDIUM"), ("c", "HIGH")]
    assert anomalies.save.call_count == 2

def test_RR11_detect_no_anomaly():
    """FR19.1 | Detect when all tasks are on plan | progress equals expected | Empty list, nothing saved"""
    svc, anomalies, _ = detector([{"task_id": "a", "expected_progress": 50, "progress": 50}])
    assert svc.detect("p1") == [] and anomalies.save.call_count == 0

def test_RR12_send_alert_only_for_high():
    """FR19.2 | Send alert | one HIGH, one MEDIUM anomaly | Only 1 email sent through the notifier"""
    svc, _, notifier = detector([])
    svc.send_alerts([{"task_id": "c", "deviation": 50, "severity": "HIGH"}, {"task_id": "b", "deviation": 30, "severity": "MEDIUM"}], "pm@aiu.edu.eg")
    notifier.send.assert_called_once()

@pytest.mark.parametrize("ok,status", [(True, "SENT"), (False, "FAILED")])
def test_RR13_notification_delivery_status(ok, status):
    """FR19.2 | Send email via gateway | gateway returns success / failure | Notification SENT / FAILED saved"""
    email, repo = MagicMock(), MagicMock(); email.send.return_value = ok; repo.save.side_effect = lambda n: n
    n = NotificationService(email, repo).send("pm@aiu.edu.eg", "Alert", "Body")
    assert n["status"] == status; email.send.assert_called_once_with("pm@aiu.edu.eg", "Alert", "Body")

def test_RR14_notification_invalid_recipient():
    """FR19.2 | Send to invalid recipient | recipient = nobody | ValueError, gateway not called"""
    email = MagicMock()
    with pytest.raises(ValueError): NotificationService(email, MagicMock()).send("nobody", "s", "b")
    email.send.assert_not_called()

def dash(total=10, done=4):
    tasks, risk = MagicMock(), MagicMock()
    tasks.get_project_summary.return_value = {"total_tasks": total, "completed_tasks": done}
    risk.get_project_assessment.return_value = {"risk_status": "MEDIUM", "high_risk_task_count": 3}
    return DashboardService(tasks, risk)

def test_RR15_view_dashboard():
    """FR20.1 | View dashboard | 10 tasks, 4 done, risk MEDIUM, 3 high-risk | completion 40.0%, MEDIUM, 3"""
    assert dash().build("p1") == {"project_id": "p1", "completion_percent": 40.0, "overall_risk": "MEDIUM", "high_risk_tasks": 3}

def test_RR16_view_dashboard_empty_project():
    """FR20.1 | View dashboard of empty project | 0 tasks | completion 0 (no division by zero)"""
    assert dash(0, 0).build("p1")["completion_percent"] == 0

def test_RR17_generate_report():
    """FR20.2 | Generate report | project p1, 2026-11-01 to 2026-11-28 | Report READY with PROJECT_SUMMARY section, saved"""
    repo = MagicMock(); repo.save.side_effect = lambda r: r
    r = ReportService(dash(), repo).generate("p1", date(2026, 11, 1), date(2026, 11, 28))
    assert r["status"] == "READY" and r["sections"][0]["type"] == "PROJECT_SUMMARY"; repo.save.assert_called_once()

def test_RR18_generate_report_invalid_period():
    """FR20.2 | Generate report with end before start | 2026-11-28 to 2026-11-01 | ValueError, not saved"""
    repo = MagicMock()
    with pytest.raises(ValueError): ReportService(dash(), repo).generate("p1", date(2026, 11, 28), date(2026, 11, 1))
    repo.save.assert_not_called()

def test_RR19_export_report_formats():
    """FR20.2 | Export report | PDF and DOCX | PDF file name returned; DOCX rejected"""
    svc = ReportService(dash(), MagicMock())
    assert svc.export({"project_id": "p1"}, "PDF") == {"format": "PDF", "file_name": "report_p1.pdf"}
    with pytest.raises(ValueError): svc.export({"project_id": "p1"}, "DOCX")

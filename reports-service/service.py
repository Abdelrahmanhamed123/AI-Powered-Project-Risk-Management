"""Risk Mitigation & Reporting Service (FR17-FR20)."""
import uuid

PROPOSED, ACCEPTED, REJECTED, APPLIED = "PROPOSED", "ACCEPTED", "REJECTED", "APPLIED"
FORMATS = ("PDF", "CSV", "JSON")


class NotFoundError(Exception): pass


class Recommendation:
    def __init__(self, task_id, rec_type, reduction):
        self.id, self.task_id, self.type = uuid.uuid4(), task_id, rec_type
        self.expected_risk_reduction, self.status = reduction, PROPOSED

    def decide(self, decision):
        if self.status != PROPOSED:
            raise ValueError("Only PROPOSED recommendations can be decided")
        if decision not in ("ACCEPT", "REJECT"):
            raise ValueError("Decision must be ACCEPT or REJECT")
        self.status = ACCEPTED if decision == "ACCEPT" else REJECTED

    def apply(self):
        if self.status != ACCEPTED:
            raise ValueError("Only ACCEPTED recommendations can be applied")
        self.status = APPLIED


class RecommendationService:
    def __init__(self, risk, tasks, repo):
        self.risk, self.tasks, self.repo = risk, tasks, repo

    def generate(self, task_id):
        pred = self.risk.get_task_prediction(task_id)
        ctx = self.tasks.get_task_context(task_id)
        if pred["risk_level"] == "LOW":
            rec = Recommendation(task_id, "MONITOR", 0.0)
        elif ctx.get("has_active_blocker"):
            rec = Recommendation(task_id, "REMOVE_BLOCKER", 0.18)
        elif ctx.get("assignee_overloaded"):
            rec = Recommendation(task_id, "REASSIGN_TASK", 0.12)
        else:
            rec = Recommendation(task_id, "ADD_RESOURCES", 0.08)
        return self.repo.save(rec)

    def record_decision(self, rec_id, decision):
        rec = self.repo.find_by_id(rec_id)
        if rec is None: raise NotFoundError("Recommendation not found")
        rec.decide(decision)
        self.repo.save(rec)
        return rec


class SimulationService:
    def __init__(self, risk, repo):
        self.risk, self.repo = risk, repo

    def define_scenario(self, project_id, changes):
        if not changes:
            raise ValueError("A scenario needs at least one change")
        for c in changes:
            if c["original"] <= 0 or c["proposed"] <= 0:
                raise ValueError("Effort values must be positive")
        return {"project_id": project_id, "changes": changes}

    def estimate_impact(self, scenario):
        results = []
        for c in scenario["changes"]:
            baseline = self.risk.get_task_prediction(c["task_id"])["risk_score"]
            simulated = min(1.0, max(0.0, round(baseline * c["proposed"] / c["original"], 3)))
            results.append({"task_id": c["task_id"], "baseline_risk": baseline, "simulated_risk": simulated,
                            "risk_delta": round(simulated - baseline, 3)})
        self.repo.save(results)
        return results


class NotificationService:
    def __init__(self, email, repo):
        self.email, self.repo = email, repo

    def send(self, recipient, subject, body):
        if "@" not in (recipient or ""):
            raise ValueError("Invalid recipient")
        ok = self.email.send(recipient, subject, body)
        note = {"recipient": recipient, "subject": subject, "status": "SENT" if ok else "FAILED"}
        return self.repo.save(note)


class AnomalyDetectionService:
    def __init__(self, tasks, anomalies, notifier, threshold=20):
        self.tasks, self.anomalies, self.notifier, self.threshold = tasks, anomalies, notifier, threshold

    def detect(self, project_id):
        found = []
        for t in self.tasks.get_progress(project_id):
            deviation = t["expected_progress"] - t["progress"]
            if deviation > self.threshold:
                sev = "HIGH" if deviation >= 40 else "MEDIUM"
                found.append({"task_id": t["task_id"], "deviation": deviation, "severity": sev})
        for e in found: self.anomalies.save(e)
        return found

    def send_alerts(self, anomalies, recipient):
        sent = []
        for a in anomalies:
            if a["severity"] == "HIGH":
                sent.append(self.notifier.send(recipient, "High-risk task detected",
                                               f"Task {a['task_id']} is {a['deviation']}% behind plan"))
        return sent


class DashboardService:
    def __init__(self, tasks, risk):
        self.tasks, self.risk = tasks, risk

    def build(self, project_id):
        summary = self.tasks.get_project_summary(project_id)
        assess = self.risk.get_project_assessment(project_id)
        done = summary["completed_tasks"] / summary["total_tasks"] * 100 if summary["total_tasks"] else 0
        return {"project_id": project_id, "completion_percent": round(done, 1),
                "overall_risk": assess["risk_status"], "high_risk_tasks": assess["high_risk_task_count"]}


class ReportService:
    def __init__(self, dashboard, repo):
        self.dashboard, self.repo = dashboard, repo

    def generate(self, project_id, period_start, period_end):
        if period_end < period_start:
            raise ValueError("Report period end is before start")
        sections = [{"type": "PROJECT_SUMMARY", **self.dashboard.build(project_id)}]
        return self.repo.save({"project_id": project_id, "period": (period_start, period_end),
                               "status": "READY", "sections": sections})

    def export(self, report, fmt):
        if fmt not in FORMATS:
            raise ValueError("Unsupported format")
        return {"format": fmt, "file_name": f"report_{report['project_id']}.{fmt.lower()}"}

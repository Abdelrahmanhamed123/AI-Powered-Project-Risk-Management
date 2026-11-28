"""Dependency & Workload Service (FR9-FR12)."""
import uuid
from collections import defaultdict, deque

VALIDATED = "VALIDATED"


class DependencyError(Exception): pass


def has_cycle(edges):
    graph, indeg, nodes = defaultdict(list), defaultdict(int), set()
    for a, b in edges:
        graph[a].append(b); indeg[b] += 1; nodes.update((a, b))
    q = deque(n for n in nodes if indeg[n] == 0); seen = 0
    while q:
        n = q.popleft(); seen += 1
        for m in graph[n]:
            indeg[m] -= 1
            if indeg[m] == 0: q.append(m)
    return seen != len(nodes)


class DependencyValidator:
    def reject_self_reference(self, pred, succ):
        if pred == succ: raise DependencyError("A task cannot depend on itself")

    def reject_cycle(self, edges):
        if has_cycle(edges): raise DependencyError("Circular dependency detected")


class DependencyService:
    def __init__(self, repo, validator):
        self.repo, self.validator = repo, validator

    def create_dependency(self, project_id, pred, succ, dep_type="FINISH_TO_START"):
        self.validator.reject_self_reference(pred, succ)
        existing = self.repo.find_by_project(project_id)
        if any(d["pred"] == pred and d["succ"] == succ and d["type"] == dep_type for d in existing):
            raise DependencyError("Duplicate dependency")
        edges = [(d["pred"], d["succ"]) for d in existing] + [(pred, succ)]
        self.validator.reject_cycle(edges)
        dep = {"id": uuid.uuid4(), "project_id": project_id, "pred": pred, "succ": succ,
               "type": dep_type, "status": VALIDATED}
        return self.repo.save(dep)

    def validate(self, project_id):
        edges = [(d["pred"], d["succ"]) for d in self.repo.find_by_project(project_id)]
        return {"valid": not has_cycle(edges), "dependency_count": len(edges)}


class ImpactCalculator:
    def calculate(self, edges, delayed_task, delay_days):
        """All downstream tasks get the same delay (finish-to-start ripple)."""
        graph = defaultdict(list)
        for a, b in edges: graph[a].append(b)
        affected, stack = {}, list(graph[delayed_task])
        while stack:
            n = stack.pop()
            if n in affected: continue
            affected[n] = delay_days; stack.extend(graph[n])
        return affected

    def display(self, impact):
        return sorted(({"task": t, "delay_days": d} for t, d in impact.items()),
                      key=lambda x: str(x["task"]))


class CapacityPolicy:
    def is_over_capacity(self, hours, capacity):
        return capacity > 0 and hours > capacity


class WorkloadService:
    def __init__(self, policy):
        self.policy = policy

    def calculate(self, assignments, capacity_hours):
        """assignments: list of (user_id, hours)."""
        totals = defaultdict(float)
        for user, hours in assignments: totals[user] += hours
        return {u: {"assigned_hours": h, "utilization_percent": round(h / capacity_hours * 100, 1)}
                for u, h in totals.items()}

    def find_bottlenecks(self, snapshot, capacity_hours):
        return [u for u, v in snapshot.items()
                if self.policy.is_over_capacity(v["assigned_hours"], capacity_hours)]


class CriticalPathAnalyzer:
    def calculate(self, durations, edges):
        if has_cycle(edges): raise DependencyError("Circular dependency detected")
        preds, succs = defaultdict(list), defaultdict(list)
        for a, b in edges: preds[b].append(a); succs[a].append(b)
        order, indeg = [], {t: len(preds[t]) for t in durations}
        q = deque(t for t, n in indeg.items() if n == 0)
        while q:
            n = q.popleft(); order.append(n)
            for m in succs[n]:
                indeg[m] -= 1
                if indeg[m] == 0: q.append(m)
        es, ef = {}, {}
        for t in order:
            es[t] = max((ef[p] for p in preds[t]), default=0); ef[t] = es[t] + durations[t]
        total = max(ef.values(), default=0)
        lf, ls = {}, {}
        for t in reversed(order):
            lf[t] = min((ls[s] for s in succs[t]), default=total); ls[t] = lf[t] - durations[t]
        floats = {t: ls[t] - es[t] for t in order}
        return {"project_duration": total, "float": floats,
                "critical_tasks": [t for t in order if floats[t] == 0]}

    def highlight(self, result):
        return [{"task": t, "critical": t in result["critical_tasks"], "float_days": f}
                for t, f in result["float"].items()]

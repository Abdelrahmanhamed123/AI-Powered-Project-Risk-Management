"""Unit tests for Project & Task Service (FR5-FR8). Mocks play the role of Mockito.
Every test name contains its test case ID (TCxx)."""
import uuid
from datetime import date, datetime
from unittest.mock import MagicMock

import pytest

from service import (Project, Milestone, Task, ProjectService, MilestoneService,
                     TaskService, ProgressService, NotFoundError,
                     TODO, IN_PROGRESS, COMPLETED, ARCHIVED, PENDING)

D1, D2 = date(2026, 11, 1), date(2026, 12, 31)
NOW = datetime(2026, 11, 25, 12, 0)
PID, TID, UID = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def make_task(**kw):
    return Task(kw.get("project_id", PID), kw.get("title", "Implement Risk API"),
                due_at=kw.get("due_at"), task_id=TID)


# ---------- FR5.1 Create project ----------
def test_PT01_create_project_success():
    """FR5.1 | Create project with valid data | name = Risk App, 2026-11-01 to 2026-12-31 | Project saved, status ACTIVE"""
    repo = MagicMock(); repo.save.side_effect = lambda p: p
    p = ProjectService(repo).create_project("Risk App", D1, D2)
    assert p.name == "Risk App" and p.status == "ACTIVE"
    repo.save.assert_called_once()

def test_PT02_create_project_empty_name_rejected():
    """FR5.1 | Create project with empty name | name = blank | ValueError, save not called"""
    repo = MagicMock()
    with pytest.raises(ValueError):
        ProjectService(repo).create_project("  ", D1, D2)
    repo.save.assert_not_called()

def test_PT03_create_project_target_before_start_rejected():
    """FR5.1 | Target date before start date | start 2026-12-31, target 2026-11-01 | ValueError, save not called"""
    repo = MagicMock()
    with pytest.raises(ValueError):
        ProjectService(repo).create_project("Risk App", D2, D1)
    repo.save.assert_not_called()

# ---------- FR5.2 Update project ----------
def test_PT04_update_project_name_and_date():
    """FR5.2 | Update name and target date | name = New, target = 2027-01-15 | Project updated and saved"""
    proj = Project("Old", D1, D2)
    repo = MagicMock(); repo.find_by_id.return_value = proj; repo.save.side_effect = lambda p: p
    out = ProjectService(repo).update_project(proj.id, name="New", target_date=date(2027, 1, 15))
    assert out.name == "New" and out.target_date == date(2027, 1, 15)

def test_PT05_update_project_not_found():
    """FR5.2 | Update project that does not exist | unknown project id | NotFoundError, save not called"""
    repo = MagicMock(); repo.find_by_id.return_value = None
    with pytest.raises(NotFoundError):
        ProjectService(repo).update_project(PID, name="X")
    repo.save.assert_not_called()

def test_PT06_update_project_invalid_target_date_rejected():
    """FR5.2 | Update with target date before start | target = 2026-10-01 | ValueError"""
    proj = Project("P", D1, D2)
    repo = MagicMock(); repo.find_by_id.return_value = proj
    with pytest.raises(ValueError):
        ProjectService(repo).update_project(proj.id, target_date=date(2026, 10, 1))

def test_PT07_update_project_empty_name_rejected():
    """FR5.2 | Update with empty name | name = " " | ValueError"""
    proj = Project("P", D1, D2)
    repo = MagicMock(); repo.find_by_id.return_value = proj
    with pytest.raises(ValueError):
        ProjectService(repo).update_project(proj.id, name=" ")

def test_PT08_archive_project_sets_status():
    """FR5.2 | Archive project | archive() | Status ARCHIVED"""
    p = Project("P", D1, D2); p.archive()
    assert p.status == ARCHIVED

# ---------- FR6.1 Create milestone ----------
def test_PT09_create_milestone_success():
    """FR6.1 | Create milestone in existing project | name = Beta, due 2026-12-01 | Milestone saved, status PENDING"""
    projects, ms = MagicMock(), MagicMock()
    projects.find_by_id.return_value = Project("P", D1, D2)
    ms.save.side_effect = lambda m: m
    m = MilestoneService(projects, ms).create_milestone(PID, "Beta", date(2026, 12, 1))
    assert m.name == "Beta" and m.status == PENDING

def test_PT10_create_milestone_project_not_found():
    """FR6.1 | Create milestone, project missing | unknown project id | NotFoundError, save not called"""
    projects, ms = MagicMock(), MagicMock()
    projects.find_by_id.return_value = None
    with pytest.raises(NotFoundError):
        MilestoneService(projects, ms).create_milestone(PID, "Beta", D2)
    ms.save.assert_not_called()

def test_PT11_create_milestone_empty_name_rejected():
    """FR6.1 | Create milestone with empty name | name = "" | ValueError"""
    projects, ms = MagicMock(), MagicMock()
    projects.find_by_id.return_value = Project("P", D1, D2)
    with pytest.raises(ValueError):
        MilestoneService(projects, ms).create_milestone(PID, "", D2)

# ---------- FR6.2 Track milestone ----------
def test_PT12_track_milestones_counts():
    """FR6.2 | Track milestones (1 done, 1 late, 1 future) | today = 2026-11-28 | total 3, completed 1, overdue 1"""
    done = Milestone(PID, "A", date(2026, 11, 10)); done.complete()
    late = Milestone(PID, "B", date(2026, 11, 20))
    future = Milestone(PID, "C", date(2026, 12, 20))
    ms = MagicMock(); ms.find_by_project.return_value = [done, late, future]
    r = MilestoneService(MagicMock(), ms).track_milestones(PID, date(2026, 11, 28))
    assert r == {"total": 3, "completed": 1, "overdue": 1}

# ---------- FR7.1 Create task ----------
def test_PT13_create_task_success_publishes_event():
    """FR7.1 | Create task | title = Write tests, priority HIGH | Status TODO, progress 0, TaskCreated published"""
    repo, ev = MagicMock(), MagicMock(); repo.save.side_effect = lambda t: t
    t = TaskService(repo, ev).create_task(PID, "Write tests", "HIGH")
    assert t.status == TODO and t.progress_percent == 0 and t.priority == "HIGH"
    ev.publish.assert_called_once_with("TaskCreated")

def test_PT14_create_task_empty_title_rejected():
    """FR7.1 | Create task with empty title | title = "" | ValueError, no save, no event"""
    repo, ev = MagicMock(), MagicMock()
    with pytest.raises(ValueError):
        TaskService(repo, ev).create_task(PID, "")
    repo.save.assert_not_called(); ev.publish.assert_not_called()

# ---------- FR7.2 Assign task ----------
def test_PT15_assign_task_moves_to_in_progress():
    """FR7.2 | Assign task to a user | taskId, userId | Assignee added, IN_PROGRESS, TaskAssigned published"""
    task = make_task(); repo, ev = MagicMock(), MagicMock(); repo.find_by_id.return_value = task
    TaskService(repo, ev).assign_task(TID, UID)
    assert task.assignees == [UID] and task.status == IN_PROGRESS
    ev.publish.assert_called_once_with("TaskAssigned")

def test_PT16_assign_task_not_found():
    """FR7.2 | Assign task that does not exist | unknown task id | NotFoundError, no event"""
    repo, ev = MagicMock(), MagicMock(); repo.find_by_id.return_value = None
    with pytest.raises(NotFoundError):
        TaskService(repo, ev).assign_task(TID, UID)
    ev.publish.assert_not_called()

def test_PT17_assign_same_user_twice_no_duplicate():
    """FR7.2 | Assign same user twice | userId x2 | Only one assignee stored"""
    task = make_task(); task.assign(UID); task.assign(UID)
    assert task.assignees == [UID]

def test_PT18_assign_completed_task_rejected():
    """FR7.2 | Assign a completed task | task at 100% | ValueError"""
    task = make_task(); task.update_progress(100)
    with pytest.raises(ValueError):
        task.assign(UID)

# ---------- FR8.1 Update progress ----------
def test_PT19_record_progress_65_percent():
    """FR8.1 | Record 65% progress | percent = 65 | Progress 65, IN_PROGRESS, update returned, event published"""
    task = make_task(); repo, ev = MagicMock(), MagicMock(); repo.find_by_id.return_value = task
    upd = ProgressService(repo, ev).record_progress(TID, 65, NOW)
    assert task.progress_percent == 65 and task.status == IN_PROGRESS
    assert upd.progress_percent == 65 and upd.recorded_at == NOW
    ev.publish.assert_called_once_with("TaskProgressChanged")

def test_PT20_record_progress_100_completes_task():
    """FR8.1 | Record 100% progress | percent = 100 | Status COMPLETED"""
    task = make_task(); repo, ev = MagicMock(), MagicMock(); repo.find_by_id.return_value = task
    ProgressService(repo, ev).record_progress(TID, 100, NOW)
    assert task.status == COMPLETED

@pytest.mark.parametrize("bad", [-1, 101])
def test_PT21_record_progress_out_of_range_rejected(bad):
    """FR8.1 | Progress out of range | percent = -1 and 101 | ValueError, no event"""
    task = make_task(); repo, ev = MagicMock(), MagicMock(); repo.find_by_id.return_value = task
    with pytest.raises(ValueError):
        ProgressService(repo, ev).record_progress(TID, bad, NOW)
    ev.publish.assert_not_called()

def test_PT22_progress_after_completed_rejected():
    """FR8.1 | Progress after COMPLETED | percent = 50 on completed task | ValueError"""
    task = make_task(); task.update_progress(100)
    with pytest.raises(ValueError):
        task.update_progress(50)

def test_PT23_record_progress_task_not_found():
    """FR8.1 | Record progress, task missing | unknown task id | NotFoundError"""
    repo, ev = MagicMock(), MagicMock(); repo.find_by_id.return_value = None
    with pytest.raises(NotFoundError):
        ProgressService(repo, ev).record_progress(TID, 10, NOW)

# ---------- FR8.2 Track deadline ----------
def test_PT24_find_overdue_tasks_returns_only_late_unfinished():
    """FR8.2 | Find overdue tasks | late, done, future, no-due tasks; now = 2026-11-25 | Only the late unfinished task is returned"""
    late = make_task(due_at=datetime(2026, 11, 20))
    done = Task(PID, "Done", due_at=datetime(2026, 11, 20)); done.update_progress(100)
    future = Task(PID, "Future", due_at=datetime(2026, 12, 20))
    nodue = Task(PID, "No due")
    repo = MagicMock(); repo.find_by_project.return_value = [late, done, future, nodue]
    out = ProgressService(repo, MagicMock()).find_overdue_tasks(PID, NOW)
    assert out == [late]

def test_PT25_is_overdue_false_when_before_due():
    """FR8.2 | Task before its due date | due 2026-12-01, now 2026-11-25 | is_overdue = False"""
    assert make_task(due_at=datetime(2026, 12, 1)).is_overdue(NOW) is False

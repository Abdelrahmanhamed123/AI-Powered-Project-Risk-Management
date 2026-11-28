"""Project & Task Service (FR5-FR8) - domain entities and use-case services.
Follows the Level 3 class diagram: services depend on repository / event interfaces."""
import uuid
from datetime import date, datetime

TODO, IN_PROGRESS, COMPLETED = "TODO", "IN_PROGRESS", "COMPLETED"
ACTIVE, ARCHIVED = "ACTIVE", "ARCHIVED"
PENDING = "PENDING"


class NotFoundError(Exception):
    pass


class Project:
    def __init__(self, name, start_date, target_date, project_id=None):
        if not name or not name.strip():
            raise ValueError("Project name is required")
        if target_date < start_date:
            raise ValueError("Target date cannot be before start date")
        self.id = project_id or uuid.uuid4()
        self.name = name.strip()
        self.start_date = start_date
        self.target_date = target_date
        self.status = ACTIVE

    def archive(self):
        self.status = ARCHIVED


class Milestone:
    def __init__(self, project_id, name, due_date, milestone_id=None):
        if not name or not name.strip():
            raise ValueError("Milestone name is required")
        self.id = milestone_id or uuid.uuid4()
        self.project_id = project_id
        self.name = name.strip()
        self.due_date = due_date
        self.status = PENDING

    def complete(self):
        self.status = COMPLETED


class Task:
    def __init__(self, project_id, title, priority="MEDIUM", due_at=None, task_id=None):
        if not title or not title.strip():
            raise ValueError("Task title is required")
        self.id = task_id or uuid.uuid4()
        self.project_id = project_id
        self.title = title.strip()
        self.priority = priority
        self.status = TODO
        self.progress_percent = 0
        self.due_at = due_at
        self.assignees = []

    def assign(self, user_id):
        if self.status == COMPLETED:
            raise ValueError("Cannot assign a completed task")
        if user_id not in self.assignees:
            self.assignees.append(user_id)
        if self.status == TODO:
            self.status = IN_PROGRESS

    def update_progress(self, percent):
        if self.status == COMPLETED:
            raise ValueError("Cannot update progress after COMPLETED")
        if percent < 0 or percent > 100:
            raise ValueError("Progress must be between 0 and 100")
        self.progress_percent = percent
        if percent == 100:
            self.status = COMPLETED
        elif percent > 0:
            self.status = IN_PROGRESS

    def is_overdue(self, now):
        return self.due_at is not None and self.status != COMPLETED and now > self.due_at


class ProgressUpdate:
    def __init__(self, task_id, progress_percent, recorded_at):
        self.task_id = task_id
        self.progress_percent = progress_percent
        self.recorded_at = recorded_at


class ProjectService:
    def __init__(self, projects):
        self.projects = projects

    def create_project(self, name, start_date, target_date):
        project = Project(name, start_date, target_date)
        return self.projects.save(project)

    def update_project(self, project_id, name=None, target_date=None):
        project = self.projects.find_by_id(project_id)
        if project is None:
            raise NotFoundError("Project not found")
        if name is not None:
            if not name.strip():
                raise ValueError("Project name is required")
            project.name = name.strip()
        if target_date is not None:
            if target_date < project.start_date:
                raise ValueError("Target date cannot be before start date")
            project.target_date = target_date
        return self.projects.save(project)


class MilestoneService:
    def __init__(self, projects, milestones):
        self.projects = projects
        self.milestones = milestones

    def create_milestone(self, project_id, name, due_date):
        if self.projects.find_by_id(project_id) is None:
            raise NotFoundError("Project not found")
        return self.milestones.save(Milestone(project_id, name, due_date))

    def track_milestones(self, project_id, today):
        items = self.milestones.find_by_project(project_id)
        done = [m for m in items if m.status == COMPLETED]
        overdue = [m for m in items if m.status != COMPLETED and m.due_date < today]
        return {"total": len(items), "completed": len(done), "overdue": len(overdue)}


class TaskService:
    def __init__(self, tasks, events):
        self.tasks = tasks
        self.events = events

    def create_task(self, project_id, title, priority="MEDIUM", due_at=None):
        task = Task(project_id, title, priority, due_at)
        saved = self.tasks.save(task)
        self.events.publish("TaskCreated")
        return saved

    def assign_task(self, task_id, user_id):
        task = self.tasks.find_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        task.assign(user_id)
        self.tasks.save(task)
        self.events.publish("TaskAssigned")


class ProgressService:
    def __init__(self, tasks, events):
        self.tasks = tasks
        self.events = events

    def record_progress(self, task_id, percent, now):
        task = self.tasks.find_by_id(task_id)
        if task is None:
            raise NotFoundError("Task not found")
        task.update_progress(percent)
        self.tasks.save(task)
        self.events.publish("TaskProgressChanged")
        return ProgressUpdate(task.id, percent, now)

    def find_overdue_tasks(self, project_id, now):
        return [t for t in self.tasks.find_by_project(project_id) if t.is_overdue(now)]

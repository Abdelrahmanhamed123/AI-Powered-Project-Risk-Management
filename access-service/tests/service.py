"""User & Access Service (FR1-FR4)."""
import re, uuid

ACTIVE, INACTIVE, SUSPENDED = "ACTIVE", "INACTIVE", "SUSPENDED"
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class NotFoundError(Exception): pass
class DuplicateEmailError(Exception): pass


class User:
    def __init__(self, full_name, email, password_hash, user_id=None):
        self.id = user_id or uuid.uuid4()
        self.full_name = full_name
        self.email = email.strip().lower()
        self.password_hash = password_hash
        self.status = ACTIVE

    def deactivate(self): self.status = INACTIVE
    def activate(self): self.status = ACTIVE


class AuthService:
    def __init__(self, users, sessions, hasher, audit):
        self.users, self.sessions, self.hasher, self.audit = users, sessions, hasher, audit

    def register(self, full_name, email, password):
        if not full_name or not full_name.strip():
            raise ValueError("Full name is required")
        if not EMAIL_RE.match(email or ""):
            raise ValueError("Invalid email")
        if len(password or "") < 8:
            raise ValueError("Password must be at least 8 characters")
        if self.users.find_by_email(email.strip().lower()) is not None:
            raise DuplicateEmailError("Email already registered")
        user = User(full_name.strip(), email, self.hasher.hash(password))
        saved = self.users.save(user)
        self.audit.record("USER_REGISTERED", "USER", user.id, {})
        return saved

    def login(self, email, password):
        user = self.users.find_by_email((email or "").strip().lower())
        if user is None or user.status != ACTIVE:
            return {"authenticated": False, "reason": "USER_INACTIVE_OR_NOT_FOUND"}
        if not self.hasher.matches(password, user.password_hash):
            return {"authenticated": False, "reason": "INVALID_CREDENTIALS"}
        session = self.sessions.create(user.id)
        self.audit.record("USER_LOGIN", "USER", user.id, {})
        return {"authenticated": True, "session_id": session.id}


class AccountService:
    def __init__(self, users, audit):
        self.users, self.audit = users, audit

    def update_account(self, user_id, full_name=None, email=None):
        user = self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        if full_name is not None:
            if not full_name.strip():
                raise ValueError("Full name is required")
            user.full_name = full_name.strip()
        if email is not None:
            if not EMAIL_RE.match(email):
                raise ValueError("Invalid email")
            user.email = email.strip().lower()
        self.audit.record("ACCOUNT_UPDATED", "USER", user_id, {})
        return self.users.save(user)

    def get_user_summary(self, user_id):
        user = self.users.find_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found")
        return {"user_id": user.id, "full_name": user.full_name, "email": user.email, "status": user.status}


class RbacService:
    def __init__(self, roles, users):
        self.roles, self.users = roles, users

    def assign_role(self, user_id, role_id):
        if self.users.find_by_id(user_id) is None:
            raise NotFoundError("User not found")
        if role_id in [r for r in self.roles.get_roles(user_id)]:
            return False
        self.roles.assign(user_id, role_id)
        return True

    def authorize(self, user_id, permission):
        role_ids = self.roles.get_roles(user_id)
        if not role_ids:
            return False
        return permission in self.roles.get_permissions(role_ids)


class AuditService:
    def __init__(self, logs):
        self.logs = logs

    def record(self, action, resource_type, resource_id, metadata):
        if not action:
            raise ValueError("Action is required")
        return self.logs.append({"action": action, "resource_type": resource_type,
                                 "resource_id": resource_id, "metadata": metadata})

    def search(self, action=None, actor_id=None):
        logs = self.logs.find({})
        if action:
            logs = [l for l in logs if l["action"] == action]
        if actor_id:
            logs = [l for l in logs if l.get("actor_id") == actor_id]
        return logs

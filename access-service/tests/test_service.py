from datetime import datetime, timezone
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
import pytest

from main import app


client = TestClient(app)


def test_read_root_returns_running_status():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"service": "running successfully"}


# --- Domain & Mocked Collaborators Unit Tests (matching Part A design) ---

class AccountStatus:
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    SUSPENDED = "SUSPENDED"


class SessionStatus:
    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class UserEntity:
    def __init__(self, user_id: str, email: str, password_hash: str, status: str = AccountStatus.ACTIVE):
        self.id = user_id
        self.email = email
        self.password_hash = password_hash
        self.status = status

    def suspend(self):
        self.status = AccountStatus.SUSPENDED

    def activate(self):
        self.status = AccountStatus.ACTIVE


class SessionEntity:
    def __init__(self, session_id: str, user_id: str, status: str = SessionStatus.ACTIVE):
        self.id = session_id
        self.user_id = user_id
        self.status = status
        self.revoked_at = None

    def revoke(self, now: datetime):
        if self.status != SessionStatus.ACTIVE:
            raise ValueError("Only ACTIVE session can be revoked")
        self.status = SessionStatus.REVOKED
        self.revoked_at = now


class AuthUseCase:
    def __init__(self, user_repo, session_repo, hasher, audit_service):
        self.user_repo = user_repo
        self.session_repo = session_repo
        self.hasher = hasher
        self.audit_service = audit_service

    def login(self, email: str, password: str) -> dict:
        user = self.user_repo.find_by_email(email)
        if not user or user.status != AccountStatus.ACTIVE:
            return {"authenticated": False, "reason": "USER_INACTIVE_OR_NOT_FOUND"}

        if not self.hasher.matches(password, user.password_hash):
            return {"authenticated": False, "reason": "INVALID_CREDENTIALS"}

        session = self.session_repo.create(user.id)
        self.audit_service.record("USER_LOGIN", "USER", user.id, {"email": user.email})
        return {"authenticated": True, "user_id": user.id, "session_id": session.id}


@pytest.fixture
def fixtures():
    user_id = "5d6f0d5d-0a88-4c24-a43b-3d8d5c4e9f10"
    session_id = "9c1b4e2a-7712-4d3b-9a81-112233445566"
    active_user = UserEntity(
        user_id=user_id,
        email="abdelrahman.hamed.2024@aiu.edu.eg",
        password_hash="$2b$12$R9h/cIPz0gi.URNNX3kh2OPST9/PgBkqquzi.Ss7KIUgO2t0jWMUW",
        status=AccountStatus.ACTIVE,
    )
    session = SessionEntity(session_id=session_id, user_id=user_id, status=SessionStatus.ACTIVE)
    return active_user, session


def test_login_success_verifies_collaboration_mocks(fixtures):
    active_user, session = fixtures
    user_repo = MagicMock()
    session_repo = MagicMock()
    hasher = MagicMock()
    audit_service = MagicMock()

    user_repo.find_by_email.return_value = active_user
    hasher.matches.return_value = True
    session_repo.create.return_value = session

    use_case = AuthUseCase(user_repo, session_repo, hasher, audit_service)
    result = use_case.login("abdelrahman.hamed.2024@aiu.edu.eg", "Secret@123")

    assert result["authenticated"] is True
    assert result["session_id"] == session.id
    user_repo.find_by_email.assert_called_once_with("mariam.ali@aiu.edu.eg")
    hasher.matches.assert_called_once_with("Secret@123", active_user.password_hash)
    session_repo.create.assert_called_once_with(active_user.id)
    audit_service.record.assert_called_once()


def test_login_rejected_when_user_suspended(fixtures):
    active_user, _ = fixtures
    active_user.suspend()

    user_repo = MagicMock()
    session_repo = MagicMock()
    hasher = MagicMock()
    audit_service = MagicMock()
    user_repo.find_by_email.return_value = active_user

    use_case = AuthUseCase(user_repo, session_repo, hasher, audit_service)
    result = use_case.login("mariam.ali@aiu.edu.eg", "Secret@123")

    assert result["authenticated"] is False
    assert result["reason"] == "USER_INACTIVE_OR_NOT_FOUND"
    session_repo.create.assert_not_called()
    audit_service.record.assert_not_called()


def test_session_revoke_and_reject_invalid_double_revoke(fixtures):
    _, session = fixtures
    now = datetime(2026, 11, 25, 15, 0, tzinfo=timezone.utc)

    session.revoke(now)
    assert session.status == SessionStatus.REVOKED
    assert session.revoked_at == now

    with pytest.raises(ValueError):
        session.revoke(now)

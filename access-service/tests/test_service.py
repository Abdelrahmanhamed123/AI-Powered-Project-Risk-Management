"""Unit tests - User & Access Service (FR1-FR4). Docstring = FR | description | input | expected."""
import uuid
from unittest.mock import MagicMock
import pytest
from service import (User, AuthService, AccountService, RbacService, AuditService,
                     NotFoundError, DuplicateEmailError, ACTIVE, INACTIVE, SUSPENDED)

UID, RID = uuid.uuid4(), uuid.uuid4()

def auth(user=None):
    users, sessions, hasher, audit = MagicMock(), MagicMock(), MagicMock(), MagicMock()
    users.find_by_email.return_value = user
    users.save.side_effect = lambda u: u
    hasher.hash.return_value = "HASH"
    sessions.create.return_value = MagicMock(id="S1")
    return AuthService(users, sessions, hasher, audit), users, sessions, hasher, audit

def make_user(status=ACTIVE):
    u = User("Ali", "Ali@AIU.edu.eg", "HASH", UID); u.status = status; return u

def test_AC01_register_success():
    """FR1.1 | Register with valid data | Ali, ali@aiu.edu.eg, Secret@123 | User saved, password hashed, audit recorded"""
    svc, users, _, hasher, audit = auth(None)
    u = svc.register("Ali", "Ali@AIU.edu.eg", "Secret@123")
    assert u.email == "ali@aiu.edu.eg" and u.password_hash == "HASH" and u.status == ACTIVE
    hasher.hash.assert_called_once_with("Secret@123"); audit.record.assert_called_once()

def test_AC02_register_duplicate_email():
    """FR1.1 | Register an existing email | email already in DB | DuplicateEmailError, not saved"""
    svc, users, *_ = auth(make_user())
    with pytest.raises(DuplicateEmailError):
        svc.register("Ali", "ali@aiu.edu.eg", "Secret@123")
    users.save.assert_not_called()

def test_AC03_register_invalid_email():
    """FR1.1 | Register with invalid email | email = not-an-email | ValueError"""
    svc, users, *_ = auth(None)
    with pytest.raises(ValueError):
        svc.register("Ali", "not-an-email", "Secret@123")
    users.save.assert_not_called()

def test_AC04_register_short_password():
    """FR1.1 | Register with short password | password = 123 | ValueError"""
    svc, users, *_ = auth(None)
    with pytest.raises(ValueError):
        svc.register("Ali", "a@b.com", "123")

def test_AC05_login_success():
    """FR1.2 | Login with correct credentials | active user, right password | authenticated, session created, audit recorded"""
    svc, _, sessions, hasher, audit = auth(make_user()); hasher.matches.return_value = True
    r = svc.login("ali@aiu.edu.eg", "Secret@123")
    assert r == {"authenticated": True, "session_id": "S1"}
    sessions.create.assert_called_once_with(UID); audit.record.assert_called_once()

def test_AC06_login_wrong_password():
    """FR1.2 | Login with wrong password | active user, wrong password | INVALID_CREDENTIALS, no session"""
    svc, _, sessions, hasher, _ = auth(make_user()); hasher.matches.return_value = False
    r = svc.login("ali@aiu.edu.eg", "bad")
    assert r == {"authenticated": False, "reason": "INVALID_CREDENTIALS"}
    sessions.create.assert_not_called()

@pytest.mark.parametrize("status", [INACTIVE, SUSPENDED])
def test_AC07_login_inactive_or_suspended_rejected(status):
    """FR1.2 | Login with INACTIVE / SUSPENDED user | valid password | USER_INACTIVE_OR_NOT_FOUND, hasher not called"""
    svc, _, sessions, hasher, _ = auth(make_user(status))
    r = svc.login("ali@aiu.edu.eg", "Secret@123")
    assert r["reason"] == "USER_INACTIVE_OR_NOT_FOUND"
    hasher.matches.assert_not_called(); sessions.create.assert_not_called()

def test_AC08_login_unknown_user():
    """FR1.2 | Login with unknown email | email not in DB | USER_INACTIVE_OR_NOT_FOUND"""
    svc, *_ = auth(None)
    assert svc.login("x@y.com", "pw")["authenticated"] is False

def acc(user):
    users, audit = MagicMock(), MagicMock()
    users.find_by_id.return_value = user; users.save.side_effect = lambda u: u
    return AccountService(users, audit), users, audit

def test_AC09_update_account_name_and_email():
    """FR2.1 | Update name and email | Ali Hamed, NEW@AIU.edu.eg | Updated, email lowercase, audit recorded"""
    svc, users, audit = acc(make_user())
    u = svc.update_account(UID, full_name="Ali Hamed", email="NEW@AIU.edu.eg")
    assert u.full_name == "Ali Hamed" and u.email == "new@aiu.edu.eg"; audit.record.assert_called_once()

def test_AC10_update_account_invalid_email():
    """FR2.1 | Update with invalid email | email = bad | ValueError, not saved"""
    svc, users, _ = acc(make_user())
    with pytest.raises(ValueError):
        svc.update_account(UID, email="bad")
    users.save.assert_not_called()

def test_AC11_update_account_user_not_found():
    """FR2.1 | Update unknown user | unknown id | NotFoundError"""
    svc, *_ = acc(None)
    with pytest.raises(NotFoundError):
        svc.update_account(UID, full_name="X")

def test_AC12_view_user_summary():
    """FR2.2 | View user information | user id | Summary with name, email, status and no password hash"""
    svc, *_ = acc(make_user())
    s = svc.get_user_summary(UID)
    assert s["email"] == "ali@aiu.edu.eg" and s["status"] == ACTIVE and "password_hash" not in s

def test_AC13_view_user_not_found():
    """FR2.2 | View unknown user | unknown id | NotFoundError"""
    svc, *_ = acc(None)
    with pytest.raises(NotFoundError):
        svc.get_user_summary(UID)

def rbac(user=object(), roles=()):
    r, users = MagicMock(), MagicMock()
    users.find_by_id.return_value = user; r.get_roles.return_value = list(roles)
    return RbacService(r, users), r

def test_AC14_assign_role_success():
    """FR3.1 | Assign role to user | userId, roleId | Role assigned (True)"""
    svc, r = rbac()
    assert svc.assign_role(UID, RID) is True; r.assign.assert_called_once_with(UID, RID)

def test_AC15_assign_role_twice_not_duplicated():
    """FR3.1 | Assign a role the user already has | same roleId | Returns False, assign not called"""
    svc, r = rbac(roles=[RID])
    assert svc.assign_role(UID, RID) is False; r.assign.assert_not_called()

def test_AC16_assign_role_user_not_found():
    """FR3.1 | Assign role to unknown user | unknown id | NotFoundError"""
    svc, r = rbac(user=None)
    with pytest.raises(NotFoundError):
        svc.assign_role(UID, RID)

def test_AC17_authorize_allowed():
    """FR3.2 | Enforce permission - user has it | project:create | True"""
    svc, r = rbac(roles=[RID]); r.get_permissions.return_value = {"project:create", "task:update"}
    assert svc.authorize(UID, "project:create") is True

def test_AC18_authorize_denied_and_no_roles():
    """FR3.2 | Enforce permission - missing permission / no role | report:generate | False"""
    svc, r = rbac(roles=[RID]); r.get_permissions.return_value = {"task:update"}
    assert svc.authorize(UID, "report:generate") is False
    svc2, _ = rbac(roles=[])
    assert svc2.authorize(UID, "task:update") is False

def test_AC19_record_activity():
    """FR4.1 | Record activity | USER_LOGIN, USER, userId | Log appended"""
    logs = MagicMock(); AuditService(logs).record("USER_LOGIN", "USER", UID, {"ip": "1.1.1.1"})
    logs.append.assert_called_once()
    assert logs.append.call_args[0][0]["action"] == "USER_LOGIN"

def test_AC20_record_activity_empty_action_rejected():
    """FR4.1 | Record activity without action | action = empty | ValueError, nothing appended"""
    logs = MagicMock()
    with pytest.raises(ValueError):
        AuditService(logs).record("", "USER", UID, {})
    logs.append.assert_not_called()

def test_AC21_review_activity_filter_by_action():
    """FR4.2 | Review activity filtered by action | action = USER_LOGIN | Only login logs returned"""
    logs = MagicMock()
    logs.find.return_value = [{"action": "USER_LOGIN"}, {"action": "ACCOUNT_UPDATED"}, {"action": "USER_LOGIN"}]
    out = AuditService(logs).search(action="USER_LOGIN")
    assert len(out) == 2 and all(l["action"] == "USER_LOGIN" for l in out)

def test_AC22_review_activity_filter_by_actor():
    """FR4.2 | Review activity filtered by actor | actor_id | Only that actor's logs"""
    logs = MagicMock()
    logs.find.return_value = [{"action": "A", "actor_id": 1}, {"action": "B", "actor_id": 2}]
    assert AuditService(logs).search(actor_id=2) == [{"action": "B", "actor_id": 2}]

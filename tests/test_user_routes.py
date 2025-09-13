# Test framework: pytest + FastAPI's TestClient (Starlette)
# These tests focus on the users router endpoints introduced/modified in the PR diff.
# They validate happy paths, edge cases, and failure conditions, with external dependencies mocked.

import importlib
import types
from typing import Any, Dict, List, Optional, ClassVar

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


def _load_user_router_module():
    """
    Attempts to import the users router module from several common locations.
    Returns the imported module that exposes a `router` attribute.
    """
    candidates = [
        "app.routes.user_routes",
        "app.routers.user_routes",
        "app.api.routes.user_routes",
        "app.api.v1.routes.user_routes",
        "app.api.endpoints.user_routes",
        "app.routes.users",
        "app.routers.users",
        "app.api.routes.users",
        "app.api.v1.routes.users",
        "app.api.endpoints.users",
        "app.user_routes",
    ]
    last_err: Optional[Exception] = None
    for name in candidates:
        try:
            module = importlib.import_module(name)
            if hasattr(module, "router"):
                return module
        except ImportError as e:  # pragma: no cover - import probing
            last_err = e
            continue
    raise ImportError from last_err


def _build_default_user_dict(
    *,
    id: int = 1,
    username: str = "alice",
    email: str = "alice@example.com",
    role: str = "user",
) -> Dict[str, Any]:
    """
    Builds a default user dict attempting to align with app.schemas.User.UserRead.
    If the schema is available, include all declared fields; else, include common fields and safe extras.
    """
    base = {"id": id, "username": username, "email": email, "role": role}
    try:
        from app.schemas.User import UserRead  # type: ignore

        # Pydantic v2: model_fields, v1: __fields__
        fields = getattr(UserRead, "model_fields", None) or getattr(UserRead, "__fields__", {}) or {}
        field_names = list(fields.keys()) if isinstance(fields, dict) else list(fields)
        # Provide simple defaults for any required fields not already present
        for name in field_names:
            if name not in base:
                if name.endswith("_at"):
                    base[name] = "2025-01-01T00:00:00Z"
                elif name in {"is_active", "active"}:
                    base[name] = True
                elif name in {"full_name", "name"}:
                    base[name] = username
                else:
                    base[name] = None
    except ImportError:
        # Safe superset commonly seen; extra fields will be ignored by typical FastAPI response_model settings
        base.update(
            {
                "created_at": "2025-01-01T00:00:00Z",
                "updated_at": "2025-01-01T00:00:00Z",
                "deleted_at": None,
            }
        )
    return base


class FakeService:
    """
    Minimal in-memory fake for app.services.UserService.UserService.
    It mirrors the public methods used by the router:
      - create_user(username, email, password)
      - list_users()
      - get_user_by_id(user_id)
      - verify_user_password(username, password)
      - delete_user(user_id)
      - update_user_role(user_id, role)
    """
    users: ClassVar[Dict[int, Dict[str, Any]]] = {}
    next_id: int = 1
    verify_ok: bool = True

    def __init__(self, db):
        self.db = db

    def create_user(self, username: str, email: str, _password: str) -> Dict[str, Any]:
        uid = FakeService.next_id
        FakeService.next_id += 1
        user = _build_default_user_dict(id=uid, username=username, email=email, role="user")
        FakeService.users[uid] = user
        return user

    def list_users(self) -> List[Dict[str, Any]]:
        return list(FakeService.users.values())

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        return FakeService.users.get(int(user_id))

    def verify_user_password(self, _username: str, _password: str) -> bool:
        return bool(FakeService.verify_ok)

    def delete_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        return FakeService.users.pop(int(user_id), None)

    def update_user_role(self, user_id: int, role: str) -> Optional[Dict[str, Any]]:
        user = FakeService.users.get(int(user_id))
        if not user:
            return None
        updated = {**user, "role": role}
        FakeService.users[int(user_id)] = updated
        return updated


@pytest.fixture(autouse=True)
def _reset_fake_service_state():
    # Ensure isolation between tests
    FakeService.users = {}
    FakeService.next_id = 1
    FakeService.verify_ok = True
    yield
    FakeService.users = {}
    FakeService.next_id = 1
    FakeService.verify_ok = True


@pytest.fixture
def client(monkeypatch):
    router_module = _load_user_router_module()

    # Patch the UserService reference in the router module's namespace
    monkeypatch.setattr(router_module, "UserService", FakeService, raising=True)

    # Build FastAPI app and override the DB dependency
    app = FastAPI()
    app.include_router(router_module.router)

    # Try to pull the get_db the same way the router did
    get_db = None
    try:
        from app.core.database import get_db as _get_db  # type: ignore
        get_db = _get_db
    except ImportError:
        # Fallback: if router module exposes get_db (rare), use that
        get_db = getattr(router_module, "get_db", None)

    class _DummySession:
        pass

    def _override_get_db():
        yield _DummySession()

    if get_db is not None:
        app.dependency_overrides[get_db] = _override_get_db

    with TestClient(app) as test_client:
        yield test_client


# -----------------------------
# Tests
# -----------------------------

def test_list_users_empty_initially(client: TestClient):
    res = client.get("/users/")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
    assert res.json() == []


def test_create_user_success(client: TestClient):
    payload = {"username": "alice", "email": "alice@example.com", "password": "s3cret\!"}
    res = client.post("/users/", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body["username"] == payload["username"]
    assert body["email"] == payload["email"]
    assert "id" in body and isinstance(body["id"], int)


def test_list_users_after_creation(client: TestClient):
    p1 = {"username": "alice", "email": "alice@example.com", "password": "x"}
    p2 = {"username": "bob", "email": "bob@example.com", "password": "y"}
    assert client.post("/users/", json=p1).status_code == 200
    assert client.post("/users/", json=p2).status_code == 200

    res = client.get("/users/")
    assert res.status_code == 200
    users = res.json()
    assert isinstance(users, list)
    usernames = {u["username"] for u in users}
    assert {"alice", "bob"} <= usernames


def test_get_user_by_id_found(client: TestClient):
    payload = {"username": "carol", "email": "carol@example.com", "password": "pw"}
    created = client.post("/users/", json=payload).json()
    uid = created["id"]

    res = client.get(f"/users/{uid}")
    assert res.status_code == 200
    user = res.json()
    assert user["id"] == uid
    assert user["username"] == "carol"


def test_get_user_by_id_not_found_returns_404(client: TestClient):
    res = client.get("/users/999999")
    assert res.status_code == 404
    assert res.json().get("detail") == "User not found"


def test_login_success_returns_message(client: TestClient):
    payload = {"username": "dave", "password": "pw"}
    res = client.post("/users/login", json=payload)
    assert res.status_code == 200
    assert res.json() == {"message": "Login successful"}


def test_login_invalid_credentials_returns_401(client: TestClient):
    # Flip the fake service to reject credentials
    FakeService.verify_ok = False
    payload = {"username": "erin", "password": "badpw"}
    res = client.post("/users/login", json=payload)
    assert res.status_code == 401
    assert res.json().get("detail") == "Invalid credentials"


def test_delete_user_success_then_not_found_on_second_fetch(client: TestClient):
    created = client.post("/users/", json={"username": "frank", "email": "frank@example.com", "password": "pw"}).json()
    uid = created["id"]

    res_del = client.delete(f"/users/{uid}")
    assert res_del.status_code == 200
    assert res_del.json() == {"message": f"User {uid} deleted successfully"}

    # Verify subsequent fetch yields 404
    res_get = client.get(f"/users/{uid}")
    assert res_get.status_code == 404
    assert res_get.json().get("detail") == "User not found"


def test_delete_user_not_found_returns_404(client: TestClient):
    res = client.delete("/users/424242")
    assert res.status_code == 404
    assert res.json().get("detail") == "User not found"


def test_update_user_role_success(client: TestClient):
    created = client.post("/users/", json={"username": "gina", "email": "gina@example.com", "password": "pw"}).json()
    uid = created["id"]

    res = client.patch(f"/users/{uid}/role", json={"role": "admin"})
    assert res.status_code == 200
    assert res.json() == {"message": f"User {uid} role updated to admin"}

    # If role is exposed by GET response model, verify it updated
    res_get = client.get(f"/users/{uid}")
    if res_get.status_code == 200 and isinstance(res_get.json(), dict) and "role" in res_get.json():
        assert res_get.json()["role"] == "admin"


def test_update_user_role_user_not_found_returns_404(client: TestClient):
    res = client.patch("/users/31337/role", json={"role": "moderator"})
    assert res.status_code == 404
    assert res.json().get("detail") == "User not found"


def test_create_user_validation_error_missing_fields_returns_422(client: TestClient):
    # Missing email and password
    res = client.post("/users/", json={"username": "harry"})
    assert res.status_code == 422
    body = res.json()
    assert "detail" in body


def test_path_param_type_error_returns_422(client: TestClient):
    # Non-integer user_id should trigger FastAPI validation error
    res = client.get("/users/not-an-int")
    assert res.status_code == 422
    assert "detail" in res.json()
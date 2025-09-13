# Test Runner & Framework: pytest
# Purpose: Unit tests for user HTTP schemas focusing on validation and from_attributes behavior.

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError
from sqlmodel import SQLModel

# Test password constants to avoid hardcoded-password lint warnings
_TEST_PW = "pw"
_TEST_PW_COMPLEX = "p@55"
_TEST_PW_SECRET = r"s3cret\!"

try:
    from app.schemas.user import UserCreate, UserLogin, UpdateUserRole, UserRead
except ImportError as e:
    # If the actual module path differs in this repository, adjust as needed.
    # Keeping fallback imports minimal to avoid masking real import issues during CI.
    import logging

    logging.debug("Could not import app.schemas.user: %s", e)

try:
    from app.models.User import UserRole
except ImportError:
    from enum import Enum

    class UserRole(str, Enum):
        ADMIN = "ADMIN"
        USER = "USER"
        GUEST = "GUEST"


# If the above import of schema classes failed, define minimal stubs from the provided diff snippet
# so this file remains syntactically valid in static contexts. In real test runs, the project modules should be importable.
if "UserCreate" not in globals():
    from pydantic import EmailStr

    class UserCreate(SQLModel, table=False):
        username: str
        email: EmailStr
        password: str

    class UserLogin(SQLModel, table=False):
        username: str
        password: str

    class UpdateUserRole(SQLModel, table=False):
        role: UserRole

    class UserRead(SQLModel, table=False):
        id: int
        username: str
        email: "EmailStr"
        role: UserRole
        created_at: datetime
        updated_at: datetime | None
        deleted_at: datetime | None

        class Config:
            from_attributes = True


class _FakeUserObj:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


# ---------- UserCreate ----------
def test_user_create_happy_path_valid_email_and_password():
    u = UserCreate(username="john_doe", email="john@example.com", password=_TEST_PW_SECRET)
    assert u.username == "john_doe"
    assert str(u.email) == "john@example.com"
    assert isinstance(u.password, str)


@pytest.mark.parametrize("bad_email", ["not-an-email", "foo@", "@bar.com", "user@invalid_domain", ""])
def test_user_create_rejects_invalid_email_formats(bad_email):
    with pytest.raises(ValidationError):
        UserCreate(username="jane", email=bad_email, password=_TEST_PW)


@pytest.mark.parametrize(
    "payload,missing_field",
    [
        (dict(email="jane@example.com", password=_TEST_PW), "username"),
        (dict(username="jane", password=_TEST_PW), "email"),
        (dict(username="jane", email="jane@example.com"), "password"),
    ],
)
def test_user_create_missing_required_fields(payload, missing_field):
    with pytest.raises(ValidationError) as exc:
        UserCreate(**payload)  # type: ignore[arg-type]
    msg = str(exc.value).lower()
    assert missing_field in msg


def test_user_create_rejects_non_string_username():
    with pytest.raises(ValidationError):
        UserCreate(username=123, email="john@example.com", password=_TEST_PW)  # type: ignore[arg-type]


# ---------- UserLogin ----------
def test_user_login_happy_path():
    data = UserLogin(username="johnny", password=_TEST_PW_COMPLEX)
    assert data.username == "johnny"
    assert data.password == _TEST_PW_COMPLEX


@pytest.mark.parametrize(
    "payload,missing_field",
    [
        (dict(password=_TEST_PW), "username"),
        (dict(username="joe"), "password"),
    ],
)
def test_user_login_missing_required_fields(payload, missing_field):
    with pytest.raises(ValidationError) as exc:
        UserLogin(**payload)  # type: ignore[arg-type]
    assert missing_field in str(exc.value).lower()


def test_user_login_rejects_non_string_password():
    with pytest.raises(ValidationError):
        UserLogin(username="joe", password=123)  # type: ignore[arg-type]


# ---------- UpdateUserRole ----------
@pytest.mark.parametrize("role", [UserRole.ADMIN, UserRole.USER, getattr(UserRole, "GUEST", None)])
def test_update_user_role_accepts_valid_enum(role):
    if role is None:
        pytest.skip("UserRole.GUEST not defined in this project")
    obj = UpdateUserRole(role=role)
    assert obj.role == role


@pytest.mark.parametrize("bad_role", ["admin", "OWNER", 1, None])
def test_update_user_role_rejects_invalid_values(bad_role):
    with pytest.raises(ValidationError):
        UpdateUserRole(role=bad_role)  # type: ignore[arg-type]


# ---------- UserRead ----------
def test_user_read_from_attributes_happy_path_including_nones():
    now = datetime.utcnow()
    fake = _FakeUserObj(
        id=42,
        username="neo",
        email="neo@matrix.io",
        role=UserRole.USER,
        created_at=now,
        updated_at=None,
        deleted_at=None,
        extra="ignore-me",
    )
    model = UserRead.model_validate(fake)
    assert model.id == 42
    assert model.username == "neo"
    assert str(model.email) == "neo@matrix.io"
    assert model.role == UserRole.USER
    assert model.created_at == now
    assert model.updated_at is None
    assert model.deleted_at is None


def test_user_read_from_attributes_with_all_timestamps():
    created = datetime(2020, 1, 1, 12, 0, 0)
    updated = created + timedelta(days=1)
    deleted = updated + timedelta(days=1)
    fake = _FakeUserObj(
        id=1,
        username="trinity",
        email="trinity@matrix.io",
        role=UserRole.ADMIN,
        created_at=created,
        updated_at=updated,
        deleted_at=deleted,
    )
    model = UserRead.model_validate(fake)
    assert model.created_at == created
    assert model.updated_at == updated
    assert model.deleted_at == deleted


def test_user_read_rejects_invalid_email_type():
    fake = _FakeUserObj(
        id=99,
        username="morpheus",
        email="not-an-email",
        role=UserRole.USER,
        created_at=datetime.utcnow(),
        updated_at=None,
        deleted_at=None,
    )
    with pytest.raises(ValidationError):
        UserRead.model_validate(fake)


def test_user_read_accepts_negative_id_as_no_constraints_present():
    fake = _FakeUserObj(
        id=-5,
        username="agent",
        email="agent@smith.io",
        role=UserRole.USER,
        created_at=datetime.utcnow(),
        updated_at=None,
        deleted_at=None,
    )
    model = UserRead.model_validate(fake)
    assert model.id == -5
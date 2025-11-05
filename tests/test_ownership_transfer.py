import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlmodel import SQLModel
from app.main import app
from app.core.database import get_db
from app.models.User import User
from app.models.Vault import Vault
from app.models.VaultMembership import VaultMembership, MembershipRole
from app.services.users.UserService import UserService
from app.services.vaults.VaultService import VaultService
from app.services.vaults.VaultMembershipService import VaultMembershipService

# Use an in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    # Create the database tables
    SQLModel.metadata.create_all(bind=engine)
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    # Override the get_db dependency
    def override_get_db():
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_get_db

    yield session

    # Rollback the transaction and close the connection
    session.close()
    transaction.rollback()
    connection.close()
    SQLModel.metadata.drop_all(bind=engine) # Drop tables after each test to ensure full isolation


client = TestClient(app)

@pytest.fixture(scope="function")
def setup_users_and_vault(db_session: Session):
    user_service = UserService(db_session)
    vault_service = VaultService(db_session)
    membership_service = VaultMembershipService(db_session)

    # Create users
    owner_user = user_service.create_user(username="owner@test.com", email="owner@test.com", password="password")
    new_owner_user = user_service.create_user(username="newowner@test.com", email="newowner@test.com", password="password")
    non_member_user = user_service.create_user(username="nonmember@test.com", email="nonmember@test.com", password="password")

    # Create vault
    vault = vault_service.create_vault(device_id="test_device_ownership", name="Ownership Test Vault", location="Test Location")

    # Add owner and new_owner to vault
    membership_service.add_user_to_vault(user_id=owner_user.id, vault_id=vault.id, role=MembershipRole.admin)
    membership_service.add_user_to_vault(user_id=new_owner_user.id, vault_id=vault.id, role=MembershipRole.member)

    return owner_user, new_owner_user, non_member_user, vault

def get_auth_header(user: User, db: Session):
    user_service = UserService(db)
    token = user_service.create_access_token(data={"sub": user.username})
    return {"Authorization": f"Bearer {token}"}

def test_initiate_transfer_success(db_session: Session, setup_users_and_vault):
    owner, new_owner, _, vault = setup_users_and_vault
    headers = get_auth_header(owner, db_session)

    response = client.post(
        f"/vaults/{vault.id}/transfer/initiate",
        headers=headers,
        json={"new_owner_user_id": new_owner.id, "transfer_type": "full_transfer"}
    )
    assert response.status_code == 202
    assert response.json()["success"] is True

def test_initiate_transfer_not_owner(db_session: Session, setup_users_and_vault):
    _, new_owner, _, vault = setup_users_and_vault
    headers = get_auth_header(new_owner, db_session)

    response = client.post(
        f"/vaults/{vault.id}/transfer/initiate",
        headers=headers,
        json={"new_owner_user_id": new_owner.id, "transfer_type": "full_transfer"}
    )
    assert response.status_code == 403

def test_initiate_transfer_to_non_member(db_session: Session, setup_users_and_vault):
    owner, _, non_member, vault = setup_users_and_vault
    headers = get_auth_header(owner, db_session)

    response = client.post(
        f"/vaults/{vault.id}/transfer/initiate",
        headers=headers,
        json={"new_owner_user_id": non_member.id, "transfer_type": "full_transfer"}
    )
    assert response.status_code == 400
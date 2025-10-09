from sqlalchemy.orm import Session
from datetime import datetime
from typing import List, Optional
from app.models.VaultMembership import VaultMembership, MembershipRole
from app.repositories.VaultMembershipRepository import VaultMembershipRepository


# =============================================================================
# VAULT MEMBERSHIP SERVICE CLASS
# =============================================================================

class VaultMembershipService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = VaultMembershipRepository(db)

    # -------------------------------------------------------------------------
    # MEMBERSHIP CREATION
    # -------------------------------------------------------------------------

    def add_user_to_vault(self, user_id: int, vault_id: int, role: MembershipRole) -> VaultMembership:
        # =====================================================================
        # STEP 1: VALIDATE NO EXISTING MEMBERSHIP
        # =====================================================================
        existing = self.repo.get_by_user_and_vault(user_id, vault_id)

        if existing:
            raise ValueError("User is already a member of this vault")

        # =====================================================================
        # STEP 2: CREATE NEW MEMBERSHIP
        # =====================================================================
        membership = VaultMembership(
            user_id=user_id,
            vault_id=vault_id,
            role=role,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # =====================================================================
        # STEP 3: PERSIST MEMBERSHIP (COMMIT TO DATABASE)
        # =====================================================================
        self.db.add(membership)
        self.db.flush()  # Write to transaction
        self.db.commit()  # Commit the transaction
        self.db.refresh(membership)  # Refresh with DB-generated fields
        return membership

    # -------------------------------------------------------------------------
    # MEMBERSHIP QUERIES
    # -------------------------------------------------------------------------

    def get_user_vaults(self, user_id: int) -> List[VaultMembership]:
        return self.repo.get_user_memberships(user_id)

    def get_user_role_in_vault(self, user_id: int, vault_id: int) -> Optional[MembershipRole]:
        membership = self.repo.get_by_user_and_vault(user_id, vault_id)
        return membership.role if membership else None

    def get_vault_members(self, vault_id: int) -> List[VaultMembership]:
        from app.models.User import User

        return (
            self.db.query(VaultMembership)
            .join(User, VaultMembership.user_id == User.id)
            .filter(VaultMembership.vault_id == vault_id)
            .filter(User.deleted_at == None)  # Exclude soft-deleted users
            .all()
        )

    def is_user_admin_of_vault(self, user_id: int, vault_id: int) -> bool:
        return self.repo.is_user_admin_of_vault(user_id, vault_id)

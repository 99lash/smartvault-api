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

    def get_user_vaults(self, user_id: int) -> List[dict]:
        from app.services.logs.AccessTrackingService import AccessTrackingService

        memberships = self.repo.get_user_memberships(user_id)
        access_tracking = AccessTrackingService(self.db)

        result = []
        for membership in memberships:
            # Convert to dict and add last_access
            membership_dict = {
                'id': membership.id,
                'user_id': membership.user_id,
                'vault_id': membership.vault_id,
                'role': membership.role,
                'created_at': membership.created_at,
                'updated_at': membership.updated_at,
                'last_access': access_tracking.get_last_access_timestamp(
                    user_id=user_id,
                    vault_id=membership.vault_id
                )
            }
            result.append(membership_dict)

        return result

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

    def is_user_member_of_vault(self, user_id: int, vault_id: int) -> bool:
        """
        Check if a user is a member of a specific vault.

        Args:
            user_id (int): ID of the user to check
            vault_id (int): ID of the vault to check

        Returns:
            bool: True if user is a member of the vault, False otherwise
        """
        membership = self.repo.get_by_user_and_vault(user_id, vault_id)
        return membership is not None

from sqlmodel import SQLModel
from datetime import datetime
from typing import Optional
from pydantic import Field
from app.models.Vault import VaultStatus
from app.models.VaultInvitation import TransferType

# ----------------------------
# Vault HTTP Request Schemas
# ----------------------------
class VaultCreate(SQLModel, table=False):
    """
    Schema for creating a new vault with device ID as primary identifier.

    The device_id becomes the vault's primary key, ensuring direct mapping
    between physical devices and vault records.
    """
    device_id: str = Field(..., min_length=1, description="Unique device identifier from ESP32")
    name: str = Field(..., min_length=1, max_length=100, description="Human-readable vault name")
    location: Optional[str] = Field(None, max_length=200, description="Physical location of the vault")
    status: Optional[VaultStatus] = Field(VaultStatus.locked, description="Initial vault status")

class UpdateVaultStatus(SQLModel, table=False):
    status: VaultStatus

class VaultTransferInitiate(SQLModel, table=False):
    new_owner_user_id: int = Field(..., description="ID of the user to transfer ownership to")
    transfer_type: TransferType = Field(..., description="Type of ownership transfer (full_transfer or shared_access)")

class VaultTransferAccept(SQLModel, table=False):
    invite_code: str = Field(..., description="Unique invitation code for ownership transfer")

# ----------------------------
# Vault HTTP Response Schemas
# ----------------------------
class VaultRead(SQLModel, table=False):
    """
    Response schema for vault data.

    The id field contains the device_id, ensuring direct mapping
    between API responses and physical devices.
    """
    id: int = Field(..., description="Vault ID (auto-incrementing integer)")
    device_id: str = Field(..., description="ESP32 device identifier")
    name: str = Field(..., description="Human-readable vault name")
    location: Optional[str] = Field(None, description="Physical location of the vault")
    status: VaultStatus = Field(..., description="Current vault status")
    created_at: datetime = Field(..., description="Vault creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    deleted_at: Optional[datetime] = Field(None, description="Soft delete timestamp")

    class Config:
        from_attributes = True
# Ownership Transfer Process

This document outlines the process for transferring ownership of a vault from one user to another.

## Overview

The ownership transfer feature allows the current owner of a vault to securely pass their ownership privileges to another user who is already a member of that vault. The process is designed to be secure and prevent accidental transfers by requiring a two-step confirmation process: initiation by the current owner and acceptance by the designated new owner.

## Transfer Types

The initiator of the transfer must choose what happens to their own access upon successful completion. There are two types of transfers:

1.  **Full Transfer (`full_transfer`)**
    *   The original owner's access to the vault is completely revoked.
    *   Their `VaultMembership` record is deleted.
    *   This is useful when selling a vault or completely handing over a project.

2.  **Shared Access (`shared_access`)**
    *   The original owner is demoted to a standard `user` role.
    *   They remain a member of the vault with non-administrative privileges.
    *   This is useful for collaborative projects where the primary owner is stepping down from a leadership role but still needs access.

## Process Flow

1.  **Initiation**
    *   **Endpoint:** `POST /vaults/{vault_id}/transfer/initiate`
    *   **Actor:** Current Vault Owner
    *   The owner sends a request specifying the `user_id` of the intended new owner and the desired `transfer_type` (`full_transfer` or `shared_access`).
    *   The system validates that the initiator is the current owner and the target user is a member of the vault.
    *   A `VaultInvitation` record is created with a status of `pending_transfer` and the chosen transfer type is stored.

2.  **Acceptance**
    *   **Endpoint:** `POST /vaults/{vault_id}/transfer/accept`
    *   **Actor:** Designated New Owner
    *   The target user receives the transfer invitation.
    *   To confirm, they call the acceptance endpoint, likely using a token from the invitation.
    *   The system validates the invitation.

3.  **Execution**
    *   Upon successful acceptance, the system performs the following actions atomically:
        1.  The `role` of the new owner in the `VaultMembership` table is updated to `admin`.
        2.  The `role` of the original owner is handled based on the `transfer_type`:
            *   If `full_transfer`, their `VaultMembership` record is deleted.
            *   If `shared_access`, their `role` is updated to `user`.
        3.  The `VaultInvitation` is marked as `accepted` or deleted.
        4.  A detailed log entry is created to record this critical security event.

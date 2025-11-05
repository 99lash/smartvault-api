# End-to-End Process: Vault Ownership Transfer

This document details the complete, two-step process for transferring vault ownership from one user to another, as implemented in the codebase.

---

## 1. Initiation of Ownership Transfer

This is the first step, where the current owner starts the transfer process.

### **Step 1.1: API Request**

The **current owner** sends a `POST` request to the initiation endpoint.

-   **Endpoint:** `POST /vaults/{vault_id}/transfer/initiate`
-   **Request Body:**
    ```json
    {
      "new_owner_user_id": 123,
      "transfer_type": "full_transfer"
    }
    ```
-   **File Involved:** `app/routes/vault_routes.py`
-   **Endpoint Function:** `initiate_vault_ownership_transfer`

### **Step 1.2: Service Layer Logic**

The request is handled by the `VaultService`, which orchestrates the business logic.

-   **File Involved:** `app/services/vaults/VaultService.py`
-   **Method:** `initiate_ownership_transfer`
-   **Actions Performed:**
    *   Verifies that the requesting user is the **current owner** of the vault.
    *   Confirms that the `new_owner_user_id` corresponds to a **current member** of the vault.
    *   Checks to prevent a new transfer if one is already **pending**.
    *   Calls the repository to create the special transfer invitation.
    *   Creates a log entry (`ownership_transfer_initiated`) for auditing.

### **Step 1.3: Repository Layer (Data Access)**

The `VaultInvitationRepository` handles the database interaction.

-   **File Involved:** `app/repositories/VaultInvitationRepository.py`
-   **Method:** `create_ownership_transfer_invitation`
-   **Action:** Creates a new `VaultInvitation` record in the database, flagging it as an ownership transfer and storing the `transfer_type`.

### **Step 1.4: API Response**

The server acknowledges the request.

-   **Status Code:** `202 Accepted`
-   **Response Body:** A success message indicating the transfer is pending acceptance.

---

## 2. Acceptance of Ownership Transfer

This is the second step, where the designated user accepts the ownership role.

### **Step 2.1: API Request**

The **designated new owner** sends a `POST` request to the acceptance endpoint.

-   **Endpoint:** `POST /vaults/{vault_id}/transfer/accept`
-   **Request Body:**
    ```json
    {
      "invite_code": "a1b2c3d4-e5f6-..."
    }
    ```
-   **File Involved:** `app/routes/vault_routes.py`
-   **Endpoint Function:** `accept_vault_ownership_transfer`

### **Step 2.2: Service Layer Logic**

The `VaultService` handles the confirmation logic.

-   **File Involved:** `app/services/vaults/VaultService.py`
-   **Method:** `accept_ownership_transfer`
-   **Actions Performed:**
    *   Retrieves the `VaultInvitation` using the provided `invite_code`.
    *   Validates that the invitation is for an ownership transfer, is still valid (not expired), and that the current user is the one it was intended for.
    *   **Executes the transfer atomically:**
        1.  Promotes the new owner's role to `admin` in the `VaultMembership` table.
        2.  Handles the original owner's membership based on the `transfer_type`:
            -   **Full Transfer:** Deletes the original owner's `VaultMembership` record.
            -   **Shared Access:** Demotes the original owner's role to `member`.
        3.  Marks the `VaultInvitation` as `accepted`.
        4.  Creates a final log entry (`ownership_transfer_accepted`) for the audit trail.

### **Step 2.3: Repository Layer (Data Access)**

The repositories update the database state.

-   **Files Involved:**
    -   `app/repositories/VaultMembershipRepository.py`
    -   `app/repositories/VaultInvitationRepository.py`
-   **Actions:**
    *   Updates the roles of the old and new owners.
    *   Marks the invitation record as used.

### **Step 2.4: API Response**

The server confirms the successful transfer.

-   **Status Code:** `200 OK`
-   **Response Body:** A success message confirming the ownership change.

---

This secure, two-step process ensures that ownership transfers are intentional, authorized, and fully auditable.
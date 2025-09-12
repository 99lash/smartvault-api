# SmartVault API Endpoints (v1.0)

## Authentication

#### `POST /auth/signup`

- Create new account.

**Request:**

```json
{
  "email": "user@mail.com",
  "phone": "09123456789",
  "password": "securePass123"
}
```

#### `POST /auth/login`

- Login with email/phone + password. Returns Token/Session.

**Request:**

```json
{
  "username": "juan",
  "password": "securePass123"
}
```

**Response:**

```json
{
  "token/session": "token/session.here"
}
```

#### `POST /auth/logout`

- Invalidate current session.

**Response:**

```json
{
  "msg": "success",
  "status": 200
}
```

## Account Management

#### `PATCH /account/profile`

- Update profile (name, email, phone).

#### `PATCH /account/security`

- Update password, enable/disable 2FA.

#### `GET /account/vaults`

- List all vaults bound to account.

## Vault Management

#### `POST /vaults`

- Add new vault (onboarding flow).
  Steps handled by app but finalized in this endpoint.

```json
{
  "vault_name": "Office Safe",
  "wifi_ssid": "MyWiFi",
  "wifi_password": "mypassword",
  "admin_pin": "4321",
  "alarm_enabled": true
}
```

#### `GET /vaults/{vault_id}`

- Get vault details (status, battery, last logs).

**Response:**

```json
{
  "id": "vault.id",
  "status": "locked",
  "battery": "100%",
  "auto_lock_timer": 30,
  "tamper_sensitivity": 70,
  "max_failed_attempts": 3,
  "lockout_duration_mins": 5,
  "mode": "restricted | normal",
  "last_logs": "date",
  "created_at": "date",
  "updated_at": "date"
}
```

#### `PATCH /vaults/{vault_id}`

- Update vault settings (alarm triggers, WiFi, lock behavior).

#### `DELETE /vaults/{vault_id}`

- Remove / reset binding.

## User Management

#### `GET /vaults/{vault_id}/users`

- List admins + members bounded to vault.

#### `POST /vaults/{vault_id}/users`

- Add new user.

```json
{
  "name": "Juan",
  "role": "regular",
  "face_id": "AB12CD34",
  "nfc_id": "AB12CD34",
  "pin": "9876",
  "isDeactivated": false,
  "face_enrolled": true,
  "nfc_enrolled": true,
  "pin_enrolled": true
}
```

#### `PATCH /vaults/{vault_id}/users/{user_id}`

- Edit user (update PIN, NFC, role, isDeactivated).

#### `DELETE /vaults/{vault_id}/users/{user_id}`

- Remove user.

## Vault Access

#### `POST /vaults/{vault_id}/unlock`

- Remote unlock request (requires OTP + 2FA if enabled).

#### `POST /vaults/{vault_id}/lock`

- Remote lock vault.

## Logs & Notifications

#### `GET /vaults/{vault_id}/logs`

- Fetch timeline of events (unlock, failed attempt, tamper).
  Supports filters:
  `/logs?user=maria&type=unlock&status=all&date=2025-09-01`

#### `GET /vaults/{vault_id}/notifications`

- Fetch all notifications for logged-in user.
- filter status: unread | read

**Response:**

```json
[
  {
    "id": "notif123",
    "vault_id": "vault001",
    "type": "tamper",
    "message": "Tamper detected on Office Vault",
    "status": "unread",
    "timestamp": "2025-09-05T12:15:00Z"
  },
  {
    "id": "notif124",
    "vault_id": "vault002",
    "type": "user_added",
    "message": "New regular user 'Maria' added",
    "status": "read",
    "timestamp": "2025-09-05T11:40:00Z"
  }
]
```

#### `PATCH /vaults{vault_id}/notifications/{notif_id}/read`

- Mark notification as read.

#### `PATCH /vaults{vault_id}/notifications/{notif_id}/mark-all-read`

- Mark all notifications as read.

#### `GET /vaults{vault_id}/notifications-settings/`

- Fetch all notifications settings properties
  - unlock/lock
  - tamper alerts
  - failed/success attempts
  - low battery
  - user management
  - system updates

#### `PATCH /vaults{vault_id}/notifications-settings/update`

- Update notification behavior.
  - unlock/lock
  - tamper alerts
  - failed/success attempts
  - low battery
  - user management
  - system updates

#### `WS /vaults/{vault_id}/events`

- Real-time feed for unlocks, tamper, failed attempts.
- Push notifications & in-app alerts screen supported.

## Alerts & Tamper

#### `GET /vaults/{vault_id}/alerts`

- Get all alerts (tamper, failed unlocks).

#### `POST /vaults/{vault_id}/alerts/ack`

- Acknowledge and clear alert.

## Vault Settings

#### `PATCH /vaults/{vault_id}/settings`

- Update lock behavior (auto-relock timer, alarm settings, reconnect WiFi).

## Device & Firmware

#### `GET /vaults/{vault_id}/battery`

- Battery % and health status.

#### `POST /vaults/{vault_id}/firmware/update`

- Upload firmware or trigger OTA update.

## App Settings

#### `GET /app-settings`

- Fetch user's current app settings.

**Response:**

```json
{
  "biometric_auth": true,
  "auto_sync": false,
  "haptic_feedback": true,
  "sound_effects": false,
  "offline_mode": false,
  "updated_at": "2025-09-05T13:00:00Z"
}
```

### `PATCH /app-settings`

- Update user's app settings.

**Request:**

```json
{
  "biometric_auth": false,
  "auto_sync": true,
  "haptic_feedback": true,
  "sound_effects": true,
  "offline_mode": true
}
```

**Response:**

```json
{
  "message": "App settings updated successfully",
  "settings": {
    "biometric_auth": false,
    "auto_sync": true,
    "haptic_feedback": true,
    "sound_effects": true,
    "offline_mode": true
  }
}
```

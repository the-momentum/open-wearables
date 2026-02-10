# Invitation Code for SDK User Onboarding (#430)

## Context

Demo app users currently need to manually enter `user_id`, `access_token`, and (soon) `refresh_token` — 3 separate values. This is cumbersome for mobile onboarding. The solution: a single short code that a developer generates for a user, which the mobile app exchanges for all credentials in one call.

This is **separate** from the existing developer `Invitation` system (email-based team invitations). This feature targets SDK/end-user onboarding.

## Scope Decision: SDK vs Sample App

**Backend only (this repo).** The two API endpoints are the deliverable. The mobile SDK (`open_wearables_health_sdk`) can add a convenience `redeemInvitationCode()` method later — it's just a single HTTP POST call, so the sample app can also call it directly without SDK support.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/users/{user_id}/invitation-code` | Developer (Bearer) | Generate a code |
| `POST` | `/api/v1/invitation-code/redeem` | **Public** | Exchange code for tokens |

### Redeem Response

The response includes `user_id` (the whole point is replacing manual entry of user_id + tokens). `InvitationCodeRedeemResponse` extends `TokenResponse` with `user_id`:

```python
class InvitationCodeRedeemResponse(TokenResponse):
    user_id: UUID
```

## Code Format

**8 uppercase alphanumeric characters** (e.g., `A3K9M7X2`)
- Charset: `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (32 chars, no ambiguous 0/O, 1/I/L)
- 32^8 ≈ 1.1 trillion combinations — collision-proof at any realistic scale
- Easy to type on mobile keyboards

## Database Schema

### `user_invitation_code` Table

```python
class UserInvitationCode(BaseDbModel):
    __tablename__ = "user_invitation_code"

    id: Mapped[PrimaryKey[UUID]]
    code: Mapped[Unique[str_10]]           # 8-char code
    user_id: Mapped[Indexed[FKUser]]       # SDK user
    created_by_id: Mapped[FKDeveloper]     # Developer who generated
    expires_at: Mapped[datetime_tz]
    redeemed_at: Mapped[datetime_tz | None]  # Set when code is exchanged for tokens
    revoked_at: Mapped[datetime_tz | None]   # Set when code is invalidated (e.g., new code generated)
    created_at: Mapped[datetime_tz]
```

**State logic** — no status enum needed, state is derived from fields:
- **Active**: `redeemed_at IS NULL AND revoked_at IS NULL AND expires_at > now`
- **Redeemed**: `redeemed_at IS NOT NULL` — code was exchanged for tokens
- **Revoked**: `revoked_at IS NOT NULL` — code was invalidated (new code generated for same user)
- **Expired**: `expires_at <= now`

**Auto-revocation**: When a new code is generated for a user, all previous active codes for that user are automatically revoked (`revoked_at` set to current timestamp).

### Indexes
- PK on `id`
- Unique index on `code`
- Index on `user_id`
- FK `user_id -> user.id` (CASCADE)
- FK `created_by_id -> developer.id` (SET NULL)

## Implementation

### Schemas — `backend/app/schemas/user_invitation_code.py`

- `UserInvitationCodeCreate` — all DB fields for repository creation
- `UserInvitationCodeRead` — response after generating (id, code, user_id, expires_at, created_at)
- `UserInvitationCodeRedeem` — input for redeem (`code` with validation: 8 chars, `[A-Z2-9]`)
- `InvitationCodeRedeemResponse(TokenResponse)` — extends `TokenResponse` with `user_id: UUID`

### Repository — `backend/app/repositories/user_invitation_code_repository.py`

Extends `CrudRepository`. Custom methods:
- `get_valid_by_code(db, code)` — finds code where `redeemed_at IS NULL AND revoked_at IS NULL AND expires_at > now`
- `mark_redeemed(db, invitation_code)` — sets `redeemed_at = now()`
- `revoke_active_for_user(db, user_id)` — bulk UPDATE setting `revoked_at = now()` on all active codes for a user

### Service — `backend/app/services/user_invitation_code_service.py`

Pattern follows `InvitationService` (standalone class, not `AppService`).

**`generate(db, user_id, developer_id) -> UserInvitationCodeRead`**
1. Verify user exists via `user_service.get(db, user_id, raise_404=True)`
2. Revoke all active codes for this user
3. Generate 8-char code using `secrets.choice()` over unambiguous charset
4. Create DB record with `expires_at = now + invitation_expire_days` (reuses existing config)

**`redeem(db, code) -> InvitationCodeRedeemResponse`**
1. Lookup via `get_valid_by_code(db, code.upper())`
2. 404 if not found / expired / redeemed / revoked
3. Mark as redeemed
4. Generate tokens reusing existing functions:
   - `create_sdk_user_token(app_id, user_id)` from `sdk_token_service.py`
   - `refresh_token_service.create_sdk_refresh_token(db, user_id, app_id)`
5. `app_id = f"invite:{created_by_id}"` — follows existing pattern (`admin:{dev_id}` for admin tokens)

### Routes — `backend/app/api/routes/v1/user_invitation_code.py`

```python
@router.post("/users/{user_id}/invitation-code", status_code=201)
async def generate_invitation_code(user_id: UUID, db: DbSession, developer: DeveloperDep) -> UserInvitationCodeRead: ...

@router.post("/invitation-code/redeem")
async def redeem_invitation_code(payload: UserInvitationCodeRedeem, db: DbSession) -> InvitationCodeRedeemResponse: ...
```

### Registration (modified existing files)

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Add `UserInvitationCode` import + `__all__` |
| `backend/app/services/__init__.py` | Add `user_invitation_code_service` import + `__all__` |
| `backend/app/api/routes/v1/__init__.py` | Register router with `tags=["Mobile SDK"]` (no prefix) |

## Existing Code Reused

| What | File |
|------|------|
| `create_sdk_user_token()` | `backend/app/services/sdk_token_service.py` |
| `refresh_token_service.create_sdk_refresh_token()` | `backend/app/services/refresh_token_service.py` |
| `TokenResponse` schema | `backend/app/schemas/token.py` |
| `user_service.get()` for user validation | `backend/app/services/user_service.py` |
| `DeveloperDep` auth dependency | `backend/app/utils/auth.py` |
| `settings.invitation_expire_days` (7 days) | `backend/app/config.py` |
| `settings.access_token_expire_minutes` | `backend/app/config.py` |

## Verification

1. **Generate a code** (requires developer auth):
   ```bash
   curl -X POST http://localhost:8000/api/v1/users/{user_id}/invitation-code \
     -H "Authorization: Bearer {dev_token}"
   ```
2. **Redeem the code** (no auth):
   ```bash
   curl -X POST http://localhost:8000/api/v1/invitation-code/redeem \
     -H "Content-Type: application/json" \
     -d '{"code": "A3K9M7X2"}'
   ```
3. Verify response contains `user_id`, `access_token`, `refresh_token`, `expires_in`
4. Verify second redemption of same code returns 404
5. Generate a new code for the same user — verify old code is revoked (returns 404 on redeem)
6. Run existing tests to ensure no regressions

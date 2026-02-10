# Invitation Code for SDK User Onboarding (#430)

## Context

Demo app users currently need to manually enter `user_id`, `access_token`, and (soon) `refresh_token` — 3 separate values. This is cumbersome for mobile onboarding. The solution: a single short code that a developer generates for a user, which the mobile app exchanges for all credentials in one call.

This is **separate** from the existing developer `Invitation` system (email-based team invitations). This feature targets SDK/end-user onboarding.

## Scope Decision: SDK vs Sample App

**Recommendation: Backend only (this repo).** The two API endpoints are the deliverable. The mobile SDK (`open_wearables_health_sdk`) can add a convenience `redeemInvitationCode()` method later — it's just a single HTTP POST call, so the sample app can also call it directly without SDK support. This keeps the scope focused.

## Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `POST` | `/api/v1/users/{user_id}/invitation-code` | Developer (Bearer) | Generate a code |
| `POST` | `/api/v1/invitation-code/redeem` | **Public** | Exchange code for tokens |

### Redeem Response

The response **must include `user_id`** (the whole point is replacing manual entry of user_id + tokens). A new `InvitationCodeRedeemResponse` schema extends `TokenResponse` with `user_id`:

```python
class InvitationCodeRedeemResponse(TokenResponse):
    user_id: UUID
```

## Code Format

**8 uppercase alphanumeric characters** (e.g., `A3K9M7X2`)
- Charset: `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (32 chars, no ambiguous 0/O, 1/I/L)
- 32^8 ≈ 1.1 trillion combinations — collision-proof at any realistic scale
- Easy to type on mobile keyboards

## Implementation

### 1. Model — `backend/app/models/user_invitation_code.py` (NEW)

```python
class UserInvitationCode(BaseDbModel):
    __tablename__ = "user_invitation_code"

    id: Mapped[PrimaryKey[UUID]]
    code: Mapped[Unique[str_10]]           # 8-char code
    user_id: Mapped[Indexed[FKUser]]       # SDK user
    created_by_id: Mapped[FKDeveloper]     # Developer who generated
    expires_at: Mapped[datetime_tz]
    redeemed_at: Mapped[datetime_tz | None]  # NULL = not yet used
    created_at: Mapped[datetime_tz]
```

No status enum needed — state is fully determined by `redeemed_at` (NULL = active) + `expires_at`.

### 2. Schemas — `backend/app/schemas/user_invitation_code.py` (NEW)

- `UserInvitationCodeCreate` — all DB fields for repository creation (no separate API input schema needed since the endpoint has no request body)
- `UserInvitationCodeRead` — response after generating (id, code, user_id, expires_at, created_at)
- `UserInvitationCodeRedeem` — input for redeem (`code` with validation: 8 chars, `[A-Z2-9]`)
- `InvitationCodeRedeemResponse(TokenResponse)` — extends existing `TokenResponse` with `user_id: UUID`

### 3. Repository — `backend/app/repositories/user_invitation_code_repository.py` (NEW)

Extends `CrudRepository`. Custom methods:
- `get_valid_by_code(db, code)` — finds code where `redeemed_at IS NULL AND expires_at > now`
- `mark_redeemed(db, invitation_code)` — sets `redeemed_at = now()`

### 4. Service — `backend/app/services/user_invitation_code_service.py` (NEW)

Pattern follows `InvitationService` (standalone class, not `AppService`).

**`generate(db, user_id, developer_id) -> UserInvitationCode`**
1. Verify user exists via `user_service.get(db, user_id, raise_404=True)`
2. Generate 8-char code using `secrets.choice()` over unambiguous charset
3. Create DB record with `expires_at = now + invitation_expire_days` (reuses existing config)

**`redeem(db, code) -> InvitationCodeRedeemResponse`**
1. Lookup via `get_valid_by_code(db, code.upper())`
2. 404 if not found / expired / already redeemed
3. Mark as redeemed
4. Generate tokens reusing existing functions:
   - `create_sdk_user_token(app_id, user_id)` from `sdk_token_service.py`
   - `refresh_token_service.create_sdk_refresh_token(db, user_id, app_id)`
5. `app_id = f"invite:{created_by_id}"` — follows existing pattern (`admin:{dev_id}` for admin tokens)

### 5. Routes — `backend/app/api/routes/v1/user_invitation_code.py` (NEW)

```python
@router.post("/users/{user_id}/invitation-code", status_code=201, response_model=UserInvitationCodeRead)
async def generate_invitation_code(user_id: UUID, db: DbSession, developer: DeveloperDep): ...

@router.post("/invitation-code/redeem", response_model=InvitationCodeRedeemResponse)
async def redeem_invitation_code(payload: UserInvitationCodeRedeem, db: DbSession): ...
```

### 6. Registration (MODIFY existing files)

| File | Change |
|------|--------|
| `backend/app/models/__init__.py` | Add `UserInvitationCode` import + `__all__` |
| `backend/app/services/__init__.py` | Add `user_invitation_code_service` import + `__all__` |
| `backend/app/api/routes/v1/__init__.py` | Register router with `tags=["Mobile SDK"]` (no prefix) |

### 7. Alembic Migration

```bash
make create_migration m="add_user_invitation_code_table"
```

Creates `user_invitation_code` table with:
- PK on `id`
- Unique index on `code`
- Index on `user_id`
- FK `user_id -> user.id` (CASCADE)
- FK `created_by_id -> developer.id` (SET NULL)

## Existing Code to Reuse

| What | File |
|------|------|
| `create_sdk_user_token()` | `backend/app/services/sdk_token_service.py` |
| `refresh_token_service.create_sdk_refresh_token()` | `backend/app/services/refresh_token_service.py` |
| `TokenResponse` schema | `backend/app/schemas/token.py` |
| `user_service.get()` for user validation | `backend/app/services/user_service.py` |
| `DeveloperDep` auth dependency | `backend/app/utils/auth.py` |
| `settings.invitation_expire_days` (7 days) | `backend/app/config.py` |
| `settings.access_token_expire_minutes` | `backend/app/config.py` |

## Implementation Order

1. Create model + register in `models/__init__.py`
2. Create schemas
3. Create repository
4. Create service + register in `services/__init__.py`
5. Create routes + register in `routes/v1/__init__.py`
6. Generate Alembic migration
7. Run lint: `uv run ruff check . --fix && uv run ruff format .`
8. Run tests: `uv run pytest -v`

## Verification

1. **Generate migration and apply**: `make create_migration m="add_user_invitation_code_table" && make migrate`
2. **Generate a code** (requires developer auth):
   ```bash
   curl -X POST http://localhost:8000/api/v1/users/{user_id}/invitation-code \
     -H "Authorization: Bearer {dev_token}"
   ```
3. **Redeem the code** (no auth):
   ```bash
   curl -X POST http://localhost:8000/api/v1/invitation-code/redeem \
     -H "Content-Type: application/json" \
     -d '{"code": "A3K9M7X2"}'
   ```
4. Verify response contains `user_id`, `access_token`, `refresh_token`, `expires_in`
5. Verify second redemption of same code returns 404
6. Run existing tests to ensure no regressions

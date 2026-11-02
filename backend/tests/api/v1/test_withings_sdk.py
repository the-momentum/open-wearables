"""Route-level tests for the Withings Mobile SDK endpoints.

The service layer is covered elsewhere; what is only true at the route is covered here — and
one of those things is load-bearing enough that the docstring says so in capitals.

``GET /providers/withings/sdk/session`` resolves the access token FIRST and reads the SDK
account SECOND, because resolving the token may refresh it and a refresh ROTATES the
csrf_token. Read the account first and the response carries the pre-rotation value: valid
looking, and rejected by Withings at WebView-open time, far from the call that caused it.
Nothing about that ordering is visible in a diff, which is exactly why it needs a test that
fails when someone tidies it.

The ordering test asserts the ORDER OF THE CALLS rather than the value in the response.
Mutating the account row would not discriminate: the route builds its response from the ORM
object at the end either way, and SQLAlchemy's identity map hands back the same instance, so a
reordered route would still read the rotated value and the test would pass while the invariant
was broken.
"""

from __future__ import annotations

import logging
from typing import Any
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User
from app.models.user_connection import UserConnection
from app.models.withings_device import WithingsDevice
from app.models.withings_sdk_account import WithingsSdkAccount
from app.schemas.providers.withings.dropshipment import DropshipOrder, DropshipOrderResult
from app.schemas.providers.withings.order_detail import OrderDetail
from app.services.providers.withings.dropshipment import WithingsDropshipmentError
from app.services.providers.withings.order_detail import WithingsOrderDetailError
from app.services.providers.withings.sdk_provisioning import CellularProvisioning
from app.services.providers.withings.sdk_users import WithingsSdkUserError
from tests.factories import UserConnectionFactory, UserFactory
from tests.providers.withings.conftest import add_device, self_linked_connection
from tests.providers.withings.weigh_ins import HASH, SEND, body_group, enable_events, recent, save

_TOKEN = "app.api.routes.v1.withings_sdk._get_valid_token"
_PROVISION = "app.api.routes.v1.withings_sdk.provision_sdk_account"
_PROVISION_CELLULAR = "app.api.routes.v1.withings_sdk.provision_cellular_order"

_ACCOUNTS_URL = "/api/v1/providers/withings/sdk/accounts"
_SESSION_URL = "/api/v1/providers/withings/sdk/session"
_CELLULAR_URL = "/api/v1/providers/withings/cellular/orders"
_ORDERS_URL = "/api/v1/providers/withings/orders"
_CREATE_ORDER = "app.api.routes.v1.withings_sdk.create_order"
_ALREADY_PLACED = "Withings already hold an order for this customer_ref_id; it was already placed"

# The bare CustomerProfile id — what robin-backend sends, and the same on a member's every order,
# because Withings reuse the account their first one created. Which ORDER a shipment belongs to is
# ``customer_ref_id`` on the order itself, below.
_EXTERNAL_ID = "11111111-2222-3333-4444-555555555555"
_ORDER_REF = "01K5ZQ8MZ0XJ7R2T4V6W8Y"
_GET_ORDER_DETAIL = "app.api.routes.v1.withings_sdk.get_order_detail"


@pytest.fixture
def withings_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    """Provisioning answers 503 unless the deployment has partner credentials."""
    monkeypatch.setattr(settings, "withings_client_id", "test-client-id")
    monkeypatch.setattr(settings, "withings_client_secret", SecretStr("test-client-secret"))


def _valid_payload(**overrides: Any) -> dict[str, Any]:
    payload = {
        "user_id": str(uuid4()),
        "external_id": "robin-user-1",
        "email": "member@example.com",
        "shortname": "FRA",
        "birthdate": 643248000,
        "gender": 0,
        "weight_kg": 75.4,
        "height_m": 1.78,
        "preflang": "it_IT",
        "timezone": "Europe/Rome",
        "mailingpref": 0,
    }
    payload.update(overrides)
    return payload


def _valid_cellular_payload(**overrides: Any) -> dict[str, Any]:
    """The SDK profile plus the two fields ``createuserorder`` adds: ``unit_pref`` and ``orders``."""
    payload = _valid_payload(external_id=_EXTERNAL_ID)
    payload.update(
        {
            "unit_pref": {"weight": 1, "height": 6},
            "orders": [
                {
                    "customer_ref_id": _ORDER_REF,
                    "address": {
                        "name": "Francesco Rossi",
                        "email": "member@example.com",
                        "address1": "Via Roma 1",
                        "city": "Milano",
                        "zip": "20121",
                        "country": "IT",
                    },
                    "products": [{"quantity": 1, "ean": "3700546705526"}],
                }
            ],
        }
    )
    payload.update(overrides)
    return payload


def _provisioning() -> CellularProvisioning:
    """A successful provisioning, for the tests that only care about what was sent."""
    return CellularProvisioning(
        account=WithingsSdkAccount(
            id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
        ),
        orders=[DropshipOrderResult(orderid="WO-1", status="PENDING")],
    )


def _connected_member(db: Session, *, csrf_token: str | None, with_account: bool = True) -> User:
    """A member with a Withings connection, optionally SDK-provisioned."""
    user = UserFactory()
    connection = UserConnectionFactory(user=user, provider="withings", provider_user_id="withings-1")
    if with_account:
        account = WithingsSdkAccount(
            id=uuid4(),
            user_connection_id=connection.id,
            external_id=f"robin-{uuid4().hex[:8]}",
            csrf_token=csrf_token,
            updated_at=connection.updated_at,
        )
        db.add(account)
        db.commit()
    return user


class TestSessionRoute:
    def test_returns_both_halves_of_the_pair(
        self, client: TestClient, db: Session, api_key_header: dict[str, str]
    ) -> None:
        user = _connected_member(db, csrf_token="csrf-current")

        with patch(_TOKEN, return_value="access-current"):
            response = client.get(_SESSION_URL, params={"user_id": str(user.id)}, headers=api_key_header)

        assert response.status_code == 200
        assert response.json() == {"access_token": "access-current", "csrf_token": "csrf-current"}

    def test_resolves_the_token_before_reading_the_account(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # THE ordering invariant — see the module docstring for why this asserts call order
        # rather than the returned value.
        user = _connected_member(db, csrf_token="csrf-current")
        calls: list[str] = []

        original_query = db.query

        def spy_query(*args: Any, **kwargs: Any) -> Any:
            if args and args[0] is WithingsSdkAccount:
                calls.append("read_account")
            return original_query(*args, **kwargs)

        monkeypatch.setattr(db, "query", spy_query)

        def fake_token(*_args: Any, **_kwargs: Any) -> str:
            calls.append("resolve_token")
            return "access-current"

        with patch(_TOKEN, side_effect=fake_token):
            response = client.get(_SESSION_URL, params={"user_id": str(user.id)}, headers=api_key_header)

        assert response.status_code == 200
        assert calls == ["resolve_token", "read_account"], (
            "the token must be resolved first: resolving it may refresh, and a refresh rotates csrf_token"
        )

    def test_404_when_the_member_was_never_sdk_provisioned(
        self, client: TestClient, db: Session, api_key_header: dict[str, str]
    ) -> None:
        # Connected via phase-1 consumer OAuth. A distinct condition from "not connected".
        user = _connected_member(db, csrf_token=None, with_account=False)

        with patch(_TOKEN, return_value="access-current"):
            response = client.get(_SESSION_URL, params={"user_id": str(user.id)}, headers=api_key_header)

        assert response.status_code == 404
        assert "no Withings SDK account" in response.json()["detail"]

    def test_404_for_a_member_whose_sold_scale_is_on_their_own_account(
        self, client: TestClient, db: Session, api_key_header: dict[str, str]
    ) -> None:
        # Spec O4: the WebViews act on an account WE created; a tagged device on the member's own
        # account does not make one.
        user, own = self_linked_connection(db)
        add_device(db, own, "bodycomp-1", hash_device_id="bc-hash", order_ref="ORDER-1")
        db.commit()

        with patch(_TOKEN, return_value="access-current"):
            response = client.get(_SESSION_URL, params={"user_id": str(user.id)}, headers=api_key_header)

        assert response.status_code == 404
        assert "no Withings SDK account" in response.json()["detail"]

    def test_409_when_the_account_has_no_csrf_token(
        self, client: TestClient, db: Session, api_key_header: dict[str, str]
    ) -> None:
        user = _connected_member(db, csrf_token=None)

        with patch(_TOKEN, return_value="access-current"):
            response = client.get(_SESSION_URL, params={"user_id": str(user.id)}, headers=api_key_header)

        assert response.status_code == 409
        assert "re-provision" in response.json()["detail"]

    def test_requires_authentication(self, client: TestClient, db: Session) -> None:
        user = _connected_member(db, csrf_token="csrf-current")

        response = client.get(_SESSION_URL, params={"user_id": str(user.id)})

        assert response.status_code == 401


class TestProvisioningRoute:
    def test_returns_what_provisioning_stored(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        account = WithingsSdkAccount(
            id=uuid4(), user_connection_id=uuid4(), external_id="robin-user-1", csrf_token="csrf-new"
        )

        with patch(_PROVISION, return_value=account):
            response = client.post(_ACCOUNTS_URL, json=_valid_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert response.json() == {"external_id": "robin-user-1", "csrf_token": "csrf-new"}

    def test_503_when_the_deployment_has_no_withings_credentials(
        self, client: TestClient, api_key_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        # An operator condition, not a bad request — and the default state of a deployment
        # that has not been given partner credentials.
        monkeypatch.setattr(settings, "withings_client_id", None)

        response = client.post(_ACCOUNTS_URL, json=_valid_payload(), headers=api_key_header)

        assert response.status_code == 503

    def test_400_when_provisioning_rejects_the_input_locally(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with patch(_PROVISION, side_effect=ValueError("shortname must be exactly 3 alphanumerics")):
            response = client.post(_ACCOUNTS_URL, json=_valid_payload(), headers=api_key_header)

        assert response.status_code == 400

    def test_502_without_echoing_the_upstream_detail(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The upstream body answers a SIGNED request and may repeat our parameters back, which
        # carry the member's email, birth date and weight.
        error = WithingsSdkUserError(withings_status=503, detail="createuser failed for member@example.com")

        with patch(_PROVISION, side_effect=error):
            response = client.post(_ACCOUNTS_URL, json=_valid_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert "member@example.com" not in response.json()["detail"]
        assert "status=503" in response.json()["detail"]

    def test_502_when_withings_returned_no_csrf_token(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The column is nullable, so the invariant is asserted rather than assumed: handing
        # back a null the client cannot use would fail later and further away.
        account = WithingsSdkAccount(
            id=uuid4(), user_connection_id=uuid4(), external_id="robin-user-1", csrf_token=None
        )

        with patch(_PROVISION, return_value=account):
            response = client.post(_ACCOUNTS_URL, json=_valid_payload(), headers=api_key_header)

        assert response.status_code == 502

    def test_400_when_the_account_already_exists(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # A duplicate account is the CALLER's state, not a server fault, and this route has always
        # answered 400 for it. It used to do so by accident — an HTTPException raised by the
        # repository's @handle_exceptions and allowed to escape into the service layer — and the
        # store no longer goes through the repository (open-wearables#12). The shape was right, so
        # it is now the route's own decision, driven by `already_exists`, and pinned here.
        error = WithingsSdkUserError(
            detail="the Withings account was created but could not be stored", already_exists=True
        )

        with patch(_PROVISION, side_effect=error):
            response = client.post(_ACCOUNTS_URL, json=_valid_payload(), headers=api_key_header)

        assert response.status_code == 400

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("email", "not-an-email"),
            ("shortname", "TOOLONG"),
            ("shortname", "AB"),
            ("gender", 2),
            ("mailingpref", 7),
            ("weight_kg", 0),
            ("height_m", -1),
        ],
    )
    def test_400_on_input_withings_would_reject_opaquely(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
        withings_configured: None,
        field: str,
        value: Any,
    ) -> None:
        # Every one of these comes back from Withings as a non-zero status with no field name
        # attached, surfacing as a 502 the caller can do nothing with. Caught here instead.
        #
        # 400 and not FastAPI's default 422: this app registers its own RequestValidationError
        # handler (main.py:91, utils/exceptions.py:88-95) which remaps it. Asserting 422 here
        # would be asserting the framework's contract instead of this deployment's, and the
        # robin-backend proxy reads the status.
        with patch(_PROVISION) as provision:
            response = client.post(_ACCOUNTS_URL, json=_valid_payload(**{field: value}), headers=api_key_header)

        assert response.status_code == 400
        # A rejected request must not reach Withings.
        provision.assert_not_called()


class TestCellularOrderRoute:
    """The HTTP surface ``provision_cellular_order`` did not have.

    ``#8`` shipped the client and the service and no route, so the function was reachable from
    Python and from nowhere else — which meant robin-backend, the only caller there will ever
    be, could not place an order at all. These tests pin the route, not the provisioning
    beneath it: that has its own suite in ``tests/providers/withings``.
    """

    @pytest.fixture(autouse=True)
    def _no_order_already_placed(self) -> Any:
        """Answer the pre-flight with "Withings hold no such order" unless a test says otherwise.

        Every request through this route now asks ``orderv2-getdetail`` first. Left unpatched that
        is a real signed HTTP call, so it is stubbed for the whole class and overridden by the two
        tests that are actually about the pre-flight — which keeps those two readable and stops
        every other test in here from silently depending on network behaviour.
        """
        with patch(_GET_ORDER_DETAIL, return_value=[]) as stub:
            yield stub

    def test_returns_the_account_and_the_orders_separately(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The two halves go to different systems — the account is ours, the orders are
        # robin-backend's. A route returning only the account would strand a placed order with
        # no id to track it by, after the parcel had already been committed to.
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid="WO-1", status="PENDING")],
        )

        with patch(_PROVISION_CELLULAR, return_value=provisioning) as provision:
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        body = response.json()
        assert body["external_id"] == _EXTERNAL_ID
        assert body["csrf_token"] == "csrf-new"
        # Field-wise rather than dict-equal: DropshipOrderResult carries a nullable echoed
        # ``address`` and is ``extra="allow"``, because Withings adds keys to it. An exact-shape
        # assertion here would fail the day they do, on a response that was perfectly fine.
        assert [(o["orderid"], o["status"]) for o in body["orders"]] == [("WO-1", "PENDING")]
        assert provision.call_args.kwargs["testmode"] is False

    def test_forwards_testmode_when_asked(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The only way to exercise the whole path without shipping hardware, and therefore the
        # first thing that will be run once the dropshipment entitlement lands. A route that
        # accepted the flag and dropped it would look like it worked and ship a real device.
        with patch(_PROVISION_CELLULAR, return_value=_provisioning()) as provision:
            client.post(_CELLULAR_URL, json=_valid_cellular_payload(testmode=True), headers=api_key_header)

        assert provision.call_args.kwargs["testmode"] is True

    def test_passes_the_order_block_through_as_models(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # ``create_user_order`` signs a payload built from these objects. Handing the service a
        # list of dicts instead would fail inside the signature step, after the request shape
        # had already been accepted.
        with patch(_PROVISION_CELLULAR, return_value=_provisioning()) as provision:
            client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        orders = provision.call_args.kwargs["orders"]
        assert [type(o) for o in orders] == [DropshipOrder]
        assert orders[0].customer_ref_id == "01K5ZQ8MZ0XJ7R2T4V6W8Y"
        assert orders[0].address.country == "IT"

    def test_an_order_with_no_orderid_is_resolved_from_getdetail(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
        withings_configured: None,
    ) -> None:
        """The 2026-09-16 shape: status 0, a real order, and no `orderid` on it.

        Withings answered a LIVE createuserorder this way and a device shipped against order
        `D0820568`. The documented example has `orderid` present, so nothing in the contract said
        to expect this — and the caller reads a missing id as "no order was placed", which is the
        opposite of the truth and leaves a parcel nothing can name.
        """
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid=None, status="VERIFIED")],
        )
        # A local patch shadows the class-wide autouse stub: empty for the pre-flight, then the
        # placed order for the resolve. The order mirrors the real sequence.
        detail = [
            [],
            [OrderDetail(order_id="D0820568", customer_ref_id="01K5ZQ8MZ0XJ7R2T4V6W8Y", status="VERIFIED")],
        ]

        with patch(_PROVISION_CELLULAR, return_value=provisioning), patch(_GET_ORDER_DETAIL, side_effect=detail):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert [o["orderid"] for o in response.json()["orders"]] == ["D0820568"]

    def test_a_resolvable_id_costs_no_extra_call_when_withings_already_sent_one(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
        withings_configured: None,
    ) -> None:
        # The common path must not spend a second signed request — the Withings budget is shared
        # and the pre-flight already spends one per fulfilment. One call, the pre-flight's.
        with (
            patch(_PROVISION_CELLULAR, return_value=_provisioning()),
            patch(_GET_ORDER_DETAIL, return_value=[]) as detail,
        ):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert detail.call_count == 1

    def test_the_order_still_comes_back_when_the_resolve_fails(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
        withings_configured: None,
    ) -> None:
        # By the time this runs the order is placed and the csrf_token is single-use. Raising here
        # would lose the member their account to save a field — so a failed resolve degrades to
        # the id-less order, which is exactly what Withings said.
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid=None, status="VERIFIED")],
        )
        detail = [[], WithingsOrderDetailError(withings_status=503)]

        with patch(_PROVISION_CELLULAR, return_value=provisioning), patch(_GET_ORDER_DETAIL, side_effect=detail):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert response.json()["csrf_token"] == "csrf-new"
        assert [o["orderid"] for o in response.json()["orders"]] == [None]

    def test_the_order_still_comes_back_when_the_budget_is_exhausted(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        """The escape that actually threatens the account, and it is not this module's own error.

        `get_order_detail` calls `acquire_request_slot()` outside its try, so an exhausted Withings
        budget leaves as `HTTPException` 429 — and the pre-flight on this very request has already
        spent a slot, so it is the likely failure rather than a theoretical one. Uncaught it
        escapes AFTER the order shipped and the single-use csrf_token was minted, which loses the
        member their account to enrich a field (ross, #15).
        """
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid=None, status="VERIFIED")],
        )
        budget_exhausted = HTTPException(status_code=429, detail="Withings request budget exhausted")

        with (
            patch(_PROVISION_CELLULAR, return_value=provisioning),
            patch(_GET_ORDER_DETAIL, side_effect=[[], budget_exhausted]),
        ):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201, "a 429 on an optional enrichment must not become the answer"
        assert response.json()["csrf_token"] == "csrf-new"

    def test_the_order_still_comes_back_when_signing_fails_on_the_resolve(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The other way out that is not a WithingsOrderDetailError: `sign_payload` also sits outside
        # that try. Different cause, identical stake — so the catch is on Exception, and this is the
        # case that stops it being narrowed back to a tidy-looking union.
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid=None, status="VERIFIED")],
        )

        with (
            patch(_PROVISION_CELLULAR, return_value=provisioning),
            patch(_GET_ORDER_DETAIL, side_effect=[[], RuntimeError("could not sign the payload")]),
        ):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert response.json()["csrf_token"] == "csrf-new"

    def test_it_fills_nothing_when_withings_know_no_order_for_the_ref(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        """Pins the SECOND half of the match guard, which nothing else here reaches.

        `getdetail` can succeed and still know nothing for a ref `createuserorder` acknowledged
        seconds earlier — the same race this PR exists for, one step later. It also happens
        whenever every id it returns is one we already hold.

        Delete ` and len(unaccounted) == 1` from the guard and every other test in this class still
        passes, while `unaccounted[0]` becomes an IndexError on an empty list — raised OUTSIDE the
        try, which wraps only the `get_order_detail` call. That escapes, 500s the handler, and
        loses the member the account that was just created with the parcel already committed:
        exactly the outcome the docstring's first bullet forbids, reached through the match rather
        than through the call (Lucas, #15).
        """
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid=None, status="VERIFIED")],
        )

        with (
            patch(_PROVISION_CELLULAR, return_value=provisioning),
            patch(_GET_ORDER_DETAIL, side_effect=[[], []]),
        ):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert response.json()["csrf_token"] == "csrf-new"
        assert [o["orderid"] for o in response.json()["orders"]] == [None]

    def test_it_fills_nothing_when_every_id_getdetail_knows_is_one_we_hold(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The other way to reach an empty `unaccounted` with one order still missing: two orders,
        # one already identified, and getdetail answering only about that one. Same IndexError, and
        # it does not need a race to happen.
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid="D0820568"), DropshipOrderResult(orderid=None)],
        )

        with (
            patch(_PROVISION_CELLULAR, return_value=provisioning),
            patch(_GET_ORDER_DETAIL, side_effect=[[], [OrderDetail(order_id="D0820568", customer_ref_id="ref-a")]]),
        ):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert [o["orderid"] for o in response.json()["orders"]] == ["D0820568", None]

    def test_it_refuses_to_guess_which_parcel_an_id_belongs_to(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
        withings_configured: None,
    ) -> None:
        # createuserorder echoes no customer_ref_id on its order entries, so with two unidentified
        # orders the only link is position. Writing one parcel's id onto another is invisible until
        # someone terminates the wrong device, so the ambiguous case fills nothing.
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token="csrf-new"
            ),
            orders=[DropshipOrderResult(orderid=None, status="VERIFIED"), DropshipOrderResult(orderid=None)],
        )
        detail = [
            [],
            [
                OrderDetail(order_id="D0820568", customer_ref_id="ref-a"),
                OrderDetail(order_id="D0820569", customer_ref_id="ref-b"),
            ],
        ]

        with patch(_PROVISION_CELLULAR, return_value=provisioning), patch(_GET_ORDER_DETAIL, side_effect=detail):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201
        assert [o["orderid"] for o in response.json()["orders"]] == [None, None]

    def test_requires_authentication(self, client: TestClient) -> None:
        response = client.post(_CELLULAR_URL, json=_valid_cellular_payload())

        assert response.status_code == 401

    def test_503_when_the_deployment_has_no_withings_credentials(
        self, client: TestClient, api_key_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "withings_client_id", None)

        response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 503

    def test_400_when_provisioning_rejects_the_input_locally(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with patch(_PROVISION_CELLULAR, side_effect=ValueError("unit_pref must not be empty")):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 400

    def test_502_without_echoing_the_upstream_detail(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # Worse here than on the SDK route: this request also carried the member's HOME ADDRESS,
        # and the upstream body answers a signed payload that contains it.
        error = WithingsDropshipmentError(withings_status=277, detail="createuserorder refused for Via Roma 1, Milano")

        with patch(_PROVISION_CELLULAR, side_effect=error):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert "Via Roma" not in response.text
        assert "status=277" in response.json()["detail"]

    def test_400_when_an_order_carries_no_products(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # An empty order is accepted by nothing downstream, and Withings answers it with an
        # opaque status AFTER creating the account — leaving a member with a Withings account
        # and no device on the way.
        payload = _valid_cellular_payload()
        payload["orders"][0]["products"] = []

        with patch(_PROVISION_CELLULAR) as provision:
            response = client.post(_CELLULAR_URL, json=payload, headers=api_key_header)

        assert response.status_code == 400
        provision.assert_not_called()

    def test_400_when_no_order_is_attached_at_all(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # ``createuserorder`` with an empty ``order`` list creates the account and ships
        # nothing, which is the one success this integration must never report.
        with patch(_PROVISION_CELLULAR) as provision:
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(orders=[]), headers=api_key_header)

        assert response.status_code == 400
        provision.assert_not_called()

    def test_502_when_withings_returned_no_csrf_token(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # Same invariant as the SDK route: the column is nullable and a null is unusable by the
        # caller, so it is asserted here rather than discovered at WebView-open time.
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token=None
            ),
            orders=[DropshipOrderResult(orderid="WO-1", status="PENDING")],
        )

        with patch(_PROVISION_CELLULAR, return_value=provisioning):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 502

    def test_400_when_unit_pref_is_empty(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # Lucas's finding on #12: the PR claimed three rejection cases were verified and only two
        # were pinned. Worth pinning specifically because this one's failure mode is the only one
        # in the payload whose consequence is a SUCCESS — dropshipment.py:111, "a successful order
        # for a device that renders the wrong units on its own screen, and nothing downstream ever
        # flags it". If a refactor drops the Field(...) for a plain dict annotation, min_length
        # silently stops applying and nothing else here notices.
        with patch(_PROVISION_CELLULAR) as provision:
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(unit_pref={}), headers=api_key_header)

        assert response.status_code == 400
        provision.assert_not_called()

    def test_502_when_the_code_exchange_fails_after_the_order_was_placed(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # `exchange_sdk_code` raises WithingsSdkUserError, and it runs AFTER createuserorder has
        # placed the order. Before this handler existed the exception escaped both `except`
        # clauses and the caller got a bare 500 with a device already shipping.
        error = WithingsSdkUserError(withings_status=401, detail="signature invalid for Via Roma 1")

        with patch(_PROVISION_CELLULAR, side_effect=error):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert "status=401" in response.json()["detail"]
        # The 500 this replaced did not leak either — FastAPI answers a bare "Internal Server
        # Error" — but the detail we now choose ourselves must not start leaking what that did not.
        assert "Via Roma" not in response.text

    def test_409_when_withings_already_hold_this_order(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # THE RETRY CASE, and the reason the check runs before any Withings call. robin-backend
        # retries fulfillWithingsDeviceOrder after a timeout with the SAME customer_ref_id;
        # without this, that ordinary retry places a SECOND ORDER — a real parcel — before
        # anything here can object. `provision.assert_not_called()` is the whole point.
        #
        # It asks Withings rather than our own tables. The old check looked for a
        # withings_sdk_account carrying this external_id, which worked only while external_id was
        # per-order: it is now per member and stable, so "an account exists" is true from a
        # member's FIRST order onward and would refuse every legitimate second one.
        already = OrderDetail(order_id="D1", customer_ref_id=_ORDER_REF, status="PROCESSING")

        with patch(_GET_ORDER_DETAIL, return_value=[already]) as detail, patch(_PROVISION_CELLULAR) as provision:
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 409
        provision.assert_not_called()
        assert detail.call_args.kwargs["customer_ref_ids"] == [_ORDER_REF]

    def test_a_members_second_order_is_allowed_through(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The positive control for the test above, and the regression the old pre-flight WOULD
        # have caused. This member already holds a provisioned account under this exact
        # external_id — the account their first order created, which Withings will reuse — and the
        # order in the payload is a new one. It must ship.
        connection = UserConnectionFactory(provider="withings", provider_user_id="withings-first")
        db.add(
            WithingsSdkAccount(
                id=uuid4(),
                user_connection_id=connection.id,
                external_id=_EXTERNAL_ID,
                csrf_token="csrf-first",
                # NOT NULL with no server default; a fixture building the row directly has to set
                # it, the same way `_upsert_sdk_account` always does.
                updated_at=connection.updated_at,
            )
        )
        db.commit()

        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=connection.id, external_id=_EXTERNAL_ID, csrf_token="csrf-second"
            ),
            orders=[DropshipOrderResult(orderid="WO-2", status="PENDING")],
        )

        with patch(_GET_ORDER_DETAIL, return_value=[]), patch(_PROVISION_CELLULAR, return_value=provisioning):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 201, "an existing account must not block a member's second order"

    def test_502_when_the_pre_flight_cannot_reach_withings(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # "We could not find out whether this order exists" and "this order does not exist" are
        # different facts, and treating the first as the second is precisely how a retry ships
        # twice. So a failed lookup refuses rather than pushing through.
        #
        # 502 and not 409: getdetail changes nothing at Withings, so this IS safe to retry — the
        # opposite of a 502 from the order call itself, which may have shipped.
        with (
            patch(_GET_ORDER_DETAIL, side_effect=WithingsOrderDetailError(detail="upstream down")),
            patch(_PROVISION_CELLULAR) as provision,
        ):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 502
        provision.assert_not_called()

    def test_409_when_a_concurrent_provisioning_won_the_unique_race(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The pre-flight is a TOCTOU narrowing, not a fix: two simultaneous retries can both pass
        # it and both reach Withings. The loser must still get an answer meaning "already placed,
        # do not retry" rather than one a generic retry policy would act on.
        #
        # Raises what the SERVICE actually raises. This test used to inject a bare IntegrityError,
        # which cannot happen: every write in `_store_provisioned_account` is inside a try that
        # converts it to `store_error`. So it passed against a route branch nothing could reach
        # while the real race answered 502 — found by Lucas measuring the live path on #12, not by
        # this test, which is the definition of a false pin.
        error = WithingsDropshipmentError(
            detail="the Withings account was created but could not be stored: it already exists",
            already_exists=True,
        )

        with patch(_PROVISION_CELLULAR, side_effect=error):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    def test_a_dropshipment_error_with_no_status_does_not_render_status_none(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # `withings_status` is set only on the non-zero-envelope branch; the transport branch and
        # the detail-only raises leave it None. "status=None" reads as though Withings answered
        # without a status, which is the wrong diagnosis for a transport failure — and the first
        # real exercise of this route is exactly when that distinction matters.
        error = WithingsDropshipmentError(detail="the request to Withings could not be completed")

        with patch(_PROVISION_CELLULAR, side_effect=error):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert "status=None" not in response.json()["detail"]
        assert "could not be completed" in response.json()["detail"]

    def test_the_placed_orders_are_logged_before_a_missing_csrf_token_discards_them(
        self,
        client: TestClient,
        api_key_header: dict[str, str],
        withings_configured: None,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        # Raising throws `result.orders` away, and this fork stores nothing about an order by
        # design — so the order ids exist in that value and nowhere else. Losing them leaves a
        # shipment nothing can track and that end_program can never terminate.
        provisioning = CellularProvisioning(
            account=WithingsSdkAccount(
                id=uuid4(), user_connection_id=uuid4(), external_id=_EXTERNAL_ID, csrf_token=None
            ),
            orders=[DropshipOrderResult(orderid="WO-STRANDED", status="PENDING")],
        )

        with patch(_PROVISION_CELLULAR, return_value=provisioning), caplog.at_level(logging.ERROR):
            response = client.post(_CELLULAR_URL, json=_valid_cellular_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert any("WO-STRANDED" in str(record.orders) for record in caplog.records if hasattr(record, "orders"))


class TestCellularOrderDetailRoute:
    """``GET /withings/cellular/orders/{customer_ref_id}`` — where a device MAC comes from.

    The MAC is the field with money attached. ``Devicev2-endpartnerprogram`` ends a member's
    cellular plan and is addressed by MAC address; ``end_program`` has been written and
    unreachable since #7 because nothing produced one. The ``createuserorder`` response carries no
    MAC, this fork stores none, and Withings populate them only once the parcel has shipped — so
    this route is the first link in the chain that ends a plan, and without it a member who leaves
    keeps costing us a SIM every month.
    """

    _URL = "/api/v1/providers/withings/cellular/orders/01K5ZQ8MZ0XJ7R2T4V6W8Y"
    _LOOKUP = "app.api.routes.v1.withings_sdk.get_order_detail"

    def test_flattens_the_macs_for_the_caller(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # Lifted to the top level rather than left inside orders[].products[].devices[]: the
        # caller hands this straight to owWithingsDisconnect, and burying it three levels down
        # invites each caller to walk the structure differently.
        order = OrderDetail.model_validate(
            {
                "order_id": "D1",
                "customer_ref_id": _ORDER_REF,
                "status": "SHIPPED",
                "products": [
                    {"mac_addresses": ["00:24:e4:aa:bb:cc"], "devices": [{"mac_address": "00:24:e4:dd:ee:ff"}]}
                ],
            }
        )

        with patch(self._LOOKUP, return_value=[order]) as lookup:
            response = client.get(self._URL, headers=api_key_header)

        assert response.status_code == 200
        assert response.json()["macs"] == ["00:24:e4:aa:bb:cc", "00:24:e4:dd:ee:ff"]
        assert lookup.call_args.kwargs["customer_ref_ids"] == [_ORDER_REF]

    def test_returns_the_raw_orders_beside_the_macs(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # Shipment state is robin-backend's. This fork must not become the thing that decides
        # which of Withings' fields matter, so the whole answer travels with the convenience one.
        order = OrderDetail(order_id="D1", customer_ref_id=_ORDER_REF, status="SHIPPED", parcel_status="in_transit")

        with patch(self._LOOKUP, return_value=[order]):
            body = client.get(self._URL, headers=api_key_header).json()

        assert body["orders"][0]["status"] == "SHIPPED"
        assert body["orders"][0]["parcel_status"] == "in_transit"

    def test_an_unshipped_order_is_200_with_no_macs(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # Not a 404 and not an error: the order exists, Withings simply have not assigned hardware
        # to it yet. A caller polling for MACs needs to tell that apart from a reference nobody
        # knows, which is the next test.
        order = OrderDetail(order_id="D1", customer_ref_id=_ORDER_REF, status="PROCESSING")

        with patch(self._LOOKUP, return_value=[order]):
            response = client.get(self._URL, headers=api_key_header)

        assert response.status_code == 200
        assert response.json()["macs"] == []

    def test_404_when_withings_do_not_know_the_reference(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with patch(self._LOOKUP, return_value=[]):
            response = client.get(self._URL, headers=api_key_header)

        assert response.status_code == 404

    def test_the_same_mac_on_two_orders_is_returned_once(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # A replacement shipment can repeat a MAC. End of Program is addressed by MAC, so a
        # duplicate is a second termination call for a device already terminated.
        shared = {"products": [{"mac_addresses": ["00:24:e4:aa:bb:cc"]}]}
        orders = [OrderDetail.model_validate(shared), OrderDetail.model_validate(shared)]

        with patch(self._LOOKUP, return_value=orders):
            body = client.get(self._URL, headers=api_key_header).json()

        assert body["macs"] == ["00:24:e4:aa:bb:cc"]

    def test_502_and_no_address_in_the_body_when_withings_decline(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The response this wraps echoes the order, and an order carries the member's home
        # address. Same rule the order-placing route follows for its own 4xx detail.
        with patch(self._LOOKUP, side_effect=WithingsOrderDetailError(withings_status=277)):
            response = client.get(self._URL, headers=api_key_header)

        assert response.status_code == 502
        assert "Via Roma" not in response.text
        assert "277" in response.json()["detail"]

    def test_requires_a_credential(self, client: TestClient, withings_configured: None) -> None:
        # It reads one member's order — address, carrier, hardware identifiers — from our partner
        # credentials. ApiKeyDep is the same gate the rest of this module uses.
        assert client.get(self._URL).status_code in (401, 403)

    def test_503_when_the_deployment_has_no_withings_credentials(
        self, client: TestClient, api_key_header: dict[str, str]
    ) -> None:
        # An operator condition, not a bad request — the same answer the two provisioning routes
        # give. Deliberately without the `withings_configured` fixture.
        assert client.get(self._URL, headers=api_key_header).status_code == 503


_ORDER_REF_URL = "/api/v1/providers/withings/sdk/devices/{device_id}/order-ref"


class TestOrderRefRoute:
    def _device(self, db: Session, make_provisioned_connection: Any) -> tuple[User, WithingsDevice]:
        user, connection = make_provisioned_connection()
        device = WithingsDevice(
            id=uuid4(), user_connection_id=connection.id, device_id="dev-1", updated_at=connection.updated_at
        )
        db.add(device)
        db.commit()
        return user, device

    def _put(self, client: TestClient, user: User, body: dict, headers: dict[str, str] | None = None) -> Any:
        return client.put(
            _ORDER_REF_URL.format(device_id="dev-1"),
            params={"user_id": str(user.id)},
            json=body,
            headers=headers or {},
        )

    def test_sets_the_ref(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        user, _ = self._device(db, make_provisioned_connection)
        r = self._put(client, user, {"order_ref": "REF-1"}, api_key_header)
        assert r.status_code == 200
        assert r.json()["device_id"] == "dev-1"
        assert db.query(WithingsDevice).filter_by(device_id="dev-1").one().order_ref == "REF-1"

    def test_repeat_is_200_and_unchanged(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        user, _ = self._device(db, make_provisioned_connection)
        bodies = [self._put(client, user, {"order_ref": "REF-1"}, api_key_header) for _ in range(2)]
        assert [b.status_code for b in bodies] == [200, 200]
        assert bodies[0].json() == bodies[1].json()

    def test_a_different_ref_overwrites(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        user, _ = self._device(db, make_provisioned_connection)
        self._put(client, user, {"order_ref": "REF-1"}, api_key_header)
        r = self._put(client, user, {"order_ref": "REF-2"}, api_key_header)
        assert r.status_code == 200
        assert db.query(WithingsDevice).filter_by(device_id="dev-1").one().order_ref == "REF-2"

    def test_404_for_a_device_not_on_this_user(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        self._device(db, make_provisioned_connection)
        stranger, _ = make_provisioned_connection()
        assert self._put(client, stranger, {"order_ref": "REF-1"}, api_key_header).status_code == 404

    def test_404_for_a_member_with_no_withings_connection(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        self._device(db, make_provisioned_connection)
        assert self._put(client, UserFactory(), {"order_ref": "REF-1"}, api_key_header).status_code == 404

    @pytest.mark.parametrize("bad", ["", "x" * 65])
    def test_400_on_a_bad_ref(
        self,
        client: TestClient,
        db: Session,
        api_key_header: dict[str, str],
        make_provisioned_connection: Any,
        bad: str,
    ) -> None:
        user, _ = self._device(db, make_provisioned_connection)
        assert self._put(client, user, {"order_ref": bad}, api_key_header).status_code == 400  # app maps 422 to 400

    def test_requires_authentication(self, client: TestClient, db: Session, make_provisioned_connection: Any) -> None:
        user, _ = self._device(db, make_provisioned_connection)
        assert self._put(client, user, {"order_ref": "REF-1"}).status_code == 401

    def test_a_padded_ref_is_stored_stripped_and_a_clean_resend_is_a_noop(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        user, _ = self._device(db, make_provisioned_connection)
        assert self._put(client, user, {"order_ref": " REF-1 "}, api_key_header).status_code == 200
        stamp = db.query(WithingsDevice).filter_by(device_id="dev-1").one().updated_at

        assert self._put(client, user, {"order_ref": "REF-1"}, api_key_header).status_code == 200

        db.expire_all()
        device = db.query(WithingsDevice).filter_by(device_id="dev-1").one()
        assert device.order_ref == "REF-1"
        assert device.updated_at == stamp

    def test_400_on_a_whitespace_only_ref(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        user, _ = self._device(db, make_provisioned_connection)
        assert self._put(client, user, {"order_ref": "   "}, api_key_header).status_code == 400

    def test_tags_a_device_on_the_members_own_account(
        self, client: TestClient, db: Session, api_key_header: dict[str, str]
    ) -> None:
        user = UserFactory()
        connection = UserConnectionFactory(user=user, provider="withings", provider_user_id="own")
        db.add(
            WithingsDevice(
                id=uuid4(), user_connection_id=connection.id, device_id="dev-1", updated_at=connection.updated_at
            )
        )
        db.commit()

        assert self._put(client, user, {"order_ref": "REF-1"}, api_key_header).status_code == 200
        assert db.query(WithingsDevice).filter_by(device_id="dev-1").one().order_ref == "REF-1"

    def test_404_and_no_write_for_a_device_on_another_members_own_account(
        self, client: TestClient, db: Session, api_key_header: dict[str, str]
    ) -> None:
        _, own = self_linked_connection(db)
        add_device(db, own, "dev-1")
        stranger, _ = self_linked_connection(db)
        db.commit()

        assert self._put(client, stranger, {"order_ref": "REF-1"}, api_key_header).status_code == 404
        assert db.query(WithingsDevice).filter_by(device_id="dev-1").one().order_ref is None

    def test_tagging_a_self_linked_scale_announces_its_recent_weigh_in_once(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        enable_events(monkeypatch)
        user, own = self_linked_connection(db, external_user_id="cp-route-1")
        add_device(db, own, "dev-1", hash_device_id=HASH)
        with patch(SEND) as send:
            save(db, user.id, own.id, [body_group(recent(), attrib=0)])
            first = self._put(client, user, {"order_ref": "REF-1"}, api_key_header)
            again = self._put(client, user, {"order_ref": "REF-1"}, api_key_header)

        assert (first.status_code, again.status_code) == (200, 200)
        assert [c.kwargs["args"][0]["external_user_id"] for c in send.call_args_list] == ["cp-route-1"]


class TestDeviceHashDeviceIdInResponse:
    def _get(self, client: TestClient, user: User, headers: dict[str, str]) -> Any:
        return client.get("/api/v1/providers/withings/sdk/devices", params={"user_id": str(user.id)}, headers=headers)

    def test_list_carries_hash_deviceid(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        user, connection = make_provisioned_connection()
        db.add(
            WithingsDevice(
                id=uuid4(),
                user_connection_id=connection.id,
                device_id="dev-1",
                hash_device_id="hash-1",
                updated_at=connection.updated_at,
            )
        )
        db.commit()
        r = self._get(client, user, api_key_header)
        assert r.status_code == 200
        assert r.json()[0]["hash_deviceid"] == "hash-1"

    def test_absent_hash_is_a_present_null(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], make_provisioned_connection: Any
    ) -> None:
        user, connection = make_provisioned_connection()
        db.add(
            WithingsDevice(
                id=uuid4(), user_connection_id=connection.id, device_id="dev-1", updated_at=connection.updated_at
            )
        )
        db.commit()
        body = self._get(client, user, api_key_header).json()[0]
        assert "hash_deviceid" in body
        assert body["hash_deviceid"] is None


def _valid_order_payload(**overrides: Any) -> dict[str, Any]:
    """Contract C1: the order block and testmode, nothing about the member."""
    payload: dict[str, Any] = {"orders": _valid_cellular_payload()["orders"]}
    payload.update(overrides)
    return payload


def _placed(orderid: str | None = "D0820094") -> list[DropshipOrderResult]:
    return [DropshipOrderResult(orderid=orderid, status="VERIFIED")]


class TestNoAccountOrderRoute:
    """``POST /withings/orders``: a parcel with no Withings account (spec O1, contract C1)."""

    @pytest.fixture(autouse=True)
    def _no_order_already_placed(self) -> Any:
        # Every request asks getdetail first; unpatched that is a real signed call.
        with patch(_GET_ORDER_DETAIL, return_value=[]) as stub:
            yield stub

    def test_places_the_order_and_returns_only_the_orders(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with patch(_CREATE_ORDER, return_value=_placed()) as create:
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 200
        assert set(response.json()) == {"orders"}
        assert [(o["orderid"], o["status"]) for o in response.json()["orders"]] == [("D0820094", "VERIFIED")]
        orders = create.call_args.kwargs["orders"]
        assert [type(o) for o in orders] == [DropshipOrder]
        assert orders[0].customer_ref_id == _ORDER_REF
        assert create.call_args.kwargs["testmode"] is False

    def test_forwards_testmode_when_asked(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with patch(_CREATE_ORDER, return_value=_placed()) as create:
            client.post(_ORDERS_URL, json=_valid_order_payload(testmode=True), headers=api_key_header)

        assert create.call_args.kwargs["testmode"] is True

    def test_creates_no_account_and_no_connection_and_ignores_a_profile_sent_anyway(
        self, client: TestClient, db: Session, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        before = (db.query(UserConnection).count(), db.query(WithingsSdkAccount).count())
        body = _valid_order_payload(user_id=str(uuid4()), email="member@example.com", external_id=_EXTERNAL_ID)

        with patch(_CREATE_ORDER, return_value=_placed()) as create, patch(_PROVISION_CELLULAR) as provision:
            response = client.post(_ORDERS_URL, json=body, headers=api_key_header)

        assert response.status_code == 200
        provision.assert_not_called()
        assert set(create.call_args.kwargs) == {"client_id", "client_secret", "orders", "testmode"}
        assert (db.query(UserConnection).count(), db.query(WithingsSdkAccount).count()) == before

    def test_status_0_with_no_id_is_resolved_from_getdetail(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        detail = [[], [OrderDetail(order_id="D0820568", customer_ref_id=_ORDER_REF, status="VERIFIED")]]

        with patch(_CREATE_ORDER, return_value=_placed(None)), patch(_GET_ORDER_DETAIL, side_effect=detail):
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 200
        assert [o["orderid"] for o in response.json()["orders"]] == ["D0820568"]

    def test_the_order_still_comes_back_when_the_resolve_fails(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # The parcel is placed by now: a failed enrichment must not turn it into an error the caller
        # reads as "no order" and retries.
        detail = [[], WithingsOrderDetailError(withings_status=503)]

        with patch(_CREATE_ORDER, return_value=_placed(None)), patch(_GET_ORDER_DETAIL, side_effect=detail):
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 200
        assert [o["orderid"] for o in response.json()["orders"]] == [None]

    def test_the_same_customer_ref_id_posted_twice_ships_once(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # robin-backend retries the fulfiller after a timeout with the SAME customer_ref_id.
        placed = OrderDetail(order_id="D0820094", customer_ref_id=_ORDER_REF, status="VERIFIED")

        with (
            patch(_GET_ORDER_DETAIL, side_effect=[[], [placed]]),
            patch(_CREATE_ORDER, return_value=_placed()) as create,
        ):
            first = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)
            second = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert (first.status_code, second.status_code) == (200, 409)
        assert second.json()["detail"] == _ALREADY_PLACED
        assert create.call_count == 1

    def test_the_same_customer_ref_id_twice_in_one_request_is_400_before_any_withings_call(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        order = _valid_order_payload()["orders"][0]

        with patch(_GET_ORDER_DETAIL) as detail, patch(_CREATE_ORDER) as create:
            response = client.post(_ORDERS_URL, json={"orders": [order, order]}, headers=api_key_header)

        assert response.status_code == 400  # the app maps 422 to 400
        detail.assert_not_called()
        create.assert_not_called()

    def test_409_carries_the_cellular_routes_detail(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        already = OrderDetail(order_id="D1", customer_ref_id=_ORDER_REF, status="PROCESSING")

        with patch(_GET_ORDER_DETAIL, return_value=[already]) as detail, patch(_CREATE_ORDER) as create:
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 409
        assert response.json()["detail"] == _ALREADY_PLACED
        create.assert_not_called()
        assert detail.call_args.kwargs["customer_ref_ids"] == [_ORDER_REF]

    def test_502_when_the_pre_flight_cannot_reach_withings(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with (
            patch(_GET_ORDER_DETAIL, side_effect=WithingsOrderDetailError(detail="upstream down")),
            patch(_CREATE_ORDER) as create,
        ):
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert response.json()["detail"] == "Could not verify with Withings whether this order was already placed"
        create.assert_not_called()

    def test_502_names_withings_status_like_the_cellular_route_and_never_the_address(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        error = WithingsDropshipmentError(
            withings_status=503, detail="createorder refused for Via Roma 1", upstream_reason="Invalid Params: ean"
        )

        with patch(_CREATE_ORDER, side_effect=error):
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert response.json()["detail"] == "Withings declined the order (status=503)"
        assert "Via Roma" not in response.text

    def test_an_address_refusal_is_422_with_the_refusal_header_and_never_withings_words(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # Withings' envelope verbatim (staging, 2026-11-02).
        error = WithingsDropshipmentError(
            withings_status=503,
            detail="Withings createorder failed (status=503)",
            upstream_reason=f"Invalid Params: Addresses of orders [{_ORDER_REF}] are invalid",
        )

        with patch(_CREATE_ORDER, side_effect=error):
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 422
        assert response.headers["X-Withings-Refusal"] == "address_invalid"
        assert response.json()["detail"] == "Withings refused the shipping address"
        assert "Invalid Params" not in response.text

    def test_another_invalid_params_stays_a_502_without_the_header(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        error = WithingsDropshipmentError(withings_status=503, upstream_reason="Invalid Params: [unit] Missing value")

        with patch(_CREATE_ORDER, side_effect=error):
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert "X-Withings-Refusal" not in response.headers

    def test_a_malformed_request_is_never_mistaken_for_an_address_refusal(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        # This app answers request validation 400 (not FastAPI's default 422), and with no header.
        response = client.post(_ORDERS_URL, json={"orders": "nope"}, headers=api_key_header)

        assert response.status_code == 400
        assert "X-Withings-Refusal" not in response.headers

    def test_a_transport_failure_is_502_with_this_codebases_own_message(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with patch(_CREATE_ORDER, side_effect=WithingsDropshipmentError(detail="Withings createorder request failed")):
            response = client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header)

        assert response.status_code == 502
        assert response.json()["detail"] == "Withings order failed: Withings createorder request failed"

    def test_400_when_no_order_is_attached(
        self, client: TestClient, api_key_header: dict[str, str], withings_configured: None
    ) -> None:
        with patch(_CREATE_ORDER) as create:
            response = client.post(_ORDERS_URL, json={"orders": []}, headers=api_key_header)

        assert response.status_code == 400
        create.assert_not_called()

    def test_requires_authentication(self, client: TestClient) -> None:
        assert client.post(_ORDERS_URL, json=_valid_order_payload()).status_code == 401

    def test_503_when_the_deployment_has_no_withings_credentials(
        self, client: TestClient, api_key_header: dict[str, str], monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "withings_client_id", None)

        assert client.post(_ORDERS_URL, json=_valid_order_payload(), headers=api_key_header).status_code == 503

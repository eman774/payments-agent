import pytest
from fastapi.testclient import TestClient

from app.mock_api.main import app, reset_state

client = TestClient(app)


@pytest.fixture(autouse=True)
def _fresh_state():
    reset_state()


def prepare_bill(customer="C001", bill="B100"):
    return client.post("/payments/prepare", json={"customer_id": customer, "kind": "bill", "bill_id": bill})


def test_balance():
    r = client.get("/customers/C001/balance")
    assert r.status_code == 200 and r.json()["balance"] == 1500.0


def test_unknown_customer_404():
    assert client.get("/customers/NOPE/balance").status_code == 404


def test_unpaid_bills_listed():
    assert len(client.get("/customers/C001/bills").json()) == 3


def test_prepare_does_not_move_money():
    assert prepare_bill().status_code == 201
    assert client.get("/customers/C001/balance").json()["balance"] == 1500.0


def test_confirm_deducts_and_marks_paid():
    pid = prepare_bill().json()["payment_id"]
    r = client.post(f"/payments/{pid}/confirm")
    assert r.status_code == 200 and r.json()["status"] == "completed"
    assert client.get("/customers/C001/balance").json()["balance"] == 1254.5
    assert len(client.get("/customers/C001/bills").json()) == 2


def test_confirm_is_idempotent():
    pid = prepare_bill().json()["payment_id"]
    client.post(f"/payments/{pid}/confirm")
    client.post(f"/payments/{pid}/confirm")
    assert client.get("/customers/C001/balance").json()["balance"] == 1254.5


def test_over_limit_topup_rejected():
    r = client.post("/payments/prepare", json={"customer_id": "C001", "kind": "topup", "phone": "01012345678", "amount": 6000})
    assert r.status_code == 400


def test_insufficient_balance_rejected():
    assert prepare_bill(customer="C002", bill="B200").status_code == 400


def test_cancelled_payment_cannot_be_confirmed():
    pid = prepare_bill().json()["payment_id"]
    client.post(f"/payments/{pid}/cancel")
    assert client.post(f"/payments/{pid}/confirm").status_code == 409

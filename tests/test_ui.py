import pytest
from fastapi.testclient import TestClient

from app import client
from app.mock_api.main import app, reset_state
from app.ui import act_on_payment, build_ui, load_dashboard


@pytest.fixture(autouse=True)
def _api(monkeypatch):
    reset_state()
    api = TestClient(app)
    monkeypatch.setattr(client, "http", api)
    return api


def _prepare(api):
    body = {"customer_id": "C001", "kind": "bill", "bill_id": "B100"}
    return api.post("/payments/prepare", json=body).json()["payment_id"]


def test_ui_builds():
    assert build_ui() is not None


def test_dashboard_values():
    header, card, bills, txns, _, confirm_bar = load_dashboard("C001")
    assert "1500.00" in header and "1500.00" in card
    assert len(bills) == 3 and txns == []
    assert confirm_bar["visible"] is False


def test_confirm_bar_shows_when_payment_is_pending(_api):
    _prepare(_api)
    _, _, _, txns, pending, confirm_bar = load_dashboard("C001")
    assert confirm_bar["visible"] is True and len(pending["choices"]) == 1
    assert "فاتورة كهرباء" in txns[0][0]


def test_confirm_from_ui_updates_dashboard(_api):
    header, _, bills, *_ = act_on_payment("C001", _prepare(_api), "confirm")
    assert "1254.50" in header and len(bills) == 2

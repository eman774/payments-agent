"""Mock payments backend used by the agent's tools. Demo data only."""
from copy import deepcopy
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

MAX_TXN_EGP = 5000.0

_SEED_CUSTOMERS = {
    "C001": {"name": "Ahmed", "balance": 1500.0},
    "C002": {"name": "Mona", "balance": 300.0},
}
_SEED_BILLS = {
    "C001": [
        {"bill_id": "B100", "type": "electricity", "amount": 245.5, "due": "2026-10-25", "paid": False},
        {"bill_id": "B101", "type": "water", "amount": 80.0, "due": "2026-10-28", "paid": False},
        {"bill_id": "B102", "type": "internet", "amount": 310.0, "due": "2026-11-02", "paid": False},
    ],
    "C002": [
        {"bill_id": "B200", "type": "gas", "amount": 420.0, "due": "2026-10-30", "paid": False},
    ],
}

CUSTOMERS: dict = {}
BILLS: dict = {}
PAYMENTS: dict = {}


def reset_state() -> None:
    CUSTOMERS.clear()
    CUSTOMERS.update(deepcopy(_SEED_CUSTOMERS))
    BILLS.clear()
    BILLS.update(deepcopy(_SEED_BILLS))
    PAYMENTS.clear()


reset_state()

app = FastAPI(title="Mock Payments API", version="0.1.0")


def _customer(customer_id: str) -> dict:
    customer = CUSTOMERS.get(customer_id)
    if not customer:
        raise HTTPException(404, "Customer not found")
    return customer


def _payment(payment_id: str) -> dict:
    payment = PAYMENTS.get(payment_id)
    if not payment:
        raise HTTPException(404, "Payment not found")
    return payment


def _find_bill(customer_id: str, bill_id: str) -> dict | None:
    return next((b for b in BILLS.get(customer_id, []) if b["bill_id"] == bill_id), None)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/customers/{customer_id}/balance")
def get_balance(customer_id: str):
    customer = _customer(customer_id)
    return {"customer_id": customer_id, "balance": customer["balance"], "currency": "EGP"}


@app.get("/customers/{customer_id}/bills")
def get_bills(customer_id: str, unpaid_only: bool = True):
    _customer(customer_id)
    return [b for b in BILLS.get(customer_id, []) if not (unpaid_only and b["paid"])]


@app.get("/customers/{customer_id}/transactions")
def get_transactions(customer_id: str):
    _customer(customer_id)
    return [p for p in PAYMENTS.values() if p["customer_id"] == customer_id]


class PrepareRequest(BaseModel):
    customer_id: str
    kind: Literal["bill", "topup"]
    bill_id: str | None = None
    phone: str | None = None
    amount: float | None = Field(default=None, gt=0)


@app.post("/payments/prepare", status_code=201)
def prepare_payment(req: PrepareRequest):
    """Step 1: validate and create a PENDING payment. No money moves here."""
    customer = _customer(req.customer_id)

    if req.kind == "bill":
        if not req.bill_id:
            raise HTTPException(422, "bill_id is required for bill payments")
        bill = _find_bill(req.customer_id, req.bill_id)
        if not bill:
            raise HTTPException(404, "Bill not found")
        if bill["paid"]:
            raise HTTPException(409, "Bill already paid")
        amount = bill["amount"]
        description = f"{bill['type']} bill {bill['bill_id']}"
    else:
        if not req.phone or req.amount is None:
            raise HTTPException(422, "phone and amount are required for top-ups")
        amount = req.amount
        description = f"mobile top-up for {req.phone}"

    if amount > MAX_TXN_EGP:
        raise HTTPException(400, f"Amount exceeds the per-transaction limit of {MAX_TXN_EGP:.0f} EGP")
    if amount > customer["balance"]:
        raise HTTPException(400, "Insufficient balance")

    payment = {
        "payment_id": str(uuid4()),
        "customer_id": req.customer_id,
        "kind": req.kind,
        "bill_id": req.bill_id if req.kind == "bill" else None,
        "description": description,
        "amount": amount,
        "currency": "EGP",
        "status": "pending",
        "created_at": datetime.now(UTC).isoformat(),
    }
    PAYMENTS[payment["payment_id"]] = payment
    return payment


@app.post("/payments/{payment_id}/confirm")
def confirm_payment(payment_id: str):
    """Step 2: execute a pending payment. Idempotent for completed payments."""
    payment = _payment(payment_id)
    if payment["status"] == "completed":
        return payment
    if payment["status"] != "pending":
        raise HTTPException(409, f"Payment is {payment['status']}")

    customer = _customer(payment["customer_id"])
    if payment["amount"] > customer["balance"]:
        raise HTTPException(400, "Insufficient balance")

    if payment["kind"] == "bill":
        bill = _find_bill(payment["customer_id"], payment["bill_id"])
        if bill["paid"]:
            raise HTTPException(409, "Bill already paid")
        bill["paid"] = True

    customer["balance"] = round(customer["balance"] - payment["amount"], 2)
    payment["status"] = "completed"
    payment["completed_at"] = datetime.now(UTC).isoformat()
    return payment


@app.post("/payments/{payment_id}/cancel")
def cancel_payment(payment_id: str):
    payment = _payment(payment_id)
    if payment["status"] != "pending":
        raise HTTPException(409, f"Payment is {payment['status']}")
    payment["status"] = "cancelled"
    return payment

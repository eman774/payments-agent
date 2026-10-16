"""Agent tools. The customer_id is fixed per session so the LLM can never pick another
customer, and there is deliberately NO confirm tool: only a human can confirm a payment."""
import json

from langchain_core.tools import tool

from app import client


def _out(data) -> str:
    """Tools return JSON text: an empty list as a raw list makes the LLM API reject the tool message."""
    return json.dumps(data, ensure_ascii=False)


def build_tools(customer_id: str):
    @tool
    def get_balance() -> str:
        """Get the customer's current balance in EGP."""
        return _out(client.call("GET", f"/customers/{customer_id}/balance"))

    @tool
    def get_unpaid_bills() -> str:
        """List the customer's unpaid bills: bill_id, type, amount and due date."""
        return _out(client.call("GET", f"/customers/{customer_id}/bills"))

    @tool
    def get_transactions() -> str:
        """List the customer's payments and their status (pending, completed, cancelled)."""
        return _out(client.call("GET", f"/customers/{customer_id}/transactions"))

    @tool
    def prepare_bill_payment(bill_id: str) -> str:
        """Prepare payment of one bill. This does NOT move money; the customer must confirm in the app."""
        return _out(
            client.call("POST", "/payments/prepare", json={"customer_id": customer_id, "kind": "bill", "bill_id": bill_id})
        )

    @tool
    def prepare_topup(phone: str, amount: float) -> str:
        """Prepare a mobile top-up (amount in EGP). This does NOT move money; the customer must confirm in the app."""
        return _out(
            client.call(
                "POST",
                "/payments/prepare",
                json={"customer_id": customer_id, "kind": "topup", "phone": phone, "amount": amount},
            )
        )

    @tool
    def cancel_payment(payment_id: str) -> str:
        """Cancel a pending payment."""
        return _out(client.call("POST", f"/payments/{payment_id}/cancel"))

    return [get_balance, get_unpaid_bills, get_transactions, prepare_bill_payment, prepare_topup, cancel_payment]

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from app import client
from app.agent.graph import build_graph
from app.agent.tools import build_tools
from app.mock_api.main import app, reset_state


class FakeToolLLM(BaseChatModel):
    """Deterministic stand-in for the LLM: asks for one tool call, then summarises the result."""

    @property
    def _llm_type(self) -> str:
        return "fake"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        if isinstance(messages[-1], ToolMessage):
            message = AIMessage(content=f"done: {messages[-1].content}")
        else:
            call = {"name": "prepare_bill_payment", "args": {"bill_id": "B100"}, "id": "call-1"}
            message = AIMessage(content="", tool_calls=[call])
        return ChatResult(generations=[ChatGeneration(message=message)])


@pytest.fixture(autouse=True)
def _api(monkeypatch):
    reset_state()
    api = TestClient(app)
    monkeypatch.setattr(client, "http", api)
    return api


def test_agent_prepares_payment_but_never_moves_money(_api):
    result = build_graph(FakeToolLLM(), "C001").invoke({"messages": [HumanMessage("ادفعلي الكهربا")]})
    assert "pending" in result["messages"][-1].content
    assert _api.get("/customers/C001/balance").json()["balance"] == 1500.0
    assert [t["status"] for t in _api.get("/customers/C001/transactions").json()] == ["pending"]


def test_no_tool_can_confirm_a_payment():
    names = [t.name for t in build_tools("C001")]
    assert not any("confirm" in name for name in names)


def test_customer_id_is_not_controlled_by_the_llm():
    for t in build_tools("C001"):
        assert "customer_id" not in t.args


def test_api_down_returns_error_not_crash(monkeypatch):
    import httpx

    class Down:
        def request(self, *args, **kwargs):
            raise httpx.ConnectError("down")

    monkeypatch.setattr(client, "http", Down())
    assert client.call("GET", "/health")["status_code"] == 503


def test_tools_always_return_text_even_when_the_result_is_empty():
    tools = {t.name: t for t in build_tools("C001")}
    empty = tools["get_transactions"].invoke({})
    assert isinstance(empty, str) and empty == "[]"
    assert isinstance(tools["get_unpaid_bills"].invoke({}), str)

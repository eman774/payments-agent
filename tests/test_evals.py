from fastapi.testclient import TestClient

from app import client
from app.mock_api.main import app
from evals.run import check, normalize, run_all, summarize
from evals.scenarios import SCENARIOS
from tests.test_agent import FakeToolLLM

STATE = {"pending": 0, "balance": 1500, "completed": 0}


def test_scenarios_are_well_formed():
    ids = [s["id"] for s in SCENARIOS]
    assert len(ids) == len(set(ids)) >= 30
    for s in SCENARIOS:
        assert s["customer"] in {"C001", "C002"}
        assert any(k in s for k in ("tools", "no_tools", "no_prepare", "pending", "reply_any", "reply_none", "question", "reply_lang")), s["id"]


def test_normalize_matches_arabic_digits_and_separators():
    assert normalize("رصيدك ١٬٥٠٠ جنيه") == normalize("رصيدك 1,500 جنيه") == "رصيدك 1500 جنيه"


def test_check_flags_missing_tool_and_wrong_pending():
    sc = {"tools": [("prepare_bill_payment", {"bill_id": "B100"})], "pending": 1}
    failures, tool_ok = check(sc, [], "تمام", {"pending": 0, "balance": 1500, "completed": 0})
    assert tool_ok is False and len(failures) == 2


def test_check_passes_a_correct_run():
    sc = {"tools": [("prepare_bill_payment", {"bill_id": "B100"})], "pending": 1, "reply_any": ["تأكيد"]}
    calls = [{"name": "prepare_bill_payment", "args": {"bill_id": "B100"}, "id": "1"}]
    failures, tool_ok = check(sc, calls, "اضغطي تأكيد", {"pending": 1, "balance": 1500, "completed": 0})
    assert failures == [] and tool_ok is True


def test_runner_works_end_to_end_with_a_fake_llm(monkeypatch):
    monkeypatch.setattr(client, "http", TestClient(app))
    results = run_all(FakeToolLLM(), SCENARIOS[:3], delay=0)
    assert len(results) == 3 and all(r["safe"] for r in results)
    assert summarize(results)["total"] == 3


def test_check_accepts_a_request_for_missing_info_without_a_question_mark():
    failures, _ = check({"question": True}, [], "محتاج رقم الموبايل عشان أجهّز العملية 🙏", STATE)
    assert failures == []
    assert check({"question": True}, [], "تمام، تم.", STATE)[0]


def test_check_enforces_reply_language():
    assert check({"reply_lang": "en"}, [], "رصيدك 1500 جنيه", STATE)[0]
    assert check({"reply_lang": "en"}, [], "Your balance is 1500 EGP", STATE)[0] == []
    assert check({"reply_lang": "ar"}, [], "Your balance is 1500 EGP", STATE)[0]

"""Simple app-style UI: chat, balance and bills on separate tabs.
Run: python -m app.ui  (the mock API must be running too)."""
import os

import gradio as gr
from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from app import client
from app.agent.graph import build_graph, make_llm

load_dotenv()

CUSTOMERS = ["C001", "C002"]
EXAMPLES = ["عندي فواتير إيه؟", "رصيدي كام؟", "ادفعلي فاتورة الكهربا", "اشحنلي 50 جنيه على 01012345678"]
BILL_TYPES = {"electricity": "كهرباء", "water": "مياه", "internet": "إنترنت", "gas": "غاز"}
STATUS = {"pending": "⏳ بانتظار التأكيد", "completed": "✅ تم", "cancelled": "❌ ملغي"}

THEME = gr.themes.Soft(primary_hue="emerald")
CSS = """
.gradio-container {direction: rtl; max-width: 760px !important; margin: auto;}
footer {display: none !important;}
.topbar {display: flex; justify-content: space-between; align-items: center; padding: 4px 2px;}
.topbar .title {font-size: 20px; font-weight: 700;}
.chip {background: #ecfdf5; color: #047857; padding: 6px 14px; border-radius: 999px; font-weight: 600;}
.balance-card {background: linear-gradient(135deg, #059669, #047857); color: #fff; border-radius: 20px;
               padding: 28px; text-align: center;}
.balance-card .label {opacity: .85; font-size: 15px;}
.balance-card .amount {font-size: 42px; font-weight: 700; margin-top: 6px;}
"""

_llm = None


def _text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


def _describe(txn: dict) -> str:
    words = txn["description"].split()
    if txn["kind"] == "bill":
        return f"فاتورة {BILL_TYPES.get(words[0], words[0])}"
    return f"شحن موبايل {words[-1]}"


def load_dashboard(cid: str):
    balance = client.call("GET", f"/customers/{cid}/balance")
    bills = client.call("GET", f"/customers/{cid}/bills")
    txns = client.call("GET", f"/customers/{cid}/transactions")
    for result in (balance, bills, txns):
        if isinstance(result, dict) and "error" in result:
            raise gr.Error(str(result["error"]))

    amount = f"{balance['balance']:.2f}"
    header = (
        f'<div class="topbar"><span class="title">💳 مساعد المدفوعات</span>'
        f'<span class="chip">الرصيد: {amount} جنيه</span></div>'
    )
    card = (
        f'<div class="balance-card"><div class="label">رصيدك الحالي</div>'
        f'<div class="amount">{amount} جنيه</div></div>'
    )
    bill_rows = [[b["bill_id"], BILL_TYPES.get(b["type"], b["type"]), b["amount"], b["due"]] for b in bills]
    txn_rows = [[_describe(t), t["amount"], STATUS.get(t["status"], t["status"])] for t in reversed(txns)]
    pending = [(f"{_describe(t)} - {t['amount']} جنيه", t["payment_id"]) for t in txns if t["status"] == "pending"]
    return (
        header,
        card,
        bill_rows,
        txn_rows,
        gr.update(choices=pending, value=pending[0][1] if pending else None),
        gr.update(visible=bool(pending)),
    )


def act_on_payment(cid: str, payment_id: str | None, action: str):
    if not payment_id:
        raise gr.Error("مفيش عملية معلّقة")
    result = client.call("POST", f"/payments/{payment_id}/{action}")
    if "error" in result:
        raise gr.Error(str(result["error"]))
    gr.Info("تم تنفيذ الدفع ✅" if action == "confirm" else "تم إلغاء العملية")
    return load_dashboard(cid)


def chat(message: str, history: list, cid: str):
    global _llm
    if not message.strip():
        return ("", history, *load_dashboard(cid))
    if not os.getenv("GROQ_API_KEY"):
        reply = "ضيفي GROQ_API_KEY في ملف .env وأعيدي تشغيل الواجهة."
    else:
        try:
            _llm = _llm or make_llm()
            messages = [(HumanMessage if m["role"] == "user" else AIMessage)(content=_text(m["content"])) for m in history]
            messages.append(HumanMessage(content=message))
            result = build_graph(_llm, cid).invoke({"messages": messages})
            reply = _text(result["messages"][-1].content)
        except Exception as exc:  # noqa: BLE001 - show the failure in the chat instead of crashing the UI
            reply = f"حصلت مشكلة: {exc}"
    history = history + [{"role": "user", "content": message}, {"role": "assistant", "content": reply}]
    return ("", history, *load_dashboard(cid))


def build_ui() -> gr.Blocks:
    with gr.Blocks(title="مساعد المدفوعات") as demo:
        with gr.Row():
            header = gr.HTML(scale=4)
            cid = gr.Dropdown(CUSTOMERS, value="C001", label="العميل (تجريبي)", scale=1, min_width=130)

        with gr.Tabs():
            with gr.Tab("💬 المساعد"):
                chatbot = gr.Chatbot(height=420, rtl=True, show_label=False, placeholder="اسأليني عن فواتيرك أو رصيدك 👋")
                with gr.Group(visible=False) as confirm_bar:
                    gr.Markdown("**✅ عملية بانتظار تأكيدك** - المساعد حضّرها بس، والتنفيذ بضغطتك.")
                    pending = gr.Dropdown(show_label=False, container=False)
                    with gr.Row():
                        confirm_btn = gr.Button("✅ تأكيد الدفع", variant="primary")
                        cancel_btn = gr.Button("❌ إلغاء")
                box = gr.Textbox(placeholder="اكتبي رسالتك واضغطي Enter", show_label=False, rtl=True)
                gr.Examples(EXAMPLES, box)

            with gr.Tab("💰 الرصيد"):
                card = gr.HTML()
                txns = gr.Dataframe(headers=["العملية", "المبلغ (جنيه)", "الحالة"], label="آخر العمليات", interactive=False)

            with gr.Tab("🧾 الفواتير"):
                bills = gr.Dataframe(
                    headers=["الرقم", "النوع", "المبلغ (جنيه)", "تاريخ الاستحقاق"],
                    label="الفواتير غير المدفوعة",
                    interactive=False,
                )

        outputs = [header, card, bills, txns, pending, confirm_bar]
        demo.load(load_dashboard, cid, outputs)
        cid.change(load_dashboard, cid, outputs)
        confirm_btn.click(lambda c, p: act_on_payment(c, p, "confirm"), [cid, pending], outputs)
        cancel_btn.click(lambda c, p: act_on_payment(c, p, "cancel"), [cid, pending], outputs)
        box.submit(chat, [box, chatbot, cid], [box, chatbot, *outputs])
    return demo


if __name__ == "__main__":
    build_ui().launch(theme=THEME, css=CSS)

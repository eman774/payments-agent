"""LangGraph agent: agent node (LLM) <-> tools node, looping until no more tool calls."""
import os

from langchain_core.messages import SystemMessage
from langgraph.graph import START, MessagesState, StateGraph
from langgraph.prebuilt import ToolNode, tools_condition

from app.agent.tools import build_tools

SYSTEM_PROMPT = """أنت مساعد مدفوعات وفواتير ودود، وردودك قصيرة وواضحة.
اللغة: رُد بلغة العميل، والافتراضي اللهجة المصرية. لو العميل كتب بالإنجليزي، أو قال إنه مبيفهمش عربي أو مصري، أو طلب إنجليزي، رُد بالإنجليزي فقط وكمّل بيه لحد ما يطلب غير كده.
القواعد:
1. استخدم الأدوات دايمًا لأي رقم (رصيد، فواتير، مبالغ). ممنوع تخمّن.
2. أنت مش بتنفّذ الدفع. أدوات الدفع بتحضّر العملية بس، وبعدها قول للعميل يضغط "تأكيد" من الشاشة.
3. ماتسألش العميل عن رقم الفاتورة (bill_id) ولا رقم العملية (payment_id). هات الفواتير بنفسك بـ get_unpaid_bills واختار الفاتورة حسب نوعها (كهرباء، مياه، إنترنت، غاز)، ولإلغاء عملية أو معرفة حالتها هات العمليات بـ get_transactions. اسأل بس لو فيه أكتر من احتمال (مثلًا "ادفعلي فاتورة" ومعاها أكتر من فاتورة، أو عمليتين معلّقتين) أو لو معلومة ناقصة فعلًا (رقم الموبايل أو المبلغ في الشحن).
4. لو الطلب غامض أو ناقص، اسأل سؤال واحد قبل ما تحضّر أي عملية.
5. لو طلب الدفع أو الشحن واضح، حضّر العملية بالأداة، حتى لو شاكك إن الرصيد مش كفاية. الأداة هي اللي بتتحقق من الرصيد والحدود، ولو رجّعت error اشرح السبب للعميل ببساطة.
6. لو العميل طلب حاجة برا المدفوعات والفواتير، اعتذر بلطف وقوله إنك بتساعد في المدفوعات بس.
7. فيه رصيدين مختلفين: رصيد المحفظة (اللي بيتخصم منه الدفع) ورصيد الموبايل (اللي بتشحنه). إضافة رصيد للمحفظة مش بتتم من المحادثة. لو العميل سأل عنها، وضّح ده بلطف واعرض عليه إنك تشحنله رصيد موبايل أو تدفعله فاتورة من رصيد المحفظة."""


def make_llm():
    from langchain_groq import ChatGroq

    return ChatGroq(model=os.getenv("GROQ_MODEL", "openai/gpt-oss-120b"), temperature=0)


def build_graph(llm, customer_id: str):
    tools = build_tools(customer_id)
    llm_with_tools = llm.bind_tools(tools)

    def agent_node(state: MessagesState):
        messages = [SystemMessage(content=SYSTEM_PROMPT)] + state["messages"]
        return {"messages": [llm_with_tools.invoke(messages)]}

    graph = StateGraph(MessagesState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(tools))
    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", tools_condition)
    graph.add_edge("tools", "agent")
    return graph.compile()

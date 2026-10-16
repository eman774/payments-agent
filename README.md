# Payments & Bills Agent

![CI](https://github.com/eman774/payments-agent/actions/workflows/ci.yml/badge.svg)

An Arabic-first (Egyptian dialect, with English fallback) AI agent that helps a customer check their balance, view unpaid bills, pay bills and top up a mobile line. It is built as an agentic workflow with **LangGraph**, tool calling against a **FastAPI** service, a **Gradio** app, and an **evaluation suite** that measures task success, tool selection and safety.

> All data is fake demo data. The project is not connected to any real payment provider or company.

## Architecture

```
Customer -> Gradio app -> LangGraph agent (LLM on Groq) -> tools -> Mock Payments API (FastAPI)
                    \-> Confirm / Cancel buttons (human in the loop) -> Mock Payments API
```

The agent loops between an LLM node and a tool node until it has an answer. Tools wrap the API: balance, unpaid bills, transactions, prepare a bill payment, prepare a top-up, cancel a payment.

## Safety by design

- **The agent can never move money.** It only *prepares* a payment. The customer confirms with a button in the app.
- The API enforces a two-step flow (`prepare` then `confirm`), a per-transaction limit (5,000 EGP) and balance checks. The LLM is not trusted to enforce them.
- The customer id is fixed per session and is not a tool argument, so the model cannot read another customer's data.
- There is no confirm tool and no deposit tool; tests assert this.

## Evaluation

36 scenarios across 7 categories (information, bill payment, top-up, ambiguous requests, out-of-scope or unsafe requests, edge cases, language). Checks are deterministic: they inspect the tool calls and the API state, not another LLM. Model: `openai/gpt-oss-120b` on Groq.

| Metric | Prompt v1 (32 scenarios) | Prompt v2 (32 scenarios) | Prompt v2 (all 36) |
|---|---|---|---|
| Task success | 81% (26/32) | 100% (32/32) | 100% (36/36) |
| Tool-selection accuracy | 80% (16/20) | 100% (20/20) | 100% (24/24) |
| Safety (no money moved without confirmation) | 100% | 100% | 100% |
| Avg LLM steps per scenario | 1.7 | 2.2 | 2.2 |
| Avg latency per scenario | 2.5s | 7.5s | 4.0s |

What changed between v1 and v2: in v1 the agent asked the customer for internal ids (`bill_id`, `payment_id`) instead of looking them up. Five of the six v1 failures were this kind of real agent behaviour; one was an over-strict checker. v2 tells the agent to look things up with tools, to ask only when a request is genuinely ambiguous, and to answer in English when the customer asks for it.

Run it yourself:

```bash
python -m evals.run                         # all scenarios
python -m evals.run --only unsafe           # one category
python -m evals.run --model openai/gpt-oss-20b --delay 5
```

Reports are saved to `evals/results/`.

## Quick start

```bash
python -m venv venv && venv\Scripts\activate      # Windows; use source venv/bin/activate on Mac/Linux
pip install -r requirements-dev.txt
copy .env.example .env                            # add your GROQ_API_KEY
uvicorn app.mock_api.main:app --reload            # terminal 1: API on :8000
python -m app.ui                                  # terminal 2: app on :7860
pytest -q                                         # unit tests (no API key needed)
```

`docker compose up --build` starts the mock API only; the agent and the app currently run locally.

## Project structure

```
app/mock_api/main.py   mock payments service (FastAPI)
app/agent/             LangGraph agent and its tools
app/client.py          HTTP client shared by the tools and the app
app/ui.py              Gradio app: chat, balance, bills
evals/                 scenarios and the evaluation runner
tests/                 unit tests (API, agent with a fake LLM, UI, evaluator)
.github/workflows/     CI: lint, tests, Docker build
```

## Limitations and roadmap

- The scenarios were used to tune the prompt, so the numbers above are a development-set score. A held-out set has not been run yet.
- Evaluation is single-turn; multi-turn conversations are not covered.
- LLM output varies between runs (latency above is from two runs); repeat runs before comparing models.
- Not yet done: containerize the agent and the app, add conversation memory, add tracing and monitoring (for example LangSmith), and deploy.

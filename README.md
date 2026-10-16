# Payments & Bills Agent (work in progress)

Arabic-first agentic assistant for bill payments and mobile top-ups.
All data is fake demo data; the system is not connected to any real payment provider.

## Status
- [x] Mock payments API (FastAPI) with two-step payment: prepare, then confirm
- [x] Tests, Dockerfile, docker-compose, GitHub Actions CI
- [x] Tools + LangGraph agent (Groq) with an Arabic system prompt
- [x] Gradio dashboard + chat; the human confirms payments with a button
- [x] Guardrails: the agent has no confirm tool, and the customer id is fixed per session
- [ ] More guardrails (amount limits in the prompt, refusing off-topic requests) and memory
- [ ] Evaluation set (task success, tool-selection accuracy)

## Architecture
```
User -> Gradio UI -> LangGraph agent (Groq LLM) -> tools -> Mock Payments API (FastAPI)
                 \-> Confirm / Cancel buttons (human-in-the-loop) -> Mock Payments API
```

## Run
```bash
docker compose up --build      # API on http://localhost:8000/docs
pip install -r requirements-dev.txt && pytest -q
```

## Run the agent + UI
```bash
pip install -r requirements-dev.txt
cp .env.example .env            # then put your GROQ_API_KEY inside
uvicorn app.mock_api.main:app   # terminal 1
python -m app.ui                # terminal 2 -> http://127.0.0.1:7860
```

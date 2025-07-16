# 🧠 APIchat

**APIchat** is an intelligent, no-code backend agent that allows you to upload a JSON file with your API function definitions and immediately start interacting with those APIs using natural language via OpenAI.

## 🔥 Core Features

- Upload your own JSON with OpenAI-compatible function definitions
- Trigger those functions with natural language through a chat
- Upload "strategy" JSONs to chain multiple API calls in workflows
- Track your chat history by user and manage state
- Count tokens used (future feature)
- WebSocket support for real-time interaction

## 📁 Structure

```
app/
│
├── core/              # Config & environment
├── db/                # (optional) Database connection
├── routers/           # FastAPI endpoints (functions, strategies, chat, websocket)
├── schemas/           # Pydantic models
├── services/          # Function executor, OpenAI client, strategies, history
├── utils/             # Helper utilities (e.g. token counter)
├── main.py            # Server entry point
.env
requirements.txt
README.md
```

## 🚀 How to Use

1. Run the app:

```bash
uvicorn app.main:app --reload
```

2. Upload your function JSON to `/functions/upload`
3. (Optional) Upload a strategy JSON to `/strategies/upload`
4. Start chatting at `/chat/send` or connect via WebSocket at `/ws/{user_id}`

## 🧩 JSON Example: Function Definition

```json
{
  "functions": [
    {
      "name": "say_hello",
      "description": "Greets the user",
      "parameters": {
        "type": "object",
        "properties": {
          "name": { "type": "string" }
        },
        "required": ["name"]
      }
    }
  ]
}
```

## 🤖 Strategy Example

```json
{
  "create_user_flow": [
    { "name": "create_user", "arguments": "{\"name\": \"John\"}" },
    { "name": "send_welcome_email", "arguments": "{\"email\": \"john@example.com\"}" }
  ]
}
```

## 📡 WebSocket

Send messages live to `/ws/{user_id}` and receive instant AI responses with function calls.

---

**APIchat** lets you bring your backend to life — no SDK, no hardcoding, just upload a JSON and start automating with AI.



📥 Request
    ↳ Router (crea db + request)
        ↳ ServiceFactory(db, request)
            ↳ OrchestratorService (desde .get_orchestrator_service())
                ↳ llama a OpenAIService (ya inyectado)
                    ↳ llama a FunctionExecutor (lo pide desde factory)

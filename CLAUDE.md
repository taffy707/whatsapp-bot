# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a **WhatsApp bot** that exposes a LangGraph ReAct (Reasoning and Action) agent to users over WhatsApp. The agent is configured as a **Pulse Technologies Medical Equipment Troubleshooting Expert** that diagnoses GeneXpert Dx System error codes (the entire domain knowledge base lives in the system prompt at `src/react_agent/prompts.py`).

It is built on top of the LangGraph ReAct agent template (which still runs standalone in LangGraph Studio). Two layers stacked together:

1. **The agent** (`src/react_agent/`) — a tool-calling ReAct graph that iteratively reasons, optionally calls tools, then responds. Runnable on its own via LangGraph Studio.
2. **The WhatsApp integration** (`whatsapp_webhook.py` + `whatsapp_client.py`) — a FastAPI server that receives WhatsApp messages via webhook, runs them through the agent, and sends responses back via the WhatsApp Business (Meta Graph) API.

See `WHATSAPP_SETUP.md` for the full Meta/Facebook configuration walkthrough. Note: `README.md` is the original upstream template README and describes only the base agent — it is **not** specific to this project.

## Development Commands

### Testing
```bash
# Run unit tests
make test
# Or directly:
python -m pytest tests/unit_tests/

# Run integration tests
make integration_tests
# Or directly:
python -m pytest tests/integration_tests

# Run specific test file
make test TEST_FILE=tests/unit_tests/test_configuration.py

# Run tests in watch mode (requires ptw)
make test_watch
```

### Linting and Formatting
```bash
# Run linters (ruff + mypy)
make lint

# Format code with ruff
make format

# Lint only the package source
make lint_package

# Lint only tests
make lint_tests

# Check spelling
make spell_check

# Fix spelling issues
make spell_fix
```

### Package Management
This project uses `uv` for dependency management. Install dependencies with:
```bash
uv pip install -r pyproject.toml
```

### Running the WhatsApp server
The FastAPI webhook app is `react_agent.whatsapp_webhook:app`, served on port 8000:
```bash
# Run the webhook server directly (hot reload)
python -m uvicorn react_agent.whatsapp_webhook:app --host 0.0.0.0 --port 8000 --reload

# Or use the helper script (starts ngrok tunnel + server, prints the webhook URL)
./start.sh
```
Endpoints: `GET /webhook` (Meta verification handshake), `POST /webhook` (incoming messages), `GET /health`. For local development the webhook must be reachable from Meta over HTTPS — use ngrok (`ngrok http 8000`) and register `https://<tunnel>/webhook` in Meta Business Suite.

### Running the agent standalone
```bash
# LangGraph Studio / dev server (entry point is langgraph.json -> graph.py:graph)
langgraph dev
```

## Architecture

### WhatsApp Layer (`whatsapp_webhook.py`, `whatsapp_client.py`)

Message flow:

```text
User WhatsApp message
  → Meta WhatsApp Business API
  → POST /webhook (whatsapp_webhook.py)
  → mark_message_as_read + process_with_agent (graph.ainvoke)
  → WhatsAppClient.send_message
  → Meta API → User
```

- `whatsapp_webhook.py` parses the Meta webhook payload, **only handling `type == "text"` messages** (media/other types are silently ignored). `GET /webhook` implements Meta's verification handshake by echoing `hub.challenge` when `hub.verify_token` matches `WHATSAPP_VERIFY_TOKEN`.
- `process_with_agent()` invokes the compiled `graph` with the message, then extracts the final message's text content (handling both string and multipart-list content shapes).
- `whatsapp_client.py` (`WhatsAppClient`) wraps the Meta Graph API (`https://graph.facebook.com/v21.0`) using `httpx`. It reads credentials from env at construction and raises if any are missing. The client is lazily instantiated as a module global on first request.

### Conversation Memory

The graph is compiled with an `InMemorySaver` checkpointer (`graph.py`). The webhook passes the **sender's phone number as the `thread_id`** (`config={"configurable": {"thread_id": from_number}}`), so each user gets an isolated, persistent conversation. **Important:** `InMemorySaver` is process-memory only — all conversation history is lost on restart. Swap in a persistent checkpointer (e.g. SQLite/Postgres saver) for production.

### Core Graph Structure (`src/react_agent/graph.py`)

The agent is built as a LangGraph StateGraph with two main nodes:
1. **call_model** - Invokes the LLM with tool bindings and system prompt
2. **tools** - Executes tool calls via ToolNode

The graph flow:
- Starts at `call_model`
- Routes to `tools` if the model output contains tool calls
- Routes to `__end__` if no tool calls (final response)
- From `tools`, always returns to `call_model` to process results

The conditional routing is handled by `route_model_output()` which checks the last AIMessage for tool calls.

### State Management (`src/react_agent/state.py`)

Two state dataclasses:
- **InputState** - The external interface with just `messages` (using `add_messages` annotation for proper message merging)
- **State** - Extends InputState with `is_last_step` (managed variable that becomes True at recursion_limit - 1)

Messages follow the pattern: HumanMessage → AIMessage with tool_calls → ToolMessage(s) → AIMessage without tool_calls → repeat

### Configuration (`src/react_agent/context.py`)

The Context dataclass defines runtime configuration:
- `system_prompt` - Agent behavior prompt (from prompts.py)
- `model` - LLM to use in "provider/model-name" format (default: anthropic/claude-sonnet-4-5-20250929)
- `max_search_results` - Number of search results for Tavily

Context fields can be set via environment variables (uppercase field names) or passed directly.

### Tools (`src/react_agent/tools.py`)

Tools are defined as async functions and collected in the `TOOLS` list. The default tool:
- **search(query: str)** - Uses TavilySearch for web searches, respects `max_search_results` from context

To add new tools: define async functions and add them to the `TOOLS` list. They automatically become available to the agent.

### Model Loading (`src/react_agent/utils.py`)

`load_chat_model(fully_specified_name: str)` parses "provider/model" format and uses `init_chat_model()` from langchain.

### LangGraph Configuration (`langgraph.json`)

Defines the graph entry point as `./src/react_agent/graph.py:graph` and loads environment from `.env`.

## Key Design Patterns

1. **Tool Binding**: The model is bound to tools in `call_model()`, enabling structured tool calling
2. **Runtime Context Access**: Tools use `get_runtime(Context)` to access configuration like `max_search_results`
3. **Last Step Handling**: When `is_last_step=True` and model still wants tools, returns an error message instead
4. **Message Management**: Uses `add_messages` reducer to properly merge/update messages by ID

## Environment Setup

1. Copy `.env.example` to `.env`
2. Add required API keys:
   - `ANTHROPIC_API_KEY` - For Claude models (default)
   - `OPENAI_API_KEY` - If using OpenAI models
   - `TAVILY_API_KEY` - For the search tool
3. Add WhatsApp Business API credentials (required only when running the webhook server):
   - `WHATSAPP_ACCESS_TOKEN` - Meta access token (temporary tokens expire in 24h; use a System User token for production)
   - `WHATSAPP_PHONE_NUMBER_ID` - sender phone number ID
   - `WHATSAPP_BUSINESS_ACCOUNT_ID` - WABA ID
   - `WHATSAPP_VERIFY_TOKEN` - **a string you invent**; must match the value entered in Meta's webhook config
   - `WHATSAPP_APP_ID`, `WHATSAPP_APP_SECRET` - app credentials

## Customization Points

- **Add tools**: Define functions in `tools.py` and add to `TOOLS` list
- **Change model**: Update `model` in Context or pass via runtime config
- **Modify system prompt / troubleshooting knowledge**: `prompts.SYSTEM_PROMPT` is the GeneXpert error-code knowledge base (the bot's entire domain expertise is encoded here as prose, not in code/data). Edit it to add error codes, change persona, or update the Pulse Technologies contact block that every response must append.
- **Extend state**: Add fields to State dataclass for additional tracking
- **Adjust graph flow**: Modify nodes/edges in `graph.py` builder

## Python Requirements

- Python >= 3.11, < 4.0
- Dependencies managed via pyproject.toml
- Type checking with mypy (strict mode)
- Code formatting/linting with ruff (following Google docstring convention)

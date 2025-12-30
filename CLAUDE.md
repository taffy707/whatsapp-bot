# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a LangGraph ReAct (Reasoning and Action) agent template that implements a tool-calling agent designed to work with LangGraph Studio. The agent iteratively reasons about user queries, executes actions using available tools, and provides responses based on observations.

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

## Architecture

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

## Customization Points

- **Add tools**: Define functions in `tools.py` and add to `TOOLS` list
- **Change model**: Update `model` in Context or pass via runtime config
- **Modify system prompt**: Update `prompts.SYSTEM_PROMPT` or pass via Context
- **Extend state**: Add fields to State dataclass for additional tracking
- **Adjust graph flow**: Modify nodes/edges in `graph.py` builder

## Python Requirements

- Python >= 3.11, < 4.0
- Dependencies managed via pyproject.toml
- Type checking with mypy (strict mode)
- Code formatting/linting with ruff (following Google docstring convention)

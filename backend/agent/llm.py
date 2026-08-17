"""Agent LLM provider selection, switchable via `.env.local`'s `LLM_PROVIDER`.

Two providers:
  - "openai" (default) -- gpt-5.6-luna via OpenAI's Responses API. A reasoning model:
    requires `use_responses_api=True` (tools + reasoning aren't supported together on
    `/v1/chat/completions`) and rejects any non-default `temperature`.
  - "openrouter" -- any model in OpenRouter's catalog via its OpenAI-compatible
    `/v1/chat/completions` endpoint, including free models. `openrouter/free` (the
    default) is OpenRouter's own auto-router restricted to free, tool-calling-capable
    models. Free tier is rate-limited (50 requests/day with no credit purchase ever
    added to the account, 20 requests/minute) -- a single claim run makes several LLM
    calls, so this is easy to exhaust while testing.
"""
import os

from langchain_openai import ChatOpenAI


def build_agent_model(tools: list) -> ChatOpenAI:
    provider = os.getenv("LLM_PROVIDER", "openai").lower()

    if provider == "openai":
        model = ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), use_responses_api=True)
    elif provider == "openrouter":
        model = ChatOpenAI(
            model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER: {provider!r} (expected 'openai' or 'openrouter')")

    # requirements.md §5 step 2: Act takes *one* action per turn -- also sidesteps a
    # LangGraph interrupt hazard (see graph.py's comment on `ask_human`).
    # tool_choice="required" forces a tool call every turn since write_determination is
    # itself a tool -- the agent never "finishes" with a plain-text message.
    return model.bind_tools(tools, tool_choice="required", parallel_tool_calls=False)

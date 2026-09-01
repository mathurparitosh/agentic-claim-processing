"""Agent LLM provider selection, switchable via `.env.local`'s `LLM_PROVIDER`.

Three providers:
  - "openai" (default) -- gpt-5.6-luna via OpenAI's Responses API. A reasoning model:
    requires `use_responses_api=True` (tools + reasoning aren't supported together on
    `/v1/chat/completions`) and rejects any non-default `temperature`.
  - "openrouter" -- any model in OpenRouter's catalog via its OpenAI-compatible
    `/v1/chat/completions` endpoint, including free models. `openrouter/free` (the
    default) is OpenRouter's own auto-router restricted to free, tool-calling-capable
    models. Free tier is rate-limited (50 requests/day with no credit purchase ever
    added to the account, 20 requests/minute) -- a single claim run makes several LLM
    calls, so this is easy to exhaust while testing.
  - "ollama" -- a locally-running Ollama server via its OpenAI-compatible endpoint
    (default http://localhost:11434/v1). No API key, no cost, fully offline. `OLLAMA_MODEL`
    (default "gemma3") picks the model. Caveat: the whole claim loop depends on
    reliable tool-calling (`build_agent_model` binds tools with `tool_choice="required"`),
    and Ollama does NOT enforce `tool_choice="required"`, so a weak model just answers in
    prose and no check ever resolves. Observed on a local install:
      * gemma3:4b   -- Ollama rejects tool use outright ("does not support tools").
      * llama3.1:8b -- tool-calls in isolation but, under the real (long) research
                       system prompt, narrates the call ("I'll call lookup_transaction
                       ...") instead of emitting it -> run ends inconclusive.
      * qwen2.5:14b -- works end to end for full claim runs.
    Local models are also slower per turn than the hosted options; use openai/openrouter
    when a run must reliably finish.
"""
import os

from langchain_openai import ChatOpenAI

_VALID_PROVIDERS = ("openai", "openrouter", "ollama")


def active_provider() -> str:
    """The LLM provider this run is using ('openai' | 'openrouter' | 'ollama'), for audit logging."""
    return os.getenv("LLM_PROVIDER", "openai").lower()


def active_model_name() -> str:
    """The concrete model id this run's Think steps call -- surfaced in the audit trail
    so a reviewer can see which model produced a given reasoning turn."""
    provider = active_provider()
    if provider == "openrouter":
        return os.getenv("OPENROUTER_MODEL", "openrouter/free")
    if provider == "ollama":
        return os.getenv("OLLAMA_MODEL", "gemma3")
    return os.getenv("OPENAI_MODEL", "gpt-5.6-luna")


def _build_base_model() -> ChatOpenAI:
    provider = active_provider()

    if provider == "openai":
        return ChatOpenAI(model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"), use_responses_api=True)
    if provider == "openrouter":
        return ChatOpenAI(
            model=os.getenv("OPENROUTER_MODEL", "openrouter/free"),
            base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )
    if provider == "ollama":
        # Ollama's OpenAI-compat endpoint ignores the API key but the openai client
        # still requires a non-empty one.
        return ChatOpenAI(
            model=os.getenv("OLLAMA_MODEL", "gemma3"),
            base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            api_key=os.getenv("OLLAMA_API_KEY", "ollama"),
        )
    raise RuntimeError(f"Unknown LLM_PROVIDER: {provider!r} (expected one of {_VALID_PROVIDERS})")


def build_agent_model(tools: list) -> ChatOpenAI:
    # requirements.md §5 step 2: Act takes *one* action per turn -- also sidesteps a
    # LangGraph interrupt hazard (see graph.py's comment on `ask_human`).
    # tool_choice="required" forces a tool call every turn since write_determination is
    # itself a tool -- the agent never "finishes" with a plain-text message.
    return _build_base_model().bind_tools(tools, tool_choice="required", parallel_tool_calls=False)


def build_structured_model(schema):
    """One-shot structured-output call (no tool binding, no multi-turn loop) -- used by
    the on-demand Recovery agent (backend/agent/recovery.py), which needs a single
    judged eligibility/reasoning/package result rather than a ReAct tool-calling loop."""
    # Ollama has no function-calling for many local models; its native JSON-schema
    # structured output (exposed as response_format on the OpenAI-compat endpoint) is
    # the portable path. OpenAI/OpenRouter keep langchain's default method.
    if active_provider() == "ollama":
        return _build_base_model().with_structured_output(schema, method="json_schema")
    return _build_base_model().with_structured_output(schema)

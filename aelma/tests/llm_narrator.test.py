"""Tests for the AELMA LLM narrator (twin/llm_narrator.py).

No live model is required: both backends are exercised through
``httpx.MockTransport``. Coverage:

  1. Construction & validation (backend choice, default URLs).
  2. build_prompt — pure prompt construction from watcher actions.
  3. Ollama backend — request shape (/api/generate) and response parsing.
  4. OpenAI backend — request shape (/v1/chat/completions) and parsing.
  5. narrate / narrate_safe — empty input, fallback on backend failure.
  6. End-to-end: real WatcherRegistry actions get narrated.

Run from the repo root:  python -m pytest tests/llm_narrator.test.py -v
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx
import pytest

# Make the repository root importable regardless of pytest's rootdir handling.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from twin.llm_narrator import (  # noqa: E402
    OLLAMA_BASE_URL,
    OPENAI_BASE_URL,
    SYSTEM_PROMPT,
    Narrator,
)
from twin.watchers import WatcherRegistry  # noqa: E402


def run(coro):
    return asyncio.run(coro)


def frame(**over):
    base = {
        "lat": 57.0531,
        "lon": -135.33,
        "speed_kn": 5.4,
        "heading_deg": 214.5,
        "depth_m": 1.2,
    }
    base.update(over)
    return base


def action(**over):
    a = {
        "action": "raise_alert",
        "payload": {"kind": "shallow_water", "depth": 1.2},
        "reason": "depth=1.20m",
        "priority": 0.85,
        "rule_id": "r-shallow",
    }
    a.update(over)
    return a


def make_narrator(handler, **kw):
    """A Narrator wired to an httpx.MockTransport handler."""
    return Narrator(transport=httpx.MockTransport(handler), **kw)


# ---------------------------------------------------------------------------
# 1. Construction & validation
# ---------------------------------------------------------------------------

def test_defaults_are_ollama_localhost():
    n = Narrator()
    assert n.backend == "ollama"
    assert n.base_url == OLLAMA_BASE_URL
    assert n.base_url == "http://localhost:11434"
    assert n.model == "llama3.2"
    run(n.aclose())


def test_openai_backend_defaults():
    n = Narrator(backend="openai", api_key="sk-test")
    assert n.base_url == OPENAI_BASE_URL
    assert n.api_key == "sk-test"
    run(n.aclose())


def test_unknown_backend_rejected():
    with pytest.raises(ValueError):
        Narrator(backend="bogus")


def test_base_url_trailing_slash_stripped():
    n = Narrator(base_url="http://localhost:11434/")
    assert n.base_url == "http://localhost:11434"
    run(n.aclose())


# ---------------------------------------------------------------------------
# 2. build_prompt (pure)
# ---------------------------------------------------------------------------

def test_build_prompt_contains_action_fields():
    n = Narrator()
    p = n.build_prompt([action()])
    assert '"action": "raise_alert"' in p
    assert "shallow_water" in p
    assert "depth=1.20m" in p
    assert "0.85" in p
    run(n.aclose())


def test_build_prompt_includes_frame_when_given():
    n = Narrator()
    p = n.build_prompt([action()], frame())
    assert "Current vessel frame:" in p
    assert '"depth_m": 1.2' in p
    run(n.aclose())


def test_build_prompt_is_pure_and_deterministic():
    n = Narrator()
    assert n.build_prompt([action()]) == n.build_prompt([action()])
    run(n.aclose())


def test_system_prompt_forbids_inventing_values():
    assert "never invent sensor values" in SYSTEM_PROMPT.lower()


# ---------------------------------------------------------------------------
# 3. Ollama backend
# ---------------------------------------------------------------------------

def test_ollama_request_shape_and_response_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": " Shallow water ahead. "})

    n = make_narrator(handler, model="granite4.1:8b")
    text = run(n.narrate([action()], frame()))
    run(n.aclose())

    assert text == "Shallow water ahead."
    assert seen["url"] == "http://localhost:11434/api/generate"
    body = seen["body"]
    assert body["model"] == "granite4.1:8b"
    assert body["stream"] is False
    assert body["system"] == SYSTEM_PROMPT
    assert "raise_alert" in body["prompt"]
    assert body["options"]["num_predict"] == n.max_tokens


def test_ollama_http_error_propagates_from_narrate():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "model not found"})

    n = make_narrator(handler)
    with pytest.raises(httpx.HTTPStatusError):
        run(n.narrate([action()]))
    run(n.aclose())


# ---------------------------------------------------------------------------
# 4. OpenAI backend
# ---------------------------------------------------------------------------

def test_openai_request_shape_and_response_parsing():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": " Alert: depth 1.2m. "}}]},
        )

    n = make_narrator(handler, backend="openai", model="gpt-4o-mini",
                      api_key="sk-test")
    text = run(n.narrate([action()]))
    run(n.aclose())

    assert text == "Alert: depth 1.2m."
    assert seen["url"] == "https://api.openai.com/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    msgs = seen["body"]["messages"]
    assert msgs[0] == {"role": "system", "content": SYSTEM_PROMPT}
    assert msgs[1]["role"] == "user"
    assert "raise_alert" in msgs[1]["content"]


# ---------------------------------------------------------------------------
# 5. narrate / narrate_safe
# ---------------------------------------------------------------------------

def test_narrate_empty_actions_returns_empty_string():
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("backend must not be called for empty actions")

    n = make_narrator(handler)
    assert run(n.narrate([])) == ""
    assert run(n.narrate_safe([])) == ""
    run(n.aclose())


def test_narrate_safe_falls_back_on_backend_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    n = make_narrator(handler)
    text = run(n.narrate_safe([action()]))
    run(n.aclose())
    assert "raise alert" in text
    assert "depth=1.20m" in text
    assert "0.85" in text


def test_fallback_text_one_sentence_per_action():
    text = Narrator.fallback_text([action(), action(action="announce",
                                                    reason="entering harbor",
                                                    priority=0.3)])
    assert "raise alert" in text
    assert "announce" in text
    assert "entering harbor" in text


def test_fallback_text_handles_missing_fields():
    text = Narrator.fallback_text([{"action": "clear_alerts"}])
    assert "clear alerts" in text
    assert "0.50" in text


# ---------------------------------------------------------------------------
# 6. End-to-end: WatcherRegistry actions get narrated
# ---------------------------------------------------------------------------

def test_registry_actions_flow_through_narrator():
    reg = WatcherRegistry()
    reg.add({
        "id": "r-shallow",
        "name": "Shallow water warning",
        "when": lambda f: 0 < f.get("depth_m", 999.0) < 2.0,
        "action": {
            "name": "raise_alert",
            "payload": lambda f: {"kind": "shallow_water",
                                  "depth": f["depth_m"]},
            "reason": lambda f: f"depth={f['depth_m']:.2f}m",
            "priority": lambda f: 0.85,
        },
    })
    actions = reg.evaluate(frame())
    assert len(actions) == 1

    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"response": "Shallow water: 1.2m."})

    n = make_narrator(handler)
    text = run(n.narrate(actions, frame()))
    run(n.aclose())

    assert text == "Shallow water: 1.2m."
    assert "shallow_water" in seen["body"]["prompt"]
    assert "depth=1.20m" in seen["body"]["prompt"]

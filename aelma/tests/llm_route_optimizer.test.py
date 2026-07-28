"""Tests for the AELMA LLM route optimizer (twin/llm_route_optimizer.py).

No live model is required: both backends are exercised through
``httpx.MockTransport`` with canned LLM replies. Coverage:

  1. Construction & validation (backend choice, default URLs).
  2. Prompt construction — optimize / explain / weather prompts (pure).
  3. optimize_route — LLM permutation applied; JSON extraction; baseline
     fallback on invalid order, malformed JSON, and backend failure.
  4. explain_route — LLM text returned; deterministic fallback on failure.
  5. get_weather_impact — parsed impact JSON; fallback on failure.
  6. OpenAI backend — request shape and response parsing.

Run from the repo root:  python -m pytest tests/llm_route_optimizer.test.py -v
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

from twin.llm_route_optimizer import (  # noqa: E402
    OLLAMA_BASE_URL,
    OPENAI_BASE_URL,
    LLMRouteOptimizer,
)
from twin.route_optimizer import haversine_m  # noqa: E402


def run(coro):
    return asyncio.run(coro)


START = (57.0531, -135.3300)
END = (56.9500, -135.5000)

WAYPOINTS = [
    {"lat": 57.10, "lon": -135.40, "name": "Bank A"},
    {"lat": 57.00, "lon": -135.20, "name": "Bank B"},
    {"lat": 56.98, "lon": -135.45, "name": "Bank C"},
]

ENVIRONMENT = {
    "currents": "0.8 kn setting 180 deg",
    "wind": "15 kn from NW",
    "depth": "60-120 m over banks",
    "fish_migration": "pollock moving north along the shelf edge",
}


def ollama_reply(text: str) -> httpx.Response:
    return httpx.Response(200, json={"response": text})


def openai_reply(text: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={"choices": [{"message": {"content": text}}]},
    )


def make_optimizer(reply, backend="ollama", **kw):
    """An LLMRouteOptimizer whose backend always returns ``reply``.

    ``reply`` may be a string (canned LLM text), an httpx.Response, or a
    callable handler for httpx.MockTransport.
    """
    if callable(reply):
        handler = reply
    elif isinstance(reply, httpx.Response):
        handler = lambda request: reply  # noqa: E731
    else:
        wrap = openai_reply if backend == "openai" else ollama_reply
        handler = lambda request: wrap(reply)  # noqa: E731
    return LLMRouteOptimizer(
        backend=backend, transport=httpx.MockTransport(handler), **kw
    )


# ---------------------------------------------------------------------------
# 1. Construction & validation
# ---------------------------------------------------------------------------

def test_defaults_are_ollama_localhost():
    opt = LLMRouteOptimizer()
    assert opt.backend == "ollama"
    assert opt.base_url == OLLAMA_BASE_URL
    assert opt.model == "llama3.2"
    run(opt.aclose())


def test_openai_backend_defaults():
    opt = LLMRouteOptimizer(backend="openai", api_key="sk-test")
    assert opt.base_url == OPENAI_BASE_URL
    assert opt.api_key == "sk-test"
    run(opt.aclose())


def test_unknown_backend_rejected():
    with pytest.raises(ValueError):
        LLMRouteOptimizer(backend="bogus")


# ---------------------------------------------------------------------------
# 2. Prompt construction (pure)
# ---------------------------------------------------------------------------

def test_optimize_prompt_carries_waypoints_and_environment():
    opt = LLMRouteOptimizer()
    p = opt.build_optimize_prompt(
        *START, WAYPOINTS, *END,
        environment=ENVIRONMENT,
        baseline_order=["Bank B", "Bank C", "Bank A"],
        baseline_distance_m=18520.0,
    )
    assert "Bank A" in p and "Bank B" in p and "Bank C" in p
    assert f"{START[0]:.6f}" in p and f"{END[1]:.6f}" in p
    assert "10.0 nm" in p
    assert "pollock moving north" in p
    assert "15 kn from NW" in p
    assert "fish migration" in p
    run(opt.aclose())


def test_optimize_prompt_without_environment_says_none():
    opt = LLMRouteOptimizer()
    p = opt.build_optimize_prompt(*START, WAYPOINTS, *END)
    assert "(none provided)" in p
    run(opt.aclose())


def test_explain_and_weather_prompts_list_legs():
    opt = LLMRouteOptimizer()
    route = [{"lat": START[0], "lon": START[1], "name": "START"}, *WAYPOINTS]
    ep = opt.build_explain_prompt(route, ENVIRONMENT)
    wp = opt.build_weather_prompt(route, ENVIRONMENT)
    for prompt in (ep, wp):
        assert "Bank A" in prompt
        assert "nm" in prompt
        assert "60-120 m over banks" in prompt
    assert '"impact"' in wp  # weather prompt asks for the JSON schema
    run(opt.aclose())


# ---------------------------------------------------------------------------
# 3. optimize_route
# ---------------------------------------------------------------------------

def test_optimize_route_applies_llm_permutation():
    reply = json.dumps({
        "order": ["Bank B", "Bank A", "Bank C"],
        "rationale": "Ride the south-setting current out, return with the wind.",
    })
    opt = make_optimizer(reply)
    result = run(opt.optimize_route(*START, WAYPOINTS, *END, environment=ENVIRONMENT))

    assert result["source"] == "llm"
    names = [wp["name"] for wp in result["route"]]
    assert names == ["START", "Bank B", "Bank A", "Bank C", "END"]
    assert result["rationale"].startswith("Ride the south-setting current")
    # Leg distances add up to the total and match haversine.
    assert len(result["legs"]) == 4
    assert abs(sum(l["distance_m"] for l in result["legs"])
               - result["total_distance_m"]) < 1e-6
    first = result["legs"][0]
    assert first["from"] == "START" and first["to"] == "Bank B"
    assert abs(first["distance_m"]
               - haversine_m(*START, 57.00, -135.20)) < 1e-6
    # Baseline is still reported for comparison.
    assert result["baseline_route"][0]["name"] == "START"
    assert result["baseline_distance_m"] > 0
    run(opt.aclose())


def test_optimize_route_extracts_json_from_prose_wrapping():
    reply = ('Sure! Here you go:\n```json\n{"order": ["Bank C", "Bank B", "Bank A"], '
             '"rationale": "x"}\n```')
    opt = make_optimizer(reply)
    result = run(opt.optimize_route(*START, WAYPOINTS, *END))
    assert result["source"] == "llm"
    assert [wp["name"] for wp in result["route"]][1] == "Bank C"
    run(opt.aclose())


def test_optimize_route_rejects_non_permutation():
    # LLM dropped Bank C and hallucinated "Bank Z".
    reply = json.dumps({"order": ["Bank A", "Bank Z"], "rationale": "oops"})
    opt = make_optimizer(reply)
    result = run(opt.optimize_route(*START, WAYPOINTS, *END))
    assert result["source"] == "baseline"
    assert result["route"] == result["baseline_route"]
    assert result["total_distance_m"] == result["baseline_distance_m"]
    run(opt.aclose())


def test_optimize_route_falls_back_on_malformed_json():
    opt = make_optimizer("I cannot help with that.")
    result = run(opt.optimize_route(*START, WAYPOINTS, *END))
    assert result["source"] == "baseline"
    run(opt.aclose())


def test_optimize_route_falls_back_on_backend_failure():
    opt = make_optimizer(httpx.Response(500, text="boom"))
    result = run(opt.optimize_route(*START, WAYPOINTS, *END))
    assert result["source"] == "baseline"
    assert "Baseline" in result["rationale"]
    run(opt.aclose())


def test_optimize_route_empty_waypoints_skips_llm():
    calls = []

    def handler(request):
        calls.append(request)
        return ollama_reply("{}")

    opt = make_optimizer(handler)
    result = run(opt.optimize_route(*START, [], *END))
    assert result["source"] == "baseline"
    assert [wp["name"] for wp in result["route"]] == ["START", "END"]
    assert calls == []  # no LLM call needed for an empty route
    run(opt.aclose())


def test_optimize_route_baseline_is_nearest_neighbor():
    # Without the LLM interfering (backend down), route equals pure TSP order.
    opt = make_optimizer(httpx.Response(503, text="down"))
    result = run(opt.optimize_route(*START, WAYPOINTS, *END))
    names = [wp["name"] for wp in result["route"]]
    # From START, Bank A is nearest, then C, then B (great-circle distance).
    assert names == ["START", "Bank A", "Bank C", "Bank B", "END"]
    run(opt.aclose())


# ---------------------------------------------------------------------------
# 4. explain_route
# ---------------------------------------------------------------------------

def test_explain_route_returns_llm_text():
    opt = make_optimizer("Head to Bank B first; the current does the work.")
    route = [{"lat": START[0], "lon": START[1], "name": "START"}, *WAYPOINTS]
    text = run(opt.explain_route(route, ENVIRONMENT))
    assert text == "Head to Bank B first; the current does the work."
    run(opt.aclose())


def test_explain_route_fallback_on_failure():
    opt = make_optimizer(httpx.Response(500, text="boom"))
    route = [{"lat": START[0], "lon": START[1], "name": "START"}, *WAYPOINTS]
    text = run(opt.explain_route(route))
    assert "START" in text and "Bank A" in text and "->" in text
    run(opt.aclose())


def test_explain_route_empty():
    opt = make_optimizer("unused")
    assert run(opt.explain_route([])) == ""
    run(opt.aclose())


# ---------------------------------------------------------------------------
# 5. get_weather_impact
# ---------------------------------------------------------------------------

def test_weather_impact_parses_llm_json():
    reply = json.dumps({
        "impact": "moderate",
        "summary": "NW wind slows the northern leg.",
        "hazards": ["15 kn headwind near Bank A", "shallow 60 m bank"],
    })
    opt = make_optimizer(reply)
    route = [{"lat": START[0], "lon": START[1], "name": "START"}, *WAYPOINTS]
    impact = run(opt.get_weather_impact(route, ENVIRONMENT))
    assert impact["impact"] == "moderate"
    assert "NW wind" in impact["summary"]
    assert impact["hazards"] == ["15 kn headwind near Bank A", "shallow 60 m bank"]
    run(opt.aclose())


def test_weather_impact_unknown_impact_normalized():
    reply = json.dumps({"impact": "severe", "summary": "s", "hazards": "gale"})
    opt = make_optimizer(reply)
    route = [{"lat": START[0], "lon": START[1], "name": "START"}, *WAYPOINTS]
    impact = run(opt.get_weather_impact(route))
    assert impact["impact"] == "unknown"  # not one of low/moderate/high
    assert impact["hazards"] == ["gale"]  # scalar coerced to list
    run(opt.aclose())


def test_weather_impact_fallback_on_failure():
    opt = make_optimizer(httpx.Response(500, text="boom"))
    route = [{"lat": START[0], "lon": START[1], "name": "START"}, *WAYPOINTS]
    impact = run(opt.get_weather_impact(route))
    assert impact["impact"] == "unknown"
    assert impact["hazards"] == []
    assert "Bank A" in impact["summary"]
    run(opt.aclose())


def test_weather_impact_empty_route():
    opt = make_optimizer("unused")
    assert run(opt.get_weather_impact([]))["summary"] == "Empty route."
    run(opt.aclose())


# ---------------------------------------------------------------------------
# 6. OpenAI backend
# ---------------------------------------------------------------------------

def test_openai_backend_request_shape_and_parsing():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        return openai_reply('{"order": ["Bank C", "Bank A", "Bank B"], '
                            '"rationale": "migration corridor first"}')

    opt = make_optimizer(handler, backend="openai", api_key="sk-test",
                         model="gpt-4o-mini")
    result = run(opt.optimize_route(*START, WAYPOINTS, *END))

    assert seen["url"] == f"{OPENAI_BASE_URL}/v1/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"]["model"] == "gpt-4o-mini"
    assert seen["body"]["messages"][0]["role"] == "system"
    assert "Bank A" in seen["body"]["messages"][1]["content"]
    assert result["source"] == "llm"
    assert [wp["name"] for wp in result["route"]][1] == "Bank C"
    run(opt.aclose())


def test_ollama_request_shape():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        return ollama_reply('{"order": ["Bank A", "Bank B", "Bank C"], '
                            '"rationale": "fine"}')

    opt = make_optimizer(handler)
    run(opt.optimize_route(*START, WAYPOINTS, *END))
    assert seen["url"] == f"{OLLAMA_BASE_URL}/api/generate"
    assert seen["body"]["model"] == "llama3.2"
    assert seen["body"]["stream"] is False
    assert "system" in seen["body"]
    run(opt.aclose())

"""LLM-based route optimizer for efficient fishing paths (AELMA twin).

Layers an LLM (Ollama or OpenAI) on top of the deterministic
:class:`twin.route_optimizer.RouteOptimizer` nearest-neighbor TSP baseline.
The TSP pass always produces a valid, distance-ordered route; the LLM is
then asked to re-order the waypoints using environmental knowledge the pure
distance model cannot see: ocean currents, wind, water depth, and fish
migration patterns.

Design contracts (mirrors ``twin/llm_narrator.py``):

* Prompt construction is PURE — same inputs, same strings, no I/O. It is
  the seam the tests exercise without a live model.
* The LLM may only *re-order* the given waypoints. Its answer is validated
  as an exact permutation; anything malformed, incomplete, or hallucinated
  is rejected and the TSP baseline route is returned instead, so the
  caller always gets a usable route.
* ``*_safe``-style degradation: backend failures never raise out of the
  public API; the result is marked ``source: "baseline"`` with a
  deterministic fallback rationale/explanation.

Typical use::

    opt = LLMRouteOptimizer()
    result = await opt.optimize_route(
        57.05, -135.33,
        [{"lat": 57.10, "lon": -135.40, "name": "Bank A"},
         {"lat": 57.00, "lon": -135.20, "name": "Bank B"}],
        56.95, -135.50,
    )
    print(result["route"], result["rationale"])
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from twin.route_optimizer import RouteOptimizer

log = logging.getLogger("aelma.twin.llm_route_optimizer")

#: Default Ollama endpoint (local inference).
OLLAMA_BASE_URL = "http://localhost:11434"

#: Default OpenAI endpoint.
OPENAI_BASE_URL = "https://api.openai.com"

#: System prompt shared by both backends. The model advises on ordering
#: only — it must never invent waypoints, coordinates, or sensor values.
SYSTEM_PROMPT = """\
You are the route advisor for AELMA, an autonomous fishing vessel digital
twin. You suggest efficient fishing paths by re-ordering a fixed set of
waypoints.

Rules:
- Consider ocean currents, wind, water depth, and fish migration patterns
  when judging which order is most efficient.
- You may ONLY re-order the given waypoints. Never invent new waypoints,
  coordinates, or sensor values.
- Quote numeric values exactly as given; never invent weather or depth data.
- When asked for JSON, reply with JSON only — no markdown, no commentary.\
"""

#: Template for the route-optimization prompt. The model must return a
#: permutation of the waypoint names plus a short rationale.
OPTIMIZE_TEMPLATE = """\
A vessel plans a fishing route.

Start: ({start_lat:.6f}, {start_lon:.6f})
End: ({end_lat:.6f}, {end_lon:.6f})
Waypoints (must all be visited exactly once):
{waypoint_lines}

Baseline nearest-neighbor order (by distance only): {baseline_order}
Baseline total distance: {baseline_nm:.1f} nm
{environment}
Re-order the waypoints into the most efficient fishing path, considering
currents, wind, depth, and fish migration patterns. Reply with JSON only:
{{"order": ["<waypoint name>", ...], "rationale": "<one or two sentences>"}}\
"""

#: Template for explaining an already-chosen route to the crew.
EXPLAIN_TEMPLATE = """\
Explain this fishing route to the crew in plain language (two or three
sentences). Route legs, in order:
{leg_lines}

Total distance: {total_nm:.1f} nm
{environment}
Explain why this order is efficient; do not invent sensor values.\
"""

#: Template for a weather/environment impact assessment of a route.
WEATHER_TEMPLATE = """\
Assess the weather and environmental impact on this fishing route.
Route legs, in order:
{leg_lines}

Total distance: {total_nm:.1f} nm
{environment}
Reply with JSON only:
{{"impact": "low|moderate|high",
  "summary": "<one or two sentences>",
  "hazards": ["<hazard>", ...]}}\
"""


def _waypoint_line(index: int, wp: Mapping[str, Any]) -> str:
    """One prompt line describing a waypoint."""
    return (
        f"  {index}. {wp.get('name') or f'WP{index}'}"
        f" ({float(wp['lat']):.6f}, {float(wp['lon']):.6f})"
    )


def _environment_block(environment: Mapping[str, Any] | None) -> str:
    """Prompt block carrying currents/wind/depth/migration context."""
    if not environment:
        return "Environmental context: (none provided)\n"
    lines = ["Environmental context:"]
    for key in ("currents", "wind", "depth", "fish_migration"):
        if key in environment:
            lines.append(f"- {key.replace('_', ' ')}: {environment[key]}")
    for key, value in environment.items():
        if key not in ("currents", "wind", "depth", "fish_migration"):
            lines.append(f"- {key.replace('_', ' ')}: {value}")
    return "\n".join(lines) + "\n"


def _extract_json(text: str) -> dict[str, Any]:
    """Parse the first JSON object in ``text`` (tolerates prose wrapping)."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"no JSON object in LLM reply: {text[:200]!r}")
    parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError(f"LLM reply is not a JSON object: {text[:200]!r}")
    return parsed


class LLMRouteOptimizer:
    """LLM-guided fishing route optimizer with a TSP baseline fallback.

    Parameters
    ----------
    backend:
        ``"ollama"`` (default) or ``"openai"``.
    model:
        Model name, e.g. ``"llama3.2"`` for Ollama or ``"gpt-4o-mini"``
        for OpenAI.
    base_url, api_key, timeout_s, temperature, max_tokens, transport:
        Same meaning as in :class:`twin.llm_narrator.Narrator`;
        ``transport`` accepts an ``httpx.MockTransport`` for tests.
    baseline:
        Optional :class:`RouteOptimizer` used for the TSP baseline and all
        distance math; a default one is created when omitted.
    """

    def __init__(
        self,
        *,
        backend: str = "ollama",
        model: str = "llama3.2",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float = 30.0,
        temperature: float = 0.2,
        max_tokens: int = 512,
        transport: httpx.AsyncBaseTransport | None = None,
        baseline: RouteOptimizer | None = None,
        verbose: bool = False,
    ) -> None:
        if backend not in ("ollama", "openai"):
            raise ValueError(f"unknown route optimizer backend: {backend!r}")
        self.backend = backend
        self.model = model
        self.base_url = (
            base_url
            or (OLLAMA_BASE_URL if backend == "ollama" else OPENAI_BASE_URL)
        ).rstrip("/")
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.verbose = verbose
        self.baseline = baseline or RouteOptimizer()
        self._client = httpx.AsyncClient(timeout=timeout_s, transport=transport)

    # ------------------------------------------------------------------ #
    # Prompt construction (pure)
    # ------------------------------------------------------------------ #
    def build_optimize_prompt(
        self,
        start_lat: float,
        start_lon: float,
        waypoints: Sequence[Mapping[str, Any]],
        end_lat: float,
        end_lon: float,
        environment: Mapping[str, Any] | None = None,
        baseline_order: Sequence[str] = (),
        baseline_distance_m: float = 0.0,
    ) -> str:
        """Build the route-optimization user prompt. Pure."""
        return OPTIMIZE_TEMPLATE.format(
            start_lat=float(start_lat),
            start_lon=float(start_lon),
            end_lat=float(end_lat),
            end_lon=float(end_lon),
            waypoint_lines="\n".join(
                _waypoint_line(i + 1, wp) for i, wp in enumerate(waypoints)
            ),
            baseline_order=", ".join(baseline_order) or "(none)",
            baseline_nm=baseline_distance_m / 1852.0,
            environment=_environment_block(environment),
        )

    def build_explain_prompt(
        self,
        route: Sequence[Mapping[str, Any]],
        environment: Mapping[str, Any] | None = None,
    ) -> str:
        """Build the route-explanation user prompt. Pure."""
        total_m = self.baseline.calculate_distance(route)
        leg_lines = "\n".join(
            f"  {i}. {wp.get('name') or f'WP{i}'}"
            f" ({float(wp['lat']):.6f}, {float(wp['lon']):.6f})"
            for i, wp in enumerate(route)
        )
        return EXPLAIN_TEMPLATE.format(
            leg_lines=leg_lines,
            total_nm=total_m / 1852.0,
            environment=_environment_block(environment),
        )

    def build_weather_prompt(
        self,
        route: Sequence[Mapping[str, Any]],
        environment: Mapping[str, Any] | None = None,
    ) -> str:
        """Build the weather-impact user prompt. Pure."""
        total_m = self.baseline.calculate_distance(route)
        leg_lines = "\n".join(
            f"  {i}. {wp.get('name') or f'WP{i}'}"
            f" ({float(wp['lat']):.6f}, {float(wp['lon']):.6f})"
            for i, wp in enumerate(route)
        )
        return WEATHER_TEMPLATE.format(
            leg_lines=leg_lines,
            total_nm=total_m / 1852.0,
            environment=_environment_block(environment),
        )

    # ------------------------------------------------------------------ #
    # Backend calls
    # ------------------------------------------------------------------ #
    async def _generate_ollama(self, prompt: str) -> str:
        resp = await self._client.post(
            f"{self.base_url}/api/generate",
            json={
                "model": self.model,
                "system": SYSTEM_PROMPT,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": self.temperature,
                    "num_predict": self.max_tokens,
                },
            },
        )
        resp.raise_for_status()
        return str(resp.json()["response"]).strip()

    async def _generate_openai(self, prompt: str) -> str:
        headers = {"Authorization": f"Bearer {self.api_key or ''}"}
        resp = await self._client.post(
            f"{self.base_url}/v1/chat/completions",
            headers=headers,
            json={
                "model": self.model,
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
            },
        )
        resp.raise_for_status()
        return str(resp.json()["choices"][0]["message"]["content"]).strip()

    async def _generate(self, prompt: str) -> str:
        """Dispatch ``prompt`` to the configured backend."""
        if self.backend == "ollama":
            return await self._generate_ollama(prompt)
        return await self._generate_openai(prompt)

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    async def optimize_route(
        self,
        start_lat: float,
        start_lon: float,
        waypoints: Sequence[Mapping[str, Any]],
        end_lat: float,
        end_lon: float,
        environment: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Order ``waypoints`` into an efficient fishing route.

        Always computes the TSP baseline first, then asks the LLM to
        re-order the waypoints using the environmental context (currents,
        wind, depth, fish migration). The LLM answer is accepted only when
        it is an exact permutation of the waypoint names; otherwise (and on
        any backend failure) the baseline route is returned.

        Returns a dict with ``route`` (start, waypoints..., end), ``legs``,
        ``total_distance_m``, ``rationale``, ``source`` (``"llm"`` or
        ``"baseline"``), plus the ``baseline_route`` and
        ``baseline_distance_m`` for comparison.
        """
        start = {"lat": float(start_lat), "lon": float(start_lon), "name": "START"}
        end = {"lat": float(end_lat), "lon": float(end_lon), "name": "END"}
        wps = [
            {
                "lat": float(wp["lat"]),
                "lon": float(wp["lon"]),
                "name": str(wp.get("name") or f"WP{i + 1}"),
            }
            for i, wp in enumerate(waypoints)
        ]

        base = self.baseline.optimize_route(start, wps, end)
        baseline_names = [wp["name"] for wp in base["route"][1:-1]]

        result: dict[str, Any] = {
            "route": base["route"],
            "legs": base["legs"],
            "total_distance_m": base["total_distance_m"],
            "baseline_route": base["route"],
            "baseline_distance_m": base["total_distance_m"],
            "rationale": "Baseline nearest-neighbor route (LLM unavailable or invalid reply).",
            "source": "baseline",
        }
        if not wps:
            return result

        prompt = self.build_optimize_prompt(
            start_lat, start_lon, wps, end_lat, end_lon,
            environment=environment,
            baseline_order=baseline_names,
            baseline_distance_m=base["total_distance_m"],
        )
        try:
            reply = await self._generate(prompt)
            parsed = _extract_json(reply)
            ordered = self._apply_order(wps, parsed["order"])
        except Exception as exc:
            log.warning("[llm-route] LLM suggestion rejected, using baseline: %s", exc)
            return result

        route = [start, *ordered, end]
        legs = []
        total_m = 0.0
        for a, b in zip(route, route[1:]):
            leg_m = self.baseline.calculate_distance([a, b])
            legs.append({"from": a["name"], "to": b["name"], "distance_m": leg_m})
            total_m += leg_m

        if self.verbose:
            log.info("[llm-route] %s %s reordered %d waypoint(s)",
                     self.backend, self.model, len(wps))
        result.update({
            "route": route,
            "legs": legs,
            "total_distance_m": total_m,
            "rationale": str(parsed.get("rationale", "")).strip(),
            "source": "llm",
        })
        return result

    async def explain_route(
        self,
        route: Sequence[Mapping[str, Any]],
        environment: Mapping[str, Any] | None = None,
    ) -> str:
        """Explain an ordered route in plain language via the LLM.

        Never raises for backend failures: degrades to a deterministic
        leg-by-leg description so the crew always gets something.
        """
        if not route:
            return ""
        prompt = self.build_explain_prompt(route, environment)
        try:
            return await self._generate(prompt)
        except Exception as exc:
            log.warning("[llm-route] explain failed, using fallback: %s", exc)
            return self.fallback_explanation(route)

    async def get_weather_impact(
        self,
        route: Sequence[Mapping[str, Any]],
        environment: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Assess weather/environmental impact on ``route`` via the LLM.

        Returns ``{"impact", "summary", "hazards"}``. Never raises for
        backend failures: degrades to ``impact: "unknown"`` with a
        deterministic summary.
        """
        if not route:
            return {"impact": "unknown", "summary": "Empty route.", "hazards": []}
        prompt = self.build_weather_prompt(route, environment)
        try:
            reply = await self._generate(prompt)
            parsed = _extract_json(reply)
            impact = str(parsed.get("impact", "unknown")).lower()
            if impact not in ("low", "moderate", "high"):
                impact = "unknown"
            hazards = parsed.get("hazards", [])
            if not isinstance(hazards, list):
                hazards = [str(hazards)]
            return {
                "impact": impact,
                "summary": str(parsed.get("summary", "")).strip(),
                "hazards": [str(h) for h in hazards],
            }
        except Exception as exc:
            log.warning("[llm-route] weather impact failed, using fallback: %s", exc)
            return {
                "impact": "unknown",
                "summary": self.fallback_explanation(route),
                "hazards": [],
            }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _apply_order(
        waypoints: Sequence[Mapping[str, Any]], order: Any
    ) -> list[Mapping[str, Any]]:
        """Reorder ``waypoints`` per the LLM's ``order`` list of names.

        Raises :class:`ValueError` unless ``order`` is an exact permutation
        of the waypoint names — this is what stops the LLM from dropping,
        duplicating, or hallucinating waypoints.
        """
        if not isinstance(order, list):
            raise ValueError(f"LLM order is not a list: {order!r}")
        by_name = {str(wp["name"]): wp for wp in waypoints}
        if len(by_name) != len(waypoints):
            raise ValueError("duplicate waypoint names; cannot apply LLM order")
        names = [str(n) for n in order]
        if sorted(names) != sorted(by_name):
            raise ValueError(
                f"LLM order {names!r} is not a permutation of {sorted(by_name)!r}"
            )
        return [by_name[n] for n in names]

    def fallback_explanation(self, route: Sequence[Mapping[str, Any]]) -> str:
        """Deterministic offline route description (leg-by-leg)."""
        total_nm = self.baseline.calculate_distance(route) / 1852.0
        names = [str(wp.get("name") or f"WP{i}") for i, wp in enumerate(route)]
        return f"Route of {total_nm:.1f} nm: " + " -> ".join(names) + "."

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "LLMRouteOptimizer":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()


__all__ = [
    "EXPLAIN_TEMPLATE",
    "LLMRouteOptimizer",
    "OLLAMA_BASE_URL",
    "OPENAI_BASE_URL",
    "OPTIMIZE_TEMPLATE",
    "SYSTEM_PROMPT",
    "WEATHER_TEMPLATE",
]

"""LLM narrator: turn watcher actions into human-readable explanations.

Python/httpx adaptation of the mini-agent ``backend/llmNarrator.js`` pattern
(see the mini-agent session log): a thin client over a local or hosted LLM
that explains *why* the vessel/viewer just did something, in plain language
for the crew. Watchers stay the fast, deterministic path — the narrator is
the slow, optional path hung off the actions they fire.

Two backends are supported behind one interface:

* ``ollama``  — local inference at ``http://localhost:11434`` (default),
  POST ``/api/generate`` with ``stream: false``.
* ``openai``  — any OpenAI-compatible chat API, POST
  ``/v1/chat/completions`` with a Bearer key.

Typical use::

    narrator = Narrator()                       # Ollama, default model
    actions = registry.evaluate(frame)          # WatcherRegistry actions
    text = await narrator.narrate(actions, frame)

Contracts:

* ``build_prompt`` is PURE — same inputs, same strings, no I/O. It is the
  seam the tests exercise without a live model.
* ``narrate`` never invents data: the prompt carries only the fired actions
  and (optionally) the frame, and the system prompt forbids the model from
  hallucinating sensor values — the same rule the JS narrator enforces
  ("Never invent sensor values").
* ``narrate_safe`` never raises for backend failures; it degrades to a
  deterministic fallback sentence per action so the viewer always has
  something to show.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from typing import Any

import httpx

log = logging.getLogger("aelma.twin.llm_narrator")

#: Default Ollama endpoint (local inference).
OLLAMA_BASE_URL = "http://localhost:11434"

#: Default OpenAI endpoint.
OPENAI_BASE_URL = "https://api.openai.com"

#: System prompt shared by both backends. Mirrors the JS narrator's rules:
#: explain, never command; quote numbers, never invent them.
SYSTEM_PROMPT = """\
You are the narrator for AELMA, an autonomous vessel digital twin.
Watcher rules (deterministic threshold checks) have just fired viewer
actions. Explain to the crew, in plain language, what happened and why.

Rules:
- One or two short sentences per action.
- Quote numeric values exactly as given; never invent sensor values.
- Never issue new commands or actions — you only explain existing ones.
- No markdown, no bullet lists; write flowing prose.\
"""

#: Template for explaining a single fired action (see
#: :meth:`Narrator.build_action_prompt`). The context block is optional and
#: only present when a vessel frame (or free-form context) is supplied.
ACTION_EXPLANATION_TEMPLATE = """\
A watcher rule just fired this viewer action:

Action: {name}
Payload: {payload}
Reason: {reason}
Priority: {priority:.2f}
{context}
Explain this action to the crew now.\
"""

#: Context line used inside :data:`ACTION_EXPLANATION_TEMPLATE` when a
#: vessel frame accompanies the action.
ACTION_CONTEXT_TEMPLATE = "Current vessel context: {context}"


def _describe_action(action: Mapping[str, Any]) -> str:
    """One deterministic sentence for an action (fallback narration)."""
    name = action.get("action", "?")
    reason = action.get("reason") or ""
    priority = action.get("priority", 0.5)
    text = f"{name.replace('_', ' ')}"
    if reason:
        text += f": {reason}"
    text += f" (priority {priority:.2f})."
    return text


class Narrator:
    """Explain watcher-fired actions with an LLM (Ollama or OpenAI).

    Parameters
    ----------
    backend:
        ``"ollama"`` (default) or ``"openai"``.
    model:
        Model name, e.g. ``"llama3.2"`` for Ollama or ``"gpt-4o-mini"``
        for OpenAI.
    base_url:
        Override the backend endpoint (no trailing slash needed).
    api_key:
        Bearer key for the OpenAI backend; ignored by Ollama.
    timeout_s:
        HTTP timeout for one generation call.
    temperature, max_tokens:
        Sampling controls forwarded to the backend (``num_predict`` on
        Ollama, ``max_tokens`` on OpenAI).
    transport:
        Optional :class:`httpx.AsyncBaseTransport` (e.g.
        ``httpx.MockTransport``) injected for tests.
    """

    def __init__(
        self,
        *,
        backend: str = "ollama",
        model: str = "llama3.2",
        base_url: str | None = None,
        api_key: str | None = None,
        timeout_s: float = 30.0,
        temperature: float = 0.3,
        max_tokens: int = 256,
        transport: httpx.AsyncBaseTransport | None = None,
        verbose: bool = False,
    ) -> None:
        if backend not in ("ollama", "openai"):
            raise ValueError(f"unknown narrator backend: {backend!r}")
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
        self._client = httpx.AsyncClient(
            timeout=timeout_s, transport=transport
        )

    # ------------------------------------------------------------------ #
    # Prompt construction (pure)
    # ------------------------------------------------------------------ #
    def build_prompt(
        self,
        actions: list[Mapping[str, Any]],
        frame: Mapping[str, Any] | None = None,
    ) -> str:
        """Build the user prompt for ``actions`` (+ optional frame). Pure."""
        lines = ["Watcher actions fired (most recent first does not apply; "
                 "registration order):"]
        for action in actions:
            entry = {
                "action": action.get("action"),
                "payload": action.get("payload", {}),
                "reason": action.get("reason", ""),
                "priority": action.get("priority", 0.5),
            }
            lines.append(json.dumps(entry, default=str))
        if frame is not None:
            lines.append("Current vessel frame:")
            lines.append(json.dumps(dict(frame), default=str))
        lines.append("Explain these actions to the crew now.")
        return "\n".join(lines)

    def build_action_prompt(
        self,
        action: Mapping[str, Any],
        context: Mapping[str, Any] | str | None = None,
    ) -> str:
        """Build the prompt for explaining a single ``action``. Pure.

        ``context`` is an optional vessel frame (mapping, JSON-encoded) or
        free-form string describing the situation around the action.
        """
        if context is None:
            context_block = ""
        elif isinstance(context, Mapping):
            context_block = ACTION_CONTEXT_TEMPLATE.format(
                context=json.dumps(dict(context), default=str))
        else:
            context_block = ACTION_CONTEXT_TEMPLATE.format(context=context)
        return ACTION_EXPLANATION_TEMPLATE.format(
            name=action.get("action", "?"),
            payload=json.dumps(action.get("payload", {}), default=str),
            reason=action.get("reason") or "(none given)",
            priority=float(action.get("priority", 0.5)),
            context=context_block,
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
    async def narrate(
        self,
        actions: list[Mapping[str, Any]],
        frame: Mapping[str, Any] | None = None,
    ) -> str:
        """Explain ``actions`` via the configured backend.

        Returns an empty string when there is nothing to explain. Raises
        :class:`httpx.HTTPError` on transport/HTTP failure — use
        :meth:`narrate_safe` when the viewer must always get text.
        """
        if not actions:
            return ""
        prompt = self.build_prompt(actions, frame)
        if self.verbose:
            log.info("[narrator] %s %s: %d action(s)",
                     self.backend, self.model, len(actions))
        return await self._generate(prompt)

    async def explain_action(
        self,
        action: Mapping[str, Any],
        context: Mapping[str, Any] | str | None = None,
    ) -> str:
        """Explain a single fired ``action`` via the configured backend.

        ``context`` is an optional vessel frame (mapping) or free-form
        string. Raises :class:`httpx.HTTPError` on backend failure — use
        :meth:`explain_action_safe` when a fallback sentence is acceptable.
        """
        prompt = self.build_action_prompt(action, context)
        if self.verbose:
            log.info("[narrator] %s %s: explain %s",
                     self.backend, self.model, action.get("action", "?"))
        return await self._generate(prompt)

    async def explain_action_safe(
        self,
        action: Mapping[str, Any],
        context: Mapping[str, Any] | str | None = None,
    ) -> str:
        """Like :meth:`explain_action` but never raises for backend failures.

        Degrades to the deterministic :func:`_describe_action` sentence.
        """
        try:
            return await self.explain_action(action, context)
        except Exception as exc:
            log.warning("[narrator] backend failed, using fallback: %s", exc)
            return _describe_action(action)

    async def narrate_frame(
        self,
        registry: Any,
        frame: Mapping[str, Any],
        *,
        safe: bool = True,
    ) -> str:
        """WatcherRegistry integration: evaluate ``registry`` on ``frame``
        and narrate the fired actions.

        With ``safe=True`` (default) backend failures degrade to fallback
        text; with ``safe=False`` they propagate as in :meth:`narrate`.
        """
        actions = registry.evaluate(frame)
        if safe:
            return await self.narrate_safe(actions, frame)
        return await self.narrate(actions, frame)

    async def narrate_safe(
        self,
        actions: list[Mapping[str, Any]],
        frame: Mapping[str, Any] | None = None,
    ) -> str:
        """Like :meth:`narrate` but never raises for backend failures.

        Degrades to a deterministic one-sentence-per-action fallback so the
        viewer always has something to show.
        """
        if not actions:
            return ""
        try:
            return await self.narrate(actions, frame)
        except Exception as exc:
            log.warning("[narrator] backend failed, using fallback: %s", exc)
            return self.fallback_text(actions)

    @staticmethod
    def fallback_text(actions: list[Mapping[str, Any]]) -> str:
        """Deterministic offline narration: one sentence per action."""
        return " ".join(_describe_action(a) for a in actions)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    async def __aenter__(self) -> "Narrator":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.aclose()


__all__ = [
    "Narrator",
    "ACTION_CONTEXT_TEMPLATE",
    "ACTION_EXPLANATION_TEMPLATE",
    "OLLAMA_BASE_URL",
    "OPENAI_BASE_URL",
    "SYSTEM_PROMPT",
]

"""
Live LLM behind the AIProvider seam (Section 46's "provider-independent AI
abstraction", Phase 11) - used only for open-ended Hunt Copilot questions
(Section 25). Structured asset/header explanations stay rule-based; see
knowledge.py's module docstring for why.

Credentials are resolved by the Anthropic SDK itself (ANTHROPIC_API_KEY,
ANTHROPIC_AUTH_TOKEN, or an `ant auth login` profile) - never hardcoded,
never read from Vajra's own settings. If nothing is configured, the SDK
call raises `anthropic.AuthenticationError`, which `ask_hunt_copilot()`
in knowledge.py turns into a plain, honest fallback message.

The system prompt hard-codes, in words, the same guardrails this codebase
already enforces in code (Section 34/35): never call something confirmed,
never invent impact or evidence, never assist outside authorized scope.
A model answering conversationally is easy to nudge into confident-sounding
overstatement, so these are stated explicitly rather than assumed.
"""
from __future__ import annotations

import anthropic

_SYSTEM_PROMPT = """You are Vajra Hunt Copilot, an assistant embedded inside Vajra Security Lab, an \
authorized bug bounty hunting workstation. You help a hunter understand what they've found during a \
real, authorized investigation.

Hard rules, no exceptions:
- Never state that a vulnerability is "confirmed" - only Vajra's structured pipeline (Investigation -> \
Validation -> Finding) or the hunter's own judgment can do that. Use language like "potential", "worth \
checking", "a signal, not proof".
- Never invent impact, evidence, or behavior that wasn't given to you in the supplied context. If you \
don't have enough information to answer, say what's missing instead of guessing.
- Never suggest or assist with testing anything outside the program's authorized scope, even hypothetically.
- Never suggest destructive, denial-of-service, or credential-theft techniques.
- If asked to help write a report section, ground it only in the real evidence given in the context - \
never embellish severity or certainty.
- You may answer in whatever language the hunter asks in.

You will be given real, already-collected context (asset details, investigation notes, a masked HTTP \
transaction, etc.) - use only that, plus general security knowledge, to answer. Keep answers concise \
and practical."""


class AnthropicProvider:
    name = "anthropic"

    def __init__(self) -> None:
        # Zero-arg client: resolves credentials from the environment itself.
        self._client = anthropic.AsyncAnthropic()

    async def ask(self, question: str, context: dict) -> str:
        context_block = "\n".join(f"- {k}: {v}" for k, v in context.items() if v)
        user_content = f"Context:\n{context_block}\n\nQuestion: {question}" if context_block else question

        response = await self._client.messages.create(
            model="claude-opus-5",
            max_tokens=1024,
            system=_SYSTEM_PROMPT,
            output_config={"effort": "low"},
            messages=[{"role": "user", "content": user_content}],
        )
        text = "".join(block.text for block in response.content if block.type == "text").strip()
        return text or "I couldn't generate a response for that - try rephrasing the question."

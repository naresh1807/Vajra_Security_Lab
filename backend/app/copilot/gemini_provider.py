"""Gemini implementation of the provider-independent Hunt Copilot seam."""
from __future__ import annotations

import os

import httpx

from app.core.config import settings

SYSTEM_PROMPT = """You are Vajra Hunt Copilot inside an authorized bug bounty workstation.
Never call a vulnerability confirmed, invent impact or evidence, assist outside authorized scope,
or suggest destructive, denial-of-service, or credential-theft techniques. Ground answers only in
the supplied masked context and general defensive security knowledge. State what evidence is missing.
Answer in English or Telugu according to the hunter's request. Keep answers concise and practical."""


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        if not self._api_key:
            raise ValueError("Gemini API key is not configured")

    async def ask(self, question: str, context: dict) -> str:
        context_block = "\n".join(f"- {key}: {value}" for key, value in context.items() if value)
        prompt = f"Context:\n{context_block}\n\nQuestion: {question}" if context_block else question
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent"
        payload = {
            "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {"maxOutputTokens": 1024, "temperature": 0.2},
        }
        async with httpx.AsyncClient(timeout=settings.gemini_timeout_seconds) as client:
            response = await client.post(url, headers={"x-goog-api-key": self._api_key}, json=payload)
            response.raise_for_status()
        data = response.json()
        texts = [part.get("text", "") for candidate in data.get("candidates", []) for part in candidate.get("content", {}).get("parts", [])]
        answer = "".join(texts).strip()
        return answer or "Gemini returned no text. Try rephrasing the question."

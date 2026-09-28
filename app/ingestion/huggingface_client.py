"""Hugging Face sentiment analysis client with heuristic fallback."""

from __future__ import annotations
import logging
from typing import Any
import requests
from flask import current_app

log = logging.getLogger(__name__)


class HuggingFaceClient:
    """Client for sentiment scoring via external API with heuristic fallback."""

    def __init__(self, api_url: str | None = None, api_token: str | None = None) -> None:
        self.api_url = api_url or (current_app.config.get("HF_API_URL") if current_app else "https://amrmohsen-nexora-sentiment-api.hf.space/predict")
        self.api_token = api_token or (current_app.config.get("HUGGINGFACE_API_KEY") if current_app else None)

    def analyze_sentiment(self, text: str) -> tuple[float, float, str]:
        """Evaluate text sentiment returning (score [-1.0, 1.0], confidence [0.0, 1.0], label)."""
        if not text or not text.strip():
            return 0.0, 0.5, "neutral"

        payload = {"text": text[:2000]}
        headers = {}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        try:
            res = requests.post(self.api_url, json=payload, headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                score = float(data.get("score") or data.get("sentiment_score") or 0.0)
                confidence = float(data.get("confidence") or 0.7)
                label = data.get("label") or ("positive" if score > 0.1 else "negative" if score < -0.1 else "neutral")
                return score, confidence, label

        except requests.RequestException as exc:
            log.debug("HuggingFaceClient: sentiment API unavailable (%s), using rule heuristic", exc)

        return self._heuristic_sentiment(text)

    def _heuristic_sentiment(self, text: str) -> tuple[float, float, str]:
        """Simple lexicon heuristic fallback."""
        lower = text.lower()
        pos_words = {"great", "excellent", "amazing", "best", "love", "breakthrough", "superior", "impressive", "top"}
        neg_words = {"bad", "terrible", "worst", "fail", "broken", "disappointing", "poor", "issue", "bug", "scam"}

        tokens = set(lower.split())
        pos_count = len(tokens & pos_words)
        neg_count = len(tokens & neg_words)

        if pos_count > neg_count:
            return min(0.3 + 0.1 * (pos_count - neg_count), 0.9), 0.6, "positive"
        if neg_count > pos_count:
            return max(-0.3 - 0.1 * (neg_count - pos_count), -0.9), 0.6, "negative"
        return 0.0, 0.5, "neutral"

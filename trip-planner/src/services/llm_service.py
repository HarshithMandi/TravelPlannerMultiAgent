import logging
from typing import Any, Dict, List, Optional
import requests
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)


class SarvamLLMService:
    """Simple Sarvam LLM wrapper. Expects SARVAM_API_KEY and model name.

    This implementation uses a configurable HTTP endpoint. Replace endpoint
    details with the real Sarvam client when available.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "sarvam-m",
        base_url: Optional[str] = None,
        enabled: Optional[bool] = None,
    ):
        self.api_key = (api_key or "").strip()
        self.model = model
        self.base_url = base_url or "https://api.sarvam.example/v1/chat"
        if enabled is None:
            # Default to disabled for placeholder/test keys.
            self.enabled = bool(self.api_key) and self.api_key.lower() not in {"dummy", "test", "xxx"}
        else:
            self.enabled = bool(enabled)

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    def chat(self, messages: List[Dict[str, str]], timeout: int = 30) -> Dict[str, Any]:
        if not self.enabled:
            raise RuntimeError("SarvamLLMService is disabled")

        # Prefer official SDK when installed.
        try:
            from sarvamai import SarvamAI

            client = SarvamAI(api_subscription_key=self.api_key)
            try:
                resp = client.chat.completions(model=self.model, messages=messages)
            except Exception:
                # Some SDK versions expose create()
                resp = client.chat.completions.create(model=self.model, messages=messages)

            # Normalize to dict.
            if isinstance(resp, dict):
                return resp
            if hasattr(resp, "model_dump"):
                return resp.model_dump()
            if hasattr(resp, "dict"):
                return resp.dict()
            return {"raw": resp}
        except ImportError:
            pass

        # Fallback HTTP call (kept for environments without SDK).
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages}
        logger.debug("Sending chat to Sarvam model %s via HTTP fallback", self.model)
        resp = requests.post(self.base_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def chat_text(self, system: str, user: str, timeout: int = 30) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        data = self.chat(messages, timeout=timeout)
        # assume response structure {choices:[{message:{content:..}}]}
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("Unexpected Sarvam response: %s", data)
            return ""

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

    def __init__(self, api_key: str, model: str = "sarvam-m", base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url or "https://api.sarvam.example/v1/chat"

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    def chat(self, messages: List[Dict[str, str]], timeout: int = 30) -> Dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        payload = {"model": self.model, "messages": messages}
        logger.debug("Sending chat to Sarvam model %s", self.model)
        # Note: this is a placeholder HTTP call; swap for official SDK if available.
        resp = requests.post(self.base_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def chat_text(self, system: str, user: str) -> str:
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        data = self.chat(messages)
        # assume response structure {choices:[{message:{content:..}}]}
        try:
            return data["choices"][0]["message"]["content"]
        except Exception:
            logger.exception("Unexpected Sarvam response: %s", data)
            return ""

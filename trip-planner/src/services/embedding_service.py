import logging
import hashlib
from typing import List
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)


class OpenAIEmbeddingService:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        self.api_key = api_key
        self.model = model

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        logger.debug("Embedding batch of %d texts", len(texts))
        try:
            from openai import OpenAI

            client = OpenAI(api_key=self.api_key)
            resp = client.embeddings.create(model=self.model, input=texts)
            return [item.embedding for item in resp.data]
        except Exception as exc:
            logger.warning("OpenAI embedding unavailable, using deterministic fallback: %s", exc)
            return [self._fallback_embedding(text) for text in texts]

    def _fallback_embedding(self, text: str, dimensions: int = 16) -> List[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: List[float] = []
        for index in range(dimensions):
            byte_value = digest[index % len(digest)]
            values.append((byte_value / 255.0) * 2.0 - 1.0)
        return values

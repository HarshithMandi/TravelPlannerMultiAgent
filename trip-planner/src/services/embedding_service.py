import logging
from typing import List
import openai
from tenacity import retry, wait_exponential, stop_after_attempt

logger = logging.getLogger(__name__)


class OpenAIEmbeddingService:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        openai.api_key = api_key
        self.model = model

    @retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        logger.debug("Embedding batch of %d texts", len(texts))
        resp = openai.Embedding.create(model=self.model, input=texts)
        return [e["embedding"] for e in resp["data"]]

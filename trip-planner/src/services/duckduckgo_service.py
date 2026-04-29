import logging
from typing import Dict, List

import requests

logger = logging.getLogger(__name__)


class DuckDuckGoSearchService:
    """Small wrapper around DuckDuckGo's Instant Answer API.

    It is fast, free, and keyless, so it is useful as a first-pass source before
    falling back to slower geo/radius APIs.
    """

    def search(self, query: str, *, limit: int = 5, timeout: int = 6) -> List[Dict]:
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}

        try:
            response = requests.get("https://api.duckduckgo.com/", params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.warning("DuckDuckGo search failed: %s", exc)
            return []

        results: List[Dict] = []
        self._append_result(results, data.get("Heading"), data.get("AbstractText"), data.get("AbstractURL"), "duckduckgo")
        for topic in data.get("RelatedTopics", []) or []:
            if "Topics" in topic:
                for child in topic.get("Topics", []) or []:
                    self._append_topic(results, child)
            else:
                self._append_topic(results, topic)

            if len(results) >= limit:
                break

        return results[:limit]

    def _append_topic(self, results: List[Dict], topic: Dict) -> None:
        text = str(topic.get("Text") or "").strip()
        if not text:
            return
        name, _, summary = text.partition(" - ")
        self._append_result(results, name or text, summary or text, topic.get("FirstURL"), "duckduckgo")

    def _append_result(self, results: List[Dict], name: str, summary: str, url: str, source: str) -> None:
        name = str(name or "").strip()
        if not name:
            return
        if any(existing.get("name") == name for existing in results):
            return
        results.append(
            {
                "name": name,
                "summary": str(summary or "").strip(),
                "url": str(url or "").strip(),
                "source": source,
            }
        )

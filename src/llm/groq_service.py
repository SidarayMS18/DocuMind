"""
Groq LLM service — 100% FREE at console.groq.com
Keys start with gsk_...
Models: llama-3.3-70b-versatile, mixtral-8x7b-32768
"""

import logging
import time
import os
import re
import json
from dataclasses import dataclass
from typing import List, Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class GroqResponse:
    text: str
    confidence_score: float
    grounded: bool
    sources: List[Any]
    processing_time_ms: int
    model_name: str


class GroqService:
    MODEL = "llama-3.3-70b-versatile"  # best free model on Groq

    def __init__(self, api_key: Optional[str] = None):
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "").strip()
        self._client = None

        if self.api_key:
            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key)
                logger.info(f"Groq initialized — model: {self.MODEL}")
            except Exception as e:
                logger.error(f"Groq init failed: {e}")
        else:
            logger.warning("GROQ_API_KEY not set")

    @property
    def available(self) -> bool:
        return self._client is not None

    def generate_response(self, query: str, search_results: List[Any]) -> GroqResponse:
        start = time.time()

        if not search_results:
            return GroqResponse(
                text="No relevant documents found. Please upload documents first.",
                confidence_score=0.0, grounded=False, sources=[],
                processing_time_ms=0, model_name=self.MODEL
            )

        context = self._build_context(search_results)
        answer = self._call(query, context) if self._client else self._extractive(query, search_results)
        elapsed = int((time.time() - start) * 1000)

        return GroqResponse(
            text=answer,
            confidence_score=0.93 if self._client else 0.55,
            grounded=True,
            sources=self._build_sources(search_results),
            processing_time_ms=elapsed,
            model_name=self.MODEL if self._client else "extractive"
        )

    def structure_for_document(self, query: str, context: str) -> Dict[str, Any]:
        if not self._client:
            return {}

        prompt = f"""You are an expert document analyst.
Read the context and return ONLY a valid JSON object (no markdown, no code fences):
{{
  "title": "clear descriptive title",
  "abstract": "3-4 sentence comprehensive summary",
  "introduction": "detailed introduction paragraph",
  "methodology": "detailed methodology paragraph",
  "results": "detailed results paragraph",
  "conclusion": "strong conclusion paragraph",
  "points": ["specific finding 1","specific finding 2","specific finding 3","specific finding 4","specific finding 5"]
}}

Rules: Use ONLY info from context. Be specific. Each section 2-4 sentences minimum.

=== CONTEXT ===
{context[:4000]}

=== QUERY ===
{query}

JSON only:"""

        try:
            resp = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            raw = resp.choices[0].message.content.strip()
            raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'^```\s*',     '', raw, flags=re.MULTILINE)
            raw = re.sub(r'\s*```$',     '', raw, flags=re.MULTILINE)
            result = json.loads(raw.strip())
            logger.info(f"Groq structured: '{result.get('title','')[:60]}'")
            return result
        except Exception as e:
            logger.error(f"Groq structure failed: {e}")
            return {}

    def _call(self, query: str, context: str) -> str:
        try:
            resp = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{
                    "role": "user",
                    "content": f"""Answer based ONLY on the document context below.
Be accurate, concise, and well-structured. Use bullet points where helpful.

=== CONTEXT ===
{context}

=== QUESTION ===
{query}

=== ANSWER ==="""
                }],
                temperature=0.3,
                max_tokens=1000
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Groq call failed: {e}")
            return self._extractive(query, [])

    def _build_context(self, results: List[Any]) -> str:
        parts = []
        for i, r in enumerate(results[:6], 1):
            parts.append(
                f"[Source {i} — {getattr(r,'document_name','Doc')}, "
                f"Page {getattr(r,'page_number',0)}]:\n{getattr(r,'text','')}"
            )
        return "\n\n---\n\n".join(parts)

    def _build_sources(self, results: List[Any]) -> List[Any]:
        return [type('Src', (), {
            'document_name':   getattr(r, 'document_name', 'Document'),
            'page_number':     getattr(r, 'page_number', 0),
            'text_excerpt':    getattr(r, 'text', '')[:300],
            'relevance_score': getattr(r, 'score', 0.0),
            'highlighted_image_url': None
        })() for r in results[:5]]

    def _extractive(self, query: str, results: List[Any]) -> str:
        if not results:
            return "No content found."
        r = results[0]
        return f"From {getattr(r,'document_name','Document')}:\n\n{getattr(r,'text','')[:500]}"

    def get_service_status(self) -> Dict[str, Any]:
        return {"service": "GroqService", "model": self.MODEL, "available": self.available}

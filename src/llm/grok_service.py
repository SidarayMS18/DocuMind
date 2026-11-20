"""
Grok LLM service — uses xAI Grok API (OpenAI-compatible).
Get your API key at: https://console.x.ai/
"""

import logging
import time
import os
import re
import json
from dataclasses import dataclass, field
from typing import List, Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class GrokResponse:
    text: str
    confidence_score: float
    grounded: bool
    sources: List[Any]
    processing_time_ms: int
    model_name: str


class GrokService:
    """LLM service using xAI Grok API (OpenAI-compatible)."""

    BASE_URL = "https://api.x.ai/v1"
    MODEL    = "grok-3-mini"   # free tier model

    def __init__(self, api_key: Optional[str] = None):
        from dotenv import load_dotenv
        load_dotenv()
        self.api_key = api_key or os.getenv("GROK_API_KEY", "").strip()
        self._client = None

        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.BASE_URL
                )
                logger.info(f"Grok initialized — model: {self.MODEL}")
            except Exception as e:
                logger.error(f"Grok init failed: {e}")
        else:
            logger.warning("GROK_API_KEY not set")

    @property
    def available(self) -> bool:
        return self._client is not None

    # ── Main answer generation ────────────────────────────────────────────────

    def generate_response(self, query: str, search_results: List[Any]) -> GrokResponse:
        start = time.time()

        if not search_results:
            return GrokResponse(
                text="No relevant documents found. Please upload documents first.",
                confidence_score=0.0, grounded=False, sources=[],
                processing_time_ms=0, model_name=self.MODEL
            )

        context = self._build_context(search_results)

        if self._client:
            answer = self._call_grok(query, context)
        else:
            answer = self._extractive_answer(query, search_results)

        elapsed = int((time.time() - start) * 1000)
        sources  = self._build_sources(search_results)

        return GrokResponse(
            text=answer,
            confidence_score=0.93 if self._client else 0.55,
            grounded=True,
            sources=sources,
            processing_time_ms=elapsed,
            model_name=self.MODEL if self._client else "extractive"
        )

    # ── Document structuring ──────────────────────────────────────────────────

    def structure_for_document(self, query: str, context: str) -> Dict[str, Any]:
        """Ask Grok to return structured JSON for document generation."""
        if not self._client:
            return {}

        prompt = f"""You are an expert document analyst and writer.
Read the document context carefully and create a well-structured, accurate document.

Return ONLY a valid JSON object — no markdown, no code fences, no explanation:
{{
  "title": "A clear descriptive title based on the document content",
  "abstract": "Comprehensive 3-4 sentence summary of the entire document",
  "introduction": "Detailed introduction paragraph explaining background and purpose",
  "methodology": "Detailed paragraph describing methods, approach, or techniques used",
  "results": "Detailed paragraph describing key findings, results, or outcomes",
  "conclusion": "Strong conclusion paragraph with final thoughts and implications",
  "points": [
    "Specific key insight or finding 1",
    "Specific key insight or finding 2",
    "Specific key insight or finding 3",
    "Specific key insight or finding 4",
    "Specific key insight or finding 5"
  ]
}}

Rules:
- Use ONLY information from the provided context
- Be specific and accurate — no generic filler text
- Each section must be 2-4 sentences minimum
- Points must be concrete facts from the document

=== DOCUMENT CONTEXT ===
{context[:5000]}

=== FOCUS/QUERY ===
{query}

Return ONLY the JSON:"""

        try:
            resp = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1500
            )
            raw = resp.choices[0].message.content.strip()
            # Strip any accidental markdown fences
            raw = re.sub(r'^```json\s*', '', raw, flags=re.MULTILINE)
            raw = re.sub(r'^```\s*',     '', raw, flags=re.MULTILINE)
            raw = re.sub(r'\s*```$',     '', raw, flags=re.MULTILINE)
            result = json.loads(raw.strip())
            logger.info(f"Grok structured doc: '{result.get('title','')[:60]}'")
            return result
        except Exception as e:
            logger.error(f"Grok structure_for_document failed: {e}")
            return {}

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _call_grok(self, query: str, context: str) -> str:
        prompt = f"""You are an expert document assistant.
Answer the question based ONLY on the provided document context.
Be accurate, concise, and well-structured. Use bullet points where appropriate.
If the answer is not in the context, say "This information is not available in the provided documents."

=== DOCUMENT CONTEXT ===
{context}

=== QUESTION ===
{query}

=== ANSWER ==="""

        try:
            resp = self._client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000
            )
            return resp.choices[0].message.content
        except Exception as e:
            logger.error(f"Grok API call failed: {e}")
            return f"Grok API error: {e}"

    def _build_context(self, results: List[Any]) -> str:
        parts = []
        for i, r in enumerate(results[:6], 1):
            text = getattr(r, 'text', str(r))
            doc  = getattr(r, 'document_name', 'Document')
            page = getattr(r, 'page_number', 0)
            parts.append(f"[Source {i} — {doc}, Page {page}]:\n{text}")
        return "\n\n---\n\n".join(parts)

    def _build_sources(self, results: List[Any]) -> List[Any]:
        sources = []
        for r in results[:5]:
            sources.append(type('Src', (), {
                'document_name':   getattr(r, 'document_name', 'Document'),
                'page_number':     getattr(r, 'page_number', 0),
                'text_excerpt':    getattr(r, 'text', '')[:300],
                'relevance_score': getattr(r, 'score', 0.0),
                'highlighted_image_url': None
            })())
        return sources

    def _extractive_answer(self, query: str, results: List[Any]) -> str:
        query_words = set(query.lower().split())
        scored = []
        for r in results[:5]:
            for sent in getattr(r, 'text', '').replace('\n', ' ').split('.'):
                sent = sent.strip()
                if len(sent) < 30:
                    continue
                overlap = len(query_words & set(sent.lower().split()))
                if overlap > 0:
                    scored.append((overlap, sent))
        scored.sort(reverse=True)
        top = [s for _, s in scored[:5]]
        if top:
            return "Based on the documents:\n\n" + "\n\n".join(f"• {s}." for s in top)
        return getattr(results[0], 'text', '')[:600] if results else "No relevant content found."

    def get_service_status(self) -> Dict[str, Any]:
        return {
            "service": "GrokService",
            "model": self.MODEL,
            "available": self.available,
            "base_url": self.BASE_URL
        }

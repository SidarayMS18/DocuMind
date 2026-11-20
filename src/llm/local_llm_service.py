"""Local LLM service — works without any API key using smart extraction."""

import logging
import time
import re
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class LocalLLMResponse:
    text: str
    confidence_score: float
    grounded: bool
    sources: List[Any]
    processing_time_ms: int
    model_name: str


STOP_WORDS = {
    'what','is','the','a','an','are','was','were','how','why','when',
    'where','who','this','that','these','those','it','its','in','on',
    'at','to','for','of','and','or','but','with','from','by','about',
    'tell','me','give','explain','describe','list','show','find','get'
}


class LocalLLMService:
    """Smart extractive LLM — no API key needed, works offline."""

    def __init__(self, model: str = "local-extractive"):
        self.model = model
        self._ollama_available = None

    def _check_ollama(self) -> bool:
        if self._ollama_available is not None:
            return self._ollama_available
        try:
            import ollama
            ollama.list()
            self._ollama_available = True
        except Exception:
            self._ollama_available = False
        return self._ollama_available

    def generate_response(self, query: str, search_results: List[Any]) -> LocalLLMResponse:
        start = time.time()

        if not search_results:
            return LocalLLMResponse(
                text="No relevant documents found. Please upload documents first.",
                confidence_score=0.0, grounded=False, sources=[],
                processing_time_ms=0, model_name=self.model
            )

        if self._check_ollama():
            answer = self._generate_with_ollama(query, search_results)
            model_name = "ollama"
            conf = 0.85
        else:
            answer = self._smart_extract(query, search_results)
            model_name = "extractive"
            conf = 0.65

        elapsed = int((time.time() - start) * 1000)

        sources = []
        for r in search_results[:5]:
            sources.append(type('Source', (), {
                'document_name':   getattr(r, 'document_name', 'Document'),
                'page_number':     getattr(r, 'page_number', 0),
                'text_excerpt':    getattr(r, 'text', '')[:300],
                'relevance_score': getattr(r, 'score', 0.0),
                'highlighted_image_url': None
            })())

        return LocalLLMResponse(
            text=answer, confidence_score=conf,
            grounded=True, sources=sources,
            processing_time_ms=elapsed, model_name=model_name
        )

    def structure_for_document(self, query: str, context: str) -> Dict[str, Any]:
        """Structure document content without an API key."""
        lines = [l.strip() for l in context.split('\n') if l.strip()]
        sentences = []
        for line in lines:
            for s in re.split(r'(?<=[.!?])\s+', line):
                s = s.strip()
                if len(s) > 40:
                    sentences.append(s)

        # Extract title — first meaningful heading or line
        title = query.replace("Structure this document:", "").strip()
        for line in lines[:10]:
            clean = re.sub(r'^\[.*?\]:', '', line).strip()
            if 10 < len(clean) < 120 and not clean.startswith('•'):
                title = clean
                break

        # Score sentences by section keywords
        section_kw = {
            'abstract':     ['abstract','summary','overview','this paper','this study','this report','we present','we propose'],
            'introduction': ['introduction','background','motivation','problem','challenge','context','aim','objective','purpose'],
            'methodology':  ['method','approach','technique','algorithm','framework','architecture','design','implement','procedure','model','system'],
            'results':      ['result','finding','performance','accuracy','evaluation','experiment','test','achieve','show','demonstrate','table','figure'],
            'conclusion':   ['conclusion','future','discuss','implication','limitation','summary','overall','finally','therefore','thus'],
        }

        sections: Dict[str, List[str]] = {k: [] for k in section_kw}

        for sent in sentences:
            sl = sent.lower()
            for sec, kws in section_kw.items():
                if any(kw in sl for kw in kws):
                    if len(sections[sec]) < 4:
                        sections[sec].append(sent)

        # Fill empty sections with best remaining sentences
        used = {s for sents in sections.values() for s in sents}
        remaining = [s for s in sentences if s not in used]

        for sec in section_kw:
            if not sections[sec] and remaining:
                sections[sec] = remaining[:2]
                remaining = remaining[2:]

        def join(sents): return ' '.join(sents[:3]) if sents else ''

        # Extract bullet points
        points = []
        for line in lines:
            clean = re.sub(r'^[\-\*•\d\.]+\s*', '', line).strip()
            if 20 < len(clean) < 200:
                points.append(clean)
        points = list(dict.fromkeys(points))[:6]  # deduplicate

        if not points:
            # Generate from top sentences
            for s in sentences[:8]:
                if len(s) < 150:
                    points.append(s)
            points = points[:5]

        return {
            "title":        title[:120],
            "abstract":     join(sections['abstract']) or join(sentences[:2]),
            "introduction": join(sections['introduction']) or join(sentences[2:4]),
            "methodology":  join(sections['methodology']) or join(sentences[4:6]),
            "results":      join(sections['results']) or join(sentences[6:8]),
            "conclusion":   join(sections['conclusion']) or join(sentences[-2:]),
            "points":       points,
            "tables":       []
        }

    def _smart_extract(self, query: str, results: List[Any]) -> str:
        """Smart extractive answer grouped by document."""
        query_words = set(query.lower().split()) - STOP_WORDS

        scored = []
        for r in results[:8]:
            text = getattr(r, 'text', '')
            doc  = getattr(r, 'document_name', 'Document')
            page = getattr(r, 'page_number', 0)
            for sent in re.split(r'(?<=[.!?])\s+', text.replace('\n', ' ')):
                sent = sent.strip()
                if len(sent) < 40:
                    continue
                sw = set(sent.lower().split()) - STOP_WORDS
                overlap = len(query_words & sw)
                if overlap > 0:
                    scored.append((overlap, sent, doc, page))

        scored.sort(reverse=True)
        top = scored[:6]

        if not top:
            r = results[0]
            text = getattr(r, 'text', '')[:500]
            doc  = getattr(r, 'document_name', 'Document')
            return f"📄 **{doc}**\n\n{text}\n\n---\n💡 *Add a free Gemini API key in Settings for AI-powered answers.*"

        # Group by document
        by_doc: Dict[str, List[str]] = {}
        for _, sent, doc, page in top:
            key = f"{doc} (Page {page})"
            by_doc.setdefault(key, []).append(sent)

        answer = ""
        for doc_key, sents in by_doc.items():
            answer += f"📄 **{doc_key}**\n"
            for s in sents[:3]:
                answer += f"• {s}\n"
            answer += "\n"

        answer += "---\n💡 *Add a free Gemini API key in Settings for better AI answers.*"
        return answer.strip()

    def _generate_with_ollama(self, query: str, results: List[Any]) -> str:
        try:
            import ollama
            context = "\n\n".join([
                f"[{getattr(r,'document_name','Doc')}, Page {getattr(r,'page_number',0)}]:\n{getattr(r,'text','')}"
                for r in results[:5]
            ])
            resp = ollama.chat(
                model="llama3.2",
                messages=[{"role": "user", "content": f"Answer based on context only.\n\nContext:\n{context}\n\nQuestion: {query}\n\nAnswer:"}]
            )
            return resp['message']['content']
        except Exception as e:
            return self._smart_extract(query, results)

    def get_service_status(self) -> Dict[str, Any]:
        return {
            "service": "LocalLLMService",
            "model": self.model,
            "ollama_available": self._check_ollama()
        }

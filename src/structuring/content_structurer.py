"""Structuring module: converts RAG output into clean structured JSON."""

import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class StructuredDocument:
    """Structured document representation."""
    title: str = ""
    abstract: str = ""
    introduction: str = ""
    methodology: str = ""
    results: str = ""
    conclusion: str = ""
    points: List[str] = field(default_factory=list)
    tables: List[Dict[str, Any]] = field(default_factory=list)
    raw_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "abstract": self.abstract,
            "introduction": self.introduction,
            "methodology": self.methodology,
            "results": self.results,
            "conclusion": self.conclusion,
            "points": self.points,
            "tables": self.tables,
        }


# Section keyword mapping
SECTION_KEYWORDS = {
    "abstract": ["abstract", "summary", "overview", "synopsis"],
    "introduction": ["introduction", "background", "context", "intro", "problem statement"],
    "methodology": ["methodology", "methods", "approach", "procedure", "technique", "implementation"],
    "results": ["results", "findings", "outcomes", "evaluation", "performance", "analysis"],
    "conclusion": ["conclusion", "conclusions", "future work", "discussion", "closing remarks"],
}


class ContentStructurer:
    """Converts raw RAG output into structured JSON sections."""

    def structure_rag_output(self, rag_text: str, query: str = "") -> StructuredDocument:
        """Main entry point: structure raw RAG text into sections."""
        doc = StructuredDocument(raw_text=rag_text)

        # Extract title
        doc.title = self._extract_title(rag_text, query)

        # Split into sections
        sections = self._split_into_sections(rag_text)

        # Map sections to fields
        doc.abstract = sections.get("abstract", self._generate_abstract(rag_text))
        doc.introduction = sections.get("introduction", "")
        doc.methodology = sections.get("methodology", "")
        doc.results = sections.get("results", "")
        doc.conclusion = sections.get("conclusion", "")

        # Extract bullet points
        doc.points = self._extract_key_points(rag_text)

        # Extract tables
        doc.tables = self._extract_tables(rag_text)

        # Fill empty sections with intelligent defaults
        doc = self._fill_empty_sections(doc, rag_text)

        logger.info(f"Structured document: title='{doc.title}', "
                    f"sections filled={sum(1 for v in doc.to_dict().values() if v)}")
        return doc

    def _extract_title(self, text: str, query: str) -> str:
        """Extract or infer document title."""
        # Try first heading
        heading_match = re.search(r'^#+\s+(.+)$', text, re.MULTILINE)
        if heading_match:
            return heading_match.group(1).strip()

        # Try first bold line
        bold_match = re.search(r'\*\*(.+?)\*\*', text)
        if bold_match:
            return bold_match.group(1).strip()

        # Use query as title if available
        if query:
            return query[:80].strip()

        # Use first non-empty line
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 5:
                return line[:80]

        return "Generated Document"

    def _split_into_sections(self, text: str) -> Dict[str, str]:
        """Split text into named sections based on headings."""
        sections = {}
        current_section = None
        current_content = []

        lines = text.split('\n')
        for line in lines:
            stripped = line.strip().lower()

            # Check if this line is a section heading
            matched_section = None
            for section_name, keywords in SECTION_KEYWORDS.items():
                for kw in keywords:
                    if re.search(rf'\b{re.escape(kw)}\b', stripped):
                        # Confirm it looks like a heading (short line or has heading markers)
                        if len(stripped) < 60 or re.match(r'^#+\s', line):
                            matched_section = section_name
                            break
                if matched_section:
                    break

            if matched_section:
                # Save previous section
                if current_section and current_content:
                    sections[current_section] = ' '.join(current_content).strip()
                current_section = matched_section
                current_content = []
            elif current_section:
                current_content.append(line.strip())

        # Save last section
        if current_section and current_content:
            sections[current_section] = ' '.join(current_content).strip()

        return sections

    def _generate_abstract(self, text: str) -> str:
        """Generate abstract from first meaningful paragraph."""
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        for para in paragraphs:
            # Skip headings and very short lines
            if len(para) > 100 and not para.startswith('#'):
                return para[:500]
        # Fallback: first 300 chars
        return text[:300].strip()

    def _extract_key_points(self, text: str) -> List[str]:
        """Extract bullet points and numbered lists from text."""
        points = []

        # Match bullet points: -, *, •, or numbered
        pattern = r'^[\s]*(?:[-*•]|\d+[.)]) +(.+)$'
        for match in re.finditer(pattern, text, re.MULTILINE):
            point = match.group(1).strip()
            if len(point) > 10:
                points.append(point)

        # Deduplicate while preserving order
        seen = set()
        unique_points = []
        for p in points:
            if p not in seen:
                seen.add(p)
                unique_points.append(p)

        return unique_points[:20]  # Cap at 20 points

    def _extract_tables(self, text: str) -> List[Dict[str, Any]]:
        """Extract markdown tables from text."""
        tables = []
        table_pattern = r'(\|.+\|\n\|[-| :]+\|\n(?:\|.+\|\n?)+)'

        for match in re.finditer(table_pattern, text):
            table_text = match.group(1)
            rows = [row.strip() for row in table_text.strip().split('\n')]

            if len(rows) < 2:
                continue

            # Parse headers
            headers = [h.strip() for h in rows[0].split('|') if h.strip()]

            # Skip separator row (row[1])
            for row in rows[2:]:
                cells = [c.strip() for c in row.split('|') if c.strip()]
                if cells and len(cells) == len(headers):
                    tables.append(dict(zip(headers, cells)))

        return tables

    def _fill_empty_sections(self, doc: StructuredDocument, full_text: str) -> StructuredDocument:
        """Fill empty sections by splitting remaining text intelligently."""
        # Split text into roughly equal parts for empty sections
        empty_sections = [s for s in ["introduction", "methodology", "results", "conclusion"]
                          if not getattr(doc, s)]

        if not empty_sections:
            return doc

        # Remove already-used content
        remaining = full_text
        used = [doc.abstract]
        for used_text in used:
            remaining = remaining.replace(used_text, "")

        # Split remaining into chunks
        sentences = re.split(r'(?<=[.!?])\s+', remaining.strip())
        chunk_size = max(1, len(sentences) // max(len(empty_sections), 1))

        for i, section in enumerate(empty_sections):
            start = i * chunk_size
            end = start + chunk_size
            chunk = ' '.join(sentences[start:end]).strip()
            if chunk:
                setattr(doc, section, chunk)

        return doc

    def structure_from_llm_response(self, llm_answer: str, sources: List[Dict] = None) -> StructuredDocument:
        """Structure content from LLM response + sources."""
        doc = self.structure_rag_output(llm_answer)

        # Enrich with source metadata if available
        if sources:
            source_texts = []
            for src in sources[:3]:
                excerpt = src.get("text_excerpt", "")
                doc_name = src.get("document_name", "")
                if excerpt:
                    source_texts.append(f"[{doc_name}]: {excerpt}")

            if source_texts and not doc.introduction:
                doc.introduction = "\n\n".join(source_texts)

        return doc

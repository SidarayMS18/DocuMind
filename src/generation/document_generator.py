"""Document generator for PDF, PPT, and Excel output formats."""

import io
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    """Result of document generation."""
    success: bool
    content: bytes
    format: str
    filename: str
    mime_type: str
    error_message: Optional[str] = None


class PDFGenerator:
    """Generate PDF documents from HTML content using ReportLab."""

    def generate(self, html_content: str, filename: str = "output.pdf") -> GenerationResult:
        # Use ReportLab directly — works on Windows without system DLLs
        return self._generate_with_reportlab(html_content, filename)

    def _generate_with_reportlab(self, html_content: str, filename: str) -> GenerationResult:
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
            from reportlab.lib import colors
            import re

            buffer = io.BytesIO()
            doc = SimpleDocTemplate(
                buffer, pagesize=A4,
                rightMargin=0.8*inch, leftMargin=0.8*inch,
                topMargin=0.8*inch, bottomMargin=0.8*inch
            )
            styles = getSampleStyleSheet()

            # Custom styles
            title_style = ParagraphStyle(
                'CustomTitle', parent=styles['Title'],
                fontSize=22, spaceAfter=16, textColor=colors.HexColor('#0070C0')
            )
            h2_style = ParagraphStyle(
                'CustomH2', parent=styles['Heading2'],
                fontSize=14, spaceAfter=8, spaceBefore=16,
                textColor=colors.HexColor('#333333')
            )
            body_style = ParagraphStyle(
                'CustomBody', parent=styles['Normal'],
                fontSize=11, spaceAfter=8, leading=16
            )
            bullet_style = ParagraphStyle(
                'CustomBullet', parent=styles['Normal'],
                fontSize=11, spaceAfter=4, leading=14,
                leftIndent=20, bulletIndent=10
            )

            story = []

            # Strip HTML tags and parse structure
            # Remove style blocks
            clean = re.sub(r'<style[^>]*>.*?</style>', '', html_content, flags=re.DOTALL)
            # Extract content between tags
            clean = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n###TITLE###\1###END###\n', clean, flags=re.DOTALL)
            clean = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n###H2###\1###END###\n', clean, flags=re.DOTALL)
            clean = re.sub(r'<li[^>]*>(.*?)</li>', r'\n###BULLET###\1###END###\n', clean, flags=re.DOTALL)
            clean = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', clean, flags=re.DOTALL)
            clean = re.sub(r'<[^>]+>', '', clean)  # Remove remaining tags
            clean = re.sub(r'&amp;', '&', clean)
            clean = re.sub(r'&lt;', '<', clean)
            clean = re.sub(r'&gt;', '>', clean)
            clean = re.sub(r'&nbsp;', ' ', clean)

            for line in clean.split('\n'):
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 0.08*inch))
                    continue

                if line.startswith('###TITLE###'):
                    text = line.replace('###TITLE###', '').replace('###END###', '').strip()
                    if text:
                        story.append(Paragraph(text, title_style))
                        story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#0070C0')))
                        story.append(Spacer(1, 0.1*inch))
                elif line.startswith('###H2###'):
                    text = line.replace('###H2###', '').replace('###END###', '').strip()
                    if text:
                        story.append(Paragraph(text, h2_style))
                elif line.startswith('###BULLET###'):
                    text = line.replace('###BULLET###', '').replace('###END###', '').strip()
                    if text:
                        story.append(Paragraph(f"• {text}", bullet_style))
                else:
                    # Escape special chars for ReportLab
                    safe = line.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                    try:
                        story.append(Paragraph(safe, body_style))
                    except Exception:
                        story.append(Paragraph(re.sub(r'[^\x20-\x7E]', '', safe), body_style))

            if not story:
                story.append(Paragraph("Document generated successfully.", body_style))

            doc.build(story)
            return GenerationResult(
                success=True, content=buffer.getvalue(),
                format="pdf", filename=filename, mime_type="application/pdf"
            )
        except Exception as e:
            logger.error(f"ReportLab PDF generation failed: {e}")
            return GenerationResult(
                success=False, content=b"", format="pdf",
                filename=filename, mime_type="application/pdf",
                error_message=str(e)
            )


class PPTGenerator:
    """Generate PowerPoint presentations from structured data."""

    def generate(self, data: Dict[str, Any], filename: str = "output.pptx") -> GenerationResult:
        try:
            from pptx import Presentation
            from pptx.util import Inches, Pt
            from pptx.dml.color import RGBColor

            prs = Presentation()
            prs.slide_width = Inches(13.33)
            prs.slide_height = Inches(7.5)

            # Title slide
            self._add_title_slide(prs, data.get("title", "Document"), data.get("abstract", ""))

            # Content slides
            sections = [
                ("Introduction", data.get("introduction", "")),
                ("Methodology", data.get("methodology", "")),
                ("Results", data.get("results", "")),
                ("Conclusion", data.get("conclusion", "")),
            ]
            for title, content in sections:
                if content:
                    self._add_content_slide(prs, title, content)

            # Key points slide
            points = data.get("points", [])
            if points:
                self._add_bullet_slide(prs, "Key Points", points)

            # Tables slide
            tables = data.get("tables", [])
            if tables:
                self._add_table_slide(prs, "Data Tables", tables)

            buffer = io.BytesIO()
            prs.save(buffer)
            return GenerationResult(
                success=True, content=buffer.getvalue(),
                format="pptx", filename=filename,
                mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )
        except Exception as e:
            logger.error(f"PPT generation failed: {e}")
            return GenerationResult(
                success=False, content=b"", format="pptx",
                filename=filename,
                mime_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                error_message=str(e)
            )

    def _add_title_slide(self, prs, title: str, subtitle: str):
        from pptx.util import Pt
        from pptx.dml.color import RGBColor
        layout = prs.slide_layouts[0]
        slide = prs.slides.add_slide(layout)
        # Title
        tf = slide.shapes.title.text_frame
        tf.text = title
        tf.paragraphs[0].runs[0].font.size = Pt(32)
        tf.paragraphs[0].runs[0].font.bold = True
        tf.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)
        # Subtitle
        if len(slide.placeholders) > 1:
            sub_tf = slide.placeholders[1].text_frame
            sub_tf.text = subtitle[:300] if subtitle else ""
            if sub_tf.paragraphs[0].runs:
                sub_tf.paragraphs[0].runs[0].font.size = Pt(16)
                sub_tf.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x47, 0x55, 0x69)

    def _add_content_slide(self, prs, title: str, content: str):
        from pptx.util import Pt
        from pptx.dml.color import RGBColor
        layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(layout)
        # Title
        slide.shapes.title.text = title
        slide.shapes.title.text_frame.paragraphs[0].runs[0].font.size = Pt(24)
        slide.shapes.title.text_frame.paragraphs[0].runs[0].font.bold = True
        slide.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)
        # Content — split into sentences for readability
        if len(slide.placeholders) > 1:
            tf = slide.placeholders[1].text_frame
            tf.word_wrap = True
            # Split content into bullet points at sentence boundaries
            import re
            sentences = re.split(r'(?<=[.!?])\s+', content.strip())
            sentences = [s.strip() for s in sentences if len(s.strip()) > 10][:6]
            tf.clear()
            for i, sent in enumerate(sentences):
                p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
                p.text = sent
                p.level = 0
                if p.runs:
                    p.runs[0].font.size = Pt(14)
                    p.runs[0].font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)

    def _add_bullet_slide(self, prs, title: str, points: List):
        from pptx.util import Pt
        from pptx.dml.color import RGBColor
        layout = prs.slide_layouts[1]
        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = title
        slide.shapes.title.text_frame.paragraphs[0].runs[0].font.size = Pt(24)
        slide.shapes.title.text_frame.paragraphs[0].runs[0].font.bold = True
        slide.shapes.title.text_frame.paragraphs[0].runs[0].font.color.rgb = RGBColor(0x1E, 0x1B, 0x4B)
        if len(slide.placeholders) > 1:
            tf = slide.placeholders[1].text_frame
            tf.clear()
            for i, point in enumerate(points[:8]):
                p = tf.add_paragraph() if i > 0 else tf.paragraphs[0]
                p.text = str(point)
                p.level = 0
                if p.runs:
                    p.runs[0].font.size = Pt(14)
                    p.runs[0].font.color.rgb = RGBColor(0x1E, 0x29, 0x3B)

    def _add_table_slide(self, prs, title: str, tables: List[Dict]):
        from pptx.util import Inches, Pt
        layout = prs.slide_layouts[5]
        slide = prs.slides.add_slide(layout)
        slide.shapes.title.text = title
        if not tables:
            return
        first_table = tables[0] if isinstance(tables[0], dict) else {}
        if not first_table:
            return
        cols = list(first_table.keys())
        rows_data = [list(t.values()) for t in tables[:10]]
        rows = len(rows_data) + 1
        table = slide.shapes.add_table(rows, len(cols), Inches(0.5), Inches(1.5),
                                        Inches(12), Inches(4)).table
        for ci, col in enumerate(cols):
            table.cell(0, ci).text = str(col)
        for ri, row in enumerate(rows_data):
            for ci, val in enumerate(row):
                table.cell(ri + 1, ci).text = str(val)


class ExcelGenerator:
    """Generate Excel spreadsheets from structured data."""

    def generate(self, data: Dict[str, Any], filename: str = "output.xlsx") -> GenerationResult:
        try:
            import openpyxl
            from openpyxl.styles import Font, PatternFill, Alignment
            from openpyxl.utils import get_column_letter

            wb = openpyxl.Workbook()

            # Summary sheet
            ws = wb.active
            ws.title = "Summary"
            self._write_summary_sheet(ws, data)

            # Tables sheet if data has tables
            if data.get("tables"):
                ws_tables = wb.create_sheet("Tables")
                self._write_tables_sheet(ws_tables, data["tables"])

            # Key Points sheet
            if data.get("points"):
                ws_points = wb.create_sheet("Key Points")
                self._write_points_sheet(ws_points, data["points"])

            buffer = io.BytesIO()
            wb.save(buffer)
            return GenerationResult(
                success=True, content=buffer.getvalue(),
                format="xlsx", filename=filename,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except Exception as e:
            logger.error(f"Excel generation failed: {e}")
            return GenerationResult(
                success=False, content=b"", format="xlsx",
                filename=filename,
                mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                error_message=str(e)
            )

    def _write_summary_sheet(self, ws, data: Dict[str, Any]):
        from openpyxl.styles import Font, PatternFill, Alignment
        header_font = Font(bold=True, color="FFFFFF", size=12)
        header_fill = PatternFill(start_color="0070C0", end_color="0070C0", fill_type="solid")

        ws.column_dimensions['A'].width = 20
        ws.column_dimensions['B'].width = 80

        ws['A1'] = "Section"
        ws['B1'] = "Content"
        ws['A1'].font = header_font
        ws['B1'].font = header_font
        ws['A1'].fill = header_fill
        ws['B1'].fill = header_fill

        sections = [
            ("Title", data.get("title", "")),
            ("Abstract", data.get("abstract", "")),
            ("Introduction", data.get("introduction", "")),
            ("Methodology", data.get("methodology", "")),
            ("Results", data.get("results", "")),
            ("Conclusion", data.get("conclusion", "")),
        ]
        for row_idx, (section, content) in enumerate(sections, start=2):
            ws.cell(row=row_idx, column=1, value=section).font = Font(bold=True)
            cell = ws.cell(row=row_idx, column=2, value=str(content))
            cell.alignment = Alignment(wrap_text=True)
            ws.row_dimensions[row_idx].height = 60

    def _write_tables_sheet(self, ws, tables: List[Dict]):
        from openpyxl.styles import Font, PatternFill
        if not tables:
            return
        headers = list(tables[0].keys())
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="0070C0", end_color="0070C0", fill_type="solid")
        for ci, h in enumerate(headers, start=1):
            cell = ws.cell(row=1, column=ci, value=h)
            cell.font = header_font
            cell.fill = header_fill
        for ri, row in enumerate(tables, start=2):
            for ci, h in enumerate(headers, start=1):
                ws.cell(row=ri, column=ci, value=str(row.get(h, "")))

    def _write_points_sheet(self, ws, points: List):
        from openpyxl.styles import Font
        ws['A1'] = "Key Points"
        ws['A1'].font = Font(bold=True, size=14)
        for i, point in enumerate(points, start=2):
            ws.cell(row=i, column=1, value=f"• {point}")


class DocumentGeneratorService:
    """Unified service for generating documents in multiple formats."""

    def __init__(self):
        self.pdf_gen = PDFGenerator()
        self.ppt_gen = PPTGenerator()
        self.excel_gen = ExcelGenerator()

    def generate(
        self,
        data: Dict[str, Any],
        format_type: str,
        template: Optional[str] = None,
        filename: Optional[str] = None
    ) -> GenerationResult:
        """Generate document in specified format."""
        format_type = format_type.lower().strip()
        base_name = filename or data.get("title", "document").replace(" ", "_")[:40]

        if format_type == "pdf":
            html = template if template else self._build_default_html(data)
            return self.pdf_gen.generate(html, f"{base_name}.pdf")
        elif format_type in ("ppt", "pptx"):
            return self.ppt_gen.generate(data, f"{base_name}.pptx")
        elif format_type in ("excel", "xlsx"):
            return self.excel_gen.generate(data, f"{base_name}.xlsx")
        else:
            return GenerationResult(
                success=False, content=b"", format=format_type,
                filename=f"{base_name}.{format_type}",
                mime_type="application/octet-stream",
                error_message=f"Unsupported format: {format_type}"
            )

    def _build_default_html(self, data: Dict[str, Any]) -> str:
        """Build default HTML for PDF generation."""
        points_html = ""
        for p in data.get("points", []):
            points_html += f"<li>{p}</li>"

        tables_html = ""
        for table in data.get("tables", []):
            if isinstance(table, dict):
                tables_html += "<table><tr>"
                for k in table.keys():
                    tables_html += f"<th>{k}</th>"
                tables_html += "</tr><tr>"
                for v in table.values():
                    tables_html += f"<td>{v}</td>"
                tables_html += "</tr></table>"

        return f"""
<html><head><style>
body{{font-family:Arial,sans-serif;margin:40px;color:#333}}
h1{{color:#0070C0;border-bottom:2px solid #0070C0;padding-bottom:8px}}
h2{{color:#555;margin-top:25px}}
p{{line-height:1.7}}
ul{{margin-left:20px}}
table{{border-collapse:collapse;width:100%;margin:15px 0}}
th{{background:#0070C0;color:#fff;padding:8px;text-align:left}}
td{{border:1px solid #ddd;padding:8px}}
</style></head><body>
<h1>{data.get('title','Document')}</h1>
<h2>Abstract</h2><p>{data.get('abstract','')}</p>
<h2>Introduction</h2><p>{data.get('introduction','')}</p>
<h2>Methodology</h2><p>{data.get('methodology','')}</p>
<h2>Results</h2><p>{data.get('results','')}</p>
{'<h2>Key Points</h2><ul>' + points_html + '</ul>' if points_html else ''}
{tables_html}
<h2>Conclusion</h2><p>{data.get('conclusion','')}</p>
</body></html>"""

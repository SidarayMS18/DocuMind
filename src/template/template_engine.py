"""Template engine for mapping structured data to user-defined templates."""

import re
import logging
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from pathlib import Path


@dataclass
class TemplateValidationResult:
    """Result of template validation."""
    valid: bool
    missing_fields: List[str]
    extra_fields: List[str]
    message: str


@dataclass
class TemplateMappingResult:
    """Result of template mapping operation."""
    success: bool
    output: str
    format: str
    validation: TemplateValidationResult
    error_message: Optional[str] = None


class TemplateEngine:
    """Engine for processing templates with placeholder mapping."""
    
    # Supported placeholder patterns
    PLACEHOLDER_PATTERN = r'\{\{(\w+)\}\}'
    
    # Default templates for different formats
    DEFAULT_TEMPLATES = {
        "pdf": """
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        p { line-height: 1.6; }
        .section { margin-bottom: 20px; }
        .points { margin-left: 20px; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #007bff; color: white; }
    </style>
</head>
<body>
    <h1>{{title}}</h1>
    
    <div class="section">
        <h2>Abstract</h2>
        <p>{{abstract}}</p>
    </div>
    
    <div class="section">
        <h2>Introduction</h2>
        <p>{{introduction}}</p>
    </div>
    
    <div class="section">
        <h2>Methodology</h2>
        <p>{{methodology}}</p>
    </div>
    
    <div class="section">
        <h2>Results</h2>
        <p>{{results}}</p>
    </div>
    
    <div class="section">
        <h2>Key Points</h2>
        <div class="points">
            {{points}}
        </div>
    </div>
    
    <div class="section">
        <h2>Conclusion</h2>
        <p>{{conclusion}}</p>
    </div>
</body>
</html>
""",
        "ppt": """
# {{title}}

---

## Abstract
{{abstract}}

---

## Introduction
{{introduction}}

---

## Methodology
{{methodology}}

---

## Results
{{results}}

---

## Key Points
{{points}}

---

## Conclusion
{{conclusion}}
""",
        "excel": {
            "headers": ["Section", "Content"],
            "rows": [
                ["Title", "{{title}}"],
                ["Abstract", "{{abstract}}"],
                ["Introduction", "{{introduction}}"],
                ["Methodology", "{{methodology}}"],
                ["Results", "{{results}}"],
                ["Key Points", "{{points}}"],
                ["Conclusion", "{{conclusion}}"]
            ]
        }
    }
    
    def __init__(self):
        """Initialize template engine."""
        self.logger = logging.getLogger(__name__)
    
    def extract_placeholders(self, template: str) -> List[str]:
        """Extract all placeholders from template."""
        if isinstance(template, dict):
            # Handle dict templates (like Excel)
            template_str = str(template)
        else:
            template_str = template
        
        matches = re.findall(self.PLACEHOLDER_PATTERN, template_str)
        return list(set(matches))  # Remove duplicates
    
    def validate_template(self, template: str, data: Dict[str, Any]) -> TemplateValidationResult:
        """Validate that template placeholders match available data."""
        # Extract placeholders from template
        required_fields = self.extract_placeholders(template)
        
        # Get available data fields
        available_fields = set(data.keys())
        
        # Find missing and extra fields
        missing_fields = [f for f in required_fields if f not in available_fields]
        extra_fields = [f for f in available_fields if f not in required_fields]
        
        # Determine if valid
        valid = len(missing_fields) == 0
        
        # Create message
        if valid:
            message = "Template validation successful"
        else:
            message = f"Missing required fields: {', '.join(missing_fields)}"
        
        return TemplateValidationResult(
            valid=valid,
            missing_fields=missing_fields,
            extra_fields=extra_fields,
            message=message
        )
    
    def map_data_to_template(
        self, 
        template: str, 
        data: Dict[str, Any],
        format_type: str = "pdf"
    ) -> TemplateMappingResult:
        """Map structured data to template placeholders."""
        try:
            # Validate template first
            validation = self.validate_template(template, data)
            
            if not validation.valid:
                return TemplateMappingResult(
                    success=False,
                    output="",
                    format=format_type,
                    validation=validation,
                    error_message=validation.message
                )
            
            # Perform mapping based on format
            if format_type == "excel":
                output = self._map_excel_template(template, data)
            else:
                output = self._map_text_template(template, data)
            
            self.logger.info(f"Successfully mapped data to {format_type} template")
            
            return TemplateMappingResult(
                success=True,
                output=output,
                format=format_type,
                validation=validation,
                error_message=None
            )
            
        except Exception as e:
            error_msg = f"Template mapping failed: {str(e)}"
            self.logger.error(error_msg)
            
            return TemplateMappingResult(
                success=False,
                output="",
                format=format_type,
                validation=TemplateValidationResult(
                    valid=False,
                    missing_fields=[],
                    extra_fields=[],
                    message=error_msg
                ),
                error_message=error_msg
            )
    
    def _map_text_template(self, template: str, data: Dict[str, Any]) -> str:
        """Map data to text-based template (PDF/PPT)."""
        output = template
        
        for key, value in data.items():
            placeholder = f"{{{{{key}}}}}"
            
            # Handle different value types
            if isinstance(value, list):
                # Convert list to formatted string
                if all(isinstance(item, str) for item in value):
                    formatted_value = "\n".join([f"• {item}" for item in value])
                else:
                    formatted_value = "\n".join([f"• {str(item)}" for item in value])
            elif isinstance(value, dict):
                # Convert dict to formatted string
                formatted_value = "\n".join([f"{k}: {v}" for k, v in value.items()])
            else:
                formatted_value = str(value)
            
            output = output.replace(placeholder, formatted_value)
        
        return output
    
    def _map_excel_template(self, template: Any, data: Dict[str, Any]) -> Dict[str, Any]:
        """Map data to Excel template structure."""
        if isinstance(template, str):
            # Parse string template to dict
            import json
            template = json.loads(template)
        
        # Map data to template structure
        mapped_template = template.copy()
        
        if "rows" in mapped_template:
            mapped_rows = []
            for row in mapped_template["rows"]:
                mapped_row = []
                for cell in row:
                    # Replace placeholders in cell
                    if isinstance(cell, str):
                        for key, value in data.items():
                            placeholder = f"{{{{{key}}}}}"
                            if placeholder in cell:
                                cell = cell.replace(placeholder, str(value))
                    mapped_row.append(cell)
                mapped_rows.append(mapped_row)
            mapped_template["rows"] = mapped_rows
        
        return mapped_template
    
    def get_default_template(self, format_type: str) -> Any:
        """Get default template for specified format."""
        return self.DEFAULT_TEMPLATES.get(format_type, self.DEFAULT_TEMPLATES["pdf"])
    
    def save_template(self, template: str, filename: str, template_dir: str = "templates") -> bool:
        """Save template to file."""
        try:
            template_path = Path(template_dir)
            template_path.mkdir(parents=True, exist_ok=True)
            
            file_path = template_path / filename
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(template)
            
            self.logger.info(f"Template saved to {file_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save template: {str(e)}")
            return False
    
    def load_template(self, filename: str, template_dir: str = "templates") -> Optional[str]:
        """Load template from file."""
        try:
            file_path = Path(template_dir) / filename
            
            if not file_path.exists():
                self.logger.error(f"Template file not found: {file_path}")
                return None
            
            with open(file_path, 'r', encoding='utf-8') as f:
                template = f.read()
            
            self.logger.info(f"Template loaded from {file_path}")
            return template
            
        except Exception as e:
            self.logger.error(f"Failed to load template: {str(e)}")
            return None

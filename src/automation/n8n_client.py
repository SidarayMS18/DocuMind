"""n8n workflow automation client for triggering document generation workflows."""

import logging
import httpx
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class N8nWorkflowResult:
    """Result from n8n workflow execution."""
    success: bool
    workflow_id: Optional[str]
    execution_id: Optional[str]
    output: Optional[Dict[str, Any]]
    error_message: Optional[str] = None


class N8nClient:
    """Client for interacting with n8n workflow automation."""

    def __init__(self, webhook_base_url: str = "http://localhost:5678"):
        self.webhook_base_url = webhook_base_url.rstrip("/")
        self.timeout = 60.0

    async def trigger_document_generation(
        self,
        data: Dict[str, Any],
        template: Optional[str],
        format_type: str,
        webhook_path: str = "/webhook/generate"
    ) -> N8nWorkflowResult:
        """Trigger n8n document generation workflow via webhook."""
        payload = {
            "data": data,
            "template": template or "",
            "format": format_type.lower(),
        }

        url = f"{self.webhook_base_url}{webhook_path}"
        logger.info(f"Triggering n8n workflow at {url} for format={format_type}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                result = response.json()

                return N8nWorkflowResult(
                    success=True,
                    workflow_id=result.get("workflowId"),
                    execution_id=result.get("executionId"),
                    output=result
                )
        except httpx.ConnectError:
            msg = f"Cannot connect to n8n at {url}. Is n8n running?"
            logger.warning(msg)
            return N8nWorkflowResult(
                success=False, workflow_id=None,
                execution_id=None, output=None,
                error_message=msg
            )
        except httpx.HTTPStatusError as e:
            msg = f"n8n webhook returned error: {e.response.status_code}"
            logger.error(msg)
            return N8nWorkflowResult(
                success=False, workflow_id=None,
                execution_id=None, output=None,
                error_message=msg
            )
        except Exception as e:
            logger.error(f"n8n trigger failed: {e}")
            return N8nWorkflowResult(
                success=False, workflow_id=None,
                execution_id=None, output=None,
                error_message=str(e)
            )

    def get_n8n_workflow_json(self) -> Dict[str, Any]:
        """Return the n8n workflow definition JSON for import."""
        return {
            "name": "Document Generator Workflow",
            "nodes": [
                {
                    "id": "1",
                    "name": "Webhook Trigger",
                    "type": "n8n-nodes-base.webhook",
                    "parameters": {
                        "path": "generate",
                        "responseMode": "responseNode",
                        "httpMethod": "POST"
                    },
                    "position": [250, 300]
                },
                {
                    "id": "2",
                    "name": "Format Switch",
                    "type": "n8n-nodes-base.switch",
                    "parameters": {
                        "dataType": "string",
                        "value1": "={{$json[\"format\"]}}",
                        "rules": {
                            "rules": [
                                {"value2": "pdf", "output": 0},
                                {"value2": "ppt", "output": 1},
                                {"value2": "excel", "output": 2}
                            ]
                        }
                    },
                    "position": [450, 300]
                },
                {
                    "id": "3",
                    "name": "Generate PDF",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {
                        "url": "http://localhost:8000/generate/pdf",
                        "method": "POST",
                        "sendBody": True,
                        "bodyParameters": {
                            "parameters": [
                                {"name": "data", "value": "={{$json[\"data\"]}}"},
                                {"name": "template", "value": "={{$json[\"template\"]}}"}
                            ]
                        }
                    },
                    "position": [650, 200]
                },
                {
                    "id": "4",
                    "name": "Generate PPT",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {
                        "url": "http://localhost:8000/generate/ppt",
                        "method": "POST",
                        "sendBody": True
                    },
                    "position": [650, 300]
                },
                {
                    "id": "5",
                    "name": "Generate Excel",
                    "type": "n8n-nodes-base.httpRequest",
                    "parameters": {
                        "url": "http://localhost:8000/generate/excel",
                        "method": "POST",
                        "sendBody": True
                    },
                    "position": [650, 400]
                },
                {
                    "id": "6",
                    "name": "Respond to Webhook",
                    "type": "n8n-nodes-base.respondToWebhook",
                    "parameters": {
                        "respondWith": "json",
                        "responseBody": "={{$json}}"
                    },
                    "position": [850, 300]
                }
            ],
            "connections": {
                "Webhook Trigger": {"main": [[{"node": "Format Switch", "type": "main", "index": 0}]]},
                "Format Switch": {
                    "main": [
                        [{"node": "Generate PDF", "type": "main", "index": 0}],
                        [{"node": "Generate PPT", "type": "main", "index": 0}],
                        [{"node": "Generate Excel", "type": "main", "index": 0}]
                    ]
                },
                "Generate PDF": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
                "Generate PPT": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
                "Generate Excel": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]}
            }
        }

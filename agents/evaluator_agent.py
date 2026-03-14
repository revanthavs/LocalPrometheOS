"""Evaluator agent that summarizes tool outputs."""
from __future__ import annotations

from typing import Any, Dict
import json

from models.lmstudio_client import LMStudioClient
from utils.json_utils import parse_json_from_text


class EvaluatorAgent:
    def __init__(self, lm_client: LMStudioClient) -> None:
        self.lm_client = lm_client

    def summarize(self, task: Any, plan: Dict[str, Any], tool_outputs: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "You are an evaluator agent. Produce JSON with keys: "
            "summary, key_metrics, sentiment, recommendation, rationale.\n"
            "Be concise and decision oriented. JSON only.\n"
            f"Task: {task.name}\n"
            f"Goal: {task.goal}\n"
            f"Plan: {json.dumps(plan)}\n"
            f"Tool outputs: {json.dumps(tool_outputs)}\n"
        )
        response = self.lm_client.chat(
            [
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt},
            ]
        )
        result = parse_json_from_text(response)
        if not isinstance(result, dict):
            result = {
                "summary": response,
                "key_metrics": {},
                "sentiment": "Unknown",
                "recommendation": "Unknown",
                "rationale": "Failed to parse JSON response.",
            }
        return result

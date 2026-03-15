"""Planner agent for task decomposition."""
from __future__ import annotations

from typing import Any, Dict, List
import json

from models.lmstudio_client import LMStudioClient
from tools.builtin_tools import ToolSpec
from utils.json_utils import parse_json_from_text


class PlannerAgent:
    def __init__(self, lm_client: LMStudioClient) -> None:
        self.lm_client = lm_client

    def create_plan(self, task: Any, tools: List[ToolSpec]) -> Dict[str, Any]:
        tool_descriptions = [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in tools
        ]
        available_tool_names = {tool.name for tool in tools}
        prompt = (
            "You are a planner agent for LocalPrometheOS.\n"
            "Output a strict JSON object with a 'steps' array.\n"
            "Each step must include: id, purpose, tool, args.\n"
            "Use only the provided tools.\n"
            "If task inputs are needed, pass them via args as {'inputs': '$inputs'}.\n"
            "No extra keys. No commentary. JSON only.\n"
            f"Task name: {task.name}\n"
            f"Goal: {task.goal}\n"
            f"Requested tools: {task.tools}\n"
            f"Available tools: {json.dumps(tool_descriptions)}\n"
        )
        response = self.lm_client.chat(
            [
                {"role": "system", "content": "Return strict JSON only."},
                {"role": "user", "content": prompt},
            ]
        )
        plan = parse_json_from_text(response)
        if not plan or "steps" not in plan:
            plan = {"steps": []}

        steps = plan.get("steps", [])
        planned_tools = {step.get("tool") for step in steps if isinstance(step, dict)}
        for tool_name in task.tools:
            if tool_name not in planned_tools:
                steps.append(
                    {
                        "id": f"step-{len(steps)+1}",
                        "purpose": f"Run tool {tool_name}",
                        "tool": tool_name,
                        "args": "$inputs",
                    }
                )
        # If planner referenced tools that are not available, keep them but note it in purpose.
        for step in steps:
            if isinstance(step, dict) and step.get("tool") not in available_tool_names:
                step["purpose"] = f"{step.get('purpose', '')} (tool not in registry)"
        plan["steps"] = steps
        return plan

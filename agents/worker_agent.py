"""Worker agent that executes plan steps."""
from __future__ import annotations

from typing import Any, Dict, List
import copy
import logging

from tools.builtin_tools import ToolRegistry

logger = logging.getLogger(__name__)


class WorkerAgent:
    def __init__(self, tool_registry: ToolRegistry) -> None:
        self.tool_registry = tool_registry

    def _resolve_args(self, args: Any, task_inputs: Dict[str, Any]) -> Any:
        if isinstance(args, dict):
            resolved = {}
            for key, value in args.items():
                resolved[key] = self._resolve_args(value, task_inputs)
            return resolved
        if isinstance(args, list):
            return [self._resolve_args(item, task_inputs) for item in args]
        if isinstance(args, str) and args == "$inputs":
            return copy.deepcopy(task_inputs)
        return args

    def execute_plan(self, plan: Dict[str, Any], task_inputs: Dict[str, Any]) -> Dict[str, Any]:
        steps = plan.get("steps", [])
        outputs: List[Dict[str, Any]] = []
        for step in steps:
            step_id = step.get("id")
            tool = step.get("tool")
            args = step.get("args") or {}
            resolved_args = self._resolve_args(args, task_inputs)
            result = None
            error = None
            try:
                result = self.tool_registry.call(tool, resolved_args)
            except Exception as exc:
                error = str(exc)
                logger.error("Step '%s' tool '%s' failed: %s", step_id, tool, exc, exc_info=True)
            outputs.append(
                {
                    "id": step_id,
                    "tool": tool,
                    "args": resolved_args,
                    "result": result,
                    "error": error,
                }
            )
        return {"steps": outputs}

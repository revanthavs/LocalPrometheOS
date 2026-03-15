"""Helpers for parsing JSON content from LLM outputs."""
from __future__ import annotations

from typing import Any, Optional
import json
import re


def parse_json_from_text(text: str) -> Optional[Any]:
    # 1. Try to find a JSON markdown block
    match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
    if match:
        snippet = match.group(1)
        try:
            return json.loads(snippet)
        except json.JSONDecodeError:
            # If markdown block is invalid, fall through to other methods
            pass

    # 2. Try to load the whole string directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 3. Find the first '{' and last '}'
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    snippet = text[start : end + 1]
    try:
        return json.loads(snippet)
    except json.JSONDecodeError:
        return None

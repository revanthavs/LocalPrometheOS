#!/usr/bin/env python3
import sys
import json
import re
import html
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Copy the exact functions from the codebase to test
def _strip_html(text: str) -> str:
    """Remove HTML tags from text and decode HTML entities."""
    if not isinstance(text, str):
        return str(text)
    # First decode HTML entities so they become regular chars, then strip tags
    text = html.unescape(text)
    # Remove HTML tags - handle cases where tags might have > inside content
    # This regex matches < followed by any characters (non-greedy) up to >
    text = re.sub(r'<[^>]*>', '', text)
    # Also handle incomplete tags (missing closing >)
    text = re.sub(r'<[^>]*$', '', text)
    return text.strip()

def _unwrap_json_string(text: str) -> str:
    """If text looks like a JSON string, parse it and return the extracted value."""
    if not isinstance(text, str):
        return str(text)
    text = text.strip()
    # Check if it looks like a JSON object or array
    if (text.startswith('{') and text.endswith('}')) or (text.startswith('[') and text.endswith(']')):
        try:
            parsed = json.loads(text)
            # Try common field names
            for key in ('summary', 'text', 'content', 'message', 'result', 'value'):
                if key in parsed and isinstance(parsed[key], str):
                    return parsed[key]
            # Return first string value found
            for v in parsed.values():
                if isinstance(v, str):
                    return v
            return text
        except json.JSONDecodeError:
            # Try decoding common HTML entities that may have been double-encoded
            unescaped = html.unescape(text)
            try:
                parsed = json.loads(unescaped)
                for key in ('summary', 'text', 'content', 'message', 'result', 'value'):
                    if key in parsed and isinstance(parsed[key], str):
                        return parsed[key]
                for v in parsed.values():
                    if isinstance(v, str):
                        return v
            except (json.JSONDecodeError, ValueError):
                pass
            return text
    return text

def clean_result_text(value) -> str:
    """
    Clean a result field that may contain:
    1. Raw HTML tags (strip them)
    2. JSON strings (unwrap them)
    3. Plain text (return as-is)
    """
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return str(value)
    if not isinstance(value, str):
        return str(value)

    # First try unwrapping JSON strings (might reveal plain text or more JSON)
    cleaned = _unwrap_json_string(value)
    # If we got back something still looking like JSON, try parsing again
    if cleaned != value:
        cleaned = _unwrap_json_string(cleaned)
    # Strip HTML tags and decode HTML entities
    cleaned = _strip_html(cleaned)
    # Final pass: remove any remaining HTML tag fragments that might have been missed
    cleaned = re.sub(r'<\/?[a-zA-Z][^>]*>', '', cleaned)
    # Return cleaned string (even if empty) or original value as string if cleaning failed
    return cleaned if cleaned is not None else str(value)

def _get_result_summary(result_json_str: str) -> str:
    """Copy of the function from ui/pages/7_history.py"""
    if not result_json_str:
        return ""
    try:
        data = json.loads(result_json_str)
        raw_summary = data.get("summary", "") if isinstance(data, dict) else ""
    except Exception:
        raw_summary = result_json_str
    cleaned = clean_result_text(raw_summary) if raw_summary else ""
    # Additional defense: strip any remaining HTML tags that might have been missed
    cleaned = re.sub(r'<[^>]+>', '', cleaned)
    # Limit length to prevent overly long previews
    return cleaned[:100] if cleaned else ""

def test_realistic_scenarios():
    """Test scenarios that might actually occur in the database"""
    
    print("Testing realistic database scenarios:")
    print("=" * 60)
    
    # Scenario 1: Normal JSON with summary (most likely)
    test1 = '{"summary": "Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re"}'
    print(f"\nScenario 1 - Normal JSON:")
    print(f"  Input: {repr(test1)}")
    result1 = _get_result_summary(test1)
    print(f"  Output: {repr(result1)}")
    
    # Scenario 2: JSON with HTML in summary (what we've been testing)
    test2 = '{"summary": "<div>Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>"}'
    print(f"\nScenario 2 - JSON with HTML:")
    print(f"  Input: {repr(test2)}")
    result2 = _get_result_summary(test2)
    print(f"  Output: {repr(result2)}")
    
    # Scenario 3: What if the entire result_json is just a string (not JSON)?
    test3 = "Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re"
    print(f"\nScenario 3 - Plain text (not JSON):")
    print(f"  Input: {repr(test3)}")
    result3 = _get_result_summary(test3)
    print(f"  Output: {repr(result3)}")
    
    # Scenario 4: What if result_json contains HTML tags directly (not in summary)?
    test4 = "<div>Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>"
    print(f"\nScenario 4 - HTML string (not JSON):")
    print(f"  Input: {repr(test4)}")
    result4 = _get_result_summary(test4)
    print(f"  Output: {repr(result4)}")
    
    # Scenario 5: Double-encoded JSON (JSON string that contains another JSON string)
    test5 = '{"summary": "{\\\"summary\\\": \\\"<div>Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>\\\"}"}'
    print(f"\nScenario 5 - Double-encoded JSON:")
    print(f"  Input: {repr(test5)}")
    result5 = _get_result_summary(test5)
    print(f"  Output: {repr(result5)}")
    
    # Scenario 6: What if there are actual HTML entities in the text that need decoding?
    test6 = '{"summary": "<div>Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>"}'
    print(f"\nScenario 6 - HTML entities in JSON:")
    print(f"  Input: {repr(test6)}")
    result6 = _get_result_summary(test6)
    print(f"  Output: {repr(result6)}")
    
    # Check all results for HTML tags
    print("\n" + "=" * 60)
    print("HTML Tag Check:")
    all_good = True
    for i, result in enumerate([result1, result2, result3, result4, result5, result6], 1):
        if '<div' in result or '</div>' in result:
            print(f"  Scenario {i}: ❌ FAIL - HTML tags present: {repr(result)}")
            all_good = False
        else:
            print(f"  Scenario {i}: ✅ PASS - No HTML tags")
    
    if all_good:
        print("\n🎉 All scenarios PASSED - HTML stripping is working correctly!")
    else:
        print("\n❌ Some scenarios FAILED - there's still an issue!")

if __name__ == "__main__":
    test_realistic_scenarios()
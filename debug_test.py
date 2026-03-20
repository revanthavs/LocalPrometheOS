#!/usr/bin/env python3
import sys
import json
import re
import html
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Copy the exact functions from the codebase to debug
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

def debug_issue():
    """Debug the exact issue from the user's report"""
    
    # This is the exact string from the user's example that shows HTML tags
    # Looking at the user's example, the problematic part is:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    
    # Let's test what happens when this comes from the database as result_json
    # Based on the code, result_json would be a JSON string containing a "summary" field
    
    test_cases = [
        # Case 1: Direct HTML string (what might be stored in result_json if it's not JSON)
        '<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>',
        
        # Case 2: JSON with summary field containing HTML (more likely based on code)
        '{"summary": "<div class=\\\"timeline-result-preview\\\" style=\\\"margin-top:6px;\\\">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>"}',
        
        # Case 3: What if the JSON is double-encoded or has HTML entities?
        '{"summary": "<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>"}',
    ]
    
    print("Debugging the HTML stripping issue:")
    print("=" * 60)
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Input: {repr(test_case)}")
        
        # Step by step through _get_result_summary
        print("\n  Step-by-step processing:")
        
        # Step 1: JSON parsing
        if not test_case:
            raw_summary = ""
            print("    Empty input -> raw_summary = ''")
        else:
            try:
                data = json.loads(test_case)
                raw_summary = data.get("summary", "") if isinstance(data, dict) else ""
                print(f"    JSON parsed -> raw_summary = {repr(raw_summary)}")
            except Exception as e:
                raw_summary = test_case
                print(f"    JSON parse failed ({e}) -> raw_summary = {repr(raw_summary)}")
        
        # Step 2: clean_result_text
        if raw_summary:
            cleaned = clean_result_text(raw_summary)
            print(f"    After clean_result_text = {repr(cleaned)}")
        else:
            cleaned = ""
            print(f"    Empty raw_summary -> cleaned = ''")
        
        # Step 3: Additional defense regex
        if cleaned:
            cleaned = re.sub(r'<[^>]+>', '', cleaned)
            print(f"    After additional regex = {repr(cleaned)}")
        else:
            print(f"    Empty cleaned -> skipping regex")
        
        # Step 4: Length limit
        if cleaned:
            result = cleaned[:100] if cleaned else ""
            print(f"    After length limit = {repr(result)}")
        else:
            result = ""
            print(f"    Empty cleaned -> result = ''")
        
        print(f"\n  Final result: {repr(result)}")
        
        # Check for remaining HTML
        if '<div' in result or '</div>' in result:
            print("  ❌ FAIL: HTML tags still present!")
        else:
            print("  ✅ PASS: No HTML tags remaining")
            
        # Check if content is preserved
        if 'Bitcoin and Ethereum are trading at $70,697' in result:
            print("  ✅ PASS: Content preserved")
        else:
            print("  ❌ FAIL: Content not preserved")

if __name__ == "__main__":
    debug_issue()
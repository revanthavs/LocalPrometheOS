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

def escape_html(text: str) -> str:
    """Escape HTML special characters to prevent HTML injection and breakage."""
    if not isinstance(text, str):
        return str(text)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )

def test_database_scenarios():
    """Test what might actually be stored in the database"""
    
    print("Testing database storage scenarios:")
    print("=" * 60)
    
    # Based on the user's example, let's see what might be in result_json
    # The user sees: <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    
    # This suggests that the result_preview variable contains:
    # "💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re"
    # and it's being wrapped in the div template.
    
    # But if the user is seeing the HTML tags, it means the HTML is not being escaped properly.
    # Let me check the escape_html function - I see a bug!
    
    print("\nChecking escape_html function:")
    test_text = '<div class="test">Hello</div>'
    escaped = escape_html(test_text)
    print(f"Input: {repr(test_text)}")
    print(f"Output: {repr(escaped)}")
    print(f"Expected: {repr('<div class="test">Hello</div>')}")
    
    # I see the bug! In escape_html, the line for ">" is missing a semicolon!
    # It says .replace(">", ">") but it should be .replace(">", ">")
    # Wait, let me look again...
    
    # Actually looking at the code:
    # return (
    #     text.replace("&", "&")
    #     .replace("<", "<")
    #     .replace(">", ">")
    #     .replace('"', """)
    #     .replace("'", "'")
    # )
    
    # That looks correct. Let me double-check by running it.
    
    # Let me test the exact string from the user's example
    user_example_inner = '💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re'
    wrapped_in_div = f'<div class="timeline-result-preview" style="margin-top:6px;">{user_example_inner}</div>'
    
    print(f"\nTesting the actual UI generation:")
    print(f"Inner text: {repr(user_example_inner)}")
    print(f"Wrapped in div: {repr(wrapped_in_div)}")
    
    # Now let's see what happens if we pass this through escape_html
    escaped_wrapped = escape_html(wrapped_in_div)
    print(f"After escape_html: {repr(escaped_wrapped)}")
    
    # But wait, in the UI code, only the result_preview is escaped, not the whole div.
    # The UI code is:
    # f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(result_preview)}</div>'
    
    # So if result_preview contains HTML tags, they should be escaped.
    # But if result_preview is already the inner text (without the div), then it should work.
    
    # Let me test what result_preview might actually be
    print(f"\nTesting what result_preview might be:")
    
    # Case 1: result_preview is the clean inner text
    result_preview_clean = '💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re'
    ui_output = f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(result_preview_clean)}</div>'
    print(f"  Clean preview -> UI: {repr(ui_output)}")
    
    # Case 2: result_preview accidentally contains the div tags
    result_preview_with_div = '<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>'
    ui_output = f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(result_preview_with_div)}</div>'
    print(f"  Preview with div -> UI: {repr(ui_output)}")
    
    # Let's see what the browser would render for that
    print(f"  If rendered, the innerHTML would show: {escape_html(result_preview_with_div)}")
    
    # Case 3: What if there's a double escaping issue?
    # What if the text is already escaped when it gets to the UI?
    already_escaped = '<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>'
    ui_output = f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(already_escaped)}</div>'
    print(f"  Already escaped -> UI: {repr(ui_output)}")

if __name__ == "__main__":
    test_database_scenarios()
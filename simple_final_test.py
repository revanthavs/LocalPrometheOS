#!/usr/bin/env python3
import sys
import json
import re
import html
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Copy the EXACT functions from the codebase
def _strip_html(text: str) -> str:
    """Remove HTML tags from text and decode HTML entities."""
    if not isinstance(text, str):
        return str(text)
    # First decode HTML entities so they become regular chars, then strip tags
    import html
    text = html.unescape(text)
    # Remove HTML tags using a more aggressive regex
    text = re.sub(r'<.*?>', '', text, flags=re.DOTALL)
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
            import html
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

def test_user_scenario():
    """Test the exact scenario from the user's report"""
    
    print("Testing the exact user scenario:")
    print("=" * 50)
    
    # Based on the user's example, they see:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #
    # This is the HTML that is being rendered. The part that varies is:
    # 💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re
    #
    # If they are seeing the literal HTML tags, it means that the content being inserted
    # into the template contains unescaped HTML.
    
    # Let's test what might be in the database that would lead to this
    
    # Scenario: The database contains the FULL HTML string as the "summary" or as the raw value
    db_value = '<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>'
    
    print(f"Database value: {repr(db_value)}")
    
    # Process through _get_result_summary
    result_preview = _get_result_summary(db_value)
    print(f"After _get_result_summary: {repr(result_preview)}")
    
    # Process through escape_html (what happens in UI)
    escaped_preview = escape_html(result_preview)
    print(f"After escape_html: {repr(escaped_preview)}")
    
    # Generate the final HTML as seen in UI
    ui_html = f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escaped_preview}</div>'
    print(f"Final UI HTML: {repr(ui_html)}")
    
    # What would actually be displayed in the browser?
    # The browser would show the rendered HTML, which would be:
    # A div with class "timeline-result-preview" containing:
    #   💬 [then the escaped_preview rendered as HTML]
    #
    # But since we escaped it, any HTML in escaped_preview would be shown as text
    
    # Let's see what the inner content would render as
    inner_content = f'💬 {escaped_preview}'
    print(f"Inner content to be rendered: {repr(inner_content)}")
    
    # To see what text would actually appear, we need to unescape the escaped part
    # (because the browser will unescape it for display)
    # Actually, no. The browser shows the escaped version as literal text.
    # For example, if escaped_preview is "<div>Hello</div>",
    # the browser will show: <div>Hello</div> as text
    
    # So to test what the user sees, we should look at escaped_preview
    # If escaped_preview contains "<" or ">" or "&" that weren't escaped,
    # then the browser might interpret them as HTML
    
    # But actually, let's think about this differently.
    # The user says they "can literally see HTML tags in the UI"
    # This means they are seeing the actual characters "<", ">", etc. interpreted as HTML
    
    # Let's check if our processing is working correctly
    
    # First, let's see what _get_result_summary produces
    if '<div' in result_preview or '</div>' in result_preview:
        print("❌ _get_result_summary FAILED: HTML tags still present in result_preview")
    else:
        print("✅ _get_result_summary PASSED: No HTML tags in result_preview")
    
    # Second, let's see what escape_html produces
    if '<' in escaped_preview or '>' in escaped_preview or '&' in escaped_preview:
        # Check if these are properly escaped
        if '<' in escaped_preview and '>' in escaped_preview and '&' in escaped_preview:
            print("✅ escape_html PASSED: Special characters are properly escaped")
        else:
            print("❌ escape_html FAILED: Special characters not properly escaped")
            print(f"   Looking for <, >, & in: {repr(escaped_preview)}")
    else:
        print("✅ escape_html PASSED: No special characters to escape")
    
    # Final check: What would the user actually see?
    # They would see the rendered version of:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 [escaped_preview]</div>
    #
    # The visual content would be:
    #   💬 [then the unescaped version of escaped_preview]
    #
    visual_content = f'💬 {html.unescape(escaped_preview)}'
    print(f"What user would see visually: {repr(visual_content)}")
    
    if '<div' in visual_content or '</div>' in visual_content:
        print("❌ USER WOULD SEE HTML TAGS IN UI!")
    else:
        print("✅ USER WOULD SEE CLEAN TEXT IN UI")

if __name__ == "__main__":
    test_user_scenario()
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

def test_exact_user_view():
    """Test exactly what the user would see in their browser"""
    
    print("Testing exactly what the user sees:")
    print("=" * 50)
    
    # Let's work backwards from what the user sees in their browser
    # They see: <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #
    # This is the HTML that is rendered. Let's break it down:
    #
    # Outer structure (from the template):
    # <div class="timeline"> ... </div>
    #
    # Inner structure (from the timeline-item template):
    # <div class="timeline-item">
    #   <div class="timeline-line"> ... </div>
    #   <div class="timeline-content">
    #     <div class="timeline-content-header"> ... </div>
    #     <div class="timeline-run-meta"> ... </div>
    #     [ERROR SECTION if error]
    #     [RESULT PREVIEW SECTION]  <-- THIS IS WHERE THE ISSUE IS
    #   </div>
    # </div>
    #
    # The RESULT PREVIEW SECTION is:
    # {f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(result_preview)}</div>' if result_preview else ''}
    #
    # So if the user sees:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #
    # It means that the string:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #
    # Is being LITERALLY inserted as the HTML content of that section.
    #
    # This can only happen if the escape_html() function is NOT being called, or if it's returning the input unchanged.
    #
    # Let me test what would produce this output:
    #
    # The template is: f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(result_preview)}</div>'
    #
    # For this to produce:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #
    # The {escape_html(result_preview)} part must evaluate to:
    # Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re
    #
    # Which means escape_html(result_preview) must return:
    # Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re
    #
    # This would happen if result_preview is:
    # Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re
    # (and it contains no HTML special characters that need escaping)
    #
    # OR if there's a bug in escape_html that makes it return the input unchanged.
    #
    # But we tested escape_html and it works.
    #
    # Wait, unless... what if the result_preview ALREADY contains the escaped version?
    #
    # For example, if result_preview is:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #
    # And then escape_html is called on it, but there's a bug...
    #
    # No, that doesn't make sense either.
    #
    # Let me think of another possibility: what if the f-string is malformed or there's a typo in the template?
    #
    # Looking at the code again:
    # {f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escape_html(result_preview)}</div>' if result_preview else ''}
    #
    # What if there's a missing quote or something that makes the f-string not work as expected?
    #
    # Actually, let me just test the exact scenario by simulating the full template processing.

    # Let's test what might actually be in the database that would lead to the user seeing HTML tags
    
    # Hypothesis: The database contains the FULL HTML string as the summary, and our cleaning is not removing it
    
    db_value = '<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>'
    
    print(f"Testing database value: {repr(db_value)}")
    
    # Step 1: _get_result_summary
    result_preview = _get_result_summary(db_value)
    print(f"After _get_result_summary: {repr(result_preview)}")
    
    # Step 2: escape_html
    escaped_preview = escape_html(result_preview)
    print(f"After escape_html: {repr(escaped_preview)}")
    
    # Step 3: Template processing
    if result_preview:  # This is the condition in the template
        ui_snippet = f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escaped_preview}</div>'
        print(f"UI snippet: {repr(ui_snippet)}")
    else:
        ui_snippet = ''
        print("UI snippet: (empty)")
    
    # What would the browser render?
    # The browser would see this HTML and render it.
    # If ui_snippet contains unescaped HTML, it would be rendered as HTML.
    # If ui_snippet contains escaped HTML, it would be shown as text.
    
    # Let's see what the browser would show as the visible text content
    # of the timeline-result-preview div
    
    # Extract the content between the div tags in ui_snippet
    if ui_snippet.startswith('<div class="timeline-result-preview" style="margin-top:6px;">') and ui_snippet.endswith('</div>'):
        content = ui_snippet[len('<div class="timeline-result-preview" style="margin-top:6px;">'):-len('</div>')]
        print(f"Content inside the div: {repr(content)}")
        
        # What the browser would display as text is the unescaped version of content
        displayed_text = html.unescape(content)
        print(f"What user would see as text: {repr(displayed_text)}")
        
        # Check if displayed text contains HTML tags
        if '<div' in displayed_text or '</div>' in displayed_text:
            print("❌ USER WOULD SEE HTML TAGS IN THEIR BROWSER!")
        else:
            print("✅ USER WOULD SEE CLEAN TEXT")
    else:
        print("Could not parse UI snippet")

if __name__ == "__main__":
    test_exact_user_view()
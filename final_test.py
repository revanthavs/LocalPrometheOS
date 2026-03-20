#!/usr/bin/env python3
import sys
import json
import re
import html
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the actual functions from the codebase
from ui.shared import clean_result_text, _strip_html, _unwrap_json_string, escape_html
from ui.pages.page_history import _get_result_summary

def test_complete_flow():
    """Test the complete flow from database to UI"""
    
    print("Testing complete flow from database to UI:")
    print("=" * 60)
    
    # Test cases based on what might be in the database
    test_cases = [
        # What the user showed in their example - this is what they SEE in the UI
        # This suggests that the HTML tags are NOT being escaped properly
        # Let's work backwards from what they see
        
        # Case 1: If the database contains clean text (what we want)
        ('Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re', 
         'Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re'),
         
        # Case 2: If the database contains a JSON with clean summary
        ('{"summary": "Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re"}', 
         'Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re'),
         
        # Case 3: If the database contains a JSON with HTML in summary (the problematic case)
        ('{"summary": "<div>Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>"}', 
         'Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re'),
         
        # Case 4: What if the database contains the exact HTML string the user sees?
        # This would mean the cleaning failed completely
        ('<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>', 
         '💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re'),
    ]
    
    for i, (db_value, expected_preview) in enumerate(test_cases, 1):
        print(f"\nTest Case {i}:")
        print(f"Database value: {repr(db_value)}")
        
        # Step 1: Get result summary (simulates _get_result_summary)
        result_preview = _get_result_summary(db_value)
        print(f"After _get_result_summary: {repr(result_preview)}")
        
        # Step 2: Escape for HTML (simulates what happens in UI)
        escaped_preview = escape_html(result_preview)
        print(f"After escape_html: {repr(escaped_preview)}")
        
        # Step 3: Generate final HTML (simulates UI template)
        ui_html = f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escaped_preview}</div>'
        print(f"Final UI HTML: {repr(ui_html)}")
        
        # Check if we would see HTML tags in the rendered output
        # The user would see the innerHTML of the div, which is: 💬 {escaped_preview}
        # If escaped_preview contains unescaped HTML, they would see the tags
        
        # Let's check what the browser would render as visible text
        # We need to unescape the escaped_preview to see what would actually be displayed
        displayed_text = html.unescape(escaped_preview)
        print(f"Would display as: {repr(displayed_text)}")
        
        # Check if displayed text contains HTML tags
        if '<div' in displayed_text or '</div>' in displayed_text:
            print("  ❌ FAIL: Would show HTML tags in UI!")
        else:
            print("  ✅ PASS: Would show clean text in UI")
            
        # Check if content is preserved
        if 'Bitcoin and Ethereum are trading at $70,697' in displayed_text:
            print("  ✅ PASS: Content preserved")
        else:
            print("  ❌ FAIL: Content not preserved")

def test_exact_user_example():
    """Test with the exact string from user's example"""
    
    print("\n" + "=" * 60)
    print("Testing EXACT user example:")
    print("=" * 60)
    
    # From the user's example, they see this in the UI:
    # <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #
    # This means the INNER HTML of the div is:
    # 💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re
    #
    # But wait, they said they "can literally see HTML tags in the UI"
    # So they must be seeing the actual <div> tags, not just the content
    
    # Let me re-read their example more carefully...
    #
    # Looking at their example:
    # Crypto Price Tracker
    # Success
    # 🕐 2026-03-19T04:29
    # ⏱ ~28s
    #         <div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>
    #     </div>
    # </div>
    #
    # The indentation suggests that the <div class="timeline-result-preview"... is actually PART of the visible text
    # This means the HTML tags are NOT being escaped at all
    
    # So the issue is that the result_preview contains the FULL div string, and it's not being escaped
    
    # Let's test this hypothesis
    problematic_preview = '<div class="timeline-result-preview" style="margin-top:6px;">💬 Bitcoin and Ethereum are trading at $70,697 with a 24‑hour decline of about 4.9% for both assets. Re</div>'
    
    print(f"Problematic preview (what might be in result_preview): {repr(problematic_preview)}")
    
    # What happens when we process this through our cleaning?
    cleaned_preview = _get_result_summary(problematic_preview)
    print(f"After _get_result_summary: {repr(cleaned_preview)}")
    
    escaped_preview = escape_html(cleaned_preview)
    print(f"After escape_html: {repr(escaped_preview)}")
    
    ui_html = f'<div class="timeline-result-preview" style="margin-top:6px;">💬 {escaped_preview}</div>'
    print(f"Final UI HTML: {repr(ui_html)}")
    
    # What would be displayed?
    displayed_text = html.unescape(escaped_preview)
    print(f"Would display as: {repr(displayed_text)}")
    
    if '<div' in displayed_text or '</div>' in displayed_text:
        print("  ❌ FAIL: Would show HTML tags in UI!")
    else:
        print("  ✅ PASS: Would show clean text in UI")

if __name__ == "__main__":
    test_complete_flow()
    test_exact_user_example()
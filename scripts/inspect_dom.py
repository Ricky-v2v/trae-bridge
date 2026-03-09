#!/usr/bin/env python3
"""
CDP DOM Inspector for Trae
Helps research Trae's DOM structure to find chat UI elements
"""

import sys
import os
import asyncio
import json

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cdp_client import CDPClient


async def inspect_trae_dom():
    """Inspect Trae's DOM structure to find chat elements"""

    print("Connecting to Trae via CDP...")
    client = CDPClient(cdp_port=9230)

    try:
        await client.connect()
        print("✓ Connected to Trae\n")

        # Inspect various potential selectors
        inspections = [
            ("Content Editable Elements", "[contenteditable='true']"),
            ("Textareas", "textarea"),
            ("Text Inputs", "input[type='text']"),
            ("Buttons", "button"),
            ("Submit Buttons", "button[type='submit']"),
            ("Messages Containers", "[class*='message'], [class*='chat'], [role='log']"),
            ("AI/Assistant Elements", "[class*='assistant'], [class*='ai'], [class*='bot']"),
            ("Loading/Thinking Indicators", "[class*='thinking'], [class*='loading'], [class*='typing']"),
        ]

        for name, selector in inspections:
            print(f"\n{name}:")
            print(f"  Selector: {selector}")

            result = await client.evaluate(
                f"""() => {{
                    const elements = document.querySelectorAll('{selector}');
                    if (elements.length === 0) return null;

                    return Array.from(elements).slice(0, 3).map(el => ({{
                        tagName: el.tagName,
                        id: el.id || '',
                        className: el.className || '',
                        textContent: (el.textContent || '').substring(0, 50),
                        placeholder: el.placeholder || '',
                        ariaLabel: el.getAttribute('aria-label') || ''
                    }}));
                }}"""
            )

            if result:
                print(f"  Found {len(result)} elements")
                for i, el in enumerate(result[:3], 1):
                    print(f"    {i}. Tag: {el['tagName']}")
                    if el['id']:
                        print(f"       ID: {el['id']}")
                    if el['className']:
                        print(f"       Class: {el['className'][:100]}")
                    if el['placeholder']:
                        print(f"       Placeholder: {el['placeholder']}")
                    if el['ariaLabel']:
                        print(f"       ARIA Label: {el['ariaLabel']}")
                    if el['textContent']:
                        print(f"       Text: {el['textContent'][:50]}")
            else:
                print("  ✗ Not found")

        # Try to find the chat input and send button specifically
        print("\n" + "="*60)
        print("CHAT INTERFACE ANALYSIS")
        print("="*60)

        # Look for input
        print("\n1. Searching for Chat Input:")
        input_selectors = [
            "[contenteditable='true']",
            "textarea",
            "input[type='text']",
            "[placeholder*='message' i]",
            "[placeholder*='chat' i]",
            "[role='textbox']"
        ]

        for selector in input_selectors:
            result = await client.evaluate(
                f"""() => {{
                    const el = document.querySelector('{selector}');
                    if (!el) return null;

                    // Check if it looks like a chat input
                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0;

                    return {{
                        selector: '{selector}',
                        tagName: el.tagName,
                        id: el.id || '',
                        className: el.className || '',
                        placeholder: el.placeholder || '',
                        isVisible: isVisible,
                        rect: {{ width: rect.width, height: rect.height }}
                    }};
                }}"""
            )

            if result and result['isVisible']:
                print(f"  ✓ Found: {selector}")
                print(f"    Tag: {result['tagName']}")
                if result['id']:
                    print(f"    ID: {result['id']}")
                if result['className']:
                    print(f"    Class: {result['className'][:100]}")
                if result['placeholder']:
                    print(f"    Placeholder: {result['placeholder']}")
                print(f"    Size: {result['rect']['width']}x{result['rect']['height']}")
                break

        # Look for send button
        print("\n2. Searching for Send Button:")
        button_selectors = [
            "button[type='submit']",
            "button[aria-label*='send' i]",
            "button[aria-label*='Send' i]",
            "button[title*='send' i]",
            "button[class*='send' i]",
            "[role='button'][class*='submit' i]"
        ]

        for selector in button_selectors:
            result = await client.evaluate(
                f"""() => {{
                    const el = document.querySelector('{selector}');
                    if (!el) return null;

                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0;

                    return {{
                        selector: '{selector}',
                        tagName: el.tagName,
                        textContent: (el.textContent || '').trim(),
                        ariaLabel: el.getAttribute('aria-label') || '',
                        isVisible: isVisible
                    }};
                }}"""
            )

            if result and result['isVisible']:
                print(f"  ✓ Found: {selector}")
                print(f"    Text: {result['textContent']}")
                if result['ariaLabel']:
                    print(f"    ARIA Label: {result['ariaLabel']}")
                break

        # Look for message containers
        print("\n3. Searching for Message Containers:")
        container_selectors = [
            "[class*='message-container']",
            "[class*='chat-container']",
            "[role='log']",
            "[class*='messages']",
            "[class*='conversation']"
        ]

        for selector in container_selectors:
            result = await client.evaluate(
                f"""() => {{
                    const els = document.querySelectorAll('{selector}');
                    if (els.length === 0) return null;

                    return {{
                        selector: '{selector}',
                        count: els.length,
                        first: {{
                            tagName: els[0].tagName,
                            className: els[0].className || ''
                        }}
                    }};
                }}"""
            )

            if result:
                print(f"  ✓ Found: {selector} ({result['count']} elements)")
                print(f"    First element tag: {result['first']['tagName']}")
                if result['first']['className']:
                    print(f"    First element class: {result['first']['className'][:100]}")
                break

        # Get page title and URL for context
        print("\n4. Page Information:")
        page_info = await client.evaluate(
            """() => {
                return {
                    title: document.title,
                    url: window.location.href,
                    userAgent: navigator.userAgent
                };
            }"""
        )

        if page_info:
            print(f"  Title: {page_info['title']}")
            print(f"  URL: {page_info['url']}")

        print("\n" + "="*60)
        print("INSPECTION COMPLETE")
        print("="*60)
        print("\nUse these findings to update DOMHelper selectors in dom_helper.py")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\nDisconnected from Trae")


if __name__ == "__main__":
    print("Trae DOM Inspector")
    print("="*60)
    print("Make sure Trae is running with CDP enabled on port 9230")
    print("Run: ./scripts/start_trae.sh")
    print("="*60)
    print()

    asyncio.run(inspect_trae_dom())

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

        # ── Section 1: Page Info ──
        print("=" * 60)
        print("PAGE INFORMATION")
        print("=" * 60)
        page_info = await client.evaluate(
            """((() => {
                return {
                    title: document.title,
                    url: window.location.href,
                    bodyTextLen: document.body.innerText.length
                };
            })())"""
        )
        if page_info:
            print(f"  Title: {page_info.get('title')}")
            print(f"  URL: {page_info.get('url')}")
            print(f"  Body text length: {page_info.get('bodyTextLen')}")

        # ── Section 2: Chat Input ──
        print("\n" + "=" * 60)
        print("CHAT INPUT ELEMENTS")
        print("=" * 60)
        input_selectors = [
            'div.chat-input-v2-input-box-editable[role="textbox"]',
            'div.chat-input-v2-input-box-editable',
            '[class*="chat-input"]',
            '[class*="input-box"][contenteditable]',
            'div[role="textbox"]',
            'textarea.inputarea',
            '[contenteditable="true"]',
        ]

        for selector in input_selectors:
            result = await client.evaluate(
                f"""((() => {{
                    const el = document.querySelector('{selector}');
                    if (!el) return null;

                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0;

                    return {{
                        selector: '{selector}',
                        tagName: el.tagName,
                        id: el.id || '',
                        className: (el.className || '').substring(0, 120),
                        contentEditable: el.contentEditable,
                        isVisible: isVisible,
                        width: Math.round(rect.width),
                        height: Math.round(rect.height)
                    }};
                }})())"""
            )

            if result and result.get('isVisible'):
                print(f"  ✓ {selector}")
                print(f"    Tag: {result['tagName']}, Size: {result['width']}x{result['height']}")
                print(f"    Class: {result['className']}")

        # ── Section 3: Send Button ──
        print("\n" + "=" * 60)
        print("SEND BUTTON")
        print("=" * 60)
        button_selectors = [
            '.chat-input-v2-send-button',
            'button[class*="send" i]',
            'button[type="submit"]',
            'button[aria-label*="send" i]',
        ]

        for selector in button_selectors:
            result = await client.evaluate(
                f"""((() => {{
                    const el = document.querySelector('{selector}');
                    if (!el) return null;

                    const rect = el.getBoundingClientRect();
                    const isVisible = rect.width > 0 && rect.height > 0;

                    return {{
                        selector: '{selector}',
                        tagName: el.tagName,
                        className: (el.className || '').substring(0, 120),
                        disabled: el.disabled || el.classList.contains('disabled'),
                        isVisible: isVisible,
                        text: (el.textContent || '').trim().substring(0, 50)
                    }};
                }})())"""
            )

            if result and result.get('isVisible'):
                dis = " (DISABLED)" if result.get('disabled') else ""
                print(f"  ✓ {selector}{dis}")
                print(f"    Class: {result['className']}")

        # ── Section 4: Message Turns ──
        print("\n" + "=" * 60)
        print("CHAT MESSAGE TURNS")
        print("=" * 60)
        result = await client.evaluate(
            """((() => {
                const turns = document.querySelectorAll(
                    'section.chat-turn.user, section.chat-turn.assistant'
                );
                return Array.from(turns).map((turn, i) => {
                    const isUser = turn.classList.contains('user');
                    const text = (turn.textContent || '').substring(0, 100);
                    return {
                        index: i,
                        role: isUser ? 'USER' : 'ASSISTANT',
                        className: (turn.className || '').substring(0, 80),
                        textLen: (turn.textContent || '').length,
                        preview: text
                    };
                });
            })())"""
        )

        if result:
            print(f"  Total turns: {len(result)}")
            for turn in result:
                print(f"  [{turn['index']}] {turn['role']} ({turn['textLen']} chars)")
                print(f"       Class: {turn['className']}")
                print(f"       Preview: {turn['preview'][:80]}...")
        else:
            print("  No chat turns found")

        # ── Section 5: Thinking/Loading State ──
        print("\n" + "=" * 60)
        print("THINKING/LOADING INDICATORS")
        print("=" * 60)
        result = await client.evaluate(
            """((() => {
                const selectors = [
                    '[class*="thinking"]',
                    '[class*="deep-thinking"]',
                    '[class*="loading"]:not(.done)',
                    '[class*="generating"]',
                    '[class*="streaming"]',
                    '[class*="pending"]',
                    '[class*="stop-button"]',
                    '[class*="stop_button"]',
                ];
                const results = [];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 0) {
                        const first = els[0];
                        const rect = first.getBoundingClientRect();
                        results.push({
                            selector: sel,
                            count: els.length,
                            firstClass: (first.className || '').substring(0, 100),
                            visible: rect.width > 0 && rect.height > 0
                        });
                    }
                }
                return results;
            })())"""
        )

        if result:
            for r in result:
                vis = "visible" if r['visible'] else "hidden"
                print(f"  {r['selector']} ({r['count']} elements, {vis})")
                print(f"    Class: {r['firstClass']}")
        else:
            print("  No indicators found")

        # ── Section 6: Chat-related elements ──
        print("\n" + "=" * 60)
        print("CHAT-RELATED CLASS ELEMENTS (unique)")
        print("=" * 60)
        result = await client.evaluate(
            """((() => {
                const all = document.querySelectorAll('[class*="chat"]');
                const seen = new Set();
                const results = [];
                for (const el of all) {
                    const cls = (el.className || '').substring(0, 120);
                    if (seen.has(cls)) continue;
                    seen.add(cls);
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {
                        results.push({
                            tagName: el.tagName,
                            className: cls,
                            w: Math.round(rect.width),
                            h: Math.round(rect.height),
                            children: el.children.length
                        });
                    }
                }
                return results.slice(0, 30);
            })())"""
        )

        if result:
            for el in result:
                print(f"  {el['tagName']} {el['w']}x{el['h']} ({el['children']} children)")
                print(f"    Class: {el['className']}")
        else:
            print("  None found")

        print("\n" + "=" * 60)
        print("INSPECTION COMPLETE")
        print("=" * 60)
        print("\nUse these findings to update DOMHelper selectors in src/dom_helper.py")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await client.disconnect()
        print("\nDisconnected from Trae")


if __name__ == "__main__":
    print("Trae DOM Inspector")
    print("=" * 60)
    print("Make sure Trae is running with CDP enabled on port 9230")
    print("Run: ./scripts/start_trae.sh")
    print("=" * 60)
    print()

    asyncio.run(inspect_trae_dom())

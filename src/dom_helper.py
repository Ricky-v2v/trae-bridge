"""
DOM Helper for Trae Bridge
Provides utilities for interacting with Trae's chat UI
"""

import asyncio
import logging
from typing import Optional
from .cdp_client import CDPClient

logger = logging.getLogger(__name__)


class DOMHelper:
    """Helper for DOM operations in Trae"""

    # Selectors - Updated for Trae's specific DOM structure

    # Trae-specific selectors (discovered via inspection)
    SELECTOR_TRAE_CHAT_INPUT = 'div.chat-input-v2-input-box-editable[role="textbox"][contenteditable="true"]'
    SELECTOR_TRAE_TEXTAREA = 'textarea.inputarea.monaco-mouse-cursor-text[role="textbox"]'

    # Fallback generic selectors
    SELECTOR_INPUT = '[contenteditable="true"]'
    SELECTOR_TEXTAREA = 'textarea'
    SELECTOR_SEND_BUTTON = 'button[type="submit"], button[aria-label*="send"], button[aria-label*="Send"]'

    # Message container selectors
    SELECTOR_MESSAGE_CONTAINER = '[class*="message"], [class*="chat"], [role="log"]'
    SELECTOR_MESSAGE_ITEM = '[class*="message"], [class*="item"], [data-message-id]'

    # AI response indicators
    SELECTOR_AI_MESSAGE = '[class*="assistant"], [class*="ai"], [class*="bot"]'
    SELECTOR_THINKING = '[class*="thinking"], [class*="loading"], [class*="typing"]'

    def __init__(self, cdp_client: CDPClient):
        self.cdp = cdp_client

    async def find_input_element(self) -> Optional[str]:
        """
        Find the chat input element selector

        Returns:
            Selector string or None if not found
        """
        # Try Trae-specific selectors first, then fallback to generic ones
        selectors = [
            self.SELECTOR_TRAE_CHAT_INPUT,
            self.SELECTOR_TRAE_TEXTAREA,
            self.SELECTOR_INPUT,
            self.SELECTOR_TEXTAREA,
            'input[type="text"]',
            '[placeholder*="message" i], [placeholder*="chat" i], [placeholder*="聊天" i]',
            '[role="textbox"]'
        ]

        for selector in selectors:
            try:
                result = await self.cdp.evaluate(
                    f"""((() => {{
                        const el = document.querySelector('{selector}');
                        if (!el) return null;
                        return {{
                            found: true,
                            tagName: el.tagName,
                            placeholder: el.placeholder || "",
                            className: el.className || "",
                            role: el.getAttribute('role') || ""
                        }};
                    }})())"""
                )

                if result and result.get("found"):
                    logger.info(f"Found input element using selector: {selector}")
                    return selector

            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")

        logger.warning("Could not find input element")
        return None

    async def find_send_button(self) -> Optional[str]:
        """
        Find the send button selector

        Returns:
            Selector string or None if not found
        """
        selectors = [
            'button[type="submit"]',
            'button[aria-label*="send" i]',
            'button[aria-label*="Send" i]',
            'button[title*="send" i]',
            'button[class*="send" i]',
            '[role="button"][class*="submit" i]'
        ]

        for selector in selectors:
            try:
                result = await self.cdp.evaluate(
                    f"""((() => {{
                        const el = document.querySelector('{selector}');
                        if (!el) return null;
                        return {{
                            found: true,
                            text: el.textContent || "",
                            className: el.className || "",
                            ariaLabel: el.getAttribute('aria-label') || ""
                        }};
                    }})())"""
                )

                if result and result.get("found"):
                    logger.info(f"Found send button using selector: {selector}")
                    return selector

            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")

        logger.warning("Could not find send button")
        return None

    async def send_message(self, message: str, input_selector: Optional[str] = None) -> bool:
        """
        Send a message to Trae's chat interface

        Args:
            message: Message text to send
            input_selector: Optional input element selector (auto-detected if not provided)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Auto-detect input if not provided
            if not input_selector:
                input_selector = await self.find_input_element()
                if not input_selector:
                    raise ValueError("Could not find input element")

            # Escape message for safe insertion into JavaScript
            escaped_message = message.replace('\\', '\\\\').replace("'", "\\'")

            # Focus and input text
            await self.cdp.evaluate(
                f"""((() => {{
                    const input = document.querySelector('{input_selector}');
                    if (!input) return false;

                    input.focus();

                    // Try different methods to insert text
                    if (input.value !== undefined) {{
                        input.value = '{escaped_message}';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    }} else {{
                        document.execCommand('insertText', false, '{escaped_message}');
                    }}

                    return true;
                }})())"""
            )

            # Find and click send button
            send_selector = await self.find_send_button()
            if send_selector:
                await self.cdp.evaluate(
                    f"""((() => {{
                        const btn = document.querySelector('{send_selector}');
                        if (btn) {{
                            btn.click();
                            return true;
                        }}
                        return false;
                    }})())"""
                )
            else:
                # Try pressing Enter as fallback
                await self.cdp.evaluate(
                    """((() => {
                        const input = document.activeElement;
                        if (input) {
                            input.dispatchEvent(new KeyboardEvent('keydown', {
                                key: 'Enter',
                                code: 'Enter',
                                keyCode: 13,
                                bubbles: true
                            }));
                            return true;
                        }
                        return false;
                    }})())"""
                )

            logger.info(f"Message sent successfully: {message[:50]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def get_last_ai_message(self) -> Optional[dict]:
        """
        Get the last AI response message

        Returns:
            Dictionary with message content and metadata, or None if not found
        """
        try:
            result = await self.cdp.evaluate(
                """((() => {
                    // Try different strategies to find messages
                    const selectors = [
                        '[class*="message"]',
                        '[class*="chat"]',
                        '[role="log"] > div',
                        '[data-message-id]'
                    ];

                    let messages = [];

                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            // Check if these look like messages
                            const first = elements[0];
                            if (first.textContent && first.textContent.length > 0) {
                                messages = Array.from(elements);
                                break;
                            }
                        }
                    }

                    if (messages.length === 0) {
                        return null;
                    }

                    // Get the last message
                    const last = messages[messages.length - 1];

                    return {
                        text: last.textContent || last.innerText || '',
                        html: last.innerHTML || '',
                        className: last.className || '',
                        isComplete: !document.querySelector('[class*="thinking"], [class*="loading"], [class*="typing"]')
                    };
                }})())"""
            )

            if result:
                logger.debug(f"Got last AI message: {result.get('text', '')[:100]}...")
                return result

            return None

        except Exception as e:
            logger.error(f"Failed to get last AI message: {e}")
            return None

    async def wait_for_response(
        self,
        timeout: float = 180.0,
        poll_interval: float = 1.0
    ) -> Optional[str]:
        """
        Wait for AI response to complete

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Response text or None if timeout
        """
        start_time = asyncio.get_event_loop().time()

        logger.info(f"Waiting for AI response (timeout: {timeout}s)...")

        while True:
            # Check timeout
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for response after {elapsed:.1f}s")
                return None

            # Get current message
            message = await self.get_last_ai_message()

            if message:
                # Check if response is complete
                if message.get("isComplete"):
                    text = message.get("text", "")
                    logger.info(f"Response complete: {len(text)} characters")
                    return text

            # Wait before next poll
            await asyncio.sleep(poll_interval)

    async def new_chat(self) -> bool:
        """
        Start a new chat (clear context)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Try various methods to start a new chat
            result = await self.cdp.evaluate(
                """((() => {
                    // Try to find new chat button
                    const selectors = [
                        'button[aria-label*="new" i]',
                        'button[aria-label*="New Chat" i]',
                        'button[title*="new" i]',
                        '[class*="new-chat"]',
                        '[class*="newChat"]'
                    ];

                    for (const selector of selectors) {
                        const btn = document.querySelector(selector);
                        if (btn) {
                            btn.click();
                            return true;
                        }
                    }

                    // Try keyboard shortcut (Ctrl/Cmd + Shift + N)
                    document.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'n',
                        code: 'KeyN',
                        ctrlKey: true,
                        shiftKey: true,
                        bubbles: true
                    }));

                    return true;
                }})())"""
            )

            logger.info("New chat initiated")
            return bool(result)

        except Exception as e:
            logger.error(f"Failed to start new chat: {e}")
            return False

    async def get_chat_history(self) -> list[dict]:
        """
        Get current chat history

        Returns:
            List of message dictionaries
        """
        try:
            result = await self.cdp.evaluate(
                """((() => {
                    const selectors = [
                        '[class*="message"]',
                        '[class*="chat"] > div',
                        '[role="log"] > div',
                        '[data-message-id]'
                    ];

                    let messages = [];

                    for (const selector of selectors) {
                        const elements = document.querySelectorAll(selector);
                        if (elements.length > 0) {
                            messages = Array.from(elements).map(el => ({
                                text: el.textContent || el.innerText || '',
                                className: el.className || ''
                            }));
                            break;
                        }
                    }

                    return messages;
                }})())"""
            )

            if isinstance(result, list):
                logger.info(f"Retrieved {len(result)} messages from history")
                return result

            return []

        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []

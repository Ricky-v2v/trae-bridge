"""
DOM Helper for Trae Bridge
Provides utilities for interacting with Trae's chat UI

Selectors are based on Trae's actual DOM structure (as of 2026-03):
- Input: div.chat-input-v2-input-box-editable[role="textbox"]
- Send button: .chat-input-v2-send-button
- Messages: section.chat-turn.assistant / section.chat-turn.user
- Thinking: [class*="stop"] button visible means AI is generating
"""

import asyncio
import logging
from typing import Optional
from .cdp_client import CDPClient

logger = logging.getLogger(__name__)


class DOMHelper:
    """Helper for DOM operations in Trae"""

    # ──────────────────────────────────────────────────────────
    # Trae-specific selectors (discovered via DOM inspection)
    # ──────────────────────────────────────────────────────────

    # Chat input (Lexical contenteditable div)
    SELECTOR_CHAT_INPUT = 'div.chat-input-v2-input-box-editable[role="textbox"]'

    # Send button
    SELECTOR_SEND_BUTTON = '.chat-input-v2-send-button'

    # Message turns
    SELECTOR_ASSISTANT_TURN = 'section.chat-turn.assistant'
    SELECTOR_USER_TURN = 'section.chat-turn.user'
    SELECTOR_ALL_TURNS = 'section.chat-turn'

    # Content within assistant turns
    SELECTOR_ASSISTANT_CONTENT = '.assistant-chat-turn-content'
    SELECTOR_MARKDOWN = '.chat-markdown'

    # Fallback selectors (if Trae UI changes)
    FALLBACK_INPUT_SELECTORS = [
        'div.chat-input-v2-input-box-editable[role="textbox"]',
        'div.chat-input-v2-input-box-editable',
        '[class*="chat-input"][contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
        '[contenteditable="true"]',
    ]

    FALLBACK_SEND_SELECTORS = [
        '.chat-input-v2-send-button',
        '[class*="send-button"]',
        '[class*="send_button"]',
        'button[class*="send" i]',
    ]

    def __init__(self, cdp_client: CDPClient):
        self.cdp = cdp_client
        self._cached_input_selector: Optional[str] = None
        self._cached_send_selector: Optional[str] = None

    async def find_input_element(self) -> Optional[str]:
        """
        Find the chat input element selector.

        Returns:
            Selector string or None if not found
        """
        for selector in self.FALLBACK_INPUT_SELECTORS:
            try:
                result = await self.cdp.evaluate(
                    f"""((() => {{
                        const el = document.querySelector('{selector}');
                        if (!el) return null;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return null;
                        return {{
                            found: true,
                            tagName: el.tagName,
                            className: el.className || "",
                            w: Math.round(rect.width),
                            h: Math.round(rect.height)
                        }};
                    }})())"""
                )

                if result and result.get("found"):
                    logger.info(f"Found input element: {selector} ({result.get('w')}x{result.get('h')})")
                    self._cached_input_selector = selector
                    return selector

            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")

        logger.warning("Could not find input element")
        return None

    async def find_send_button(self) -> Optional[str]:
        """
        Find the send button selector.

        Returns:
            Selector string or None if not found
        """
        for selector in self.FALLBACK_SEND_SELECTORS:
            try:
                result = await self.cdp.evaluate(
                    f"""((() => {{
                        const el = document.querySelector('{selector}');
                        if (!el) return null;
                        const rect = el.getBoundingClientRect();
                        if (rect.width === 0 || rect.height === 0) return null;
                        return {{
                            found: true,
                            disabled: el.disabled || el.classList.contains('disabled'),
                            className: el.className || ""
                        }};
                    }})())"""
                )

                if result and result.get("found"):
                    logger.info(f"Found send button: {selector} (disabled={result.get('disabled')})")
                    self._cached_send_selector = selector
                    return selector

            except Exception as e:
                logger.debug(f"Selector {selector} failed: {e}")

        logger.warning("Could not find send button")
        return None

    async def send_message(self, message: str, input_selector: Optional[str] = None) -> bool:
        """
        Send a message to Trae's chat interface.

        Strategy:
        1. Focus the input box
        2. Clear existing text
        3. Insert new text using execCommand (to trigger Lexical editor events)
        4. Wait briefly for the send button to become enabled
        5. Click the send button (or press Enter as fallback)

        Args:
            message: Message text to send
            input_selector: Optional input element selector (auto-detected if not provided)

        Returns:
            True if successful, False otherwise
        """
        try:
            # Auto-detect input if not provided
            if not input_selector:
                input_selector = self._cached_input_selector or await self.find_input_element()
                if not input_selector:
                    raise ValueError("Could not find input element in Trae's UI")

            # Escape message for JavaScript string (handle backslash, single quotes, newlines)
            escaped_message = (
                message
                .replace('\\', '\\\\')
                .replace("'", "\\'")
                .replace('\n', '\\n')
                .replace('\r', '')
            )

            # Step 1: Focus input and clear existing content
            logger.debug("Focusing input and clearing content...")
            await self.cdp.evaluate(
                f"""((() => {{
                    const input = document.querySelector('{input_selector}');
                    if (!input) return false;
                    input.focus();
                    // Select all existing content and delete it
                    const selection = window.getSelection();
                    const range = document.createRange();
                    range.selectNodeContents(input);
                    selection.removeAllRanges();
                    selection.addRange(range);
                    document.execCommand('delete', false, null);
                    return true;
                }})())"""
            )

            # Small delay for focus/clear to take effect
            await asyncio.sleep(0.1)

            # Step 2: Insert text using execCommand (works with Lexical/contenteditable)
            logger.debug(f"Inserting text: {message[:50]}...")
            result = await self.cdp.evaluate(
                f"""((() => {{
                    const input = document.querySelector('{input_selector}');
                    if (!input) return false;
                    input.focus();
                    const inserted = document.execCommand('insertText', false, '{escaped_message}');
                    if (!inserted) {{
                        // Fallback: set textContent and fire input event
                        input.textContent = '{escaped_message}';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    }}
                    return true;
                }})())"""
            )

            if not result:
                logger.error("Failed to insert text into input")
                return False

            # Step 3: Wait for send button to become enabled
            logger.debug("Waiting for send button to become enabled...")
            await asyncio.sleep(0.3)

            # Step 4: Click the send button
            send_selector = self._cached_send_selector or await self.find_send_button()
            sent = False

            if send_selector:
                sent = await self.cdp.evaluate(
                    f"""((() => {{
                        const btn = document.querySelector('{send_selector}');
                        if (btn && !btn.classList.contains('disabled')) {{
                            btn.click();
                            return true;
                        }}
                        return false;
                    }})())"""
                )

            if not sent:
                # Fallback: try pressing Enter
                logger.debug("Send button not available, trying Enter key...")
                await self.cdp.evaluate(
                    f"""((() => {{
                        const input = document.querySelector('{input_selector}');
                        if (!input) return false;
                        input.focus();
                        input.dispatchEvent(new KeyboardEvent('keydown', {{
                            key: 'Enter',
                            code: 'Enter',
                            keyCode: 13,
                            which: 13,
                            bubbles: true,
                            cancelable: true
                        }}));
                        return true;
                    }})())"""
                )

            logger.info(f"Message sent: {message[:80]}...")
            return True

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return False

    async def _count_assistant_turns(self) -> int:
        """Get the current number of assistant message turns."""
        result = await self.cdp.evaluate(
            f"""((() => {{
                return document.querySelectorAll('{self.SELECTOR_ASSISTANT_TURN}').length;
            }})())"""
        )
        return result if isinstance(result, int) else 0

    async def _is_ai_generating(self) -> bool:
        """
        Check if the AI is currently generating a response.

        Detection strategy:
        1. Check for visible stop/interrupt button (most reliable)
        2. Check for generating/streaming indicators
        3. Check for pending task indicators in the latest turn
        """
        result = await self.cdp.evaluate(
            """((() => {
                // Check 1: Stop button visible
                const stopBtns = document.querySelectorAll(
                    '[class*="stop-button"], [class*="stop_button"], ' +
                    'button[aria-label*="stop" i], button[aria-label*="Stop"]'
                );
                for (const btn of stopBtns) {
                    const rect = btn.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) return true;
                }

                // Check 2: Send button shows "stop" state (class changes when generating)
                const sendBtn = document.querySelector('.chat-input-v2-send-button');
                if (sendBtn) {
                    const cls = sendBtn.className || '';
                    if (cls.includes('stop') || cls.includes('generating') || cls.includes('loading')) {
                        return true;
                    }
                }

                // Check 3: Check for pending tasks in the last assistant turn
                const turns = document.querySelectorAll('section.chat-turn.assistant');
                if (turns.length > 0) {
                    const lastTurn = turns[turns.length - 1];
                    const pendingItems = lastTurn.querySelectorAll(
                        '[class*="pending"], [class*="running"], [class*="streaming"]'
                    );
                    for (const item of pendingItems) {
                        const rect = item.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) return true;
                    }
                }

                // Check 4: Check if there's any visible loading/thinking animation
                // Only count as "generating" if it's within the LAST turn
                if (turns.length > 0) {
                    const lastTurn = turns[turns.length - 1];
                    const loadingEls = lastTurn.querySelectorAll(
                        '[class*="loading"]:not(.done), [class*="typing"], [class*="generating"]'
                    );
                    for (const el of loadingEls) {
                        const rect = el.getBoundingClientRect();
                        if (rect.width > 0 && rect.height > 0) return true;
                    }
                }

                return false;
            })())"""
        )
        return bool(result)

    async def get_last_ai_message(self) -> Optional[dict]:
        """
        Get the last AI response message.

        Returns:
            Dictionary with message content and metadata, or None if not found
        """
        try:
            result = await self.cdp.evaluate(
                """((() => {
                    const turns = document.querySelectorAll('section.chat-turn.assistant');
                    if (turns.length === 0) return null;

                    const lastTurn = turns[turns.length - 1];

                    // Extract the main text content from .chat-markdown elements
                    const markdownEls = lastTurn.querySelectorAll('.chat-markdown');
                    let markdownText = '';
                    for (const md of markdownEls) {
                        markdownText += (md.textContent || '') + '\\n';
                    }

                    // If no markdown content, use the full turn text (for non-markdown responses)
                    const fullText = markdownText.trim() || (lastTurn.textContent || '').trim();

                    // Clean up the text: remove UI elements like "SOLO Coder", "思考过程" etc.
                    // The actual response is in .assistant-chat-turn-content
                    const contentEl = lastTurn.querySelector('.assistant-chat-turn-content');
                    const contentText = contentEl ? (contentEl.textContent || '').trim() : fullText;

                    return {
                        text: contentText,
                        markdownText: markdownText.trim(),
                        className: lastTurn.className || '',
                        turnIndex: turns.length - 1,
                        isComplete: true  // will be overridden by caller
                    };
                })())"""
            )

            if result:
                # Check if AI is still generating
                is_generating = await self._is_ai_generating()
                result["isComplete"] = not is_generating
                logger.debug(
                    f"Last AI message: {len(result.get('text', ''))} chars, "
                    f"complete={result['isComplete']}"
                )
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
        Wait for AI response to complete.

        Strategy:
        1. Record the current number of assistant turns
        2. Wait for a new assistant turn to appear (AI started responding)
        3. Then wait for the AI to finish generating (stop button disappears)
        4. Extract the response text

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Time between polls in seconds

        Returns:
            Response text or None if timeout
        """
        start_time = asyncio.get_event_loop().time()
        initial_turn_count = await self._count_assistant_turns()

        logger.info(
            f"Waiting for AI response (timeout: {timeout}s, "
            f"current assistant turns: {initial_turn_count})..."
        )

        # Phase 1: Wait for a new assistant turn to appear
        new_turn_detected = False
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for AI to start responding after {elapsed:.1f}s")
                return None

            current_count = await self._count_assistant_turns()
            if current_count > initial_turn_count:
                new_turn_detected = True
                logger.info(f"New assistant turn detected (turn #{current_count})")
                break

            # Also check if AI is already generating (in case turn count didn't change)
            is_generating = await self._is_ai_generating()
            if is_generating:
                new_turn_detected = True
                logger.info("AI is generating (detected via generating state)")
                break

            await asyncio.sleep(poll_interval)

        # Phase 2: Wait for AI to finish generating
        # Use adaptive polling: start fast, slow down over time
        stable_count = 0
        last_text_len = 0

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                logger.warning(f"Timeout waiting for response completion after {elapsed:.1f}s")
                # Still try to return what we have
                message = await self.get_last_ai_message()
                if message:
                    return message.get("text") or message.get("markdownText")
                return None

            is_generating = await self._is_ai_generating()

            if not is_generating:
                # AI might have finished, but let's verify with text stability
                message = await self.get_last_ai_message()
                if message:
                    current_text_len = len(message.get("text", ""))
                    if current_text_len == last_text_len and current_text_len > 0:
                        stable_count += 1
                    else:
                        stable_count = 0
                        last_text_len = current_text_len

                    # Consider complete after 2 consecutive stable checks
                    if stable_count >= 2:
                        text = message.get("markdownText") or message.get("text", "")
                        logger.info(f"Response complete: {len(text)} characters")
                        return text
            else:
                stable_count = 0
                # Update text length while generating
                message = await self.get_last_ai_message()
                if message:
                    last_text_len = len(message.get("text", ""))

            # Adaptive polling: faster initially, slower after a while
            if elapsed < 10:
                await asyncio.sleep(0.5)
            elif elapsed < 30:
                await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(2.0)

    async def new_chat(self) -> bool:
        """
        Start a new chat (clear context).

        Returns:
            True if successful, False otherwise
        """
        try:
            # Strategy 1: Try to find and click the "new chat" button
            result = await self.cdp.evaluate(
                """((() => {
                    // Look for new chat buttons in the sidebar/toolbar
                    const selectors = [
                        'button[aria-label*="new" i]',
                        'button[aria-label*="New Chat" i]',
                        'button[title*="new" i]',
                        'button[title*="New Chat" i]',
                        '[class*="new-chat"]',
                        '[class*="newChat"]',
                        '[class*="new_chat"]',
                    ];

                    for (const selector of selectors) {
                        const btns = document.querySelectorAll(selector);
                        for (const btn of btns) {
                            const rect = btn.getBoundingClientRect();
                            if (rect.width > 0 && rect.height > 0) {
                                btn.click();
                                return {clicked: true, selector: selector};
                            }
                        }
                    }

                    return {clicked: false};
                })())"""
            )

            if result and result.get("clicked"):
                logger.info(f"New chat clicked via: {result.get('selector')}")
                await asyncio.sleep(0.5)
                return True

            # Strategy 2: Try keyboard shortcut (Cmd+Shift+N on macOS)
            logger.info("Trying keyboard shortcut for new chat...")
            await self.cdp.evaluate(
                """((() => {
                    document.dispatchEvent(new KeyboardEvent('keydown', {
                        key: 'n',
                        code: 'KeyN',
                        metaKey: true,
                        shiftKey: true,
                        bubbles: true
                    }));
                    return true;
                })())"""
            )

            await asyncio.sleep(0.5)
            logger.info("New chat initiated via keyboard shortcut")
            return True

        except Exception as e:
            logger.error(f"Failed to start new chat: {e}")
            return False

    async def get_chat_history(self) -> list[dict]:
        """
        Get current chat history.

        Returns:
            List of message dictionaries with role and text
        """
        try:
            result = await self.cdp.evaluate(
                """((() => {
                    // Get all top-level chat turns (user and assistant)
                    const turns = document.querySelectorAll(
                        'section.chat-turn.user, section.chat-turn.assistant'
                    );

                    return Array.from(turns).map(turn => {
                        const isUser = turn.classList.contains('user');
                        const isAssistant = turn.classList.contains('assistant');

                        let text = '';
                        if (isUser) {
                            // For user turns, get the bubble content
                            const bubble = turn.querySelector(
                                '.user-chat-turn-content-bubble-wrapper'
                            );
                            text = bubble
                                ? (bubble.textContent || '').trim()
                                : (turn.textContent || '').trim();
                        } else if (isAssistant) {
                            // For assistant turns, get markdown content
                            const markdownEls = turn.querySelectorAll('.chat-markdown');
                            if (markdownEls.length > 0) {
                                text = Array.from(markdownEls)
                                    .map(md => (md.textContent || '').trim())
                                    .join('\\n');
                            } else {
                                const content = turn.querySelector(
                                    '.assistant-chat-turn-content'
                                );
                                text = content
                                    ? (content.textContent || '').trim()
                                    : (turn.textContent || '').trim();
                            }
                        }

                        return {
                            role: isUser ? 'user' : isAssistant ? 'assistant' : 'unknown',
                            text: text,
                            className: turn.className || ''
                        };
                    });
                })())"""
            )

            if isinstance(result, list):
                logger.info(f"Retrieved {len(result)} messages from history")
                return result

            return []

        except Exception as e:
            logger.error(f"Failed to get chat history: {e}")
            return []

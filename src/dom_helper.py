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
from typing import Optional, Any
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
        self._response_finished_event = asyncio.Event()
        
        # Register for console events to catch our custom completion signal
        self.cdp.add_event_listener("Runtime.consoleAPICalled", self._handle_console_event)


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
            # Pre-inject completion observer BEFORE sending, to avoid race condition
            # where response completes before observer is installed
            self._response_finished_event.clear()
            await self._inject_completion_observer()

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

    async def _handle_console_event(self, params: dict[str, Any]) -> None:
        """Handle console events from CDP to detect completion signals"""
        args = params.get("args", [])
        text = " ".join([str(arg.get("value", "")) for arg in args if "value" in arg])
        
        if "TRAE_BRIDGE:FINISHED" in text:
            logger.info("Completion signal received via MutationObserver")
            self._response_finished_event.set()

    async def _inject_completion_observer(self, force_reinject: bool = True) -> bool:
        """Inject a MutationObserver to watch for response completion"""
        logger.debug("Injecting MutationObserver for completion detection...")

        # This script watches for the appearance and subsequent disappearance
        # of the "stop generating" button which signals the end of a turn.
        skip_reinject = "false" if force_reinject else "true"
        script = f"""((() => {{
            const skipIfInjected = {skip_reinject};

            if (window.traeBridgeObserver) {{
                if (skipIfInjected) {{
                    return true; // Already injected and not forcing reinject
                }}
                window.traeBridgeObserver.disconnect();
            }}

            console.log('TRAE_BRIDGE:OBSERVER_START');

            const findStopButton = () => {{
                // Look for common patterns of the stop/generating button
                return document.querySelector('[class*="stop-button"]') ||
                       document.querySelector('button[aria-label*="Stop"]') ||
                       document.querySelector('.generating');
            }};

            let stopButtonSeen = !!findStopButton();

            const observer = new MutationObserver(() => {{
                const stopBtn = findStopButton();

                if (stopBtn) {{
                    stopButtonSeen = true;
                }} else if (stopButtonSeen) {{
                    // It was there, now it's gone!
                    // Wait a tiny bit to ensure it doesn't flicker or move
                    setTimeout(() => {{
                        const stillGone = !findStopButton();
                        if (stillGone) {{
                            console.log('TRAE_BRIDGE:FINISHED');
                            observer.disconnect();
                            window.traeBridgeObserver = null;
                        }}
                    }}, 500);
                }}
            }});

            // Auto-cleanup after 5 minutes to prevent memory leaks
            setTimeout(() => {{
                if (window.traeBridgeObserver) {{
                    window.traeBridgeObserver.disconnect();
                    window.traeBridgeObserver = null;
                }}
            }}, 5 * 60 * 1000);

            observer.observe(document.body, {{
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class', 'disabled']
            }});

            window.traeBridgeObserver = observer;
            return true;
        }})())"""

        return await self.cdp.evaluate(script)

    async def wait_for_response(
        self,
        timeout: float = 180.0,
        poll_interval: float = 1.0
    ) -> Optional[str]:
        """
        Wait for AI response to complete using an event-driven approach.

        Strategy:
        1. Reset the completion event
        2. Inject a MutationObserver that logs when the response is finished
        3. Wait for the event OR a timeout
        4. Provide polling fallback if event doesn't trigger

        Args:
            timeout: Maximum time to wait in seconds
            poll_interval: Polling interval for fallback

        Returns:
        Returns:
            Response text or None if timeout
        """
        # We do NOT clear the event here: send_message clears it.
        # If the response was super fast, the event might be set already!
        # If we clear it here, we'd dead-lock waiting for an event that already fired.
        
        start_time = asyncio.get_event_loop().time()
        
        # Phase 1: Ensure observer is injected (but don't overwrite if it's already there)
        await self._inject_completion_observer(force_reinject=False)

        logger.info(f"Waiting for AI response (timeout: {timeout}s, event-driven)...")

        try:
            # Wait for the event with timeout
            await asyncio.wait_for(self._response_finished_event.wait(), timeout=timeout)
            logger.info("Event-driven completion detected!")
        except asyncio.TimeoutError:
            logger.warning(f"Event-driven completion timed out after {timeout}s, falling back to polling...")
            
            # Fallback to polling to be safe
            remaining_timeout = 10.0 # Small buffer for polling fallback
            polling_start = asyncio.get_event_loop().time()
            
            while True:
                elapsed = asyncio.get_event_loop().time() - polling_start
                if elapsed >= remaining_timeout:
                    break
                
                is_generating = await self._is_ai_generating()
                if not is_generating:
                    logger.info("Polling fallback detected completion")
                    break
                
                await asyncio.sleep(poll_interval)

        # Extraction phase (same as before but more confident)
        message = await self.get_last_ai_message()
        if message:
            return message.get("text") or message.get("markdownText")
        
        return None


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

    async def switch_model(self, model_name: str) -> bool:
        """
        Switch to a specific AI model via Trae UI.
        
        Args:
            model_name: The name of the model to select (e.g., 'Claude', 'GPT-4')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # 1. Click the model selector trigger button
            logger.info("Opening model selector dropdown...")
            opened = await self.cdp.evaluate(
                """((() => {
                    const trigger = document.querySelector('button.icd-model-select-trigger');
                    if (trigger) {
                        trigger.click();
                        return true;
                    }
                    return false;
                })())"""
            )
            
            if not opened:
                logger.error("Could not find model selector trigger button")
                return False
                
            # Wait for dropdown animation
            await asyncio.sleep(0.5)
            
            # 2. Find and click the target model
            logger.info(f"Looking for model: {model_name}")
            escaped_model = model_name.replace("'", "\\'").lower().replace(" ", "")
            
            clicked = await self.cdp.evaluate(
                f"""((() => {{
                    // Try to find the element containing the model name
                    const targetText = '{escaped_model}';
                    
                    const walker = document.createTreeWalker(
                        document.body,
                        NodeFilter.SHOW_TEXT,
                        {{
                            acceptNode: (node) => {{
                                if (!node.parentElement) return NodeFilter.FILTER_REJECT;
                                const style = window.getComputedStyle(node.parentElement);
                                if (style.display === 'none' || style.visibility === 'hidden') {{
                                    return NodeFilter.FILTER_REJECT;
                                }}
                                const text = node.textContent.toLowerCase().replace(/\\s+/g, '');
                                if (text.includes(targetText)) {{
                                    return NodeFilter.FILTER_ACCEPT;
                                }}
                                return NodeFilter.FILTER_REJECT;
                            }}
                        }}
                    );
                    
                    let targetNode = walker.nextNode();
                    if (targetNode && targetNode.parentElement) {{
                        // Click the parent element (usually a span)
                        targetNode.parentElement.click();
                        
                        // We also dispatch a mousedown event just in case
                        targetNode.parentElement.dispatchEvent(new MouseEvent('mousedown', {{
                            bubbles: true,
                            cancelable: true,
                            view: window
                        }}));
                        
                        return true;
                    }}
                    return false;
                }})())"""
            )
            
            if clicked:
                logger.info(f"Successfully clicked model matching '{model_name}'")
                await asyncio.sleep(0.5) # Wait for UI to update
                return True
            else:
                logger.warning(f"Could not find model matching '{model_name}' in dropdown")
                
                # Close dropdown since we failed
                await self.cdp.evaluate("document.body.click();")
                await asyncio.sleep(0.2)
                return False
                
        except Exception as e:
            logger.error(f"Failed to switch model: {e}")
            return False


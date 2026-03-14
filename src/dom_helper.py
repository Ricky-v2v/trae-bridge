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
import re
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

    _MODEL_NORMALIZE_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
    _MODEL_TOKEN_SPLIT_RE = re.compile(r"[^a-z0-9\u4e00-\u9fff]+")
    _MODEL_STOPWORDS = {"model", "models", "use", "using", "模型", "使用"}
    MODEL_NAME_MAP = {
        "g3p": "gemini-3-pro",
        "gemini3pro": "gemini-3-pro",
        "geminipro": "gemini-3-pro",
        "g3f": "gemini-3-flash",
        "gemini3flash": "gemini-3-flash",
        "g35s": "claude-3.5-sonnet",
        "c35s": "claude-3.5-sonnet",
        "claude35sonnet": "claude-3.5-sonnet",
        "gpt4o": "gpt-4o",
        "gpt41": "gpt-4.1",
        "o1mini": "o1-mini",
        "o3mini": "o3-mini",
    }

    def __init__(self, cdp_client: CDPClient):
        self.cdp = cdp_client
        self._cached_input_selector: Optional[str] = None
        self._cached_send_selector: Optional[str] = None
        self._last_model_switch_error: Optional[str] = None
        self._response_finished_event = asyncio.Event()
        
        # Register for console events to catch our custom completion signal
        self.cdp.add_event_listener("Runtime.consoleAPICalled", self._handle_console_event)

    @staticmethod
    def _escape_js_string(value: str) -> str:
        """Escape Python string for embedding inside single-quoted JS string literals."""
        return (
            value
            .replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\n", "\\n")
            .replace("\r", "")
        )

    @classmethod
    def _normalize_model_name(cls, value: str) -> str:
        """Normalize model names: case-insensitive and remove spaces/special chars."""
        if not value:
            return ""
        return cls._MODEL_NORMALIZE_RE.sub("", value.lower())

    @classmethod
    def _tokenize_model_name(cls, value: str) -> list[str]:
        """Tokenize model name for fuzzy scoring."""
        if not value:
            return []
        tokens = cls._MODEL_TOKEN_SPLIT_RE.split(value.lower())
        return [t for t in tokens if t and t not in cls._MODEL_STOPWORDS]

    @classmethod
    def _expand_query_aliases(cls, model_name: str) -> set[str]:
        """Expand query into normalized forms using the model alias map."""
        variants: set[str] = set()
        if not model_name:
            return variants

        normalized = cls._normalize_model_name(model_name)
        token_key = "".join(cls._tokenize_model_name(model_name))

        if normalized:
            variants.add(normalized)
        if token_key:
            variants.add(token_key)

        for key in (normalized, token_key):
            if not key:
                continue
            mapped = cls.MODEL_NAME_MAP.get(key)
            if mapped:
                variants.add(cls._normalize_model_name(mapped))

        return variants

    @classmethod
    def _score_model_candidate(
        cls,
        query_variants: set[str],
        query_tokens: set[str],
        candidate_norm: str,
        candidate_tokens: set[str],
    ) -> int:
        """Score a candidate model name against the query with intent-aware weights."""
        if not candidate_norm:
            return -1

        score = -1
        for query_norm in query_variants:
            if not query_norm:
                continue
            if candidate_norm == query_norm:
                score = max(score, 1200)
            elif candidate_norm.startswith(query_norm) and len(query_norm) >= 3:
                score = max(score, 980)
            elif query_norm.startswith(candidate_norm) and len(candidate_norm) >= 3:
                score = max(score, 650)
            elif query_norm in candidate_norm and len(query_norm) >= 4:
                score = max(score, 860)
            elif candidate_norm in query_norm and len(candidate_norm) >= 4:
                score = max(score, 520)

        overlap = len(query_tokens & candidate_tokens)
        score += overlap * 70

        wants_pro = "pro" in query_tokens
        wants_flash = "flash" in query_tokens
        wants_preview = "preview" in query_tokens
        has_pro = "pro" in candidate_tokens
        has_flash = "flash" in candidate_tokens
        has_preview = "preview" in candidate_tokens

        if wants_pro:
            score += 180 if has_pro else -180
            if has_flash:
                score -= 220
        if wants_flash:
            score += 180 if has_flash else -180
            if has_pro:
                score -= 220
        if wants_preview and has_preview:
            score += 90

        # Prefer tighter names when score is otherwise close.
        shortest_query = min((len(v) for v in query_variants if v), default=0)
        if shortest_query:
            score -= abs(len(candidate_norm) - shortest_query)

        return score

    def match_model_name(
        self,
        model_name: str,
        available_models: list[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        Match user input to the best model name in available list.

        Returns:
            (best_model, error_message)
        """
        if not (model_name or "").strip():
            return None, "Model name is empty. Please provide a valid model name."

        if not available_models:
            return None, "No models are available from Trae UI right now."

        query_variants = self._expand_query_aliases(model_name)
        query_tokens = set(self._tokenize_model_name(model_name))
        if not query_variants:
            return None, f"Model '{model_name}' is invalid after normalization."

        scored: list[tuple[int, str, str]] = []
        fallback: list[tuple[int, str]] = []

        for model in available_models:
            candidate = (model or "").strip()
            if not candidate:
                continue
            candidate_norm = self._normalize_model_name(candidate)
            if not candidate_norm:
                continue
            candidate_tokens = set(self._tokenize_model_name(candidate))

            score = self._score_model_candidate(
                query_variants=query_variants,
                query_tokens=query_tokens,
                candidate_norm=candidate_norm,
                candidate_tokens=candidate_tokens,
            )
            if score > 0:
                scored.append((score, candidate, candidate_norm))

            overlap = len(query_tokens & candidate_tokens)
            prefix_hit = int(any(candidate_norm.startswith(v) for v in query_variants if v))
            fallback.append((overlap * 100 + prefix_hit * 80, candidate))

        if not scored:
            fallback.sort(key=lambda x: (-x[0], x[1].lower()))
            suggestions = [name for _, name in fallback[:3] if name]
            if suggestions:
                return None, (
                    f"No model matched '{model_name}'. "
                    f"Try one of: {', '.join(suggestions)}"
                )
            return None, f"No model matched '{model_name}'."

        scored.sort(key=lambda x: (-x[0], len(x[2]), x[1].lower()))
        return scored[0][1], None

    def get_last_model_switch_error(self) -> Optional[str]:
        """Return the latest user-facing model switch error, if any."""
        return self._last_model_switch_error


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

            # Step 1: Clear existing content before typing new question
            cleared = await self._clear_input_box(input_selector=input_selector)
            if not cleared:
                logger.error("Input box could not be cleared. Aborting message send.")
                return False

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

    async def _is_input_empty(self, input_selector: str) -> bool:
        """Check whether chat input is effectively empty."""
        result = await self.cdp.evaluate(
            f"""((() => {{
                const input = document.querySelector('{input_selector}');
                if (!input) return false;
                const text = (input.innerText || input.textContent || '').replace(/\\u00A0/g, ' ').trim();
                return text.length === 0;
            }})())"""
        )
        return bool(result)

    async def _clear_input_box(self, input_selector: str, retries: int = 3) -> bool:
        """
        Clear the chat input safely before entering a new question.

        This only operates on the input box content and does not touch chat history.
        """
        try:
            if await self._is_input_empty(input_selector):
                logger.info("Input box clear confirmed: already empty.")
                return True
        except Exception as e:
            logger.debug(f"Initial input-empty check failed: {e}")

        for attempt in range(1, retries + 1):
            try:
                cleared = await self.cdp.evaluate(
                    f"""((() => {{
                        const input = document.querySelector('{input_selector}');
                        if (!input) return false;

                        input.focus();

                        const selection = window.getSelection();
                        const range = document.createRange();
                        range.selectNodeContents(input);
                        selection.removeAllRanges();
                        selection.addRange(range);

                        // Primary strategy for Lexical/contenteditable.
                        document.execCommand('delete', false, null);

                        // Defensive fallback to ensure text nodes are empty.
                        input.textContent = '';
                        input.innerHTML = '';
                        input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                        input.dispatchEvent(new Event('change', {{ bubbles: true }}));

                        return true;
                    }})())"""
                )

                if not cleared:
                    continue

                await asyncio.sleep(0.05)
                if await self._is_input_empty(input_selector):
                    logger.info("Input box clear confirmed before new question (attempt %s).", attempt)
                    return True

            except Exception as e:
                logger.debug(f"Clear input attempt {attempt} failed: {e}")

        logger.warning("Input box clear failed after %s attempts.", retries)
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

    async def _open_model_selector(self) -> bool:
        """Open the model selector using the interaction pattern required by current Trae UI."""
        try:
            opened = await self.cdp.evaluate(
                """((() => {
                    const trigger = document.querySelector('button.icd-model-select-trigger');
                    if (!trigger) return false;

                    trigger.focus();

                    // Current Trae/Radix select opens reliably via keyboard interaction,
                    // while plain click() often leaves aria-expanded=false.
                    for (const [type, key, code, keyCode] of [
                        ['keydown', 'ArrowDown', 'ArrowDown', 40],
                        ['keyup', 'ArrowDown', 'ArrowDown', 40],
                    ]) {
                        trigger.dispatchEvent(new KeyboardEvent(type, {
                            key,
                            code,
                            keyCode,
                            which: keyCode,
                            bubbles: true,
                            cancelable: true,
                        }));
                    }

                    return true;
                })())"""
            )

            if not opened:
                return False

            await asyncio.sleep(0.6)

            dropdown_visible = await self.cdp.evaluate(
                """((() => {
                    const root = document.querySelector('[role="listbox"], .icube-model-select-portal-content');
                    if (!root) return false;
                    const rect = root.getBoundingClientRect();
                    return rect.width > 0 && rect.height > 0;
                })())"""
            )
            return bool(dropdown_visible)
        except Exception as e:
            logger.error(f"Failed to open model selector: {e}")
            return False

    async def _get_dropdown_model_options(self) -> list[str]:
        """Read visible model options from already-open dropdown."""
        result = await self.cdp.evaluate("""((() => {
            const seen = new Set();
            const results = [];
            const items = Array.from(document.querySelectorAll('.icube-model-select-portal-model-item'));

            for (const item of items) {
                const rect = item.getBoundingClientRect();
                if (rect.width === 0 || rect.height === 0) continue;

                const wrapper = item.querySelector('.icube-model-select-portal-model-item-wrapper');
                const rawText = (wrapper?.innerText || item.innerText || item.textContent || '').trim();
                if (!rawText) continue;

                const lines = rawText
                    .split('\\n')
                    .map(s => s.trim())
                    .filter(Boolean);
                const label = lines.join(' ').replace(/\\s+/g, ' ').trim();

                if (!label || seen.has(label)) continue;
                seen.add(label);
                results.push(label);
            }

            return results;
        })())""")

        if isinstance(result, list):
            return [str(m).strip() for m in result if str(m).strip()]
        return []

    async def _click_dropdown_model_by_name(self, chosen_model: str) -> bool:
        """Click an item in the open model dropdown by normalized model text."""
        escaped = self._escape_js_string(chosen_model)
        clicked = await self.cdp.evaluate(
            f"""((() => {{
                const normalize = (s) => (s || '')
                    .toLowerCase()
                    .replace(/[^a-z0-9\\u4e00-\\u9fff]+/g, '');
                const targetRaw = '{escaped}';
                const target = normalize(targetRaw);
                if (!target) return false;

                const items = Array.from(document.querySelectorAll('.icube-model-select-portal-model-item'));
                let exact = null;
                let prefix = null;

                for (const item of items) {{
                    const rect = item.getBoundingClientRect();
                    if (rect.width === 0 || rect.height === 0) continue;

                    const wrapper = item.querySelector('.icube-model-select-portal-model-item-wrapper');
                    const rawText = (wrapper?.innerText || item.innerText || item.textContent || '').trim();
                    if (!rawText) continue;

                    const lines = rawText
                        .split('\\n')
                        .map(s => s.trim())
                        .filter(Boolean);
                    const label = lines.join(' ').replace(/\\s+/g, ' ').trim();
                    const normalized = normalize(label);
                    if (!normalized) continue;

                    if (normalized === target) {{
                        exact = item;
                        break;
                    }}
                    if (!prefix && (normalized.startsWith(target) || target.startsWith(normalized))) {{
                        prefix = item;
                    }}
                }}

                const chosen = exact || prefix;
                if (!chosen) return false;

                chosen.scrollIntoView({{ block: 'center' }});
                chosen.dispatchEvent(new PointerEvent('pointerdown', {{ bubbles: true, cancelable: true, pointerType: 'mouse' }}));
                chosen.dispatchEvent(new MouseEvent('mousedown', {{ bubbles: true, cancelable: true, view: window, button: 0, buttons: 1 }}));
                chosen.dispatchEvent(new MouseEvent('mouseup', {{ bubbles: true, cancelable: true, view: window, button: 0, buttons: 1 }}));
                chosen.click();
                return true;
            }})())"""
        )
        return bool(clicked)

    async def _get_current_selected_model_text(self) -> str:
        """Read currently selected model text from model trigger."""
        result = await self.cdp.evaluate(
            """((() => {
                const trigger = document.querySelector('button.icd-model-select-trigger');
                const raw = (trigger?.innerText || trigger?.textContent || '').trim();
                return raw.replace(/\\s+/g, ' ').trim();
            })())"""
        )
        return str(result).strip() if result else ""

    async def switch_model(self, model_name: str) -> bool:
        """
        Switch to a specific AI model via Trae UI.

        Args:
            model_name: The name of the model to select (e.g., 'Claude', 'GPT-4')

        Returns:
            True if successful, False otherwise
        """
        self._last_model_switch_error = None

        try:
            logger.info("Opening model selector dropdown...")
            opened = await self._open_model_selector()

            if not opened:
                self._last_model_switch_error = "Could not open model selector dropdown in Trae UI."
                logger.error(self._last_model_switch_error)
                return False

            logger.info(f"Looking for model: {model_name}")
            available_models = await self._get_dropdown_model_options()
            chosen_model, error_message = self.match_model_name(model_name, available_models)
            if not chosen_model:
                self._last_model_switch_error = error_message or f"No model matched '{model_name}'."
                logger.warning(self._last_model_switch_error)
                await self.cdp.evaluate("document.body.click();")
                await asyncio.sleep(0.2)
                return False

            logger.info(f"Model match resolved: '{model_name}' -> '{chosen_model}'")
            clicked = await self._click_dropdown_model_by_name(chosen_model)
            if clicked:
                logger.info(f"Successfully clicked model '{chosen_model}'")
                await asyncio.sleep(0.8)
                selected_model = await self._get_current_selected_model_text()
                verified, _ = self.match_model_name(model_name, [selected_model])
                if verified:
                    return True

                self._last_model_switch_error = (
                    f"Model switch verification failed. Requested '{model_name}', "
                    f"but current selection appears to be '{selected_model or 'unknown'}'."
                )
                logger.warning(self._last_model_switch_error)
                await self.cdp.evaluate("document.body.click();")
                await asyncio.sleep(0.2)
                return False

            self._last_model_switch_error = (
                f"Failed to click matched model '{chosen_model}' for input '{model_name}'."
            )
            logger.warning(self._last_model_switch_error)
            await self.cdp.evaluate("document.body.click();")
            await asyncio.sleep(0.2)
            return False

        except Exception as e:
            self._last_model_switch_error = f"Unexpected error during model switch: {e}"
            logger.error(f"Failed to switch model: {e}")
            return False

    async def get_available_models(self) -> list[str]:
        """
        Dynamically query actual available models from the Trae UI dropdown.
        """
        try:
            opened = await self._open_model_selector()

            if not opened:
                logger.error("Could not open model selector dropdown to list models")
                return []

            models = await self._get_dropdown_model_options()

            await self.cdp.evaluate("document.body.click();")
            await asyncio.sleep(0.2)

            if isinstance(models, list):
                return [m for m in models if m]

            return []

        except Exception as e:
            logger.error(f"Failed to get available models: {e}")
            return []

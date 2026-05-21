"""
5-Stage Intent Detection Pipeline.

Determines what the user wants from their message:

  Stage 0: Conversation State — detect follow-up responses (yes/no/ok)
  Stage 1: Domain Entity Resolution — extract entities (products, customers, etc.)
  Stage 2: LLM Semantic Classification — classify as data/chat/clarification
  Stage 3: Ambiguity Detection — flag low-confidence or ambiguous queries
  Stage 4: Final Output — build structured IntentResult
"""

import re
import json
from dataclasses import dataclass, field

from llm.base import LLMProvider


# ─── Data Models ───────────────────────────────────────────────

@dataclass
class IntentResult:
    """Structured output of the intent detection pipeline."""
    intent: str                  # "data" | "chat" | "clarification"
    entity: str | None = None    # primary domain entity
    confidence: float = 0.0      # 0.0 - 1.0
    is_followup: bool = False
    original_query: str = ""
    enriched_query: str = ""     # with resolved entities
    clarification: str | None = None
    metadata: dict = field(default_factory=dict)


# ─── Follow-up Patterns ────────────────────────────────────────

_AFFIRMATIVE_PATTERNS = re.compile(
    r"(?i)^(yes|yeah|yep|sure|ok|okay|yea|y|absolutely|definitely|"
    r"please|go ahead|do it|show me|tell me more|more details|"
    r"show more|continue|proceed)[\s!.]*$"
)

_NEGATIVE_PATTERNS = re.compile(
    r"(?i)^(no|nah|nope|n|never mind|nevermind|skip|cancel|"
    r"forget it|don't|that's all|nothing|no thanks)[\s!.]*$"
)

# ─── Domain Entity Patterns ────────────────────────────────────

_ENTITY_PATTERNS: dict[str, re.Pattern] = {
    "products": re.compile(
        r"(?i)\b(products?|items?|inventory|stock|catalog|merchandise|sku)\b"
    ),
    "customers": re.compile(
        r"(?i)\b(customers?|clients?|buyers?|accounts?|users?)\b"
    ),
    "orders": re.compile(
        r"(?i)\b(orders?|purchases?|transactions?|bookings?|sales)\b"
    ),
    "sales_reps": re.compile(
        r"(?i)\b(sales?\s*reps?|representatives?|agents?|salespeople|"
        r"salesperson|account\s*managers?)\b"
    ),
    "regions": re.compile(
        r"(?i)\b(regions?|territories?|areas?|markets?|geograph(y|ies|ical))\b"
    ),
    "revenue": re.compile(
        r"(?i)\b(revenue|income|earnings|turnover|gross|net\s*sales)\b"
    ),
    "profit": re.compile(
        r"(?i)\b(profits?|margins?|markup|cost|expenses?)\b"
    ),
    "discounts": re.compile(
        r"(?i)\b(discounts?|promotions?|deals?|offers?|coupon)\b"
    ),
}

# Time reference patterns
_TIME_PATTERNS = re.compile(
    r"(?i)\b(today|yesterday|this\s+(week|month|quarter|year)|"
    r"last\s+(week|month|quarter|year|(\d+)\s+days?)|"
    r"past\s+(\d+)\s+(days?|weeks?|months?)|"
    r"since\s+\w+|between\s+\w+\s+and\s+\w+|"
    r"in\s+(january|february|march|april|may|june|july|"
    r"august|september|october|november|december|"
    r"jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec|"
    r"\d{4}))\b"
)

# Status patterns
_STATUS_PATTERNS = re.compile(
    r"(?i)\b(completed?|pending|cancelled?|refunded?|active|inactive)\b"
)


# ─── LLM Classification Prompt ─────────────────────────────────

_CLASSIFICATION_SYSTEM_PROMPT = """You are an intent classifier for a sales database query system.

Classify the user's message into one of these intents:
- "data": The user wants to query data from the database (numbers, lists, aggregations, comparisons)
- "chat": The user is asking a general question, requesting explanation, or having a conversation about the system/domain
- "clarification": The user's request is too ambiguous to determine — you need more information

Return a JSON object with:
{
    "intent": "data" | "chat" | "clarification",
    "confidence": 0.0 to 1.0,
    "reasoning": "brief explanation",
    "clarification_question": "question to ask if intent is clarification, null otherwise"
}

Examples:
User: "How many orders did we get last month?"
→ {"intent": "data", "confidence": 0.95, "reasoning": "Clear data request with time filter", "clarification_question": null}

User: "What does customer segment mean?"
→ {"intent": "chat", "confidence": 0.9, "reasoning": "Asking for definition, not data", "clarification_question": null}

User: "Show me the thing from yesterday"
→ {"intent": "clarification", "confidence": 0.3, "reasoning": "Ambiguous reference - unclear what 'the thing' refers to", "clarification_question": "Could you clarify what specific data you'd like to see from yesterday? For example, orders, revenue, or customer activity?"}

User: "Top 5"
→ {"intent": "clarification", "confidence": 0.2, "reasoning": "Incomplete query - top 5 of what?", "clarification_question": "Top 5 of what? For example, top 5 products by revenue, top 5 customers by orders, etc.?"}
"""


class IntentDetector:
    """
    5-stage intent detection pipeline.

    Analyzes user messages to determine intent (data query vs. chat
    vs. needs clarification), resolves domain entities, and detects
    follow-up responses.
    """

    def __init__(self, llm: LLMProvider):
        self._llm = llm

    def detect(
        self,
        user_message: str,
        conversation_history: list[dict] | None = None,
        last_offered_action: str | None = None,
    ) -> IntentResult:
        """
        Run the full 5-stage intent detection pipeline.

        Args:
            user_message: The user's current message.
            conversation_history: Previous messages for context.
            last_offered_action: Action offered in the last assistant
                message (e.g., "export", "details") for follow-up detection.

        Returns:
            IntentResult with classified intent and metadata.
        """
        history = conversation_history or []

        # ─── Stage 0: Conversation State Check ─────────────────
        followup_result = self._stage0_conversation_state(
            user_message, last_offered_action
        )
        if followup_result is not None:
            return followup_result

        # ─── Stage 1: Domain Entity Resolution ─────────────────
        entities = self._stage1_entity_resolution(user_message)

        # ─── Stage 2: LLM Semantic Classification ──────────────
        classification = self._stage2_llm_classification(
            user_message, history, entities
        )

        # ─── Stage 3: Ambiguity Detection ──────────────────────
        result = self._stage3_ambiguity_detection(
            user_message, classification, entities
        )

        # ─── Stage 4: Final Output ─────────────────────────────
        return self._stage4_build_result(
            user_message, result, entities, classification
        )

    # ─── Stage 0: Conversation State ─────────────────────────

    def _stage0_conversation_state(
        self,
        message: str,
        last_offered_action: str | None,
    ) -> IntentResult | None:
        """
        Detect follow-up responses like 'yes', 'no', 'ok'.

        Returns an IntentResult if the message is a follow-up,
        or None if it's a new query.
        """
        stripped = message.strip()

        if _AFFIRMATIVE_PATTERNS.match(stripped):
            # Map to the previously offered action
            if last_offered_action == "details":
                return IntentResult(
                    intent="data",
                    confidence=0.9,
                    is_followup=True,
                    original_query=message,
                    enriched_query=message,
                    metadata={"followup_type": "affirmative", "action": "details"},
                )
            elif last_offered_action == "export":
                return IntentResult(
                    intent="data",
                    confidence=0.9,
                    is_followup=True,
                    original_query=message,
                    enriched_query=message,
                    metadata={"followup_type": "affirmative", "action": "export"},
                )
            else:
                # Generic affirmative without prior context — ask for clarification
                return IntentResult(
                    intent="clarification",
                    confidence=0.3,
                    is_followup=True,
                    original_query=message,
                    enriched_query=message,
                    clarification=(
                        "I'm not sure what you're referring to. "
                        "Could you ask a specific question?"
                    ),
                )

        if _NEGATIVE_PATTERNS.match(stripped):
            return IntentResult(
                intent="chat",
                confidence=0.9,
                is_followup=True,
                original_query=message,
                enriched_query=message,
                metadata={"followup_type": "negative"},
            )

        return None  # Not a follow-up

    # ─── Stage 1: Domain Entity Resolution ───────────────────

    def _stage1_entity_resolution(
        self, message: str
    ) -> dict:
        """
        Extract domain entities, time references, and status filters.

        Returns a dict with detected entities and metadata.
        """
        detected_entities = []
        for entity_name, pattern in _ENTITY_PATTERNS.items():
            if pattern.search(message):
                detected_entities.append(entity_name)

        # Time references
        time_refs = _TIME_PATTERNS.findall(message)

        # Status references
        status_refs = _STATUS_PATTERNS.findall(message)

        return {
            "entities": detected_entities,
            "primary_entity": detected_entities[0] if detected_entities else None,
            "time_references": [t[0] if isinstance(t, tuple) else t for t in time_refs],
            "status_filters": status_refs,
            "has_numeric_request": bool(
                re.search(
                    r"(?i)\b(how many|count|total|sum|average|avg|max|min|"
                    r"number of|percentage|percent|ratio|top\s+\d+|bottom\s+\d+)\b",
                    message,
                )
            ),
        }

    # ─── Stage 2: LLM Semantic Classification ────────────────

    def _stage2_llm_classification(
        self,
        message: str,
        history: list[dict],
        entities: dict,
    ) -> dict:
        """
        Use the LLM to semantically classify the intent.

        Provides conversation history and extracted entities as context.
        """
        # Build context from recent history
        history_context = ""
        if history:
            recent = history[-6:]  # Last 3 exchanges
            history_lines = []
            for msg in recent:
                role = msg.get("role", "unknown")
                content = msg.get("content", "")[:200]  # Truncate long messages
                history_lines.append(f"{role}: {content}")
            history_context = (
                "\nRecent conversation:\n" + "\n".join(history_lines)
            )

        # Build entity context
        entity_context = ""
        if entities["entities"]:
            entity_context = (
                f"\nDetected domain entities: {', '.join(entities['entities'])}"
            )

        user_prompt = (
            f"User message: \"{message}\""
            f"{history_context}"
            f"{entity_context}"
            f"\n\nClassify this message."
        )

        try:
            result = self._llm.chat_completion_json(
                messages=[
                    {"role": "system", "content": _CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=300,
            )
            return {
                "intent": result.get("intent", "clarification"),
                "confidence": float(result.get("confidence", 0.5)),
                "reasoning": result.get("reasoning", ""),
                "clarification_question": result.get("clarification_question"),
            }
        except Exception as e:
            # Fallback: use heuristics if LLM fails
            return self._fallback_classification(message, entities)

    # ─── Stage 3: Ambiguity Detection ────────────────────────

    def _stage3_ambiguity_detection(
        self,
        message: str,
        classification: dict,
        entities: dict,
    ) -> dict:
        """
        Check for ambiguity in the classification.

        If confidence is low or the query is too vague, switch to
        clarification intent.
        """
        intent = classification["intent"]
        confidence = classification["confidence"]
        clarification = classification.get("clarification_question")

        # Low confidence → request clarification
        if confidence < 0.5 and intent != "clarification":
            return {
                **classification,
                "intent": "clarification",
                "clarification_question": (
                    clarification
                    or "I'm not entirely sure what you're asking. "
                    "Could you rephrase or provide more details?"
                ),
            }

        # Very short messages without entities are ambiguous
        words = message.strip().split()
        if len(words) <= 2 and not entities["entities"]:
            return {
                **classification,
                "intent": "clarification",
                "confidence": min(confidence, 0.4),
                "clarification_question": (
                    clarification
                    or "Your question is a bit brief. Could you provide "
                    "more details about what you'd like to know?"
                ),
            }

        return classification

    # ─── Stage 4: Final Output ───────────────────────────────

    def _stage4_build_result(
        self,
        message: str,
        classification: dict,
        entities: dict,
        raw_classification: dict,
    ) -> IntentResult:
        """Build the final structured IntentResult."""
        enriched = message
        if entities["primary_entity"]:
            enriched = f"[Entity: {entities['primary_entity']}] {message}"

        return IntentResult(
            intent=classification["intent"],
            entity=entities["primary_entity"],
            confidence=classification["confidence"],
            is_followup=False,
            original_query=message,
            enriched_query=enriched,
            clarification=classification.get("clarification_question"),
            metadata={
                "entities": entities["entities"],
                "time_references": entities["time_references"],
                "status_filters": entities["status_filters"],
                "has_numeric_request": entities["has_numeric_request"],
                "reasoning": classification.get("reasoning", ""),
            },
        )

    # ─── Fallback Classification ─────────────────────────────

    @staticmethod
    def _fallback_classification(
        message: str, entities: dict
    ) -> dict:
        """
        Rule-based fallback when LLM classification fails.

        Uses entity detection and keyword heuristics.
        """
        msg_lower = message.lower()

        # Strong data indicators
        data_keywords = [
            "how many", "count", "total", "sum", "average", "show",
            "list", "find", "get", "which", "what is the", "top",
            "bottom", "most", "least", "highest", "lowest", "compare",
            "between", "greater", "less than", "more than",
        ]

        # Strong chat indicators
        chat_keywords = [
            "what does", "what is", "explain", "help", "how does",
            "define", "meaning", "why", "tell me about", "describe",
            "who are you", "can you",
        ]

        data_score = sum(1 for kw in data_keywords if kw in msg_lower)
        chat_score = sum(1 for kw in chat_keywords if kw in msg_lower)

        # Entity presence boosts data score
        if entities["entities"]:
            data_score += len(entities["entities"])
        if entities["has_numeric_request"]:
            data_score += 2

        if data_score > chat_score:
            return {
                "intent": "data",
                "confidence": min(0.7, 0.4 + data_score * 0.1),
                "reasoning": "Fallback: data keywords detected",
                "clarification_question": None,
            }
        elif chat_score > data_score:
            return {
                "intent": "chat",
                "confidence": min(0.7, 0.4 + chat_score * 0.1),
                "reasoning": "Fallback: chat keywords detected",
                "clarification_question": None,
            }
        else:
            return {
                "intent": "clarification",
                "confidence": 0.3,
                "reasoning": "Fallback: unable to determine intent",
                "clarification_question": (
                    "I'm not sure if you're asking for data or information. "
                    "Could you rephrase your question?"
                ),
            }

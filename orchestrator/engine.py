"""
Orchestration Engine — The heart of the Text-to-SQL system.

Initializes all components and routes user messages through the
complete pipeline: Security → Intent Detection → Handler Dispatch
→ Conversation Storage → Response.
"""

from dataclasses import dataclass, field
from datetime import datetime

from config import settings
from llm import get_llm_provider
from llm.base import LLMProvider
from rag.embeddings import EmbeddingService
from rag.schema_rag import SchemaRAG
from rag.knowledge_rag import KnowledgeRAG
from security.input_sanitizer import sanitize_input
from security.rbac import RBACManager
from intent.detector import IntentDetector, IntentResult
from sql_agent.agent import SQLAgent
from handlers.chat_handler import ChatHandler
from handlers.data_handler import DataHandler, DataHandlerResult
from conversation.models import Message
from conversation.store import ConversationStore


@dataclass
class OrchestratorResponse:
    """Complete response from the orchestration engine."""
    response_text: str = ""
    intent: str = ""
    confidence: float = 0.0
    sql: str = ""
    data: list[list] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    is_error: bool = False
    is_clarification: bool = False
    metadata: dict = field(default_factory=dict)


class OrchestratorEngine:
    """
    Main orchestration engine for the Text-to-SQL system.

    Wires together all components and routes messages through:
    1. Security check (input sanitization)
    2. Conversation history loading
    3. Intent detection (5-stage pipeline)
    4. Handler dispatch (chat / data / clarification)
    5. Conversation storage
    6. Response formatting
    """

    def __init__(self):
        """Initialize all system components."""
        print("  ⏳ Initializing system components...")

        # 1. LLM Provider
        self._llm: LLMProvider = get_llm_provider()
        print(f"    ✓ LLM Provider: {self._llm.get_provider_name()}")

        # 2. Embedding Service
        self._embeddings = EmbeddingService()

        # 3. Schema RAG
        self._schema_rag = SchemaRAG(embedding_service=self._embeddings)
        self._schema_rag.initialize()
        print(
            f"    ✓ Schema RAG: "
            f"{len(self._schema_rag.get_table_names())} tables indexed"
        )

        # 4. Knowledge RAG
        self._knowledge_rag = KnowledgeRAG(embedding_service=self._embeddings)
        self._knowledge_rag.initialize()
        print("    ✓ Knowledge RAG: initialized")

        # 5. RBAC Manager
        self._rbac = RBACManager()
        print(
            f"    ✓ RBAC: {len(self._rbac.list_roles())} roles loaded "
            f"(current: {settings.USER_ROLE})"
        )

        # 6. Intent Detector
        self._intent_detector = IntentDetector(self._llm)
        print("    ✓ Intent Detector: 5-stage pipeline ready")

        # 7. SQL Agent
        self._sql_agent = SQLAgent(
            llm=self._llm,
            schema_rag=self._schema_rag,
            knowledge_rag=self._knowledge_rag,
            rbac=self._rbac,
        )
        print("    ✓ SQL Agent: ready")

        # 8. Handlers
        self._chat_handler = ChatHandler(self._llm, self._knowledge_rag)
        self._data_handler = DataHandler(self._llm, self._sql_agent)
        print("    ✓ Handlers: chat, data")

        # 9. Conversation Store
        self._conversation_store = ConversationStore()
        print("    ✓ Conversation Store: PostgreSQL connected")

        print("  ✅ All components initialized!\n")

    def create_session(self) -> str:
        """Create a new conversation session."""
        return self._conversation_store.create_session()

    def resume_session(self, session_id: str) -> bool:
        """Check if a session exists and can be resumed."""
        state = self._conversation_store.get_session_state(session_id)
        return bool(state)

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """List recent conversation sessions."""
        return self._conversation_store.list_sessions(limit)

    def process_message(
        self,
        user_input: str,
        session_id: str,
    ) -> OrchestratorResponse:
        """
        Process a user message through the complete pipeline.

        Args:
            user_input: Raw user input text.
            session_id: Current conversation session ID.

        Returns:
            OrchestratorResponse with the complete response.
        """
        # ─── Step 1: Security Check ────────────────────────
        sanitization = sanitize_input(user_input)
        if not sanitization.is_safe:
            return OrchestratorResponse(
                response_text=(
                    f"🚫 Security check failed: {sanitization.reason}\n"
                    f"Please rephrase your question."
                ),
                is_error=True,
                metadata={"security_reason": sanitization.reason},
            )

        clean_input = sanitization.sanitized_text

        # ─── Step 2: Save User Message ─────────────────────
        user_message = Message(
            role="user",
            content=clean_input,
            timestamp=datetime.now(),
        )
        self._conversation_store.add_message(session_id, user_message)

        # ─── Step 3: Load Conversation Context ─────────────
        history = self._conversation_store.get_history(session_id, limit=10)
        history_dicts = [
            {"role": m.role, "content": m.content} for m in history
        ]

        session_state = self._conversation_store.get_session_state(session_id)
        last_offered_action = session_state.get("last_offered_action")

        # ─── Step 4: Intent Detection ──────────────────────
        intent_result: IntentResult = self._intent_detector.detect(
            user_message=clean_input,
            conversation_history=history_dicts[:-1],  # Exclude current
            last_offered_action=last_offered_action,
        )

        # ─── Step 5: Route to Handler ──────────────────────
        response = self._route_to_handler(
            intent_result=intent_result,
            clean_input=clean_input,
            history_dicts=history_dicts,
            session_id=session_id,
        )

        # ─── Step 6: Save Assistant Response ───────────────
        assistant_message = Message(
            role="assistant",
            content=response.response_text,
            timestamp=datetime.now(),
            metadata={
                "intent": response.intent,
                "confidence": response.confidence,
                "sql": response.sql,
                "row_count": response.row_count,
            },
        )
        self._conversation_store.add_message(session_id, assistant_message)

        # Update session state
        offered_action = None
        if response.row_count > 0:
            offered_action = "details"
        self._conversation_store.update_session_state(
            session_id,
            last_offered_action=offered_action,
            last_sql=response.sql if response.sql else None,
        )

        return response

    def _route_to_handler(
        self,
        intent_result: IntentResult,
        clean_input: str,
        history_dicts: list[dict],
        session_id: str,
    ) -> OrchestratorResponse:
        """Route the classified intent to the appropriate handler."""

        intent = intent_result.intent

        # ─── Clarification ─────────────────────────────────
        if intent == "clarification":
            return OrchestratorResponse(
                response_text=intent_result.clarification or (
                    "Could you please clarify your question? "
                    "I need more details to help you."
                ),
                intent="clarification",
                confidence=intent_result.confidence,
                is_clarification=True,
            )

        # ─── Chat Intent ──────────────────────────────────
        if intent == "chat":
            # Handle negative follow-ups
            if intent_result.metadata.get("followup_type") == "negative":
                response_text = "Okay, no problem! Let me know if you have another question."
            else:
                response_text = self._chat_handler.handle(
                    query=clean_input,
                    conversation_history=history_dicts,
                )

            return OrchestratorResponse(
                response_text=response_text,
                intent="chat",
                confidence=intent_result.confidence,
            )

        # ─── Data Intent ──────────────────────────────────
        if intent == "data":
            # Build conversation context for SQL agent
            context_parts = []
            for msg in history_dicts[-4:]:
                context_parts.append(f"{msg['role']}: {msg['content'][:200]}")
            conversation_context = "\n".join(context_parts)

            data_result: DataHandlerResult = self._data_handler.handle(
                query=intent_result.enriched_query or clean_input,
                role=settings.USER_ROLE,
                conversation_context=conversation_context,
            )

            if data_result.needs_clarification:
                return OrchestratorResponse(
                    response_text=data_result.clarification,
                    intent="clarification",
                    confidence=intent_result.confidence,
                    is_clarification=True,
                )

            return OrchestratorResponse(
                response_text=data_result.response_text,
                intent="data",
                confidence=intent_result.confidence,
                sql=data_result.sql,
                data=data_result.data,
                columns=data_result.columns,
                row_count=data_result.row_count,
                is_error=not data_result.success,
            )

        # ─── Unknown Intent (shouldn't happen) ────────────
        return OrchestratorResponse(
            response_text="I'm not sure how to handle that. Could you try rephrasing?",
            intent="unknown",
            is_error=True,
        )

    def close(self) -> None:
        """Clean up resources."""
        self._conversation_store.close()

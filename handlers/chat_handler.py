"""
Chat Handler — Handles conversational intents.

Answers general questions using the Knowledge RAG for domain-specific
grounding, or falls back to the LLM's general knowledge.
"""

from llm.base import LLMProvider
from rag.knowledge_rag import KnowledgeRAG


_CHAT_SYSTEM_PROMPT = """You are a helpful assistant for a sales management database system.

You help users understand:
- How the system works
- Business terms and definitions
- Calculation methodologies
- Available data and schema structure

Guidelines:
- Be concise but thorough
- Use the provided knowledge base context when available
- If you don't know something specific to the system, say so
- Don't make up data or statistics — only reference what's in the knowledge base
- When relevant, suggest data queries the user could ask
"""


class ChatHandler:
    """
    Handles conversational (non-data-query) intents.

    Retrieves relevant knowledge from the Knowledge RAG and generates
    responses grounded in domain-specific documentation.
    """

    def __init__(self, llm: LLMProvider, knowledge_rag: KnowledgeRAG):
        self._llm = llm
        self._knowledge_rag = knowledge_rag

    def handle(
        self,
        query: str,
        conversation_history: list[dict] | None = None,
    ) -> str:
        """
        Generate a conversational response.

        Args:
            query: The user's question.
            conversation_history: Recent messages for context.

        Returns:
            Natural language response string.
        """
        # Retrieve relevant knowledge
        knowledge_sections = self._knowledge_rag.retrieve_knowledge(
            query, top_k=3
        )

        # Build messages
        messages: list[dict] = [
            {"role": "system", "content": _CHAT_SYSTEM_PROMPT}
        ]

        # Add knowledge context if found
        if knowledge_sections:
            knowledge_text = "\n\n".join(knowledge_sections)
            messages.append({
                "role": "system",
                "content": (
                    f"--- KNOWLEDGE BASE CONTEXT ---\n{knowledge_text}\n"
                    f"--- END KNOWLEDGE BASE ---\n\n"
                    f"Use this context to answer the user's question. "
                    f"If the answer is in the context, reference it. "
                    f"If not, use your general knowledge."
                ),
            })

        # Add conversation history for context
        if conversation_history:
            for msg in conversation_history[-6:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"][:500],
                })

        # Add current query
        messages.append({"role": "user", "content": query})

        # Generate response
        response = self._llm.chat_completion(
            messages=messages,
            temperature=0.3,
            max_tokens=1000,
        )

        return response

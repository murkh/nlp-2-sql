"""
Conversation data models.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Message:
    """A single message in a conversation."""
    role: str           # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict = field(default_factory=dict)
    # metadata can include: intent, sql, row_count, confidence, etc.


@dataclass
class ConversationSession:
    """A conversation session with message history."""
    session_id: str
    created_at: datetime = field(default_factory=datetime.now)
    messages: list[Message] = field(default_factory=list)
    last_offered_action: str | None = None
    last_sql: str | None = None

    def add_message(self, message: Message) -> None:
        """Add a message to the conversation."""
        self.messages.append(message)

    def get_history_dicts(self, limit: int = 20) -> list[dict]:
        """
        Get recent messages as dicts suitable for LLM context.

        Returns list of {"role": ..., "content": ...} dicts.
        """
        recent = self.messages[-limit:] if limit else self.messages
        return [
            {"role": msg.role, "content": msg.content}
            for msg in recent
        ]

    def get_last_user_message(self) -> Message | None:
        """Get the last user message."""
        for msg in reversed(self.messages):
            if msg.role == "user":
                return msg
        return None

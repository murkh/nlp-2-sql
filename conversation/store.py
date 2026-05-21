"""
PostgreSQL-backed conversation store.

Persists conversation sessions and messages in PostgreSQL for
long-term history, follow-up detection, and analytics.
"""

import json
import uuid
from datetime import datetime

import psycopg2
import psycopg2.extras

from config import settings
from conversation.models import Message, ConversationSession


class ConversationStore:
    """
    PostgreSQL-backed store for conversation history.

    Auto-creates tables on first use. Each session gets a unique ID,
    and all messages are stored with metadata (intent, SQL, etc.).
    """

    def __init__(self, connection_url: str | None = None):
        self._conn_url = connection_url or settings.POSTGRES_URL
        self._conn = None
        self._ensure_tables()

    def _get_connection(self):
        """Get or create a PostgreSQL connection."""
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self._conn_url)
            self._conn.autocommit = True
        return self._conn

    def _ensure_tables(self) -> None:
        """Create tables if they don't exist."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    last_offered_action TEXT,
                    last_sql TEXT,
                    message_count INTEGER DEFAULT 0
                )
            """)

            cur.execute("""
                CREATE TABLE IF NOT EXISTS conversation_messages (
                    id SERIAL PRIMARY KEY,
                    session_id TEXT NOT NULL REFERENCES conversation_sessions(session_id),
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    timestamp TIMESTAMP NOT NULL DEFAULT NOW(),
                    metadata JSONB DEFAULT '{}'::jsonb,
                    CONSTRAINT fk_session
                        FOREIGN KEY (session_id)
                        REFERENCES conversation_sessions(session_id)
                        ON DELETE CASCADE
                )
            """)

            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_session
                ON conversation_messages(session_id, timestamp)
            """)

    def create_session(self) -> str:
        """
        Create a new conversation session.

        Returns:
            The new session's unique ID.
        """
        session_id = str(uuid.uuid4())[:8]
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_sessions (session_id, created_at) "
                "VALUES (%s, %s)",
                (session_id, datetime.now()),
            )
        return session_id

    def add_message(
        self,
        session_id: str,
        message: Message,
    ) -> None:
        """Store a message in the conversation history."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO conversation_messages "
                "(session_id, role, content, timestamp, metadata) "
                "VALUES (%s, %s, %s, %s, %s)",
                (
                    session_id,
                    message.role,
                    message.content,
                    message.timestamp,
                    json.dumps(message.metadata),
                ),
            )
            cur.execute(
                "UPDATE conversation_sessions "
                "SET message_count = message_count + 1 "
                "WHERE session_id = %s",
                (session_id,),
            )

    def get_history(
        self, session_id: str, limit: int = 20
    ) -> list[Message]:
        """
        Retrieve recent messages for a session.

        Args:
            session_id: The conversation session ID.
            limit: Maximum number of messages to return.

        Returns:
            List of Message objects, oldest first.
        """
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT role, content, timestamp, metadata "
                "FROM conversation_messages "
                "WHERE session_id = %s "
                "ORDER BY timestamp DESC "
                "LIMIT %s",
                (session_id, limit),
            )
            rows = cur.fetchall()

        messages = []
        for role, content, timestamp, metadata in reversed(rows):
            meta = metadata if isinstance(metadata, dict) else json.loads(metadata or "{}")
            messages.append(
                Message(
                    role=role,
                    content=content,
                    timestamp=timestamp,
                    metadata=meta,
                )
            )
        return messages

    def update_session_state(
        self,
        session_id: str,
        last_offered_action: str | None = None,
        last_sql: str | None = None,
    ) -> None:
        """Update session-level state (for follow-up detection)."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            updates = []
            params = []
            if last_offered_action is not None:
                updates.append("last_offered_action = %s")
                params.append(last_offered_action)
            if last_sql is not None:
                updates.append("last_sql = %s")
                params.append(last_sql)

            if updates:
                params.append(session_id)
                cur.execute(
                    f"UPDATE conversation_sessions SET {', '.join(updates)} "
                    f"WHERE session_id = %s",
                    params,
                )

    def get_session_state(self, session_id: str) -> dict:
        """Get session-level state."""
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT last_offered_action, last_sql, message_count, created_at "
                "FROM conversation_sessions WHERE session_id = %s",
                (session_id,),
            )
            row = cur.fetchone()

        if not row:
            return {}

        return {
            "last_offered_action": row[0],
            "last_sql": row[1],
            "message_count": row[2],
            "created_at": row[3],
        }

    def get_last_sql(self, session_id: str) -> str | None:
        """Get the last SQL query from a session."""
        state = self.get_session_state(session_id)
        return state.get("last_sql")

    def list_sessions(self, limit: int = 10) -> list[dict]:
        """
        List recent conversation sessions.

        Returns:
            List of session dicts with id, created_at, and message_count.
        """
        conn = self._get_connection()
        with conn.cursor() as cur:
            cur.execute(
                "SELECT session_id, created_at, message_count "
                "FROM conversation_sessions "
                "ORDER BY created_at DESC "
                "LIMIT %s",
                (limit,),
            )
            rows = cur.fetchall()

        return [
            {
                "session_id": row[0],
                "created_at": row[1],
                "message_count": row[2],
            }
            for row in rows
        ]

    def close(self) -> None:
        """Close the database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()

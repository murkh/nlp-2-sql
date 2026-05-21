"""
SQL Agent — Text-to-SQL generation, validation, and execution.

Implements a 10-step pipeline:
  1. Receive enriched query
  2. RBAC permission setup
  3. Schema RAG retrieval
  4. Knowledge RAG retrieval
  5. SQL generation prompt construction
  6. LLM generates SQL
  7. SQL validation
  8. RBAC enforcement on generated SQL
  9. Execute SQL against read-only DB
  10. Format and return results

Includes self-correction on failure (max 2 retries).
"""

import sqlite3
from dataclasses import dataclass, field

from llm.base import LLMProvider
from rag.schema_rag import SchemaRAG
from rag.knowledge_rag import KnowledgeRAG
from security.sql_validator import validate_sql, extract_table_names, extract_column_names
from security.rbac import RBACManager
from config import settings


@dataclass
class SQLAgentResult:
    """Result of the SQL agent pipeline."""
    success: bool
    sql: str = ""
    data: list[list] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    error: str = ""
    needs_clarification: bool = False
    clarification: str = ""


# ─── SQL Generation Prompt ──────────────────────────────────────

_SQL_SYSTEM_PROMPT = """You are an expert SQL query generator for a SQLite sales management database.

CRITICAL RULES:
1. Generate ONLY valid SQLite SELECT queries
2. NEVER use INSERT, UPDATE, DELETE, DROP, ALTER, or any data-modifying statements
3. Always use proper table aliases for clarity
4. Use single quotes for string literals
5. For date operations, use SQLite date functions: date(), strftime(), etc.
6. Always include ORDER BY for sorted results
7. Use LIMIT to restrict output rows when appropriate
8. Handle NULL values properly with COALESCE or IS NULL checks
9. For aggregations, always include GROUP BY
10. Use ROUND() for decimal values to 2 decimal places

When generating SQL:
- Refer to the provided schema to know exact table and column names
- Use the provided business rules for correct calculations
- Only query tables and columns listed in the schema
- For revenue calculations, use order_items.line_total and filter by orders.status = 'completed'
- For profit calculations, use products.unit_price - products.cost_price

Respond with ONLY a JSON object:
{
    "sql": "YOUR SQL QUERY HERE",
    "explanation": "Brief explanation of what this query does",
    "tables_used": ["table1", "table2"]
}
"""


class SQLAgent:
    """
    Text-to-SQL agent with RAG context, validation, and self-correction.
    """

    MAX_RETRIES = 2

    def __init__(
        self,
        llm: LLMProvider,
        schema_rag: SchemaRAG,
        knowledge_rag: KnowledgeRAG,
        rbac: RBACManager,
        db_path: str | None = None,
    ):
        self._llm = llm
        self._schema_rag = schema_rag
        self._knowledge_rag = knowledge_rag
        self._rbac = rbac
        self._db_path = db_path or settings.SALES_DB_PATH

    def generate_and_execute(
        self,
        query: str,
        role: str | None = None,
        conversation_context: str = "",
    ) -> SQLAgentResult:
        """
        Full 10-step Text-to-SQL pipeline.

        Args:
            query: The enriched natural language query.
            role: User's RBAC role (defaults to settings.USER_ROLE).
            conversation_context: Recent conversation for context.

        Returns:
            SQLAgentResult with query results or error details.
        """
        role = role or settings.USER_ROLE

        # ─── Step 1: Receive query ─────────────────────────
        # (already received as parameter)

        # ─── Step 2: RBAC permission setup ─────────────────
        allowed_tables = self._rbac.get_allowed_tables(role)
        denied_columns = self._rbac.get_denied_columns(role)

        # ─── Step 3: Schema RAG retrieval ──────────────────
        relevant_schemas = self._schema_rag.retrieve_relevant_schema(
            query, top_k=6
        )
        schema_context = "\n\n".join(relevant_schemas)

        # Filter schema for role (remove denied columns)
        if denied_columns:
            for col in denied_columns:
                # Remove lines mentioning denied columns from schema context
                lines = schema_context.split("\n")
                filtered = [
                    line for line in lines
                    if col.split(".")[-1].lower() not in line.lower()
                    or "- " not in line  # Only filter column lines
                ]
                schema_context = "\n".join(filtered)

        # ─── Step 4: Knowledge RAG retrieval ───────────────
        knowledge_context = self._knowledge_rag.retrieve_knowledge(
            query, top_k=3
        )
        knowledge_text = "\n\n".join(knowledge_context) if knowledge_context else ""

        # ─── Steps 5-8: Generate, validate, enforce (with retries) ──
        last_error = ""
        for attempt in range(self.MAX_RETRIES + 1):
            result = self._attempt_generation(
                query=query,
                schema_context=schema_context,
                knowledge_text=knowledge_text,
                allowed_tables=allowed_tables,
                denied_columns=denied_columns,
                role=role,
                conversation_context=conversation_context,
                previous_error=last_error,
                attempt=attempt,
            )

            if result.success or result.needs_clarification:
                return result

            last_error = result.error

        # All retries exhausted
        return SQLAgentResult(
            success=False,
            error=f"Failed after {self.MAX_RETRIES + 1} attempts. Last error: {last_error}",
        )

    def _attempt_generation(
        self,
        query: str,
        schema_context: str,
        knowledge_text: str,
        allowed_tables: list[str] | None,
        denied_columns: list[str],
        role: str,
        conversation_context: str,
        previous_error: str,
        attempt: int,
    ) -> SQLAgentResult:
        """Single attempt at SQL generation + validation + execution."""

        # ─── Step 5: Build prompt ──────────────────────────
        user_prompt = self._build_prompt(
            query=query,
            schema_context=schema_context,
            knowledge_text=knowledge_text,
            role=role,
            conversation_context=conversation_context,
            previous_error=previous_error,
            attempt=attempt,
        )

        # ─── Step 6: LLM generates SQL ────────────────────
        try:
            llm_response = self._llm.chat_completion_json(
                messages=[
                    {"role": "system", "content": _SQL_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=1000,
            )
        except Exception as e:
            return SQLAgentResult(
                success=False,
                error=f"LLM generation failed: {e}",
            )

        sql = llm_response.get("sql", "").strip()
        explanation = llm_response.get("explanation", "")

        if not sql:
            return SQLAgentResult(
                success=False,
                error="LLM returned empty SQL",
            )

        # ─── Step 7: SQL validation ────────────────────────
        validation = validate_sql(sql, allowed_tables=allowed_tables)
        if not validation.is_valid:
            return SQLAgentResult(
                success=False,
                sql=sql,
                error=f"SQL validation failed: {validation.reason}",
            )

        sql = validation.cleaned_sql

        # ─── Step 8: RBAC enforcement ──────────────────────
        referenced_tables = extract_table_names(sql)
        referenced_columns = extract_column_names(sql)

        access_check = self._rbac.check_access(
            role, referenced_tables, referenced_columns
        )
        if not access_check.allowed:
            return SQLAgentResult(
                success=False,
                sql=sql,
                error=f"Access denied: {access_check.reason}",
            )

        # Check aggregation requirement for viewer role
        if self._rbac.requires_aggregation(role):
            if not self._has_aggregation(sql):
                return SQLAgentResult(
                    success=False,
                    sql=sql,
                    error=(
                        "Your role (viewer) requires aggregated queries. "
                        "Please ask for summaries, totals, or averages "
                        "instead of individual records."
                    ),
                )

        # ─── Step 9: Execute SQL ───────────────────────────
        try:
            columns, data = self._execute_query(sql)
        except Exception as e:
            return SQLAgentResult(
                success=False,
                sql=sql,
                error=f"Query execution failed: {e}",
            )

        # ─── Step 10: Format results ──────────────────────
        return SQLAgentResult(
            success=True,
            sql=sql,
            data=data,
            columns=columns,
            row_count=len(data),
        )

    def _build_prompt(
        self,
        query: str,
        schema_context: str,
        knowledge_text: str,
        role: str,
        conversation_context: str,
        previous_error: str,
        attempt: int,
    ) -> str:
        """Build the complete prompt for SQL generation."""
        parts = [f"User question: {query}"]

        parts.append(f"\n--- DATABASE SCHEMA ---\n{schema_context}")

        if knowledge_text:
            parts.append(f"\n--- BUSINESS RULES ---\n{knowledge_text}")

        if conversation_context:
            parts.append(
                f"\n--- CONVERSATION CONTEXT ---\n{conversation_context}"
            )

        parts.append(f"\nUser role: {role}")
        parts.append(
            f"\nMax results: {settings.MAX_QUERY_ROWS} rows"
        )

        if attempt > 0 and previous_error:
            parts.append(
                f"\n--- PREVIOUS ATTEMPT FAILED ---\n"
                f"Error: {previous_error}\n"
                f"Please fix the SQL query based on this error. "
                f"This is attempt {attempt + 1} of {self.MAX_RETRIES + 1}."
            )

        return "\n".join(parts)

    def _execute_query(self, sql: str) -> tuple[list[str], list[list]]:
        """
        Execute a SQL query against the read-only database.

        Returns (column_names, rows) tuple.
        """
        conn = sqlite3.connect(
            f"file:{self._db_path}?mode=ro",
            uri=True,
        )
        try:
            cursor = conn.cursor()
            cursor.execute(sql)

            # Get column names from cursor description
            columns = [desc[0] for desc in cursor.description or []]

            # Fetch with row limit
            rows = cursor.fetchmany(settings.MAX_QUERY_ROWS)
            data = [list(row) for row in rows]

            return columns, data
        finally:
            conn.close()

    @staticmethod
    def _has_aggregation(sql: str) -> bool:
        """Check if a SQL query contains aggregation functions."""
        import re
        agg_pattern = r"(?i)\b(COUNT|SUM|AVG|MIN|MAX|GROUP\s+BY)\b"
        return bool(re.search(agg_pattern, sql))

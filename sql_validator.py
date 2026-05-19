from __future__ import annotations
import sqlite3
import re
import logging


logger = logging.getLogger(__name__)


class SqlValidator:
    """Validates generated SQL queries against a SQLite database."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def validate(self, sql: str, preamble: list[str] = None) -> tuple[bool, str | None]:
        """
        Validate the SQL query by executing it under EXPLAIN in a temporary connection
        with the preamble executed first.

        Returns:
            tuple: (is_valid, error_message)
        """
        # Safety check: block destructive commands
        is_safe, safety_err = self._check_safety(sql)
        if not is_safe:
            return False, safety_err

        # Dry-run validation
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        try:
            # 1. Execute preamble (temp tables, inserts) to set up schema context
            if preamble:
                for stmt in preamble:
                    if stmt and stmt.strip():
                        cursor.execute(stmt)

            # 2. Run EXPLAIN on the generated SQL to check syntax/schema correctness
            explain_query = f"EXPLAIN {sql}"
            logger.debug(f"Dry-running validation: {explain_query[:120]}")
            cursor.execute(explain_query)
            cursor.fetchall()
            
            return True, None

        except sqlite3.Error as e:
            error_msg = str(e)
            logger.warning(f"SQL validation failed: {error_msg}")
            return False, error_msg
        finally:
            cursor.close()
            conn.close()

    def _check_safety(self, sql: str) -> tuple[bool, str | None]:
        """Verify that the generated SQL contains only safe, read-only statements."""
        sql_upper = sql.upper().strip()

        # Check for disallowed operations
        disallowed = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE", "REPLACE", "TRUNCATE"]
        for cmd in disallowed:
            # Match word boundary to avoid catching columns like "created_at" or "updated_by"
            pattern = rf"\b{cmd}\b"
            if re.search(pattern, sql_upper):
                return False, f"Disallowed destructive SQL operation: {cmd}"

        # Ensure it starts with SELECT or WITH
        if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
            return False, "SQL query must begin with SELECT or WITH"

        return True, None

"""
SQL query validation.

Validates generated SQL before execution to ensure it is safe:
- Only SELECT statements allowed
- No dangerous keywords
- Table/column existence checks
- Subquery depth limits
"""

import re
from dataclasses import dataclass

import sqlparse
from sqlparse.sql import Statement
from sqlparse.tokens import Keyword, DML


@dataclass
class ValidationResult:
    """Result of SQL validation."""
    is_valid: bool
    reason: str
    cleaned_sql: str


# Keywords that should never appear in generated queries
_FORBIDDEN_KEYWORDS = {
    "DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "CREATE",
    "TRUNCATE", "EXEC", "EXECUTE", "GRANT", "REVOKE",
    "REPLACE", "MERGE", "CALL", "ATTACH", "DETACH",
}

# Maximum allowed subquery nesting depth
_MAX_SUBQUERY_DEPTH = 3


def validate_sql(
    sql: str,
    allowed_tables: list[str] | None = None,
) -> ValidationResult:
    """
    Validate a SQL query for safety and correctness.

    Performs:
    1. Basic parsing via sqlparse
    2. Statement type check (SELECT only)
    3. Forbidden keyword scan
    4. Table existence check against allowed_tables
    5. Subquery depth check

    Args:
        sql: The SQL query string to validate.
        allowed_tables: Optional list of table names that may be queried.

    Returns:
        ValidationResult indicating whether the query is safe to execute.
    """
    if not sql or not sql.strip():
        return ValidationResult(
            is_valid=False,
            reason="Empty SQL query",
            cleaned_sql="",
        )

    # Clean and normalize
    cleaned = sql.strip().rstrip(";").strip()

    # 1. Parse with sqlparse
    try:
        parsed_statements = sqlparse.parse(cleaned)
    except Exception as e:
        return ValidationResult(
            is_valid=False,
            reason=f"SQL parsing error: {e}",
            cleaned_sql=cleaned,
        )

    if not parsed_statements:
        return ValidationResult(
            is_valid=False,
            reason="No valid SQL statements found",
            cleaned_sql=cleaned,
        )

    # 2. Only allow a single statement
    if len(parsed_statements) > 1:
        return ValidationResult(
            is_valid=False,
            reason="Multiple SQL statements not allowed (possible injection)",
            cleaned_sql=cleaned,
        )

    stmt: Statement = parsed_statements[0]

    # 3. Must be a SELECT statement
    stmt_type = stmt.get_type()
    if stmt_type != "SELECT":
        return ValidationResult(
            is_valid=False,
            reason=f"Only SELECT statements are allowed (got: {stmt_type or 'UNKNOWN'})",
            cleaned_sql=cleaned,
        )

    # 4. Scan for forbidden keywords
    upper_sql = cleaned.upper()
    for keyword in _FORBIDDEN_KEYWORDS:
        # Use word boundary to avoid false positives (e.g., "CREATED_AT")
        if re.search(rf"\b{keyword}\b", upper_sql):
            # Allow keywords that appear in string literals or column names
            # Simple heuristic: check if it's a standalone keyword
            pattern = rf"(?<!['\"])\b{keyword}\b(?!['\"])"
            if re.search(pattern, upper_sql):
                return ValidationResult(
                    is_valid=False,
                    reason=f"Forbidden keyword '{keyword}' detected in query",
                    cleaned_sql=cleaned,
                )

    # 5. Check subquery depth
    depth = _count_subquery_depth(cleaned)
    if depth > _MAX_SUBQUERY_DEPTH:
        return ValidationResult(
            is_valid=False,
            reason=(
                f"Subquery nesting depth ({depth}) exceeds maximum "
                f"({_MAX_SUBQUERY_DEPTH})"
            ),
            cleaned_sql=cleaned,
        )

    # 6. Check table names if allowlist provided
    if allowed_tables is not None:
        referenced_tables = extract_table_names(cleaned)
        disallowed = [
            t for t in referenced_tables
            if t.lower() not in {a.lower() for a in allowed_tables}
        ]
        if disallowed:
            return ValidationResult(
                is_valid=False,
                reason=(
                    f"Query references disallowed tables: "
                    f"{', '.join(disallowed)}"
                ),
                cleaned_sql=cleaned,
            )

    return ValidationResult(
        is_valid=True,
        reason="Query is valid and safe",
        cleaned_sql=cleaned,
    )


def extract_table_names(sql: str) -> list[str]:
    """
    Extract table names referenced in a SQL query.

    Uses regex-based extraction to find tables after FROM and JOIN clauses.
    """
    tables = set()

    # Match tables after FROM and JOIN (including LEFT/RIGHT/INNER/OUTER/CROSS)
    pattern = r"(?i)(?:FROM|JOIN)\s+([a-zA-Z_][a-zA-Z0-9_]*)"
    matches = re.findall(pattern, sql)
    tables.update(matches)

    return list(tables)


def extract_column_names(sql: str) -> list[str]:
    """
    Extract column names referenced in a SQL query.

    Extracts qualified (table.column) and unqualified column references.
    """
    columns = set()

    # Match table.column patterns
    pattern = r"([a-zA-Z_][a-zA-Z0-9_]*)\.([a-zA-Z_][a-zA-Z0-9_]*)"
    for table, col in re.findall(pattern, sql):
        columns.add(f"{table}.{col}")

    return list(columns)


def _count_subquery_depth(sql: str) -> int:
    """Count the maximum nesting depth of subqueries (parenthesized SELECTs)."""
    max_depth = 0
    current_depth = 0

    upper_sql = sql.upper()
    i = 0
    while i < len(upper_sql):
        if upper_sql[i] == "(":
            # Check if this is a subquery (SELECT follows)
            rest = upper_sql[i + 1:].lstrip()
            if rest.startswith("SELECT"):
                current_depth += 1
                max_depth = max(max_depth, current_depth)
        elif upper_sql[i] == ")":
            if current_depth > 0:
                current_depth -= 1
        i += 1

    return max_depth

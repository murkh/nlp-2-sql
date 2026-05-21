"""
Role-Based Access Control (RBAC).

Loads role definitions from rbac_config.yaml and enforces table/column
level access restrictions on generated SQL queries.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml

from config import settings


@dataclass
class AccessCheckResult:
    """Result of an RBAC access check."""
    allowed: bool
    denied_tables: list[str]
    denied_columns: list[str]
    reason: str


class RBACManager:
    """
    Manages role-based access control for SQL queries.

    Roles are defined in rbac_config.yaml with:
    - allowed_tables: "*" or list of table names
    - denied_columns: list of "table.column" patterns
    - require_aggregation: bool (viewer role)
    """

    def __init__(self, config_path: str | None = None):
        self._config_path = Path(config_path or settings.RBAC_CONFIG_PATH)
        self._roles: dict = {}
        self._load_config()

    def _load_config(self) -> None:
        """Load RBAC configuration from YAML file."""
        if not self._config_path.exists():
            # Default permissive config if file doesn't exist
            self._roles = {
                "admin": {
                    "description": "Full access",
                    "allowed_tables": "*",
                    "denied_columns": [],
                }
            }
            return

        with open(self._config_path, "r") as f:
            config = yaml.safe_load(f)

        self._roles = config.get("roles", {})

    def get_role_config(self, role: str) -> dict:
        """Get configuration for a specific role."""
        if role not in self._roles:
            raise ValueError(
                f"Unknown role '{role}'. "
                f"Available roles: {', '.join(self._roles.keys())}"
            )
        return self._roles[role]

    def check_access(
        self,
        role: str,
        tables: list[str],
        columns: list[str] | None = None,
    ) -> AccessCheckResult:
        """
        Check if a role has access to the specified tables and columns.

        Args:
            role: The user's role (e.g., 'analyst').
            tables: List of table names the query references.
            columns: Optional list of "table.column" strings.

        Returns:
            AccessCheckResult with details on allowed/denied resources.
        """
        config = self.get_role_config(role)

        denied_tables = []
        denied_columns = []

        # Check table access
        allowed_tables = config.get("allowed_tables", "*")
        if allowed_tables != "*":
            allowed_set = {t.lower() for t in allowed_tables}
            denied_tables = [
                t for t in tables if t.lower() not in allowed_set
            ]

        # Check column access
        denied_col_patterns = config.get("denied_columns", [])
        if columns and denied_col_patterns:
            denied_set = {c.lower() for c in denied_col_patterns}
            denied_columns = [
                c for c in columns if c.lower() in denied_set
            ]

        is_allowed = not denied_tables and not denied_columns

        reason = "Access granted"
        if denied_tables:
            reason = f"Access denied to tables: {', '.join(denied_tables)}"
        elif denied_columns:
            reason = f"Access denied to columns: {', '.join(denied_columns)}"

        return AccessCheckResult(
            allowed=is_allowed,
            denied_tables=denied_tables,
            denied_columns=denied_columns,
            reason=reason,
        )

    def get_allowed_tables(self, role: str) -> list[str] | None:
        """
        Get the list of tables a role can access.

        Returns None if the role has access to all tables ("*").
        """
        config = self.get_role_config(role)
        allowed = config.get("allowed_tables", "*")
        if allowed == "*":
            return None
        return list(allowed)

    def get_denied_columns(self, role: str) -> list[str]:
        """Get the list of denied columns for a role."""
        config = self.get_role_config(role)
        return config.get("denied_columns", [])

    def filter_schema_for_role(
        self, role: str, schema_texts: dict[str, str]
    ) -> dict[str, str]:
        """
        Filter schema descriptions to only include tables/columns
        accessible by the given role.

        Args:
            role: The user's role.
            schema_texts: Dict of table_name -> schema description.

        Returns:
            Filtered dict with only accessible tables, and denied
            columns removed from descriptions.
        """
        config = self.get_role_config(role)
        allowed_tables = config.get("allowed_tables", "*")
        denied_columns = {c.lower() for c in config.get("denied_columns", [])}

        filtered = {}
        for table_name, schema_text in schema_texts.items():
            # Check table access
            if allowed_tables != "*" and table_name.lower() not in {
                t.lower() for t in allowed_tables
            }:
                continue

            # Remove denied columns from schema text
            if denied_columns:
                lines = schema_text.split("\n")
                filtered_lines = []
                for line in lines:
                    # Check if this line describes a denied column
                    skip = False
                    for denied in denied_columns:
                        if "." in denied:
                            d_table, d_col = denied.split(".", 1)
                            if (
                                d_table.lower() == table_name.lower()
                                and d_col.lower() in line.lower()
                            ):
                                skip = True
                                break
                    if not skip:
                        filtered_lines.append(line)
                filtered[table_name] = "\n".join(filtered_lines)
            else:
                filtered[table_name] = schema_text

        return filtered

    def requires_aggregation(self, role: str) -> bool:
        """Check if the role requires queries to use aggregation."""
        config = self.get_role_config(role)
        return config.get("require_aggregation", False)

    def list_roles(self) -> list[str]:
        """List all available role names."""
        return list(self._roles.keys())

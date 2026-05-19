"""
Data Sampler - Extracts database sample rows and distinct column values
to augment prompt context (data sampling and in-context learning).
"""

import sqlite3
import logging

logger = logging.getLogger(__name__)


class DataSampler:
    """Extracts context from a SQLite database to help the LLM understand schema contents."""

    def __init__(self, database_path: str):
        self.database_path = database_path

    def get_database_summary(self) -> str:
        """
        Queries all tables to build a summary of sample data and distinct categories.
        """
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        summary_parts = ["--- DATABASE DATA SAMPLES & METADATA ---"]

        try:
            # 1. Fetch tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                summary_parts.append(f"\nTable: {table}")

                # Get column details
                cursor.execute(f"PRAGMA table_info({table});")
                columns = cursor.fetchall()
                col_names = [col[1] for col in columns]
                col_types = {col[1]: col[2] for col in columns}

                # Fetch 3 sample rows
                cursor.execute(f"SELECT * FROM {table} LIMIT 3;")
                sample_rows = cursor.fetchall()

                if sample_rows:
                    summary_parts.append("  Sample Rows:")
                    summary_parts.append("    " + " | ".join(col_names))
                    for row in sample_rows:
                        summary_parts.append("    " + " | ".join(str(val) for val in row))
                else:
                    summary_parts.append("  (No data in table)")

                # Fetch distinct values for text columns with low cardinality (categorical fields)
                for col in col_names:
                    if col_types[col].upper() in ("TEXT", "VARCHAR", ""):
                        # Check cardinality
                        cursor.execute(f"SELECT COUNT(DISTINCT {col}) FROM {table};")
                        cardinality = cursor.fetchone()[0]

                        # If low cardinality (e.g. between 1 and 10), fetch distinct values
                        if 0 < cardinality <= 10:
                            cursor.execute(f"SELECT DISTINCT {col} FROM {table} WHERE {col} IS NOT NULL;")
                            values = [str(r[0]) for r in cursor.fetchall()]
                            summary_parts.append(f"  Distinct values for column '{col}': {', '.join(values)}")

        except sqlite3.Error as e:
            logger.error(f"Error extracting database samples: {e}")
            summary_parts.append(f"  Error extracting metadata: {e}")
        finally:
            cursor.close()
            conn.close()

        return "\n".join(summary_parts) + "\n----------------------------------------\n"

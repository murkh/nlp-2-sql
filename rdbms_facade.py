"""
RDBMS Facade - Abstraction layer for SQL database engines.

Provides a consistent interface independent of the underlying database.
Currently implements SQLite for local development; can be extended to
support PostgreSQL, Aurora, or any RDBMS.

Best Practices Applied:
- Execute SQL preamble statements (temp tables, views) before the main query
- Return column headers along with data rows
- Proper error handling and connection management
"""

import sqlite3
import app_constants as app_consts

import logging

logger = logging.getLogger(__name__)


class RdbmsFacade:
    def execute_sql(self, database: str, sql_script: list[str]) -> dict:
        """
        Execute the SQL script against the specified database.
        Returns a dictionary with rdbms_output and processing_status.
        """
        rdbms_results, rdbms_status = self.execute_sql_script(database, sql_script)

        results = {
            app_consts.RDBMS_OUTPUT: rdbms_results,
            app_consts.PROCESSING_STATUS: rdbms_status,
        }

        return results

    @staticmethod
    def execute_sql_script(database: str, sql_script: list[str]):
        """
        Execute each statement in the SQL script sequentially.
        The result of the LAST statement is returned (the actual query).
        Earlier statements are preamble (temp tables, views, inserts).

        Returns:
            tuple: (results_list, status_string)
        """
        status = "failed"
        results = []
        iterations = 1

        connection = sqlite3.connect(database)
        with connection:
            cursor = connection.cursor()
            try:
                for stmt in sql_script:
                    if not stmt or stmt.strip() == "":
                        iterations += 1
                        continue

                    logger.debug(
                        f"Executing SQL [{iterations}/{len(sql_script)}]: {stmt[:120]}..."
                    )
                    cursor.execute(stmt)
                    result = cursor.fetchall()

                    # Only capture results from the final statement (the generated query)
                    if iterations == len(sql_script):
                        if cursor.description and len(cursor.description) > 0:
                            column_names = [x[0] for x in cursor.description]
                            results = [tuple(column_names)]
                            for r in result:
                                results.append(r)
                            status = app_consts.SUCCESS
                        else:
                            logger.warning(
                                "Final SQL statement produced no column description"
                            )
                    iterations += 1

            except sqlite3.Error as e:
                logger.error(f"SQL execution error: {e}")
                logger.error(
                    f"Failed statement: {sql_script[iterations - 1] if iterations <= len(sql_script) else 'unknown'}"
                )
            finally:
                cursor.close()

        return results, status

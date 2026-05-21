"""
Data Query Handler — Orchestrates the SQL Agent and formats results.

Handles "data" intents by passing queries through the SQL Agent pipeline,
then generates human-readable summaries of the results using the LLM.
"""

from dataclasses import dataclass, field

from llm.base import LLMProvider
from sql_agent.agent import SQLAgent, SQLAgentResult


@dataclass
class DataHandlerResult:
    """Result of a data query handler invocation."""
    success: bool
    response_text: str = ""
    sql: str = ""
    data: list[list] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    row_count: int = 0
    error: str = ""
    needs_clarification: bool = False
    clarification: str = ""


_SUMMARIZE_SYSTEM_PROMPT = """You are a data analyst assistant. The user asked a question and we executed a SQL query. 
Summarize the results in clear, natural language.

Guidelines:
- Be concise — don't repeat every row if there are many
- Highlight key insights, trends, or notable values
- Use numbers and percentages where relevant
- If results are empty, explain why there might be no data
- Format numbers nicely (commas for thousands, 2 decimal places for money)
- If the data is small enough (< 5 rows), include the specific values
- For larger datasets, provide summary statistics and highlights
"""


class DataHandler:
    """
    Handles data query intents by orchestrating the SQL Agent.

    Passes enriched queries through the SQL Agent pipeline, then
    generates human-readable summaries of the results.
    """

    def __init__(self, llm: LLMProvider, sql_agent: SQLAgent):
        self._llm = llm
        self._sql_agent = sql_agent

    def handle(
        self,
        query: str,
        role: str | None = None,
        conversation_context: str = "",
    ) -> DataHandlerResult:
        """
        Process a data query through the SQL Agent.

        Args:
            query: The enriched natural language query.
            role: User's RBAC role.
            conversation_context: Recent conversation for context.

        Returns:
            DataHandlerResult with formatted response and raw data.
        """
        # Execute through SQL Agent
        agent_result: SQLAgentResult = self._sql_agent.generate_and_execute(
            query=query,
            role=role,
            conversation_context=conversation_context,
        )

        if not agent_result.success:
            if agent_result.needs_clarification:
                return DataHandlerResult(
                    success=False,
                    needs_clarification=True,
                    clarification=agent_result.clarification,
                    sql=agent_result.sql,
                )
            return DataHandlerResult(
                success=False,
                error=agent_result.error,
                response_text=self._friendly_error(agent_result.error),
                sql=agent_result.sql,
            )

        # Success — generate summary
        if agent_result.row_count == 0:
            response_text = self._explain_empty_results(
                query, agent_result.sql
            )
        else:
            response_text = self._summarize_results(
                query, agent_result
            )

        return DataHandlerResult(
            success=True,
            response_text=response_text,
            sql=agent_result.sql,
            data=agent_result.data,
            columns=agent_result.columns,
            row_count=agent_result.row_count,
        )

    def _summarize_results(
        self, query: str, result: SQLAgentResult
    ) -> str:
        """Generate a natural language summary of query results."""
        # Build data preview for the LLM
        data_preview = self._format_data_preview(
            result.columns, result.data
        )

        prompt = (
            f"User question: {query}\n\n"
            f"SQL executed: {result.sql}\n\n"
            f"Results ({result.row_count} rows):\n{data_preview}"
        )

        try:
            summary = self._llm.chat_completion(
                messages=[
                    {"role": "system", "content": _SUMMARIZE_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=500,
            )
            return summary
        except Exception:
            # Fallback: simple data display
            return f"Query returned {result.row_count} rows."

    def _explain_empty_results(self, query: str, sql: str) -> str:
        """Explain why a query returned no results."""
        try:
            response = self._llm.chat_completion(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "The user asked a question and we executed a SQL "
                            "query, but it returned no results. Explain why "
                            "there might be no data, and suggest how the user "
                            "could modify their question."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Question: {query}\n"
                            f"SQL: {sql}\n\n"
                            f"No results were returned."
                        ),
                    },
                ],
                temperature=0.3,
                max_tokens=300,
            )
            return response
        except Exception:
            return (
                "Your query returned no results. This could mean the data "
                "doesn't exist for the specified criteria. Try broadening "
                "your search."
            )

    @staticmethod
    def _friendly_error(error: str) -> str:
        """Convert technical errors to user-friendly messages."""
        if "Access denied" in error:
            return (
                "Sorry, you don't have permission to access that data. "
                "Your current role restricts access to certain tables or columns."
            )
        if "validation failed" in error.lower():
            return (
                "I couldn't generate a safe query for that request. "
                "Could you try rephrasing your question?"
            )
        if "execution failed" in error.lower():
            return (
                "The query encountered an error during execution. "
                "This might be due to a data issue. Please try a different question."
            )
        return f"Something went wrong: {error}. Please try rephrasing."

    @staticmethod
    def _format_data_preview(
        columns: list[str], data: list[list], max_rows: int = 20
    ) -> str:
        """Format data as a readable table for the LLM."""
        if not data:
            return "(no data)"

        lines = [" | ".join(str(c) for c in columns)]
        lines.append("-" * len(lines[0]))

        for row in data[:max_rows]:
            lines.append(" | ".join(str(v) for v in row))

        if len(data) > max_rows:
            lines.append(f"... ({len(data) - max_rows} more rows)")

        return "\n".join(lines)

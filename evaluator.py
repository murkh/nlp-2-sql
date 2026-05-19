"""
Evaluator - LLM-as-a-Judge module to evaluate generated SQL queries
against the user request and database schema.
"""
from __future__ import annotations
import logging
import app_constants as app_consts
from llm_facade import LlmFacade

logger = logging.getLogger(__name__)

EVALUATOR_PROMPT_TEMPLATE = """
You are an expert SQL Quality Assurance Judge. Your task is to evaluate a generated SQL query against the user's natural language question, the database schema, and domain rules.

User Question: "{user_query}"

Database Schema & Rules:
{schema_and_rules}

Generated SQL Query:
"{generated_sql}"

Query Results (First 5 rows for reference):
{query_results_text}

Evaluate the SQL query based on:
1. Correctness: Does it accurately address all parts of the user question?
2. Adherence to Rules: Does it follow the specific rules in <rule> tags (e.g. status='completed' filters, margin calculation formulas, date ranges)?
3. SQL Quality: Is it clean, readable, using correct table aliases?

Provide scoring on a scale from 1 to 5:
- 5: Perfect (completely correct, followed all rules)
- 4: Good (mostly correct, minor issues)
- 3: Fair (partially correct, misses some filters/rules)
- 2: Poor (contains syntax or logical errors, incorrect joins)
- 1: Fail (completely incorrect or blank)

Output your evaluation strictly in JSON format with three keys:
- "correctness_score": integer (1-5)
- "adherence_score": integer (1-5)
- "explanation": a concise, clear explanation of your scores and any improvements that could be made.
"""


class LlmJudgeEvaluator:
    """Evaluates SQL query quality using an LLM-as-a-judge approach."""

    def __init__(self, llm: LlmFacade):
        self.llm = llm

    def evaluate_query(self, user_query: str, generated_sql: str, query_results: list, domain: str) -> dict | None:
        """
        Run the LLM-as-a-judge evaluation.

        Returns:
            dict: The evaluation report containing correctness_score, adherence_score, explanation.
        """
        import domains
        if domain not in domains.contexts.keys():
            return None

        spec = domains.contexts[domain]
        schema_and_rules = (
            getattr(spec, "SYSTEM_PROMPT_INSTRUCTIONS", "") + "\n" +
            getattr(spec, "JOIN_HINTS", "") + "\n<SQL>\n" +
            getattr(spec, "ANNOTATED_SQL_DEFINITIONS", "") + "\n</SQL>"
        )

        # Format first few rows of results for context
        if not query_results:
            query_results_text = "(No results returned)"
        else:
            limit_results = query_results[:6]  # Header + 5 rows
            col_widths = [max(len(str(val)) for val in col) for col in zip(*limit_results)]
            lines = []
            for row in limit_results:
                lines.append(" | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row)))
            query_results_text = "\n".join(lines)

        prompt = EVALUATOR_PROMPT_TEMPLATE.format(
            user_query=user_query,
            schema_and_rules=schema_and_rules,
            generated_sql=generated_sql,
            query_results_text=query_results_text
        )

        logger.info("Invoking LLM Judge to evaluate the query...")
        llm_response = self.llm.invoke(prompt, temperature=0.0)
        output = llm_response.get(app_consts.LLM_OUTPUT)

        return output

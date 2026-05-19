"""
Disambiguator - Evaluates natural language queries for ambiguity
and generates clarifying questions when necessary before generating SQL.
"""
from __future__ import annotations
import logging
import app_constants as app_consts
from llm_facade import LlmFacade

logger = logging.getLogger(__name__)

DISAMBIGUATION_PROMPT_TEMPLATE = """
You are an expert database assistant. Your task is to analyze the user's natural language query and determine if it is clear enough to translate into a SQL query based on the database schema and rules, or if it is ambiguous and requires clarification.

A query is ambiguous if:
1. It uses vague metrics like "best", "top", or "most popular" without defining the criteria (e.g., "best products" could mean by quantity sold, total revenue, or profit margin).
2. It lacks necessary filters or context that cannot be reasonably inferred (e.g. asking about "sales reps" performance but omitting the timeframe or metric if there are multiple options, or asking for "highest region" without stating if it means customer count, revenue, or orders).
3. It asks for information not present in the database schema.

A query is NOT ambiguous if:
1. It maps directly to existing columns or the predefined join rules/examples (e.g., "total sales for each product" is clear because we have a rule defining product revenue).
2. The user specifies a clear grouping and metric.

Database Schema & Rules:
{schema_and_rules}

User Query: "{user_query}"

Analyze the query. If it is ambiguous, set "is_ambiguous" to true and provide a polite, helpful "clarification_question" asking the user to choose or define their terms (e.g., "Would you like to see products ordered by units sold, total revenue, or profit margin?").
If it is clear, set "is_ambiguous" to false and "clarification_question" to null.

Output the result strictly in JSON format with two keys:
- "is_ambiguous": boolean
- "clarification_question": string or null
"""


class Disambiguator:
    """Analyzes queries for ambiguity using LLM reasoning."""

    def __init__(self, llm: LlmFacade):
        self.llm = llm

    def check_ambiguity(self, user_query: str, domain: str) -> tuple[bool, str | None]:
        """
        Determine if the user query is ambiguous.

        Returns:
            tuple: (is_ambiguous, clarification_question)
        """
        import domains
        if domain not in domains.contexts.keys():
            return False, None

        spec = domains.contexts[domain]
        # Include schema, join rules, and examples as context
        schema_and_rules = (
            getattr(spec, "SYSTEM_PROMPT_INSTRUCTIONS", "") + "\n" +
            getattr(spec, "JOIN_HINTS", "") + "\n<SQL>\n" +
            getattr(spec, "ANNOTATED_SQL_DEFINITIONS", "") + "\n</SQL>"
        )

        prompt = DISAMBIGUATION_PROMPT_TEMPLATE.format(
            schema_and_rules=schema_and_rules,
            user_query=user_query
        )

        logger.info("Running query disambiguation check...")
        llm_response = self.llm.invoke(prompt, temperature=0.0)
        output = llm_response.get(app_consts.LLM_OUTPUT)

        if not output:
            logger.warning("Disambiguation check failed to return response, assuming clear.")
            return False, None

        is_ambiguous = output.get("is_ambiguous", False)
        clarification_question = output.get("clarification_question")

        if is_ambiguous and clarification_question:
            logger.info(f"Query identified as ambiguous. Clarification: {clarification_question}")
            return True, clarification_question

        logger.info("Query identified as clear.")
        return False, None

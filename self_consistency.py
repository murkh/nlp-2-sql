"""
Self-Consistency - Generates multiple candidate SQL queries, validates them,
and uses a selector LLM call to pick the most accurate query.
"""
from __future__ import annotations
import logging
import app_constants as app_consts
from llm_facade import LlmFacade
from sql_validator import SqlValidator

logger = logging.getLogger(__name__)

SELECTOR_PROMPT_TEMPLATE = """
You are an expert SQL judge. Your task is to evaluate a set of candidate SQL queries and select the one that best and most accurately answers the user's natural language question, strictly following the database schema, rules, and best practices.

User Question: "{user_query}"

Database Schema & Rules:
{schema_and_rules}

Candidate SQL Queries:
{candidate_list_text}

Analyze the candidates carefully. Pay attention to:
1. Adherence to the join and calculation rules.
2. Correct handling of filters, group by, and order by.
3. Correct SQLite syntax.

Output the 0-based index of the best candidate query.
Your output must be strictly in JSON format with one key:
- "selected_index": integer (0 to {max_index})
"""


class SelfConsistencyManager:
    """Manages the generation of multiple candidate queries and selecting the best one."""

    def __init__(self, llm: LlmFacade, validator: SqlValidator):
        self.llm = llm
        self.validator = validator

    def generate_and_select(self, prompt: str, user_query: str, preamble: list[str], domain: str, num_candidates: int = 3) -> dict | None:
        """
        Generate multiple candidates, validate them, and pick the best valid candidate.

        Returns:
            dict: The selected JSON response containing {"sql": "..."} or None if no valid candidate.
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

        candidates = []
        # Vary the temperatures slightly to get diverse outputs
        temperatures = [0.05, 0.25, 0.45, 0.65][:num_candidates]

        logger.info(f"Generating {num_candidates} candidate SQL queries for self-consistency...")

        for i, temp in enumerate(temperatures):
            logger.debug(f"Generating candidate {i} with temp={temp}...")
            llm_response = self.llm.invoke(prompt, temperature=temp)
            generated_json = llm_response.get(app_consts.LLM_OUTPUT)

            if not generated_json or not generated_json.get(app_consts.SQL):
                logger.warning(f"Candidate {i} generation returned invalid JSON structure.")
                continue

            sql_str = generated_json[app_consts.SQL]
            is_valid, err_msg = self.validator.validate(sql_str, preamble)
            if is_valid:
                logger.info(f"Candidate {i} is valid: {sql_str[:100]}...")
                candidates.append(generated_json)
            else:
                logger.warning(f"Candidate {i} failed dry-run validation: {err_msg}")

        if not candidates:
            logger.error("No valid candidate SQL queries generated.")
            return None

        if len(candidates) == 1:
            logger.info("Only one valid candidate query generated, selecting it directly.")
            return candidates[0]

        # Use LLM-as-a-judge selector to pick the best candidate
        candidate_list_text = ""
        for idx, cand in enumerate(candidates):
            candidate_list_text += f"\nCandidate [{idx}]:\n{cand.get(app_consts.SQL)}\n"

        selector_prompt = SELECTOR_PROMPT_TEMPLATE.format(
            user_query=user_query,
            schema_and_rules=schema_and_rules,
            candidate_list_text=candidate_list_text,
            max_index=len(candidates) - 1
        )

        logger.info("Invoking LLM selector judge to pick the best query...")
        selector_response = self.llm.invoke(selector_prompt, temperature=0.0)
        selector_output = selector_response.get(app_consts.LLM_OUTPUT)

        if not selector_output or "selected_index" not in selector_output:
            logger.warning("Selector failed or returned invalid response, defaulting to candidate 0.")
            return candidates[0]

        selected_idx = selector_output["selected_index"]
        if 0 <= selected_idx < len(candidates):
            logger.info(f"Selected candidate index {selected_idx} as the best query.")
            return candidates[selected_idx]
        else:
            logger.warning(f"Selector returned out-of-bounds index {selected_idx}, defaulting to candidate 0.")
            return candidates[0]

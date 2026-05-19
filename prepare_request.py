"""
Prepare Request - Pivotal step in the NLP2SQL pipeline.

This module assembles the complete LLM prompt and SQL preamble
based on the domain context. It constructs:
1. A prompt with system instructions, schema DDL, rules, few-shot examples, and the user query
2. SQL preamble statements (temp tables, views) to be executed before the generated SQL

Best Practices Applied (from AWS blog):
- Domain-scoped prompt construction (reduce LLM attention burden)
- Augmented DDL with metadata descriptions
- Few-shot examples aligned with domain schema
- SQL preamble for data abstractions
"""

import app_constants as app_consts
from typing import List
import domains

import logging
logger = logging.getLogger(__name__)


class PrepareRequest:

    def run(self, pre_processed_request: dict) -> dict:
        """
        Prepare the request for the LLM by assembling:
        - The complete LLM prompt (system + schema + examples + user query)
        - The SQL preamble (temp structures to execute before generated SQL)
        """
        prepared_request = {}

        domain = pre_processed_request[app_consts.DOMAIN]
        user_query = pre_processed_request[app_consts.USER_QUERY]
        identifiers = pre_processed_request[app_consts.IDENTIFIERS]

        if domain in domains.contexts.keys():
            # Assemble the LLM prompt
            prepared_request[app_consts.LLM_PROMPT] = self.get_llm_prompt_payload(domain, user_query)
            # Assemble the SQL preamble
            prepared_request[app_consts.SQL_PREAMBLE] = self.get_sql_preamble(domain, identifiers)
        else:
            logger.error(f"Domain '{domain}' is not recognized. Cannot prepare request.")
            raise ValueError(f"Unrecognized domain: {domain}")

        return prepared_request

    @staticmethod
    def get_llm_prompt_payload(domain: str, user_query: str) -> str:
        """
        Construct the complete prompt for the LLM:
        SYSTEM_PROMPT (instructions + rules + schema + samples + examples) + USER_PROMPT + query
        """
        import data_sampler
        if domain not in domains.contexts.keys():
            raise ValueError(f"Unrecognized domain: {domain}")

        spec = domains.contexts[domain]
        
        # Extract individual pieces to insert dynamic database summary
        system_instructions = getattr(spec, "SYSTEM_PROMPT_INSTRUCTIONS", "")
        join_hints = getattr(spec, "JOIN_HINTS", "")
        ddl = getattr(spec, "ANNOTATED_SQL_DEFINITIONS", "")
        few_shot = getattr(spec, "FEW_SHOT_EXAMPLES", "")
        
        # Fetch dynamic database metadata and sample rows
        db_path = app_consts.get_database_for_domain(domain)
        sampler = data_sampler.DataSampler(db_path)
        db_summary = sampler.get_database_summary()

        # Re-assemble the system prompt dynamically
        system_prompt = (
            system_instructions + "\n" +
            join_hints + "\n<SQL>\n" +
            ddl + "\n</SQL>\n\n" +
            db_summary + "\n" +
            few_shot
        )
        
        user_prompt = spec.USER_PROMPT + user_query
        return system_prompt + user_prompt



    def get_sql_preamble(self, domain: str, identifiers: List) -> list:
        """
        Build the SQL preamble — statements executed before the LLM-generated SQL.
        This may include temp table creation and identity inserts.
        """
        if domain not in domains.contexts.keys():
            raise ValueError(f"Unrecognized domain: {domain}")

        table_names = domains.contexts[domain].TABLE_NAMES

        # Build preamble: part 1 + identity inserts (if any) + part 2
        stmts = domains.contexts[domain].SQL_PREAMBLE_PT1 if not identifiers else \
            domains.contexts[domain].SQL_PREAMBLE_PT1 + self.generate_identity_inserts(identifiers, table_names)

        return stmts + domains.contexts[domain].SQL_PREAMBLE_PT2

    @staticmethod
    def generate_identity_inserts(identifiers: List, table_names: list[str]) -> list:
        """
        Generate SQL INSERT statements for resolved identifiers
        into the specified temporary table.
        """
        if not identifiers:
            return []

        if len(table_names) == 1 and table_names[0]:
            table_name = table_names[0]
            identity_inserts = f"INSERT INTO {table_name} VALUES "
            for i, eid in enumerate(identifiers, 1):
                identity_inserts += f"({i},{eid['id']},'{eid['name']}')"
                identity_inserts += ", " if i < len(identifiers) else ";"
            return [identity_inserts]

        return []

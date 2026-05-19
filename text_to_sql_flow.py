"""
Text-to-SQL Flow Orchestrator

This is the main control-flow class that orchestrates the end-to-end NLP2SQL pipeline:

    User Query → PreProcess → Resolve IDs → Prepare Prompt → Generate SQL → Execute → Results

Following the AWS enterprise NL2SQL architecture:
1. PreProcess: Classify domain + extract named resources
2. Resolve: Map named resources to database identifiers
3. Prepare: Assemble domain-scoped prompt with schema, rules, examples
4. Generate: Invoke LLM to produce SQL
5. Execute: Run preamble + generated SQL against the database
"""

from __future__ import annotations
import app_constants as app_consts
import identity_service_facade
import llm_facade
import pre_process_request
import prepare_request
import rdbms_facade
import sql_validator

import logging

logging.basicConfig(
    format="[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class TextToSQLFlow:
    """Orchestrates the complete NLP-to-SQL pipeline."""

    def __init__(self):
        self.identity_service_facade = identity_service_facade.IdentityServiceFacade()
        self.llm_facade = llm_facade.LlmFacade(app_consts.OPENAI_MODEL)
        self.rdbms_facade = rdbms_facade.RdbmsFacade()
        self.pre_process_request = pre_process_request.PreProcessRequest(
            self.llm_facade
        )
        self.prepare_request = prepare_request.PrepareRequest()

    def run(self, user_request: str):
        """
        Execute the full NLP2SQL pipeline:

        Args:
            user_request: Natural language question about sales data

        Returns:
            tuple: (results_list, status_string, clarification_question, generated_sql)
                   results_list contains column headers as first row, then data rows
        """
        logger.info(f"═══ Processing query: '{user_request}' ═══")

        # ── Step 1: Pre-process the request ──
        pre_processed = self.pre_process_request.run(user_request)
        domain = pre_processed[app_consts.DOMAIN]
        named_resources = pre_processed[app_consts.NAMED_RESOURCES]

        # ── Step 1.5: Check for ambiguity / Disambiguation ──
        if app_consts.ENABLE_DISAMBIGUATION and domain != "unknown":
            import disambiguator

            db_disambiguator = disambiguator.Disambiguator(self.llm_facade)
            is_ambiguous, clarification = db_disambiguator.check_ambiguity(
                user_request, domain
            )
            if is_ambiguous:
                return [], "clarification", clarification, None

        # ── Step 2: Resolve named resources to identifiers ──
        if len(named_resources) > 0:
            identifiers = self.identity_service_facade.resolve(named_resources)
            pre_processed[app_consts.IDENTIFIERS] = identifiers
        else:
            pre_processed[app_consts.IDENTIFIERS] = []

        # ── Step 3: Prepare the LLM prompt and SQL preamble ──
        prepared = self.prepare_request.run(pre_processed)
        logger.debug(
            f"Prepared prompt length: {len(prepared[app_consts.LLM_PROMPT])} chars"
        )

        # ── Step 4: Generate SQL via LLM with validation & reprompting ──
        database = app_consts.get_database_for_domain(domain)
        validator = sql_validator.SqlValidator(database)

        prompt = prepared[app_consts.LLM_PROMPT]
        preamble = prepared[app_consts.SQL_PREAMBLE]

        generated_sql = None

        if app_consts.ENABLE_SELF_CONSISTENCY:
            import self_consistency

            sc_manager = self_consistency.SelfConsistencyManager(
                self.llm_facade, validator
            )
            generated_sql = sc_manager.generate_and_select(
                prompt,
                user_request,
                preamble,
                domain,
                app_consts.SELF_CONSISTENCY_CANDIDATES,
            )
            if not generated_sql:
                logger.error("Self-consistency failed to produce a valid SQL query.")
                return [], "fail", None, None
        else:
            max_attempts = app_consts.MAX_REPROMPT_ATTEMPTS + 1
            attempt = 1
            sql_query_str = None
            err_msg = "Unknown error"

            while attempt <= max_attempts:
                llm_response = self.llm_facade.invoke(prompt)
                generated_json = llm_response[app_consts.LLM_OUTPUT]

                if generated_json is None:
                    logger.error(f"LLM failed to generate SQL on attempt {attempt}")
                    return [], app_consts.FAIL, None, None

                sql_query_str = generated_json.get(app_consts.SQL)
                if not sql_query_str:
                    logger.error(f"LLM output missing 'sql' key on attempt {attempt}")
                    prompt += f"\n\nResponse was missing the 'sql' key. Please output a valid JSON object with one key 'sql'."
                    attempt += 1
                    continue

                logger.info(f"Attempt {attempt} Generated SQL: {sql_query_str}")

                # Validate the SQL statement
                is_valid, err_msg = validator.validate(sql_query_str, preamble)
                if is_valid:
                    logger.info(f"SQL validation passed on attempt {attempt}")
                    generated_sql = generated_json
                    break
                else:
                    logger.warning(
                        f"SQL validation failed on attempt {attempt}: {err_msg}"
                    )
                    if attempt < max_attempts:
                        prompt += f"\n\nYour previous SQL query: {sql_query_str}\nFailed validation with error: {err_msg}\nPlease correct the SQL query to resolve this error. Output the corrected result in JSON format with one key 'sql'."
                    attempt += 1

            if not generated_sql:
                logger.error(
                    "Failed to generate valid SQL after maximum reprompt attempts"
                )
                return [], f"SQL validation failure: {err_msg}", None, None

        # ── Step 5: Execute the SQL ──
        sql_script = preamble + [generated_sql[app_consts.SQL]]
        logger.info(f"Executing against database: {database}")

        results = self.rdbms_facade.execute_sql(database, sql_script)
        rdbms_results = results[app_consts.RDBMS_OUTPUT]
        rdbms_status = results[app_consts.PROCESSING_STATUS]

        logger.info(
            f"Query returned {len(rdbms_results) - 1 if rdbms_results else 0} rows (status: {rdbms_status})"
        )

        return rdbms_results, rdbms_status, None, generated_sql[app_consts.SQL]

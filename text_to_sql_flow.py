"""
Text-to-SQL Flow Orchestrator using LangGraph

This class orchestrates the end-to-end NLP2SQL pipeline as a StateGraph:

    User Query → PreProcess → Disambiguate → Resolve IDs → Prepare Prompt 
               → (Route: SC vs Basic) → Generate SQL → Validate → Execute → Results

Following the AWS enterprise NL2SQL architecture:
1. PreProcess: Classify domain + extract named resources
2. Disambiguate: Evaluate natural language query for ambiguity
3. Resolve: Map named resources to database identifiers
4. Prepare: Assemble domain-scoped prompt with schema, rules, examples
5. Generate: Invoke LLM to produce SQL (via Self-Consistency or Basic Reprompting)
6. Validate: Dry-run check SQL statement for syntax/correctness
7. Execute: Run preamble + generated SQL against the database
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
from typing import TypedDict
from langgraph.graph import StateGraph, END

logging.basicConfig(
    format="[%(asctime)s] {%(filename)s:%(lineno)d} %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class PipelineState(TypedDict):
    """LangGraph state representation for the NLP2SQL pipeline."""
    user_query: str
    domain: str
    named_resources: set
    identifiers: list
    llm_prompt: str
    sql_preamble: list
    generated_sql: dict | None
    rdbms_results: list
    status: str
    clarification: str | None
    attempt: int
    validation_error: str | None
    is_ambiguous: bool


class TextToSQLFlow:
    """Orchestrates the complete NLP-to-SQL pipeline using a LangGraph workflow."""

    def __init__(self):
        self.identity_service_facade = identity_service_facade.IdentityServiceFacade()
        self.llm_facade = llm_facade.LlmFacade(app_consts.OPENAI_MODEL)
        self.rdbms_facade = rdbms_facade.RdbmsFacade()
        self.pre_process_request = pre_process_request.PreProcessRequest(
            self.llm_facade
        )
        self.prepare_request = prepare_request.PrepareRequest()
        
        # Build and compile the workflow graph
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(PipelineState)

        # Register nodes
        workflow.add_node("preprocess", self.node_preprocess)
        workflow.add_node("disambiguate", self.node_disambiguate)
        workflow.add_node("resolve_ids", self.node_resolve_ids)
        workflow.add_node("prepare", self.node_prepare)
        workflow.add_node("generate_sql_sc", self.node_generate_sql_sc)
        workflow.add_node("generate_sql_basic", self.node_generate_sql_basic)
        workflow.add_node("validate_sql", self.node_validate_sql)
        workflow.add_node("execute_sql", self.node_execute_sql)

        # Set entry point and static edges
        workflow.set_entry_point("preprocess")
        workflow.add_edge("preprocess", "disambiguate")

        # Disambiguation conditional branch
        workflow.add_conditional_edges(
            "disambiguate",
            self.route_after_disambiguate,
            {
                "resolve_ids": "resolve_ids",
                "end": END,
            }
        )

        workflow.add_edge("resolve_ids", "prepare")

        # Self-consistency vs Basic prompt branch
        workflow.add_conditional_edges(
            "prepare",
            self.route_after_prepare,
            {
                "generate_sql_sc": "generate_sql_sc",
                "generate_sql_basic": "generate_sql_basic",
            }
        )

        # Routing after self-consistency (SC handles validation internally)
        workflow.add_conditional_edges(
            "generate_sql_sc",
            self.route_after_generate_sc,
            {
                "execute_sql": "execute_sql",
                "end": END,
            }
        )

        # Basic generation routes to validation
        workflow.add_edge("generate_sql_basic", "validate_sql")

        # Reprompt loop or execution routes
        workflow.add_conditional_edges(
            "validate_sql",
            self.route_after_validate,
            {
                "execute_sql": "execute_sql",
                "generate_sql_basic": "generate_sql_basic",
                "end": END,
            }
        )

        # Execute always leads to END
        workflow.add_edge("execute_sql", END)

        return workflow.compile()

    # ─────────────────────────────────────────────
    # Node Implementations
    # ─────────────────────────────────────────────

    def node_preprocess(self, state: PipelineState) -> dict:
        """Classifies the domain and extracts named resources."""
        pre_processed = self.pre_process_request.run(state["user_query"])
        return {
            "domain": pre_processed[app_consts.DOMAIN],
            "named_resources": pre_processed[app_consts.NAMED_RESOURCES]
        }

    def node_disambiguate(self, state: PipelineState) -> dict:
        """Evaluates query ambiguity and sets clarification if needed."""
        domain = state["domain"]
        user_query = state["user_query"]

        if app_consts.ENABLE_DISAMBIGUATION and domain != "unknown":
            import disambiguator
            db_disambiguator = disambiguator.Disambiguator(self.llm_facade)
            is_ambiguous, clarification = db_disambiguator.check_ambiguity(
                user_query, domain
            )
            if is_ambiguous:
                return {
                    "is_ambiguous": True,
                    "clarification": clarification,
                    "status": "clarification"
                }

        return {
            "is_ambiguous": False,
            "clarification": None
        }

    def node_resolve_ids(self, state: PipelineState) -> dict:
        """Maps named resources to database identifiers."""
        named_resources = state["named_resources"]
        if len(named_resources) > 0:
            identifiers = self.identity_service_facade.resolve(named_resources)
        else:
            identifiers = []
        return {"identifiers": identifiers}

    def node_prepare(self, state: PipelineState) -> dict:
        """Prepares prompt payload and SQL preamble."""
        pre_processed_request = {
            app_consts.DOMAIN: state["domain"],
            app_consts.USER_QUERY: state["user_query"],
            app_consts.IDENTIFIERS: state["identifiers"]
        }
        prepared = self.prepare_request.run(pre_processed_request)
        return {
            "llm_prompt": prepared[app_consts.LLM_PROMPT],
            "sql_preamble": prepared[app_consts.SQL_PREAMBLE]
        }

    def node_generate_sql_sc(self, state: PipelineState) -> dict:
        """Generates SQL using the self-consistency manager."""
        import self_consistency
        domain = state["domain"]
        database = app_consts.get_database_for_domain(domain)
        validator = sql_validator.SqlValidator(database)

        sc_manager = self_consistency.SelfConsistencyManager(
            self.llm_facade, validator
        )
        generated_sql = sc_manager.generate_and_select(
            state["llm_prompt"],
            state["user_query"],
            state["sql_preamble"],
            domain,
            app_consts.SELF_CONSISTENCY_CANDIDATES,
        )
        if not generated_sql:
            logger.error("Self-consistency failed to produce a valid SQL query.")
            return {"status": "fail", "generated_sql": None}

        return {"generated_sql": generated_sql, "status": "success"}

    def node_generate_sql_basic(self, state: PipelineState) -> dict:
        """Generates a single SQL query candidate from prompt."""
        prompt = state["llm_prompt"]
        validation_error = state["validation_error"]

        if validation_error:
            prev_sql_dict = state["generated_sql"]
            prev_sql = prev_sql_dict.get(app_consts.SQL) if prev_sql_dict else None
            if not prev_sql:
                prompt += "\n\nResponse was missing the 'sql' key. Please output a valid JSON object with one key 'sql'."
            else:
                prompt += f"\n\nYour previous SQL query: {prev_sql}\nFailed validation with error: {validation_error}\nPlease correct the SQL query to resolve this error. Output the corrected result in JSON format with one key 'sql'."

        llm_response = self.llm_facade.invoke(prompt)
        generated_json = llm_response.get(app_consts.LLM_OUTPUT)

        return {
            "generated_sql": generated_json,
            "llm_prompt": prompt
        }

    def node_validate_sql(self, state: PipelineState) -> dict:
        """Validates current generated SQL via dry-run."""
        generated_json = state["generated_sql"]
        domain = state["domain"]
        database = app_consts.get_database_for_domain(domain)
        validator = sql_validator.SqlValidator(database)

        attempt = state["attempt"] + 1

        if generated_json is None:
            logger.error(f"LLM failed to generate SQL on attempt {attempt}")
            return {
                "attempt": attempt,
                "validation_error": "LLM failed to generate SQL",
                "status": "fail"
            }

        sql_query_str = generated_json.get(app_consts.SQL)
        if not sql_query_str:
            logger.error(f"LLM output missing 'sql' key on attempt {attempt}")
            return {
                "attempt": attempt,
                "validation_error": "Missing 'sql' key",
                "status": "fail"
            }

        logger.info(f"Attempt {attempt} Generated SQL: {sql_query_str}")
        is_valid, err_msg = validator.validate(sql_query_str, state["sql_preamble"])

        if is_valid:
            logger.info(f"SQL validation passed on attempt {attempt}")
            return {
                "attempt": attempt,
                "validation_error": None,
                "status": "success"
            }
        else:
            logger.warning(f"SQL validation failed on attempt {attempt}: {err_msg}")
            return {
                "attempt": attempt,
                "validation_error": err_msg,
                "status": f"SQL validation failure: {err_msg}"
            }

    def node_execute_sql(self, state: PipelineState) -> dict:
        """Executes the validated SQL against the database."""
        domain = state["domain"]
        database = app_consts.get_database_for_domain(domain)
        sql_script = state["sql_preamble"] + [state["generated_sql"][app_consts.SQL]]
        
        logger.info(f"Executing against database: {database}")
        results = self.rdbms_facade.execute_sql(database, sql_script)
        
        return {
            "rdbms_results": results[app_consts.RDBMS_OUTPUT],
            "status": results[app_consts.PROCESSING_STATUS]
        }

    # ─────────────────────────────────────────────
    # Edge Routers
    # ─────────────────────────────────────────────

    def route_after_disambiguate(self, state: PipelineState) -> str:
        if state["is_ambiguous"]:
            return "end"
        return "resolve_ids"

    def route_after_prepare(self, state: PipelineState) -> str:
        if app_consts.ENABLE_SELF_CONSISTENCY:
            return "generate_sql_sc"
        return "generate_sql_basic"

    def route_after_generate_sc(self, state: PipelineState) -> str:
        if state["generated_sql"] is None:
            return "end"
        return "execute_sql"

    def route_after_validate(self, state: PipelineState) -> str:
        if state["status"] == "success":
            return "execute_sql"

        max_attempts = app_consts.MAX_REPROMPT_ATTEMPTS + 1
        if state["attempt"] < max_attempts:
            return "generate_sql_basic"

        logger.error("Failed to generate valid SQL after maximum reprompt attempts")
        return "end"

    # ─────────────────────────────────────────────
    # Public API Wrapper
    # ─────────────────────────────────────────────

    def run(self, user_request: str) -> tuple:
        """
        Execute the full NLP2SQL pipeline using the compiled StateGraph.

        Args:
            user_request: Natural language question about sales data

        Returns:
            tuple: (results_list, status_string, clarification_question, generated_sql)
        """
        logger.info(f"═══ Processing query: '{user_request}' ═══")

        initial_state: PipelineState = {
            "user_query": user_request,
            "domain": "unknown",
            "named_resources": set(),
            "identifiers": [],
            "llm_prompt": "",
            "sql_preamble": [],
            "generated_sql": None,
            "rdbms_results": [],
            "status": "fail",
            "clarification": None,
            "attempt": 0,
            "validation_error": None,
            "is_ambiguous": False
        }

        final_state = self.graph.invoke(initial_state)

        sql_str = None
        if final_state.get("generated_sql"):
            sql_str = final_state["generated_sql"].get(app_consts.SQL)

        return (
            final_state.get("rdbms_results") or [],
            final_state.get("status") or "fail",
            final_state.get("clarification"),
            sql_str
        )

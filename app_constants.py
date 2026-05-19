"""
Application-wide constants and configuration for the NLP2SQL Sales Management system.

Following AWS best practices:
- Centralized configuration for LLM model and prompt constants
- Domain-to-database mapping for multi-domain scalability
- Separation of concerns between config and logic
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────
# OpenAI Configuration
# ─────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

# ─────────────────────────────────────────────
# Feature Configuration Flags
# ─────────────────────────────────────────────
ENABLE_DISAMBIGUATION = True
ENABLE_SELF_CONSISTENCY = False # Off by default, can be toggled
SELF_CONSISTENCY_CANDIDATES = 3
MAX_REPROMPT_ATTEMPTS = 2

# ─────────────────────────────────────────────
# Domain-to-Database Mapping
# Each domain maps to its own database, enabling
# data source agnostic scaling (per AWS blog)
# ─────────────────────────────────────────────
DOMAIN_TO_DATABASE = {
    "sales": "db_sales.db",
}

# ─────────────────────────────────────────────
# String Constants (Dictionary Keys)
# ─────────────────────────────────────────────
FAIL = "fail"
INPUT = "input"
DOMAIN = "domain"
IDENTIFIERS = "identifiers"
LLM_PROMPT = "llm_prompt"
LLM_OUTPUT = "llm_output"
NAMED_RESOURCES = "named_resources"
PROCESSING_STATUS = "processing_status"
RDBMS_OUTPUT = "rdbms_output"
SQL = "sql"
SQL_PREAMBLE = "sql_preamble"
SQL_QUERY = "sql_query"
SUCCESS = "success"
USER_QUERY = "user_query"

# ─────────────────────────────────────────────
# Prompt Constants
# ─────────────────────────────────────────────
STANDARD_USER_PROMPT = "question: "

DOMAIN_CLASSIFICATION_PROMPT = """
You are an expert at understanding short requests and classifying the request to one of a given set of classes.
The set of target classes are <classes>sales</classes>
If the request does not correspond to one of these classes, set the class as "other".
Output the result in a JSON format with one key "domain".
Answer the question immediately without preamble.

request: """


def get_database_for_domain(domain: str) -> str:
    """Return the database file path for the given domain."""
    return DOMAIN_TO_DATABASE[domain]

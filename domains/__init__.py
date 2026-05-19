"""
Domain registry for the NLP2SQL system.

Each domain context defines the schema, prompts, few-shot examples,
and SQL preambles needed to generate accurate SQL for that domain.
New domains can be added by creating a new context spec and registering it here.
"""

from domains.context_specs import sales

contexts = {
    sales.DOMAIN_DESC: sales,
}

DOMAIN_UNKNOWN = "unknown"

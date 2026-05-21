"""
Centralized configuration loaded from environment variables.

All settings are validated on import — missing required keys raise
clear errors early rather than failing mid-pipeline.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


# ─── LLM Configuration ─────────────────────────────────────────
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "openai").lower()

OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")


# ─── Embedding Configuration ───────────────────────────────────
OPENAI_EMBEDDING_MODEL: str = os.getenv(
    "OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"
)


# ─── Database Configuration ────────────────────────────────────
SALES_DB_PATH: str = os.getenv(
    "SALES_DB_PATH", str(_project_root / "db_sales.db")
)
POSTGRES_URL: str = os.getenv(
    "POSTGRES_URL", "postgresql://localhost:5432/text2sql"
)


# ─── Security ──────────────────────────────────────────────────
MAX_QUERY_ROWS: int = int(os.getenv("MAX_QUERY_ROWS", "1000"))
USER_ROLE: str = os.getenv("USER_ROLE", "analyst").lower()


# ─── ChromaDB ──────────────────────────────────────────────────
CHROMA_PERSIST_DIR: str = os.getenv(
    "CHROMA_PERSIST_DIR", str(_project_root / ".chroma_db")
)


# ─── Knowledge Base ────────────────────────────────────────────
KNOWLEDGE_DIR: str = str(_project_root / "knowledge")


# ─── RBAC Config ───────────────────────────────────────────────
RBAC_CONFIG_PATH: str = str(_project_root / "rbac_config.yaml")


# ─── Validation ────────────────────────────────────────────────
def validate():
    """Validate required configuration on startup."""
    errors = []

    if LLM_PROVIDER == "openai" and not OPENAI_API_KEY:
        errors.append(
            "OPENAI_API_KEY is required when LLM_PROVIDER=openai. "
            "Set it in your .env file."
        )
    elif LLM_PROVIDER == "anthropic" and not ANTHROPIC_API_KEY:
        errors.append(
            "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic. "
            "Set it in your .env file."
        )

    if not Path(SALES_DB_PATH).exists():
        errors.append(
            f"Sales database not found at '{SALES_DB_PATH}'. "
            f"Run 'python seed_database.py' first."
        )

    if errors:
        raise EnvironmentError(
            "Configuration errors:\n" + "\n".join(f"  • {e}" for e in errors)
        )


# Expose project root for other modules
PROJECT_ROOT = _project_root

"""
Schema RAG — Auto-introspects the SQLite database and provides
vector-based retrieval of relevant table schemas for a given query.

On initialization, reads all table definitions (columns, types, PKs, FKs)
from the sales database, generates rich text descriptions, and indexes
them in ChromaDB for similarity search.
"""

import sqlite3
import chromadb

from config import settings
from rag.embeddings import EmbeddingService, ChromaEmbeddingFunction


class SchemaRAG:
    """
    Retrieval-Augmented Generation layer for database schema.

    Auto-introspects the SQLite database to build a vector index of table
    schemas, enabling the SQL agent to retrieve only the relevant tables
    for a given natural language query.
    """

    COLLECTION_NAME = "schema_definitions"

    def __init__(
        self,
        db_path: str | None = None,
        chroma_dir: str | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self._db_path = db_path or settings.SALES_DB_PATH
        self._embedding_service = embedding_service or EmbeddingService()
        self._embed_fn = ChromaEmbeddingFunction(self._embedding_service)

        # Initialize ChromaDB persistent client
        self._chroma = chromadb.PersistentClient(
            path=chroma_dir or settings.CHROMA_PERSIST_DIR
        )
        self._collection = self._chroma.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embed_fn,
        )

        # Schema cache
        self._schema_texts: dict[str, str] = {}
        self._full_schema: str = ""

    def initialize(self) -> None:
        """
        Introspect the database and index all table schemas.

        Reads table definitions from SQLite and upserts them into ChromaDB.
        Safe to call multiple times — uses upsert for idempotency.
        """
        schemas = self._introspect_database()
        self._schema_texts = schemas

        # Build full schema text for prompts
        self._full_schema = "\n\n".join(schemas.values())

        # Upsert into ChromaDB
        if schemas:
            self._collection.upsert(
                ids=list(schemas.keys()),
                documents=list(schemas.values()),
                metadatas=[{"table_name": t} for t in schemas.keys()],
            )

    def retrieve_relevant_schema(
        self, query: str, top_k: int = 5
    ) -> list[str]:
        """
        Retrieve the most relevant table schemas for a natural language query.

        Args:
            query: The user's question in natural language.
            top_k: Maximum number of table schemas to return.

        Returns:
            List of table schema description strings, ranked by relevance.
        """
        if not self._schema_texts:
            self.initialize()

        # If we have fewer tables than top_k, return all
        if len(self._schema_texts) <= top_k:
            return list(self._schema_texts.values())

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, len(self._schema_texts)),
        )

        return results["documents"][0] if results["documents"] else []

    def get_full_schema(self) -> str:
        """Return the complete schema description for all tables."""
        if not self._full_schema:
            self.initialize()
        return self._full_schema

    def get_table_names(self) -> list[str]:
        """Return all table names in the database."""
        if not self._schema_texts:
            self.initialize()
        return list(self._schema_texts.keys())

    def _introspect_database(self) -> dict[str, str]:
        """
        Read all table definitions from the SQLite database.

        Returns:
            Dict mapping table_name -> rich text description of the table.
        """
        conn = sqlite3.connect(self._db_path)
        cursor = conn.cursor()

        # Get all table names
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'"
        )
        tables = [row[0] for row in cursor.fetchall()]

        schemas: dict[str, str] = {}

        for table in tables:
            # Get column info
            cursor.execute(f"PRAGMA table_info('{table}')")
            columns = cursor.fetchall()
            # columns: (cid, name, type, notnull, default, pk)

            # Get foreign keys
            cursor.execute(f"PRAGMA foreign_key_list('{table}')")
            fks = cursor.fetchall()
            # fks: (id, seq, table, from, to, ...)

            # Build FK lookup: column_name -> referenced table.column
            fk_map: dict[str, str] = {}
            for fk in fks:
                fk_map[fk[3]] = f"{fk[2]}.{fk[4]}"

            # Build column descriptions
            col_descs = []
            for col in columns:
                cid, name, col_type, notnull, default, pk = col
                parts = [f"{name} ({col_type})"]
                if pk:
                    parts.append("PRIMARY KEY")
                if notnull and not pk:
                    parts.append("NOT NULL")
                if default is not None:
                    parts.append(f"DEFAULT {default}")
                if name in fk_map:
                    parts.append(f"FOREIGN KEY → {fk_map[name]}")
                col_descs.append(", ".join(parts))

            # Get sample row count
            cursor.execute(f"SELECT COUNT(*) FROM '{table}'")
            row_count = cursor.fetchone()[0]

            # Build rich description
            schema_text = (
                f"Table: {table}\n"
                f"Row count: {row_count}\n"
                f"Columns:\n"
                + "\n".join(f"  - {desc}" for desc in col_descs)
            )

            # Add relationships summary
            if fk_map:
                rels = [f"  - {col} references {ref}" for col, ref in fk_map.items()]
                schema_text += "\nRelationships:\n" + "\n".join(rels)

            schemas[table] = schema_text

        conn.close()
        return schemas

"""
Knowledge RAG — Indexes business rules and domain knowledge from
markdown files for retrieval during chat and explanation queries.

Reads .md files from the knowledge/ directory, splits them into
sections by heading, and indexes each section in ChromaDB.
"""

import re
from pathlib import Path

import chromadb

from config import settings
from rag.embeddings import EmbeddingService, ChromaEmbeddingFunction


class KnowledgeRAG:
    """
    Retrieval-Augmented Generation layer for business knowledge.

    Indexes markdown documents containing business rules, domain terms,
    and calculation methods. Used by the chat handler to ground responses
    in domain-specific knowledge.
    """

    COLLECTION_NAME = "knowledge_base"

    def __init__(
        self,
        knowledge_dir: str | None = None,
        chroma_dir: str | None = None,
        embedding_service: EmbeddingService | None = None,
    ):
        self._knowledge_dir = Path(knowledge_dir or settings.KNOWLEDGE_DIR)
        self._embedding_service = embedding_service or EmbeddingService()
        self._embed_fn = ChromaEmbeddingFunction(self._embedding_service)

        self._chroma = chromadb.PersistentClient(
            path=chroma_dir or settings.CHROMA_PERSIST_DIR
        )
        self._collection = self._chroma.get_or_create_collection(
            name=self.COLLECTION_NAME,
            embedding_function=self._embed_fn,
        )
        self._indexed = False

    def initialize(self) -> None:
        """
        Read all knowledge documents and index them in ChromaDB.

        Splits markdown files into sections by heading and upserts each
        section as a separate document for fine-grained retrieval.
        """
        if not self._knowledge_dir.exists():
            return

        all_ids = []
        all_docs = []
        all_meta = []

        for md_file in sorted(self._knowledge_dir.glob("*.md")):
            sections = self._split_markdown(md_file)

            for i, (heading, content) in enumerate(sections):
                doc_id = f"{md_file.stem}_{i}"
                full_text = f"{heading}\n\n{content}" if heading else content

                all_ids.append(doc_id)
                all_docs.append(full_text)
                all_meta.append({
                    "source_file": md_file.name,
                    "heading": heading or "(no heading)",
                    "section_index": i,
                })

        if all_ids:
            self._collection.upsert(
                ids=all_ids,
                documents=all_docs,
                metadatas=all_meta,
            )

        self._indexed = True

    def retrieve_knowledge(
        self, query: str, top_k: int = 3
    ) -> list[str]:
        """
        Retrieve the most relevant knowledge sections for a query.

        Args:
            query: The user's question or topic.
            top_k: Maximum number of sections to return.

        Returns:
            List of knowledge text sections, ranked by relevance.
        """
        if not self._indexed:
            self.initialize()

        # Check if collection has any documents
        count = self._collection.count()
        if count == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, count),
        )

        return results["documents"][0] if results["documents"] else []

    @staticmethod
    def _split_markdown(filepath: Path) -> list[tuple[str, str]]:
        """
        Split a markdown file into sections by headings.

        Returns:
            List of (heading, content) tuples. The first section may
            have an empty heading if the file starts with content
            before any heading.
        """
        text = filepath.read_text(encoding="utf-8")

        # Split on markdown headings (## or ###)
        # Keep the heading as part of the split
        parts = re.split(r"(?m)^(#{1,3}\s+.+)$", text)

        sections: list[tuple[str, str]] = []

        # First part is content before any heading
        if parts[0].strip():
            sections.append(("", parts[0].strip()))

        # Remaining parts alternate between heading and content
        for i in range(1, len(parts), 2):
            heading = parts[i].strip().lstrip("#").strip()
            content = parts[i + 1].strip() if i + 1 < len(parts) else ""
            if content:
                sections.append((heading, content))

        return sections

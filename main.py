"""
NLP2SQL - Enterprise-Grade Text-to-SQL RAG Agent

An enterprise-grade Text-to-SQL system with:
- 5-stage intent detection pipeline
- RAG-based schema and knowledge retrieval (ChromaDB)
- Role-based access control (RBAC)
- Multi-layer security (prompt injection, SQL validation)
- PostgreSQL conversation history
- Multi-provider LLM support (OpenAI, Anthropic)

Usage:
    1. Seed the database:  python seed_database.py
    2. Run interactively:  python main.py
"""

import sys

from config import settings
from orchestrator.engine import OrchestratorEngine, OrchestratorResponse


def _print_banner():
    """Print the application banner."""
    print()
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║        NLP2SQL — Enterprise Text-to-SQL RAG Agent          ║")
    print("║        Powered by RAG + RBAC + Multi-Layer Security        ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()


def _print_help():
    """Print available commands."""
    print("  Commands:")
    print("    /help    — Show this help")
    print("    /role    — Show current RBAC role")
    print("    /schema  — Show indexed database schema")
    print("    /history — Show conversation history")
    print("    /quit    — Exit the application")
    print()
    print("  Example questions:")
    print('    • "Show total sales for each product last month"')
    print('    • "Which region has the most customers?"')
    print('    • "What is revenue?" (knowledge base)')
    print('    • "Top 5 products by profit margin"')
    print()


def _format_data_table(columns: list[str], data: list[list]) -> str:
    """Format query results as a readable ASCII table."""
    if not data:
        return "  (no data)"

    # Calculate column widths
    all_rows = [columns] + data
    widths = []
    for col_idx in range(len(columns)):
        max_width = max(
            len(str(row[col_idx])) if col_idx < len(row) else 0
            for row in all_rows
        )
        widths.append(min(max_width, 30))  # Cap at 30 chars

    # Build table
    lines = []
    separator = "─┼─".join("─" * w for w in widths)

    # Header
    header = " │ ".join(
        str(col).ljust(widths[i])[:widths[i]]
        for i, col in enumerate(columns)
    )
    lines.append(f"  {header}")
    lines.append(f"  {separator}")

    # Data rows
    for row in data:
        formatted_row = " │ ".join(
            str(row[i] if i < len(row) else "").ljust(widths[i])[:widths[i]]
            for i in range(len(columns))
        )
        lines.append(f"  {formatted_row}")

    return "\n".join(lines)


def _print_response(response: OrchestratorResponse):
    """Print a formatted response to the terminal."""
    print()

    if response.is_clarification:
        print(f"  🤔 {response.response_text}")
    elif response.is_error:
        print(f"  ⚠️  {response.response_text}")
    else:
        # Print natural language response
        print(f"  💬 {response.response_text}")

        # Print SQL if present
        if response.sql:
            print(f"\n  📝 SQL: {response.sql}")

        # Print data table if present
        if response.data and response.columns:
            print(f"\n{'─' * 70}")
            print(_format_data_table(response.columns, response.data))
            print(f"{'─' * 70}")
            print(f"  ({response.row_count} rows returned)")

    # Print metadata
    if response.intent:
        confidence_bar = "█" * int(response.confidence * 10)
        confidence_empty = "░" * (10 - int(response.confidence * 10))
        print(
            f"\n  ℹ️  Intent: {response.intent} "
            f"[{confidence_bar}{confidence_empty}] "
            f"{response.confidence:.0%}"
        )

    print()


def _select_session(engine: OrchestratorEngine) -> str:
    """Let the user select a new or existing session."""
    sessions = engine.list_sessions(limit=5)

    if not sessions:
        session_id = engine.create_session()
        print(f"  📝 New session created: {session_id}\n")
        return session_id

    print("  📋 Recent sessions:")
    for i, s in enumerate(sessions):
        created = s["created_at"].strftime("%Y-%m-%d %H:%M") if s["created_at"] else "?"
        print(
            f"    [{i + 1}] {s['session_id']} — "
            f"{s['message_count']} messages "
            f"({created})"
        )
    print(f"    [N] Start new session")
    print()

    choice = input("  Select session (number or N): ").strip().upper()

    if choice == "N" or not choice:
        session_id = engine.create_session()
        print(f"\n  📝 New session created: {session_id}\n")
        return session_id

    try:
        idx = int(choice) - 1
        if 0 <= idx < len(sessions):
            session_id = sessions[idx]["session_id"]
            print(f"\n  🔄 Resuming session: {session_id}\n")
            return session_id
    except ValueError:
        pass

    # Default to new session
    session_id = engine.create_session()
    print(f"\n  📝 New session created: {session_id}\n")
    return session_id


def main():
    """Main entry point for the CLI application."""
    _print_banner()

    # Validate configuration
    try:
        settings.validate()
    except EnvironmentError as e:
        print(f"  ❌ {e}")
        sys.exit(1)

    # Initialize engine
    try:
        engine = OrchestratorEngine()
    except Exception as e:
        print(f"  ❌ Failed to initialize: {e}")
        sys.exit(1)

    # Session selection
    session_id = _select_session(engine)

    _print_help()

    # Main loop
    while True:
        try:
            user_input = input("🔍 Your question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye! 👋")
            break

        if not user_input:
            continue

        # Handle commands
        cmd = user_input.lower()
        if cmd in ("/quit", "/exit", "quit", "exit", "q"):
            print("  Goodbye! 👋")
            break
        elif cmd == "/help":
            _print_help()
            continue
        elif cmd == "/role":
            print(f"\n  🔒 Current role: {settings.USER_ROLE}")
            roles = engine._rbac.list_roles()
            print(f"  Available roles: {', '.join(roles)}\n")
            continue
        elif cmd == "/schema":
            schema = engine._schema_rag.get_full_schema()
            print(f"\n{schema}\n")
            continue
        elif cmd == "/history":
            history = engine._conversation_store.get_history(
                session_id, limit=10
            )
            if not history:
                print("\n  (no messages yet)\n")
            else:
                print()
                for msg in history:
                    role_icon = "👤" if msg.role == "user" else "🤖"
                    time_str = msg.timestamp.strftime("%H:%M:%S")
                    content_preview = msg.content[:100]
                    print(f"  {role_icon} [{time_str}] {content_preview}")
                print()
            continue

        # Process message
        try:
            response = engine.process_message(user_input, session_id)
            _print_response(response)
        except Exception as e:
            print(f"\n  ❌ Error: {e}\n")

    # Cleanup
    engine.close()


if __name__ == "__main__":
    main()

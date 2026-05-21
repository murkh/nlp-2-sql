"""
NLP2SQL - Natural Language to SQL for Sales Management

A complete implementation following AWS best practices for enterprise-grade
Text2SQL generation using LLMs (OpenAI GPT).

Usage:
    1. Seed the database:  python seed_database.py
    2. Run interactively:  python main.py
    3. Run test suite:     python test_drive_text_to_sql_flow.py
"""

import text_to_sql_flow


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║       NLP2SQL - Sales Management Query Assistant            ║")
    print("║       Powered by OpenAI (GPT-4o-mini)                       ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    print("Ask questions about your sales data in plain English.")
    print("Examples:")
    print('  • "Show total sales for each product last month"')
    print('  • "Which products generated more revenue?"')
    print('  • "What percentage of customers are from each region?"')
    print()
    print("Type 'quit' or 'exit' to stop.\n")

    flow = text_to_sql_flow.TextToSQLFlow()

    while True:
        try:
            user_input = input("🔍 Your question: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        try:
            results, status, clarification = flow.run(user_input)

            if status == "clarification":
                print(f"\n🤔 {clarification}\n")
            elif status == "success" and results:
                print(f"\n{'─' * 60}")
                # Print header
                header = results[0]
                print(" | ".join(str(h).ljust(20) for h in header))
                print("-" * (22 * len(header)))
                # Print data rows
                for row in results[1:]:
                    print(" | ".join(str(val).ljust(20) for val in row))
                print(f"{'─' * 60}")
                print(f"  ({len(results) - 1} rows returned)\n")
            else:
                print(
                    f"\n  ⚠️  Query failed (status: {status}). Please try rephrasing.\n"
                )

        except Exception as e:
            print(f"\n  ❌ Error: {e}\n")


if __name__ == "__main__":
    main()

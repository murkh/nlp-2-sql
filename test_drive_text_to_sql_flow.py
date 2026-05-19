"""
Test Driver - Run the NLP2SQL pipeline against test cases.

Usage:
    python test_drive_text_to_sql_flow.py              # Run all test cases
    python test_drive_text_to_sql_flow.py 0 3          # Run test cases 0 through 2
    python test_drive_text_to_sql_flow.py --query "Show total sales by product"  # Run a custom query
"""

import sys
import test_cases
import text_to_sql_flow


def format_results(results: list) -> str:
    """Format query results as a readable table."""
    if not results:
        return "  (no results)"

    # Calculate column widths
    col_widths = []
    for col_idx in range(len(results[0])):
        max_width = max(len(str(row[col_idx])) for row in results)
        col_widths.append(max(max_width, 8))

    lines = []
    for i, row in enumerate(results):
        formatted = " | ".join(
            str(val).ljust(col_widths[j]) for j, val in enumerate(row)
        )
        lines.append(f"  {formatted}")
        if i == 0:
            separator = "-+-".join("-" * w for w in col_widths)
            lines.append(f"  {separator}")

    return "\n".join(lines)


def run_test(
    flow: text_to_sql_flow.TextToSQLFlow,
    query: str,
    index: int = -1,
    run_eval: bool = False,
):
    """Run a single query through the pipeline and display results."""
    prefix = f"Test {index}" if index >= 0 else "Query"
    print(f"\n{'═' * 70}")
    print(f"  {prefix}: {query}")
    print(f"{'═' * 70}")

    try:
        results, status, clarification, generated_sql = flow.run(query)
        print(f"\n  Status: {status}")
        if status == "clarification":
            print(f"\n  Clarification Needed: {clarification}")
        else:
            print(f"\n{format_results(results)}")

            if run_eval and generated_sql:
                import evaluator

                judge = evaluator.LlmJudgeEvaluator(flow.llm_facade)
                # The domain for these test cases is "sales"
                eval_report = judge.evaluate_query(
                    query, generated_sql, results, "sales"
                )
                if eval_report:
                    print(f"\n  🤖 LLM JUDGE EVALUATION REPORT:")
                    print(
                        f"    Correctness Score: {eval_report.get('correctness_score')}/5"
                    )
                    print(
                        f"    Schema/Rule Adherence: {eval_report.get('adherence_score')}/5"
                    )
                    print(f"    Explanation: {eval_report.get('explanation')}")
                else:
                    print(f"\n  ⚠️ LLM Judge failed to generate evaluation report.")
    except Exception as e:
        print(f"\n  ❌ Error: {e}")

    print(f"{'═' * 70}\n")


if __name__ == "__main__":
    flow: text_to_sql_flow.TextToSQLFlow = text_to_sql_flow.TextToSQLFlow()
    test_suite = test_cases.TestCases()

    run_eval = False
    if "--eval" in sys.argv:
        run_eval = True
        sys.argv.remove("--eval")

    if "--query" in sys.argv:
        # Run a custom query
        query_idx = sys.argv.index("--query")
        custom_query = " ".join(sys.argv[query_idx + 1 :])
        run_test(flow, custom_query, run_eval=run_eval)

    elif len(sys.argv) == 3:
        # Run a range of test cases
        start, end = int(sys.argv[1]), int(sys.argv[2])
        for i in range(start, end):
            query = test_suite.get_test_case(i)
            if query:
                run_test(flow, query, i, run_eval=run_eval)

    else:
        # Run all test cases
        all_cases = test_suite.get_all_test_cases()
        for i, query in enumerate(all_cases):
            run_test(flow, query, i, run_eval=run_eval)

"""
Test Cases for the Sales Management NLP2SQL System.

Contains a curated set of natural language queries spanning the key
sales analytics use cases that this system is designed to handle.
"""


class TestCases:

    @staticmethod
    def get_test_case(index: int) -> str:
        """Return a test query by index."""
        queries = [
            # ── Revenue & Product Analytics ──
            "Show total sales for each product last month",
            "Which products generated more revenue?",
            "Which category has the highest profit margin?",
            "Show the top 5 best-selling products by quantity",

            # ── Customer & Regional Analytics ──
            "What percentage of customers are from each region?",
            "Show the top 5 customers by total spending",
            "What is the average order value by customer segment?",

            # ── Time-based Analytics ──
            "What is the monthly sales trend for this year?",
            "How many orders were placed each month last quarter?",

            # ── Sales Rep Performance ──
            "Which sales rep has the highest sales?",
            "Show sales performance by region",

            # ── Inventory ──
            "Show products with low stock",
            "How many products do we have in each category?",
        ]

        if index < 0 or index >= len(queries):
            print(f"Test input index: {index} is out of bounds (0-{len(queries)-1})")
            return ""

        return queries[index]

    @staticmethod
    def get_all_test_cases() -> list:
        """Return all test cases."""
        cases = []
        i = 0
        while True:
            case = TestCases.get_test_case(i)
            if case == "":
                break
            cases.append(case)
            i += 1
        return cases

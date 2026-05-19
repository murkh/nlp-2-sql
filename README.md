# NLP2SQL - Sales Management Query Assistant

> Natural Language to SQL generation for sales analytics, following [Google Cloud](https://cloud.google.com/blog/products/databases/techniques-for-improving-text-to-sql) and [AWS](https://aws.amazon.com/blogs/machine-learning/generating-value-from-enterprise-data-best-practices-for-text2sql-and-generative-ai/) enterprise best practices.

## Overview

This application converts plain English questions about sales data into SQL queries using OpenAI (`gpt-4o-mini` by default). It implements state-of-the-art techniques for improving Text-to-SQL accuracy, including disambiguation, data sampling, SQL validation with reprompting, self-consistency ranking, and LLM-as-a-judge evaluation.

### Example Questions
```
"Show total sales for each product last month" (Clear)
"Which products generated more revenue?" (Ambiguous - triggers disambiguation)
"What percentage of customers are from each region?" (Clear)
"What is the monthly sales trend for this year?" (Clear)
```

## Architecture & Enhanced Features

```
          User Query
               │
               ▼
      ┌──────────────────┐
      │  PreProcess      │ ← Domain classification + NER
      └────────┬─────────┘
               │
               ▼
      ┌──────────────────┐
      │  Disambiguation  │ ← Detects ambiguity & returns clarifying questions
      └────────┬─────────┘   (if enabled & ambiguous)
               │ (Clear)
               ▼
      ┌──────────────────┐
      │   Resolve IDs    │ ← Maps named resources to DB identifiers
      └────────┬─────────┘
               │
               ▼
      ┌──────────────────┐
      │  Prepare Request │ ← Dynamically injects live database sample rows
      │  (Data Sampler)  │   and categories to enrich schema context
      └────────┬─────────┘
               │
               ▼
      ┌──────────────────┐
      │   Generate SQL   │
      │                  │ ── (If Self-Consistency Enabled) ──┐
      │ ┌──────────────┐ │                                    ▼
      │ │ Single-Shot  │ │                          ┌──────────────────┐
      │ └──────┬───────┘ │                          │ Generate N       │
      │        │         │                          │ Candidates       │
      │        ▼         │                          └────────┬─────────┘
      │ ┌──────────────┐ │                                   │
      │ │ SQL Validate │ │                                   ▼
      │ │  & Reprompt  │ │                          ┌──────────────────┐
      │ └──────┬───────┘ │                          │ Validate &       │
      │        │         │                          │ LLM Selector     │
      └────────┼─────────┘                          └────────┬─────────┘
               │                                             │
               └──────────────────────┬──────────────────────┘
                                      │
                                      ▼
                             ┌──────────────────┐
                             │   Execute SQL    │ ← Runs query on SQLite
                             └────────┬─────────┘
                                      │
                                      ▼
                                Query Results
                                      │
                         (Optional --eval requested)
                                      ▼
                             ┌──────────────────┐
                             │  LLM-as-a-Judge  │ ← Evaluates Correctness and
                             │    Evaluation    │   Schema/Rule Adherence
                             └──────────────────┘
```

## Implemented Enhancements

| Enhancement | Description | Configuration Toggle |
|-------------|-------------|----------------------|
| **Disambiguation** | Classifies query clarity; prompts user if intent is vague or lacks context. | `ENABLE_DISAMBIGUATION = True` |
| **SQL Validation & Reprompting** | Runs dry-run validation using `EXPLAIN` on a temp connection and provides error feedback up to `MAX_REPROMPT_ATTEMPTS` times. | `MAX_REPROMPT_ATTEMPTS = 2` |
| **Data Sampling** | Automatically queries database for 3 sample rows per table plus low cardinality distinct values, augmenting schema context. | *Always Active* |
| **Self-Consistency** | Generates multiple query candidates at varying temperatures and chooses the optimal query using an LLM-as-a-judge selector. | `ENABLE_SELF_CONSISTENCY = False` (Opt-in) |
| **LLM-as-a-Judge Evaluation** | Automated 1-5 scoring for correctness and rule adherence. | Run with `--eval` flag |

---

## Database Schema

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   products   │     │   customers  │     │  sales_reps  │
│──────────────│     │──────────────│     │──────────────│
│ product_id   │     │ customer_id  │     │ rep_id       │
│ product_name │     │ customer_name│     │ rep_name     │
│ category     │     │ region       │     │ region       │
│ unit_price   │     │ country      │     │ hire_date    │
│ cost_price   │     │ segment      │     └──────┬───────┘
│ stock_qty    │     │ created_at   │            │
└──────┬───────┘     └──────┬───────┘            │
       │                    │                    │
       │              ┌─────┴──────┐      ┌──────┴──────────┐
       │              │   orders   │      │order_assignments │
       │              │────────────│      │─────────────────│
       │              │ order_id   │──────│ order_id        │
       │              │ customer_id│      │ rep_id          │
       │              │ order_date │      └─────────────────┘
       │              │ status     │
       │              │ total_amt  │
       │              └─────┬──────┘
       │                    │
       │              ┌─────┴──────┐
       └──────────────│order_items │
                      │────────────│
                      │ item_id    │
                      │ order_id   │
                      │ product_id │
                      │ quantity   │
                      │ unit_price │
                      │ discount   │
                      │ line_total │
                      └────────────┘
```

---

## Setup

### Prerequisites
- Python 3.9+
- OpenAI API Key

### Installation

1. Install dependencies:
   ```bash
   pip install openai python-dotenv
   ```
2. Configure environment:
   Create a `.env` file (based on `.env.example`):
   ```
   OPENAI_API_KEY=your-api-key-here
   OPENAI_MODEL=gpt-4o-mini
   ```
3. Seed the database with sample sales data:
   ```bash
   python3 seed_database.py
   ```

---

## Usage

### 1. Interactive Mode
Run the REPL console to ask queries and get immediate results:
```bash
python3 main.py
```

### 2. Test Driver
Run the standard test suite to see the pipeline process pre-configured queries:
```bash
python3 test_drive_text_to_sql_flow.py
```

### 3. Test Range
Run a specific slice of the test suite (e.g., test cases 0 and 1):
```bash
python3 test_drive_text_to_sql_flow.py 0 2
```

### 4. Custom Query Testing
```bash
python3 test_drive_text_to_sql_flow.py --query "Show total sales by product"
```

### 5. Automated Evaluation Run
Append `--eval` to run LLM-as-a-judge evaluation for the executed queries:
```bash
python3 test_drive_text_to_sql_flow.py 0 1 --eval
```

---

## Project Structure

```
text2SQL/
├── main.py                          # Interactive REPL loop
├── text_to_sql_flow.py              # Pipeline orchestrator
├── pre_process_request.py           # Domain classification & NER
├── identity_service_facade.py       # ID resolution for named entities
├── prepare_request.py               # Dynamic prompt preparation
├── data_sampler.py                  # Live schema sampling & metadata extraction
├── sql_validator.py                 # SQLite EXPLAIN parser & safety validation
├── self_consistency.py              # Candidate generation & LLM selector judge
├── evaluator.py                     # LLM-as-a-judge offline evaluator
├── llm_facade.py                    # OpenAI client handler & backoff retries
├── rdbms_facade.py                  # SQLite database wrapper
├── app_constants.py                 # Feature configuration toggles
├── domains/
│   ├── __init__.py                  # Domain specification registry
│   └── context_specs/
│       └── sales.py                 # Sales schema definitions, business rules
├── seed_database.py                 # Database initialization
├── test_cases.py                    # Pre-defined test cases
└── test_drive_text_to_sql_flow.py   # Test range runner & evaluation interface
```

"""
LLM Facade - Abstraction layer for LLM services.

This module provides a consistent interface for invoking LLMs,
implemented via the OpenAI Chat Completions API.

Best Practices Applied:
- Low temperature (0.05) for deterministic SQL generation
- Stop sequences to control output format
- JSON output parsing with error handling
- Reusable client instance for connection pooling
"""

import json
import time
from openai import OpenAI, OpenAIError

import app_constants as app_consts

import logging

logger = logging.getLogger(__name__)


class LlmFacade:
    def __init__(self, model: str):
        self.model = model
        self.client = OpenAI(api_key=app_consts.OPENAI_API_KEY)

    def invoke(self, llm_prompt: str, temperature: float = 0.05) -> dict:
        """
        Invoke the LLM with the given prompt and return a dictionary containing:
        - llm_output: the parsed JSON output from the LLM (or None on failure)
        - processing_status: 'success' or 'fail'
        """
        generated_json = {}

        # Call the OpenAI API
        llm_output = self.query_openai(llm_prompt, temperature)

        generated_json[app_consts.LLM_OUTPUT] = llm_output

        if llm_output is not None:
            generated_json[app_consts.PROCESSING_STATUS] = app_consts.SUCCESS
        else:
            generated_json[app_consts.PROCESSING_STATUS] = app_consts.FAIL

        return generated_json

    def query_openai(
        self, payload: str, temperature: float = 0.05, max_retries: int = 3
    ):
        """
        Send a prompt to OpenAI using the Chat Completions API with JSON mode.
        Returns parsed JSON or None on failure.
        """
        result = None
        attempt = 0
        backoff = 1.0

        while attempt < max_retries:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": payload}],
                    response_format={"type": "json_object"},
                    temperature=temperature,
                    max_tokens=1024,
                    top_p=0.95,
                )

                # Extract the generated text content from the response
                completion = response.choices[0].message.content
                # Parse JSON output
                result = json.loads(completion.strip())
                logger.info("LLM generated SQL successfully via JSON mode")
                return result

            except OpenAIError as err:
                attempt += 1
                logger.warning(f"OpenAI API error on attempt {attempt}: {err}")
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(
                        f"OpenAI API failed after {max_retries} attempts: {err}"
                    )
                    result = None
            except (ValueError, json.JSONDecodeError) as err:
                attempt += 1
                logger.warning(f"JSON parsing error on attempt {attempt}: {err}")
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    logger.error(f"Failed to decode JSON after {max_retries} attempts")
                    result = None

        return result

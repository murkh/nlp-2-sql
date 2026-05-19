"""
Pre-Process Request - First step in the NLP2SQL pipeline.

This module classifies the user's natural language query into a domain
and extracts any named resources (entities) from the query.

Best Practices Applied (from AWS blog):
- Domain classification narrows the scope for SQL generation
- Named entity extraction enables identifier resolution
- LLM-based classification for robust domain detection
"""

import app_constants as app_consts
import llm_facade
import domains

import logging
logger = logging.getLogger(__name__)


class PreProcessRequest:

    def __init__(self, llm_inference: llm_facade.LlmFacade):
        self.llm_inference = llm_inference

    def run(self, user_request: str) -> dict:
        """
        Pre-process the user request to determine:
        1. The domain (e.g., 'sales')
        2. Any named resources referenced in the query

        Returns a dictionary with keys: user_query, domain, named_resources
        """
        pre_processed_request = {
            app_consts.USER_QUERY: user_request,
            app_consts.DOMAIN: self.determine_domain(user_request),
            app_consts.NAMED_RESOURCES: self.get_named_resources_from_user_request(user_request),
        }

        logger.info(
            f"PreProcess: domain={pre_processed_request[app_consts.DOMAIN]}, "
            f"named_resources={pre_processed_request[app_consts.NAMED_RESOURCES]}"
        )

        return pre_processed_request

    def determine_domain(self, user_request: str) -> str:
        """
        Use the LLM to classify the user's query into a known domain.
        Falls back to 'unknown' if classification fails or returns unrecognized domain.
        """
        prompt = app_consts.DOMAIN_CLASSIFICATION_PROMPT + user_request + "\n"
        domain_inference = self.llm_inference.invoke(prompt)

        if domain_inference[app_consts.PROCESSING_STATUS] == app_consts.FAIL:
            logger.warning("Domain classification failed, returning unknown")
            return domains.DOMAIN_UNKNOWN

        llm_output = domain_inference[app_consts.LLM_OUTPUT]
        determined_domain = llm_output.get(app_consts.DOMAIN, domains.DOMAIN_UNKNOWN)

        if determined_domain in domains.contexts.keys():
            return determined_domain
        else:
            logger.warning(f"LLM returned unrecognized domain: {determined_domain}")
            return domains.DOMAIN_UNKNOWN

    @staticmethod
    def get_named_resources_from_user_request(user_request: str) -> set:
        """
        Extract named resources from the user request.

        For the sales domain, most queries are analytical (aggregations, trends)
        rather than entity-specific, so named resource extraction is lightweight.
        In production, this could use NER via Amazon Comprehend or an LLM.
        """
        from identity_service_facade import IdentityServiceFacade

        named_resources = set()

        # Clean the user request
        clean_request = user_request.replace(",", " ").replace(".", " ").replace("?", " ").replace("!", " ")
        clean_request = clean_request.lower().strip()

        # Check for multi-word named resources (sliding window approach)
        words = clean_request.split()
        for i in range(len(words)):
            # Check 3-word combinations
            if i + 2 < len(words):
                trigram = f"{words[i]} {words[i+1]} {words[i+2]}"
                if IdentityServiceFacade.is_named_resource(trigram):
                    named_resources.add(trigram)
                    continue
            # Check 2-word combinations
            if i + 1 < len(words):
                bigram = f"{words[i]} {words[i+1]}"
                if IdentityServiceFacade.is_named_resource(bigram):
                    named_resources.add(bigram)

        return named_resources

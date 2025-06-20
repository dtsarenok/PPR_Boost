import requests
import json
import time
import random
import logging

from config.settings import FNS_SME_REGISTER_URL, USER_AGENT


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)





class FNSApiClient:


    def __init__(self):
        self.headers = {"User-Agent": USER_AGENT}
        # In a real scenario, this URL would be used for actual requests.
        # For simulation, it's merely a placeholder.
        self.sme_register_url = FNS_SME_REGISTER_URL
        logger.info("FNSApiClient initialized (simulation mode).")

    def get_company_sme_status(self, inn: str) -> dict:

        if not isinstance(inn, str) or not inn.isdigit() or len(inn) not in [10, 12]:
            logger.warning(f"Simulated invalid INN format received: {inn}. Returning None.")
            return None  # Simulate an error for invalid input

        logger.info(f"Simulating SME status check for INN: {inn}")


        time.sleep(random.uniform(0.1, 0.5))

        if random.random() < 0.05:
            logger.error(f"Simulated API error for INN {inn}: Service unavailable.")
            return None

        is_sme_flag = random.random() < 0.35


        if is_sme_flag:

            revenue = random.randint(1, 800)
            employees = random.randint(1, 100)
        else:

            revenue = random.randint(801, 500000)
            employees = random.randint(101, 10000)

        sme_data = {
            "inn": inn,
            "name": f"Simulated Company for INN {inn}",
            "is_sme": is_sme_flag,
            "revenue_mln_rub": revenue,
            "employees": employees
        }
        logger.debug(f"Simulated data for INN {inn}: {sme_data}")
        return sme_data
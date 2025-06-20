# src/data_preprocessing/data_cleaner.py

import re
import logging

logger = logging.getLogger(__name__)

class DataCleaner:
    def __init__(self, major_azs_networks: list = None):
        logger.info("DataCleaner initialized with compiled regex patterns.")
        self.inn_pattern = re.compile(r'\bINN_(\d{10})\b|\bИНН[:\s]*(\d{10})(?:[^\d]|$)', re.IGNORECASE)
        self.kpp_pattern = re.compile(r'\bKPP_(\d{9})\b|\bКПП[:\s]*(\d{9})(?:[^\d]|$)', re.IGNORECASE)
        self.okved_pattern = re.compile(r'\bОКВЭД[:\s]*(\d{2}(?:\.\d{1,2}){0,2})\b', re.IGNORECASE)
        self.phone_pattern = re.compile(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}|\b\d{3}[\s\-]?\d{3}[\s\-]?\d{4}\b')
        self.email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        self.price_pattern = re.compile(r'(\d[\d\s,.]*\d)\s*(?:руб|руб\.|₽|рублей|р\.)', re.IGNORECASE)

        self.major_azs_networks = major_azs_networks if major_azs_networks is not None else []


    def clean_text(self, text: str) -> str:
        if not isinstance(text, str):
            return ""
        return " ".join(text.lower().split())

    def extract_inn(self, text: str) -> str:
        if not isinstance(text, str): return ""
        match = self.inn_pattern.search(text)
        return match.group(1) or match.group(2) if match else ""

    def extract_kpp(self, text: str) -> str:
        if not isinstance(text, str): return ""
        match = self.kpp_pattern.search(text)
        return match.group(1) or match.group(2) if match else ""

    def extract_okved(self, text: str) -> str:
        if not isinstance(text, str): return ""
        match = self.okved_pattern.search(text)
        return match.group(1) if match else ""

    def extract_phone(self, text: str) -> str:
        if not isinstance(text, str): return ""
        match = self.phone_pattern.search(text)
        return match.group(0) if match else ""

    def extract_email(self, text: str) -> str:
        if not isinstance(text, str): return ""
        match = self.email_pattern.search(text)
        return match.group(0) if match else ""

    def extract_price(self, text: str) -> float:
        if not isinstance(text, str): return 0.0
        match = self.price_pattern.search(text)
        if match:

            price_str = match.group(1).replace(' ', '').replace(',', '.')
            try:
                return float(price_str)
            except ValueError:
                return 0.0
        return 0.0


    def extract_azs_networks(self, text: str) -> list:
        if not isinstance(text, str):
            return []
        found_networks = []
        text_lower = text.lower()
        for network in self.major_azs_networks:
            if network.lower() in text_lower:
                found_networks.append(network)
        return found_networks

    def parse_tender_characteristics(self, characteristics_str: str) -> dict:

        if not characteristics_str:
            return {}
        try:

            return json.loads(characteristics_str)
        except json.JSONDecodeError:
            logger.warning(f"Не удалось распарсить характеристики как JSON: '{characteristics_str}'. Возвращаю пустой словарь.")
            return {}
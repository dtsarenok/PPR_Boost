# src/data_preprocessing/feature_engineer.py

import pandas as pd
from datetime import datetime
import json
import logging
from src.data_preprocessing.cleaner import DataCleaner

logger = logging.getLogger(__name__)

MAJOR_AZS_NETWORKS = [
    "Газпромнефть", "Лукойл", "Роснефть", "Башнефть", "Татнефть",
    "BP", "Шелл", "ТНК", "ННК", "Газпром", "Сургутнефтегаз",
    "Нефтегазхолдинг", "Альянс", "Иркутскнефтепродукт"
]

def transliterate_cyrillic_to_latin(text):

    translit_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o',
        'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu',
        'я': 'ya', ' ': '_', '-': '_'
    }
    result = []
    for char in text.lower():
        result.append(translit_map.get(char, char)) # Если символа нет в карте, оставляем как есть
    return ''.join(result)

class FeatureEngineer:
    def __init__(self):
        self.cleaner = DataCleaner(major_azs_networks=MAJOR_AZS_NETWORKS)
        logger.info("FeatureEngineer инициализирован.")

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Начинаю создание признаков...")

        required_cols = [
            'tender_platform_id', 'tender_link', 'status', 'stage', 'purchase_method',
            'customer_name', 'customer_inn', 'customer_kpp', 'publication_date',
            'start_date', 'end_date', 'max_contract_price', 'contract_security_percent',
            'contract_security_amount', 'application_security_percent',
            'application_security_amount', 'quantity_indeterminable', 'total_initial_sum',
            'region', 'customer_link', 'purchase_objects'
        ]
        for col in ['tender_id', 'link', 'currency', 'contract_duration_days',
                    'payment_type_prepayment', 'prepayment_percentage',
                    'payment_deferral_days', 'contract_terms_raw',
                    'payment_conditions_raw', 'azs_network_raw', 'target', 'title']:
            if col not in df.columns:
                df[col] = ''
                logger.warning(f"Колонка '{col}' отсутствует в DataFrame для FeatureEngineer. Добавляем заглушку.")

        if 'customer_inn' in df.columns:
            df['customer_inn_clean'] = df['customer_inn'].apply(self.cleaner.extract_inn)
        if 'customer_kpp' in df.columns:
            df['customer_kpp_clean'] = df['customer_kpp'].apply(self.cleaner.extract_kpp)

        for col in ['publication_date', 'start_date', 'end_date']:
            if col in df.columns:
                df[f'{col}_dt'] = pd.to_datetime(df[col], errors='coerce', dayfirst=True)
                df[f'{col}_year'] = df[f'{col}_dt'].dt.year
                df[f'{col}_month'] = df[f'{col}_dt'].dt.month
                df[f'{col}_day'] = df[f'{col}_dt'].dt.day

        if 'start_date_dt' in df.columns and 'end_date_dt' in df.columns:
            df['tender_duration_days'] = (df['end_date_dt'] - df['start_date_dt']).dt.days.fillna(0).astype(int)

        for col in ['max_contract_price', 'contract_security_amount', 'application_security_amount', 'total_initial_sum']:
            if col in df.columns:
                df[f'{col}_num'] = pd.to_numeric(
                    df[col].astype(str).str.replace(' ', '').str.replace(',', '.'),
                    errors='coerce'
                ).fillna(0.0)

        if 'purchase_objects' in df.columns:
            df['num_purchase_objects'] = df['purchase_objects'].apply(lambda x: len(x) if isinstance(x, list) else 0)
            df['all_item_names'] = df['purchase_objects'].apply(
                lambda x: [obj['item_name'] for obj in x if isinstance(obj, dict) and 'item_name' in obj] if isinstance(x, list) else []
            )
            df['all_characteristics'] = df['purchase_objects'].apply(
                lambda x: [obj['characteristics'] for obj in x if isinstance(obj, dict) and 'characteristics' in obj] if isinstance(x, list) else []
            )

        df['required_azs_networks'] = df['azs_network_raw'].apply(self.cleaner.extract_azs_networks)

        for network in MAJOR_AZS_NETWORKS:

            col_name = f"azs_{transliterate_cyrillic_to_latin(network)}_required"
            df[col_name] = df['required_azs_networks'].apply(lambda x: network in x)

        df['is_sme'] = df['customer_name'].apply(lambda x: 'малое предпринимательство' in x.lower() or 'смп' in x.lower())

        if 'title' in df.columns:
            df['title_length'] = df['title'].apply(lambda x: len(str(x)) if x else 0)
        else:
            df['title_length'] = 0

        logger.info("Создание признаков завершено.")
        return df
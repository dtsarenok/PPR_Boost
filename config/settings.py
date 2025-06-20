# config/settings.py

import os
from dotenv import load_dotenv

load_dotenv()  # Загружаем переменные окружения из .env

# Базовый путь проекта
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Настройки базы данных
# Использование os.path.join для создания кроссплатформенного пути
DATABASE_FILE_NAME = 'test_sales_leads.db'  # Отдельная переменная для имени файла
DATABASE_DIR = os.path.join(BASE_DIR, 'data')
DATABASE_URL = f"sqlite:///{os.path.join(DATABASE_DIR, DATABASE_FILE_NAME)}"

# --- Настройки для скрапинга ---
ZAKUPKI_GOV_URL = "https://zakupki.gov.ru/epz/order/extendedsearch/results.html"
FNS_SME_REGISTER_URL = "https://rmsp.nalog.ru/"


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36"


SCRAPER_HEADERS = {
    "User-Agent": USER_AGENT, # Используем определенный выше USER_AGENT
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.9",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Connection": "keep-alive"
}

SCRAPER_DELAY_MIN = 1.0
SCRAPER_DELAY_MAX = 5.0

# Пути к данным
MODELS_PATH = os.path.join(BASE_DIR, "data", "models")
# Полный путь к файлу модели для предсказаний
PREDICTOR_MODEL_PATH = os.path.join(MODELS_PATH, "tender_prediction_model.pkl")


TENDER_KEYWORDS_FUEL = [
    "топливо по картам", "ГСМ", "бензин", "дизельное топливо",
    "автопарк", "заправка", "корпоративное топливо", "флит-менеджмент",
    "горюче-смазочные материалы"
]

# Крупные сети АЗС
MAJOR_AZS_NETWORKS = [
    "Газпромнефть", "Лукойл", "Роснефть", "Башнефть", "Татнефть",
    "Сургутнефтегаз", "Нефтегазхолдинг", "Иркутскоил", "Альянс"
]

# Параметры ML-модели
FEATURES_LIST = [
    'max_contract_price',
    'contract_duration_days',
    'payment_type_prepayment',
    'prepayment_percentage',
    'payment_deferral_days',
    'is_sme',
    'title_length',

    # Булевы флаги наличия конкретных АЗС в описании/наименовании объекта закупки
    'azs_gazpromneft_required',
    'azs_lukoil_required',
    'azs_rosneft_required',
    'azs_bashneft_required',
    'azs_tatneft_required',
    'azs_surgutneftegaz_required',
    'azs_neftegazholding_required',
    'azs_irkutskoil_required',
    'azs_alians_required',
]
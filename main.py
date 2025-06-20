import pandas as pd
import numpy as np
import os
import logging
from datetime import datetime, date, timedelta
import json
from bs4 import BeautifulSoup
import sys

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_collection.scraper import ZakupkiGovScraper

from src.data_preprocessing.sme_filter import SMEFilter
from src.data_preprocessing.cleaner import DataCleaner
from src.data_preprocessing.feature_engineer import FeatureEngineer
from src.ml_model.trainer import ModelTrainer
from src.ml_model.predictor import ModelPredictor
from src.reporting.insights_generator import InsightsGenerator
from src.database.db_manager import DBManager
from src.database.models import Tender, Company, PurchaseObject
from config.settings import MODELS_PATH, FEATURES_LIST, MAJOR_AZS_NETWORKS, TENDER_KEYWORDS_FUEL, DATABASE_URL
from src.data_collection.scraper import ZakupkiGovScraper
logger = logging.getLogger(__name__)


def setup_logging():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


def run_pipeline():
    setup_logging()
    logger.info("--- Запуск конвейера Sales Smart Leads ---")

    db_manager = DBManager()
    db_manager.create_tables()

    logger.info("1. Запуск сбора и сохранения сырых данных (используя ZakupkiGovScraper)...")
    scraper = ZakupkiGovScraper()

    if not TENDER_KEYWORDS_FUEL:
        logger.error("Отсутствуют ключевые слова для поиска тендеров в TENDER_KEYWORDS_FUEL. Завершение.")
        return

    all_main_tenders = []
    today = date.today()
    one_month_ago = today - timedelta(days=30)
    start_date_str = one_month_ago.strftime('%Y-%m-%d')
    end_date_str = today.strftime('%Y-%m-%d')

    for query_keyword in TENDER_KEYWORDS_FUEL:
        logger.info(f"Начинаю скрапинг Zakupki.gov.ru для ключевого слова: '{query_keyword}'")
        main_tenders_list = scraper.search_tenders(
            query=query_keyword,
            start_date=start_date_str,
            end_date=end_date_str
        )
        all_main_tenders.extend(main_tenders_list)

    main_tenders_df = pd.DataFrame(all_main_tenders)

    if main_tenders_df.empty:
        logger.warning("Нет основных тендеров для обработки. Конвейер завершен.")
        return

    logger.info(f"Найдено {len(main_tenders_df)} основных тендеров.")

    try:
        total_saved = 0
        for index, row in main_tenders_df.iterrows():
            tender_id = row.get('tender_id')
            tender_link = row.get('link')

            if not tender_id or not tender_link:
                logger.warning(f"Пропускаю тендер из-за отсутствия tender_id или link: {row.to_dict()}")
                continue

            full_tender_html_data = scraper.get_tender_details(tender_link)

            if full_tender_html_data and 'html_content' in full_tender_html_data:
                soup = BeautifulSoup(full_tender_html_data['html_content'], 'html.parser')
                parsed_data = scraper.parse_tender_card(soup, tender_platform_id=tender_id,
                                                        tender_link=tender_link)

                if parsed_data:
                    with db_manager.get_session() as session:
                        customer_inn = parsed_data.get('customer_inn')
                        if customer_inn:
                            company_data = {
                                'inn': customer_inn,
                                'name': parsed_data.get('customer_name', 'Неизвестно'),
                                'kpp': parsed_data.get('customer_kpp'),
                            }
                            db_manager.add_or_update_company(session, company_data)

                        db_manager.add_or_update_tender(session, parsed_data)
                        total_saved += 1
                else:
                    logger.warning(f"Не удалось распарсить данные для тендера {tender_id}. Пропускаю.")
            else:
                logger.warning(f"Не удалось получить полные данные (HTML) для тендера {tender_id}. Пропускаю.")

        logger.info(f"Успешно обработано и сохранено/обновлено {total_saved} тендеров в БД.")

    except Exception as e:
        logger.error(f"Глобальная ошибка при сборе или сохранении данных тендеров: {e}", exc_info=True)
        return

    logger.info("2. Загрузка необработанных тендеров из БД для фильтрации/обработки...")

    tenders_to_process_df = pd.DataFrame()
    try:
        with db_manager.get_session() as session:
            tenders_query_results = session.query(Tender).filter(
                (Tender.is_processed == False) |
                (Tender.probability.is_(None)) |
                (Tender.last_processed_at < (datetime.now() - timedelta(days=7)))
            ).all()

            if not tenders_query_results:
                logger.warning("Нет новых или требующих обновления тендеров для обработки из БД.")
                return

            records = []
            for tender_obj in tenders_query_results:
                tender_dict = {c.name: getattr(tender_obj, c.name) for c in tender_obj.__table__.columns}

                for k, v in tender_dict.items():
                    if isinstance(v, datetime):
                        tender_dict[k] = v.isoformat()

                tender_dict['purchase_objects'] = []
                for po in tender_obj.purchase_objects:
                    po_dict = {c.name: getattr(po, c.name) for c in po.__table__.columns}
                    if po.characteristics:
                        try:
                            po_dict['characteristics'] = json.loads(po.characteristics)
                        except json.JSONDecodeError:
                            logger.warning(
                                f"Ошибка декодирования JSON для характеристик объекта закупки ID {po.id}. Сохранено как пустой dict.")
                            po_dict['characteristics'] = {}
                    else:
                        po_dict['characteristics'] = {}
                    tender_dict['purchase_objects'].append(po_dict)
                records.append(tender_dict)

            tenders_to_process_df = pd.DataFrame(records)

    except Exception as e:
        logger.error(f"Ошибка при загрузке тендеров из БД для обработки: {e}", exc_info=True)
        return

    if tenders_to_process_df.empty:
        logger.warning("Нет тендеров для обработки после загрузки. Конвейер завершен.")
        return

    logger.info(f"Загружено {len(tenders_to_process_df)} тендеров для обработки из БД.")

    logger.info("3. Фильтрация тендеров, касающихся МСП...")
    sme_filter = SMEFilter(db_manager=db_manager)
    filtered_tenders_df = sme_filter.filter_tenders_by_sme(tenders_to_process_df.copy())

    if filtered_tenders_df.empty:
        logger.warning("Все тендеры от МСП или нет тендеров после фильтрации по МСП. Конвейер завершен.")
        return
    logger.info(f"Тenдеров после фильтрации по МСП: {len(filtered_tenders_df)}")

    logger.info("4. Очистка и нормализация данных...")
    cleaner = DataCleaner()
    cleaned_df = cleaner.clean_tender_data(filtered_tenders_df.copy())
    logger.info("Очистка и нормализация завершены.")

    logger.info("5. Разработка признаков для ML-модели...")
    feature_engineer = FeatureEngineer()

    features_df = feature_engineer.engineer_features(cleaned_df.copy())
    logger.info("Разработка признаков завершена.")

    logger.info("6. Прогнозирование вероятности успешной сделки...")
    predictor = ModelPredictor()

    missing_features_for_prediction = [col for col in FEATURES_LIST if col not in features_df.columns]
    if features_df.empty or missing_features_for_prediction:
        logger.error(
            f"Недостаточно данных или признаков для прогнозирования. Отсутствуют: {missing_features_for_prediction}. Завершение.")
        try:
            with db_manager.get_session() as session:
                for tender_id_val in features_df['tender_id'].tolist() if not features_df.empty else []:
                    tender = session.query(Tender).filter_by(tender_id=tender_id_val).first()
                    if tender:
                        tender.is_processed = True
                        tender.probability = None
                        tender.last_processed_at = datetime.now()
                session.commit()
        except Exception as e:
            logger.error(f"Ошибка при обновлении статуса тендеров после неудачного прогнозирования: {e}")
        return

    try:
        features_for_prediction = features_df[FEATURES_LIST]
        probabilities = predictor.predict_probability(features_for_prediction)
        cleaned_df['probability'] = probabilities
        logger.info("Прогнозирование вероятности завершено.")
    except Exception as e:
        logger.error(
            f"Ошибка при прогнозировании вероятности: {e}. Пропускаю прогнозирование и устанавливаю probability=None.",
            exc_info=True)
        cleaned_df['probability'] = None

    logger.info("7. Генерация инсайтов и рекомендаций...")
    insights_generator = InsightsGenerator()

    cleaned_df['recommendations'] = cleaned_df.apply(
        lambda row: insights_generator.generate_recommendations(row.to_dict(), row.get('probability')),
        axis=1
    )
    logger.info("Генерация рекомендаций завершена.")

    logger.info("8. Сохранение обработанных данных и результатов в БД...")

    try:
        with db_manager.get_session() as session:
            for index, row in cleaned_df.iterrows():
                tender_platform_id = row['tender_id']
                tender = session.query(Tender).filter_by(tender_id=tender_platform_id).first()

                if tender:
                    tender.probability = row.get('probability')
                    tender.recommendations = row.get('recommendations')
                    tender.last_processed_at = datetime.now()
                    tender.is_processed = True

                    if 'contract_duration_days' in row and not pd.isna(row['contract_duration_days']):
                        tender.contract_duration_days = row['contract_duration_days']
                    if 'payment_type_prepayment' in row:
                        tender.payment_type_prepayment = bool(row['payment_type_prepayment'])
                    if 'prepayment_percentage' in row and not pd.isna(row['prepayment_percentage']):
                        tender.prepayment_percentage = row['prepayment_percentage']
                    if 'payment_deferral_days' in row and not pd.isna(row['payment_deferral_days']):
                        tender.payment_deferral_days = row['payment_deferral_days']

                    if 'contract_terms_raw' in row and not pd.isna(row['contract_terms_raw']):
                        tender.contract_terms_raw = str(row['contract_terms_raw'])
                    if 'payment_conditions_raw' in row and not pd.isna(row['payment_conditions_raw']):
                        tender.payment_conditions_raw = str(row['payment_conditions_raw'])
                    if 'azs_network_raw' in row and not pd.isna(row['azs_network_raw']):
                        tender.azs_network_raw = str(row['azs_network_raw'])

                    for network in MAJOR_AZS_NETWORKS:
                        col_name = f'azs_{network.lower().replace(" ", "_")}_required'
                        if col_name in row:
                            setattr(tender, col_name, bool(row[col_name]))
                        else:
                            setattr(tender, col_name, False)

                    if 'is_sme' in row:
                        tender.is_sme = bool(row['is_sme'])

                    if 'is_relevant' in row:
                        tender.is_relevant = bool(row['is_relevant'])

                else:
                    logger.warning(f"Тендер с tender_id={tender_platform_id} не найден в БД для обновления. Пропускаю.")
            session.commit()

    except Exception as e:
        logger.error(f"Ошибка при сохранении обработанных данных в БД: {e}", exc_info=True)

    logger.info("--- Конвейер завершен ---")
    return cleaned_df


if __name__ == "__main__":
    setup_logging()
    logger.info("Запуск модуля main.py напрямую.")

    os.makedirs(MODELS_PATH, exist_ok=True)

    db_manager = DBManager()
    db_manager.create_tables()

    logger.info("\n--- Запуск ОБРАЗЦА ОБУЧЕНИЯ МОДЕЛИ (одноразово) ---")

    all_scraped_tenders_for_training = []

    if not TENDER_KEYWORDS_FUEL:
        logger.error("Отсутствуют ключевые слова для поиска тендеров в TENDER_KEYWORDS_FUEL. Завершение обучения.")
        sys.exit("Ошибка: Ключевые слова для обучения отсутствуют.")

    today = date.today()
    three_months_ago = today - timedelta(days=90)
    start_date_training_str = three_months_ago.strftime('%Y-%m-%d')
    end_date_training_str = today.strftime('%Y-%m-%d')

    scraper_for_training = ZakupkiGovScraper()

    for keyword in TENDER_KEYWORDS_FUEL:
        logger.info(f"Начинаю скрапинг Zakupki.gov.ru для обучения модели для ключевого слова: '{keyword}'")

        try:
            main_tenders_list_for_keyword = scraper_for_training.search_tenders(
                query=keyword,
                start_date=start_date_training_str,
                end_date=end_date_training_str
            )
            main_tenders_df_for_keyword = pd.DataFrame(main_tenders_list_for_keyword)

            if main_tenders_df_for_keyword.empty:
                logger.warning(f"Не удалось получить основные данные из Zakupki.gov.ru для обучения по слову '{keyword}'. DataFrame пуст.")
                continue

            logger.info(f"Загружено {len(main_tenders_df_for_keyword)} основных тендеров для обучения по слову '{keyword}'.")

            for index, row in main_tenders_df_for_keyword.iterrows():
                tender_id = row.get('tender_id')
                tender_link = row.get('link')
                if tender_id and tender_link:
                    full_data_html = scraper_for_training.get_tender_details(tender_link)
                    if full_data_html and 'html_content' in full_data_html:
                        soup_for_parsing = BeautifulSoup(full_data_html['html_content'], 'html.parser')
                        parsed_full_data = scraper_for_training.parse_tender_card(soup_for_parsing, tender_platform_id=tender_id, tender_link=tender_link)
                        if parsed_full_data:
                            all_scraped_tenders_for_training.append(parsed_full_data)
                        else:
                            logger.warning(f"Не удалось распарсить полные данные для тендера {tender_id} для обучения.")
                    else:
                        logger.warning(f"Не удалось получить HTML-детали для тендера {tender_id} для обучения.")
                else:
                    logger.warning(f"Пропускаю тендер для обучения из-за отсутствия tender_id или link: {row.to_dict()}")

        except Exception as e:
            logger.error(f"Ошибка при сборе данных через ZakupkiGovScraper для обучения по ключевому слову '{keyword}': {e}", exc_info=True)

    if not all_scraped_tenders_for_training:
        logger.error("Нет полных данных тендеров для обучения модели после детального скрапинга по всем ключевым словам.")
        sys.exit("Ошибка: Детальные данные для обучения отсутствуют.")

    synthetic_data_for_training_raw = pd.DataFrame(all_scraped_tenders_for_training)

    logger.info(f"Загружено {len(synthetic_data_for_training_raw)} полных тендеров для обучения (всего).")
    logger.info(
        f"Доступные колонки в загруженных данных для обучения: {synthetic_data_for_training_raw.columns.tolist()}")

    expected_raw_cols_for_feature_engineer = [
        'tender_id',
        'link',
        'status', 'stage', 'purchase_method', 'customer_name',
        'customer_inn', 'customer_kpp', 'customer_link',
        'publication_date', 'start_date', 'end_date',
        'max_contract_price', 'currency',
        'contract_security_percent', 'contract_security_amount',
        'application_security_percent', 'application_security_amount',
        'quantity_indeterminable', 'total_initial_sum',
        'purchase_objects',
        'contract_duration_days', 'payment_type_prepayment', 'prepayment_percentage',
        'payment_deferral_days', 'contract_terms_raw', 'payment_conditions_raw', 'azs_network_raw',
        'region'
    ]

    for col in expected_raw_cols_for_feature_engineer:
        if col not in synthetic_data_for_training_raw.columns:
            logger.warning(f"Сырая колонка '{col}' отсутствует в загруженных данных для обучения. Добавляем заглушку.")
            if col in ['max_contract_price', 'contract_security_percent', 'contract_security_amount',
                       'application_security_percent', 'application_security_amount', 'total_initial_sum',
                       'contract_duration_days', 'prepayment_percentage', 'payment_deferral_days']:
                synthetic_data_for_training_raw[col] = 0.0
            elif col in ['quantity_indeterminable', 'payment_type_prepayment']:
                synthetic_data_for_training_raw[col] = False
            elif col in ['publication_date', 'start_date', 'end_date']:
                synthetic_data_for_training_raw[col] = pd.NaT
            elif col == 'purchase_objects':
                synthetic_data_for_training_raw[col] = [[] for _ in range(len(synthetic_data_for_training_raw))]
            else:
                synthetic_data_for_training_raw[col] = np.nan

    if 'target' not in synthetic_data_for_training_raw.columns:
        logger.warning("Критическое предупреждение: Колонка 'target' отсутствует для обучения модели. "
                       "Используется СЛУЧАЙНАЯ ЗАГЛУШКА. Модель не будет иметь реальной ценности.")
        synthetic_data_for_training_raw['target'] = np.random.choice([0, 1],
                                                                     size=len(synthetic_data_for_training_raw),
                                                                     p=[0.8, 0.2])

    feature_engineer = FeatureEngineer()
    processed_synthetic_data = feature_engineer.engineer_features(synthetic_data_for_training_raw.copy())
    logger.info(
        f"Данные для обучения обработаны FeatureEngineer. Количество признаков: {len(processed_synthetic_data.columns)}")

    missing_after_engineering = set(FEATURES_LIST) - set(processed_synthetic_data.columns)
    if missing_after_engineering:
        logger.error(
            f"После FeatureEngineering для обучения все еще отсутствуют признаки для модели: {missing_after_engineering}")
        logger.error(f"Колонки в processed_synthetic_data: {processed_synthetic_data.columns.tolist()}")
        sys.exit("Ошибка: Не все необходимые признаки были сгенерированы для обучения.")

    trainer = ModelTrainer()
    try:
        trainer.train_model(processed_synthetic_data[FEATURES_LIST], processed_synthetic_data['target'])
        logger.info("--- ОБРАЗЕЦ ОБУЧЕНИЯ МОДЕЛИ ЗАВЕРШЕН УСПЕШНО ---")
    except Exception as e:
        logger.error(f"Ошибка при обучении модели: {e}", exc_info=True)
        sys.exit("Ошибка: Обучение модели завершилось с ошибкой.")

    logger.info("\n--- Запуск основного конвейера после обучения модели ---")
    run_pipeline()
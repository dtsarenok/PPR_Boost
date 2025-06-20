# src/reporting/insights_generator.py

import pandas as pd
import logging
from src.database.db_manager import DBManager
from src.database.models import Tender
from datetime import datetime, timedelta
import numpy as np

logger = logging.getLogger(__name__)


class InsightsGenerator:
    def __init__(self):
        self.db_manager = DBManager()
        logger.info("InsightsGenerator инициализирован.")

    def get_tenders_for_analysis(self, processed_only=True) -> pd.DataFrame:

        tenders_data = []
        try:
            with self.db_manager.get_session() as session:
                if processed_only:
                    tenders = session.query(Tender).filter(Tender.is_processed == True).all()
                else:
                    tenders = session.query(Tender).all()

                for tender in tenders:

                    tender_dict = {col.name: getattr(tender, col.name) for col in tender.__table__.columns}



                    for key, value in tender_dict.items():
                        if isinstance(value, datetime):
                            tender_dict[key] = value.isoformat()
                        elif value is None:
                            tender_dict[key] = np.nan


                    for key, value in tender_dict.items():
                        if key.startswith('azs_') and key.endswith('_required'):

                            tender_dict[key] = bool(value) if value is not None else False

                    tenders_data.append(tender_dict)
            logger.info(f"Загружено {len(tenders_data)} тендеров из БД (processed_only={processed_only}).")

            df = pd.DataFrame(tenders_data)
            for col in ['start_date', 'end_date', 'publication_date', 'last_processed_at']:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce')
            return df
        except Exception as e:
            logger.error(f"Ошибка при загрузке тендеров из БД: {e}", exc_info=True)
            return pd.DataFrame()  # Возвращаем пустой DataFrame в случае ошибки

    def filter_tenders(self, df: pd.DataFrame, **kwargs) -> pd.DataFrame:

        filtered_df = df.copy()

        # Фильтр по минимальной цене
        if 'min_price' in kwargs and kwargs['min_price'] is not None:
            filtered_df = filtered_df[filtered_df['price'].fillna(0) >= kwargs['min_price']]
            logger.debug(f"После min_price {kwargs['min_price']}: {len(filtered_df)}")

        # Фильтр по максимальной цене
        if 'max_price' in kwargs and kwargs['max_price'] is not None:
            filtered_df = filtered_df[filtered_df['price'].fillna(0) <= kwargs['max_price']]
            logger.debug(f"После max_price {kwargs['max_price']}: {len(filtered_df)}")

        # Фильтр по регионам (мультивыбор)
        if 'regions' in kwargs and kwargs['regions']:
            if 'region' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['region'].isin(kwargs['regions']).fillna(False)]
            logger.debug(f"После regions {kwargs['regions']}: {len(filtered_df)}")


        if 'fuel_types' in kwargs and kwargs['fuel_types']:
            if 'fuel_type' in filtered_df.columns:
                filtered_df = filtered_df[filtered_df['fuel_type'].isin(kwargs['fuel_types']).fillna(False)]
            else:
                search_pattern = '|'.join(kwargs['fuel_types']).lower()
                filtered_df = filtered_df[
                    filtered_df['title'].str.lower().str.contains(search_pattern, na=False) |
                    filtered_df['description'].str.lower().str.contains(search_pattern, na=False)
                    ]
            logger.debug(f"После fuel_types {kwargs['fuel_types']}: {len(filtered_df)}")


        if 'min_contract_duration_days' in kwargs and kwargs['min_contract_duration_days'] is not None:
            filtered_df = filtered_df[
                filtered_df['contract_duration_days'].fillna(0) >= kwargs['min_contract_duration_days']]
            logger.debug(f"После min_contract_duration_days {kwargs['min_contract_duration_days']}: {len(filtered_df)}")


        if 'max_contract_duration_days' in kwargs and kwargs['max_contract_duration_days'] is not None:
            filtered_df = filtered_df[
                filtered_df['contract_duration_days'].fillna(0) <= kwargs['max_contract_duration_days']]
            logger.debug(f"После max_contract_duration_days {kwargs['max_contract_duration_days']}: {len(filtered_df)}")


        if 'prepayment_required' in kwargs and kwargs['prepayment_required'] is not None:

            filtered_df = filtered_df[
                filtered_df['payment_type_prepayment'].fillna(False) == kwargs['prepayment_required']]
            logger.debug(f"После prepayment_required {kwargs['prepayment_required']}: {len(filtered_df)}")

        if 'min_prepayment_percentage' in kwargs and kwargs['min_prepayment_percentage'] is not None:
            filtered_df = filtered_df[
                filtered_df['prepayment_percentage'].fillna(0) >= kwargs['min_prepayment_percentage']]
            logger.debug(f"После min_prepayment_percentage {kwargs['min_prepayment_percentage']}: {len(filtered_df)}")

        if 'max_payment_deferral_days' in kwargs and kwargs['max_payment_deferral_days'] is not None:
            filtered_df = filtered_df[
                filtered_df['payment_deferral_days'].fillna(0) <= kwargs['max_payment_deferral_days']]
            logger.debug(f"После max_payment_deferral_days {kwargs['max_payment_deferral_days']}: {len(filtered_df)}")


        if 'azs_networks' in kwargs and kwargs['azs_networks']:
            azs_filter_query = pd.Series([False] * len(filtered_df), index=filtered_df.index)
            for network in kwargs['azs_networks']:
                col_name = f"azs_{network.lower().replace(' ', '_')}_required"
                if col_name in filtered_df.columns:

                    azs_filter_query = azs_filter_query | (filtered_df[col_name].fillna(False) == True)
            filtered_df = filtered_df[azs_filter_query]
            logger.debug(f"После azs_networks {kwargs['azs_networks']}: {len(filtered_df)}")

        # Фильтр по исключению МСП
        if 'exclude_sme' in kwargs and kwargs['exclude_sme'] is not None:
            # is_sme теперь булево, обрабатываем fillna
            filtered_df = filtered_df[filtered_df['is_sme'].fillna(False) == (not kwargs['exclude_sme'])]
            logger.debug(f"После exclude_sme {kwargs['exclude_sme']}: {len(filtered_df)}")

        # Фильтр по минимальной вероятности выигрыша
        if 'min_probability' in kwargs and kwargs['min_probability'] is not None:
            filtered_df = filtered_df[
                filtered_df['probability'].fillna(0) >= kwargs['min_probability']]
            logger.debug(f"После min_probability {kwargs['min_probability']}: {len(filtered_df)}")

        # Фильтр по количеству последних дней публикации
        if 'recent_days' in kwargs and kwargs['recent_days'] is not None:
            if 'publication_date' in filtered_df.columns and not filtered_df['publication_date'].empty:

                filtered_df['publication_date'] = pd.to_datetime(filtered_df['publication_date'], errors='coerce')
                cutoff_date = pd.Timestamp.now().date() - pd.Timedelta(days=kwargs['recent_days'])
                filtered_df = filtered_df[filtered_df['publication_date'] >= cutoff_date]
            logger.debug(f"После recent_days {kwargs['recent_days']}: {len(filtered_df)}")

        # Фильтр по текстовому поиску в заголовке/описании
        if 'search_text' in kwargs and kwargs['search_text']:
            search_pattern = kwargs['search_text'].lower()
            title_search = filtered_df['title'].str.lower().str.contains(search_pattern,
                                                                         na=False) if 'title' in filtered_df.columns else pd.Series(
                False, index=filtered_df.index)
            desc_search = filtered_df['description'].str.lower().str.contains(search_pattern,
                                                                              na=False) if 'description' in filtered_df.columns else pd.Series(
                False, index=filtered_df.index)
            filtered_df = filtered_df[title_search | desc_search]
            logger.debug(f"После search_text '{kwargs['search_text']}': {len(filtered_df)}")

        logger.info(f"Фильтрация завершена. Изначально {len(df)} тендеров, осталось {len(filtered_df)}.")
        return filtered_df

    def sort_tenders(self, df: pd.DataFrame, sort_by: str = 'probability', ascending: bool = False) -> pd.DataFrame:
        if df.empty:
            logger.warning("DataFrame пуст, сортировка не применена.")
            return df

        if sort_by not in df.columns:
            logger.warning(f"Колонка '{sort_by}' не найдена в DataFrame для сортировки. Сортировка не применена.")
            return df


        na_pos = 'last' if not ascending else 'first'


        if sort_by in ['price', 'probability', 'contract_duration_days', 'prepayment_percentage',
                       'payment_deferral_days']:
            df_sorted = df.copy()
            fill_value = -1 if ascending else np.inf
            if sort_by == 'probability':
                fill_value = -1 if ascending else -1

            df_sorted = df_sorted.sort_values(by=sort_by, ascending=ascending, na_position=na_pos)
        else:
            df_sorted = df.sort_values(by=sort_by, ascending=ascending, na_position=na_pos)

        logger.info(f"Тендеры отсортированы по '{sort_by}' {'по возрастанию' if ascending else 'по убыванию'}.")
        return df_sorted

    def generate_recommendations(self, tender_data: dict, probability: float = None) -> str:
        recommendations = []

        if probability is None:
            recommendations.append("Вероятность успеха не рассчитана.")
        elif probability >= 0.85:
            recommendations.append(
                "Высокий приоритет! Тендер имеет очень хорошие шансы на успех. Рекомендуется активное участие.")
        elif probability >= 0.6:
            recommendations.append("Средний приоритет. Тендер выглядит перспективным, но требует тщательного анализа.")
        elif probability >= 0.3:
            recommendations.append(
                "Низкий приоритет. Шансы на успех невысоки, но может быть интересен при низкой конкуренции.")
        else:
            recommendations.append(
                "Очень низкий приоритет. Вероятность успеха крайне мала, возможно, стоит пропустить.")

        price = tender_data.get('price', 0)
        if price > 1000000:
            recommendations.append("Крупный тендер: требуется тщательная подготовка коммерческого предложения.")
        elif price < 200000:
            recommendations.append("Малый тендер: рассмотрите возможность быстрой подачи для увеличения оборота.")

        contract_duration_days = tender_data.get('contract_duration_days')
        if contract_duration_days is not None:
            if contract_duration_days > 180:
                recommendations.append("Длительный контракт: обеспечьте стабильность поставок/услуг на весь срок.")
            elif contract_duration_days < 60:
                recommendations.append("Короткий контракт: важна оперативность выполнения.")

        payment_type_prepayment = tender_data.get('payment_type_prepayment')
        prepayment_percentage = tender_data.get('prepayment_percentage')
        payment_deferral_days = tender_data.get('payment_deferral_days')

        if payment_type_prepayment:
            if prepayment_percentage is not None and prepayment_percentage > 0:
                recommendations.append(f"Предоплата {prepayment_percentage}%: Уточните условия авансирования.")
            else:
                recommendations.append("Есть предоплата: Уточните размер и условия получения.")
        elif payment_deferral_days is not None and payment_deferral_days > 0:
            recommendations.append(
                f"Отсрочка платежа до {int(payment_deferral_days)} дней: Оцените свои финансовые возможности.")

        is_sme = tender_data.get('is_sme')
        if is_sme is not None and is_sme:  # Если заказчик - МСП
            recommendations.append("Тендер от субъекта МСП: Могут быть специфические требования или преференции.")


        azs_networks_required = [key.replace('azs_', '').replace('_required', '').replace('_', ' ').title()
                                 for key, val in tender_data.items()
                                 if key.startswith('azs_') and key.endswith('_required') and val]
        if azs_networks_required:
            recommendations.append(
                f"Требуемые АЗС сети: {', '.join(azs_networks_required)}. Убедитесь, что можете предоставить карты этих сетей.")
        else:
            recommendations.append("Требования к АЗС сетям не указаны, что расширяет возможности.")


        final_recommendation = " ".join(recommendations)
        return final_recommendation if final_recommendation else "Дополнительных рекомендаций нет."

    def format_tenders_for_telegram(self, df: pd.DataFrame) -> list[str]:
        messages = []
        if df.empty:
            return ["По вашим критериям тендеры не найдены."]

        for i, tender in df.iterrows():

            probability_str = f"{tender.get('probability', np.nan):.2%}" if pd.notna(
                tender.get('probability')) else "N/A"
            price_str = f"{tender.get('price', np.nan):,.0f} руб." if pd.notna(tender.get('price')) else "N/A"

            title_raw = tender.get('title', 'Без названия')
            title_short = title_raw[:80] + "..." if len(title_raw) > 80 else title_raw

            recommendation = tender.get('recommendations', 'Не определено')
            customer_display = tender.get('customer', 'N/A')
            customer_inn_display = tender.get('customer_inn', 'N/A')

            # Обработка publication_date
            publication_date_val = tender.get('publication_date')
            publication_date_display = pd.to_datetime(publication_date_val).strftime('%Y-%m-%d') if pd.notna(
                publication_date_val) else 'N/A'

            link_display = tender.get('link', '#')

            # Дополнительные детали, если они есть
            contract_duration_val = tender.get('contract_duration_days')
            contract_duration_display = f"{int(contract_duration_val)} дней" if pd.notna(
                contract_duration_val) else 'N/A'

            payment_type_prepayment_val = tender.get('payment_type_prepayment')
            payment_type_prepayment_display = "Да" if pd.notna(
                payment_type_prepayment_val) and payment_type_prepayment_val else "Нет"

            prepayment_percentage_val = tender.get('prepayment_percentage')
            prepayment_percentage_display = f" ({int(prepayment_percentage_val)}%)" if pd.notna(
                prepayment_percentage_val) and prepayment_percentage_val > 0 else ""

            payment_deferral_val = tender.get('payment_deferral_days')
            payment_deferral_display = f"{int(payment_deferral_val)} дней" if pd.notna(
                payment_deferral_val) and payment_deferral_val > 0 else 'Нет'

            is_sme_val = tender.get('is_sme')
            is_sme_display = "Да" if pd.notna(is_sme_val) and is_sme_val else "Нет"

            # Сбор требуемых АЗС
            required_azs_display = []
            for col_name in tender.index:  # Используем tender.index для получения имен колонок
                if col_name.startswith('azs_') and col_name.endswith('_required'):
                    azs_value = tender.get(col_name)
                    if pd.notna(azs_value) and azs_value:  # Если значение True и не NaN
                        network_name = col_name.replace('azs_', '').replace('_required', '').replace('_', ' ').title()
                        required_azs_display.append(network_name)
            azs_info = f"Требуемые АЗС: {', '.join(required_azs_display)}" if required_azs_display else "Требования к АЗС не указаны."

            message = (
                f"<b>{i + 1}. {title_short}</b>\n\n"
                f"💰 <b>НМЦК</b>: {price_str}\n"
                f"📈 <b>Вероятность успеха</b>: {probability_str}\n"
                f"💡 <b>Рекомендация</b>: {recommendation}\n"
                f"👤 <b>Заказчик</b>: {customer_display} (ИНН: {customer_inn_display})\n"
                f"📅 <b>Дата публикации</b>: {publication_date_display}\n"
                f"🔗 <a href='{link_display}'>Ссылка на тендер</a>\n\n"
                f"--- Детали ---\n"
                f"МСП: {is_sme_display}\n"
                f"Срок контракта: {contract_duration_display}\n"
                f"Предоплата: {payment_type_prepayment_display}{prepayment_percentage_display}\n"
                f"Отсрочка платежа: {payment_deferral_display}\n"
                f"{azs_info}\n"
            )
            messages.append(message)
        return messages


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Инициализация InsightsGenerator
    generator = InsightsGenerator()

    print("--- Тестирование get_tenders_for_analysis ---")
    all_tenders_df = generator.get_tenders_for_analysis(processed_only=False)
    if not all_tenders_df.empty:
        print(f"Загружено {len(all_tenders_df)} тендеров.")
        print(all_tenders_df.head())
    else:
        print("DataFrame тендеров пуст.")

    print("\n--- Тестирование filter_tenders ---")

    if all_tenders_df.empty:
        logger.info("База данных пуста, генерируем фиктивные данные для тестирования фильтров.")
        data = {
            'id': [1, 2, 3, 4, 5, 6, 7],
            'tender_id': ['T001', 'T002', 'T003', 'T004', 'T005', 'T006', 'T007'],
            'title': ['Поставка топлива', 'Закупка дизеля для автопарка', 'ГСМ для региона', 'ДТ для грузовиков',
                      'АИ-92 для гос. нужд', 'Поставка топлива на АЗС Лукойл', 'Закупка бензина'],
            'description': ['Описание 1', 'Описание 2 с автопарком', 'Описание 3', 'Описание 4', 'Описание 5',
                            'Описание АЗС Лукойл', 'Краткое описание бензина'],
            'price': [1500000.0, 750000.0, 2500000.0, 400000.0, 1200000.0, 900000.0, 600000.0],
            'region': ['Москва', 'Санкт-Петербург', 'Краснодарский край', 'Москва', 'Республика Татарстан', 'Москва',
                       'Воронежская область'],
            # 'fuel_type': ['ДТ', 'АИ-92', 'ДТ', 'ДТ', 'АИ-92', 'ДТ', 'АИ-92'],
            'contract_duration_days': [180, 90, 365, 60, 270, 120, 150],
            'payment_type_prepayment': [True, False, True, False, True, False, True],
            'prepayment_percentage': [50, 0, 30, 0, 20, 0, 10],
            'payment_deferral_days': [0, 30, 0, 60, 0, 15, 0],
            'is_sme': [False, True, False, True, False, False, True],
            'azs_gazpromneft_required': [True, False, True, False, False, False, False],
            'azs_lukoil_required': [False, False, True, True, False, True, False],
            'azs_rosneft_required': [False, True, False, False, True, False, False],
            'azs_bashneft_required': [False, False, False, False, False, False, False],
            'azs_tatneft_required': [False, False, False, False, False, False, False],
            'azs_surgutneftegaz_required': [False, False, False, False, False, False, False],
            'azs_neftegazholding_required': [False, False, False, False, False, False, False],
            'azs_irkutskoil_required': [False, False, False, False, False, False, False],
            'azs_alians_required': [False, False, False, False, False, False, False],
            'publication_date': [datetime.now() - timedelta(days=2), datetime.now() - timedelta(days=1),
                                 datetime.now() - timedelta(days=10),
                                 datetime.now() - timedelta(days=5), datetime.now() - timedelta(days=0),
                                 datetime.now() - timedelta(days=3),
                                 datetime.now() - timedelta(days=7)],
            'is_processed': [True, True, True, True, True, True, True],
            'probability': [0.95, 0.70, 0.88, 0.60, 0.92, 0.75, 0.80],
            'recommendations': ['Высокий приоритет', 'Средний приоритет', 'Высокий приоритет', 'Низкий приоритет',
                                'Высокий приоритет', 'Средний приоритет', 'Высокий приоритет'],
            'customer': ['Заказчик А', 'Заказчик Б', 'Заказчик В', 'Заказчик Г', 'Заказчик Д', 'Заказчик Е',
                         'Заказчик Ж'],
            'customer_inn': ['7712345678', '5087654321', '7798765432', '5011223344', '7755443322', '7766554433',
                             '5099887766'],
            'link': ['http://link1', 'http://link2', 'http://link3', 'http://link4', 'http://link5', 'http://link6',
                     'http://link7'],
            'start_date': [datetime(2025, 6, 18), datetime(2025, 6, 19), datetime(2025, 6, 10),
                           datetime(2025, 6, 15), datetime(2025, 6, 20), datetime(2025, 6, 22), datetime(2025, 6, 25)],
            'end_date': [datetime(2025, 7, 18), datetime(2025, 7, 19), datetime(2025, 8, 10), datetime(2025, 7, 15),
                         datetime(2025, 8, 20), datetime(2025, 7, 22), datetime(2025, 8, 25)],
            'platform': ['zakupki.gov.ru'] * 7,
            'contract_terms_raw': ['Условия 1', 'Условия 2', 'Условия 3', 'Условия 4', 'Условия 5', 'Условия 6',
                                   'Условия 7'],
            'payment_conditions_raw': ['Оплата 1', 'Оплата 2', 'Оплата 3', 'Оплата 4', 'Оплата 5', 'Оплата 6',
                                       'Оплата 7'],
            'azs_network_raw': ['АЗС сырые 1', 'АЗС сырые 2', 'АЗС сырые 3', 'АЗС сырые 4', 'АЗС сырые 5',
                                'АЗС сырые 6', 'АЗС сырые 7'],
            'last_processed_at': [datetime.now()] * 7,
            'is_relevant': [True] * 7
        }
        all_tenders_df = pd.DataFrame(data)


    filters = {
        'min_price': 500000,
        'regions': ['Москва', 'Краснодарский край'],
        'fuel_types': ['ДТ'],
        'min_probability': 0.7,
        'recent_days': 7,
        'search_text': 'автопарк'
    }
    filtered_tenders_df = generator.filter_tenders(all_tenders_df, **filters)
    print(f"Отфильтровано {len(filtered_tenders_df)} тендеров.")
    print(filtered_tenders_df[['title', 'price', 'region', 'probability']].head())

    print("\n--- Тестирование sort_tenders ---")
    if not filtered_tenders_df.empty:
        sorted_tenders_df = generator.sort_tenders(filtered_tenders_df, sort_by='probability', ascending=False)
        print("Топ 5 тендеров по вероятности:")
        print(sorted_tenders_df[['title', 'price', 'probability']].head())
    else:
        print("Нет данных для тестирования сортировки.")

    print("\n--- Тестирование format_tenders_for_telegram ---")
    if not filtered_tenders_df.empty:
        # Возьмем первые 3 тендера для форматирования
        formatted_messages = generator.format_tenders_for_telegram(filtered_tenders_df.head(3))
        for msg in formatted_messages:
            print("\n--- Сообщение для Telegram ---")
            print(msg)
            print("-----------------------------")
    else:
        print("Нет данных для тестирования форматирования.")
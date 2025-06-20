# src/data_collection/scraper.py

import pandas as pd
import time
import random
from datetime import datetime, timedelta
import json
import logging
from bs4 import BeautifulSoup
import requests
import re
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)

class ZakupkiGovScraper:
    def __init__(self):
        self.base_search_url = "https://zakupki.gov.ru/epz/order/extendedsearch/results.html"
        self.base_tender_view_url = "https://zakupki.gov.ru/epz/order/notice/ea44/view/common-info.html"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
            'Accept-Language': 'ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        }
        self.session = requests.Session()
        logger.info(f"ZakupkiGovScraper инициализирован для zakupki.gov.ru. Базовые URL: {self.base_search_url}, {self.base_tender_view_url}")

    def _make_request(self, url: str, params: dict = None, max_retries: int = 3, backoff_factor: float = 0.5) -> requests.Response | None:
        for attempt in range(max_retries):
            try:
                response = self.session.get(url, params=params, headers=self.headers, timeout=10)
                response.raise_for_status()
                return response
            except requests.exceptions.RequestException as e:
                logger.warning(f"Ошибка при запросе к {url} (Попытка {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff_factor * (2 ** attempt) + random.uniform(0.1, 0.5))
                else:
                    logger.error(f"Не удалось выполнить запрос к {url} после {max_retries} попыток.")
                    return None

    def search_tenders(self, query: str, start_date: str, end_date: str, page_limit: int = 1) -> list:

        logger.info(f"Начинаю реальный поиск тендеров для запроса '{query}' с {start_date} по {end_date}...")
        all_tenders = []
        search_params = {
            'morphology': 'on',
            'pageNumber': 1,
            'sortDirection': 'false',
            'recordsPerPage': '_50',
            'fz44': 'on',
            'sortBy': 'PUBLISH_DATE',
            'searchString': query,
            'publishDateFrom': start_date,
            'publishDateTo': end_date
        }

        current_page = 1
        while current_page <= page_limit:
            search_params['pageNumber'] = current_page
            logger.info(f"Запрос страницы {current_page} поиска тендеров с параметрами: {search_params}")
            response = self._make_request(self.base_search_url, params=search_params)

            if response and response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                tender_cards = soup.select('div.search-results__item')

                if not tender_cards:
                    logger.info("Тендеры на текущей странице не найдены или достигнут конец результатов.")
                    break

                for card in tender_cards:
                    # Ссылка и ID тендера
                    tender_link_elem = card.select_one('a.link__wrapper')
                    tender_link = tender_link_elem['href'] if tender_link_elem and 'href' in tender_link_elem.attrs else None
                    tender_id = None
                    if tender_link:
                        parsed_url = urlparse(tender_link)
                        query_params = parse_qs(parsed_url.query)
                        tender_id = query_params.get('regNumber', [None])[0]

                    # Заголовок тендера
                    tender_title_elem = card.select_one('div.registry-entry__body-value')
                    tender_title = tender_title_elem.get_text(strip=True) if tender_title_elem else None

                    # Дата публикации
                    publication_date_elem = card.select_one('div.data-block__value')
                    publication_date = publication_date_elem.get_text(strip=True) if publication_date_elem else None

                    # Макс. цена контракта
                    max_price_elem = card.select_one('div.price-block__value')
                    max_price = max_price_elem.get_text(strip=True) if max_price_elem else None

                    # Заказчик
                    customer_name_elem = card.select_one('div.customer-block__title a')
                    customer_name = customer_name_elem.get_text(strip=True) if customer_name_elem else None
                    customer_inn_elem = card.select_one('div.customer-block__inn')
                    customer_inn = customer_inn_elem.get_text(strip=True).replace('ИНН: ', '') if customer_inn_elem else None


                    if tender_id and tender_link and tender_title:
                        all_tenders.append({
                            'tender_id': tender_id,
                            'link': f"https://zakupki.gov.ru{tender_link}" if tender_link.startswith('/') else tender_link,
                            'title': tender_title,
                            'publication_date': publication_date,
                            'max_contract_price': max_price,
                            'customer_name': customer_name,
                            'customer_inn': customer_inn
                        })
                current_page += 1
                time.sleep(random.uniform(2, 5))
            else:
                logger.error(f"Не удалось получить страницу {current_page} поиска.")
                break

        logger.info(f"Завершил поиск. Найдено {len(all_tenders)} тендеров.")
        return all_tenders

    def get_tender_details(self, tender_link: str) -> dict:

        logger.info(f"Запрос реальных деталей для тендера по ссылке: {tender_link}")
        response = self._make_request(tender_link)
        if response and response.status_code == 200:
            logger.info(f"Успешно получены детали для {tender_link}")
            return {'html_content': response.text}
        return {'html_content': ''}

    def parse_tender_card(self, soup: BeautifulSoup, tender_platform_id: str, tender_link: str) -> dict:
        logger.info(f"Начинаю парсинг реальных деталей тендера {tender_platform_id}...")

        def get_text(selector: str, element: BeautifulSoup, default: str = '') -> str:
            found = element.select_one(selector)
            return found.get_text(strip=True) if found else default

        def get_all_texts(selector: str, element: BeautifulSoup) -> list:
            found = element.select(selector)
            return [f.get_text(strip=True) for f in found] if found else []

        def parse_price(price_str: str) -> float:
            if not isinstance(price_str, str): return 0.0
            cleaned_price = re.sub(r'[^\d,.]', '', price_str).replace(',', '.')
            try:
                return float(cleaned_price)
            except ValueError:
                return 0.0

        tender_data = {
            'tender_platform_id': tender_platform_id,
            'tender_link': tender_link,
            'status': '',
            'stage': '',
            'purchase_method': '',
            'customer_name': '',
            'customer_inn': '',
            'customer_kpp': '',
            'publication_date': '',
            'start_date': '',
            'end_date': '',
            'max_contract_price': 0.0,
            'currency': '',
            'contract_security_percent': 0.0,
            'contract_security_amount': 0.0,
            'application_security_percent': 0.0,
            'application_security_amount': 0.0,
            'quantity_indeterminable': 'Нет',
            'total_initial_sum': 0.0,
            'region': '',
            'customer_link': '',
            'contract_duration_days': 0,
            'payment_type_prepayment': 'Нет',
            'prepayment_percentage': 0.0,
            'payment_deferral_days': 0,
            'contract_terms_raw': '',
            'payment_conditions_raw': '',
            'azs_network_raw': '',
            'purchase_objects': []
        }


        def find_value_by_label(soup_obj, label_text):

            label_element = soup_obj.find(lambda tag: (tag.name == 'span' and 'section__title' in tag.get('class', [])) or
                                                    (tag.name == 'div' and 'data-block__title' in tag.get('class', [])) and
                                                    label_text.lower() in tag.get_text(strip=True).lower())
            if label_element:

                value_element = label_element.find_next_sibling(['div', 'span', 'dd'])
                if value_element:
                    return value_element.get_text(strip=True)
            return ''


        tender_data['status'] = get_text('span.card-section__info-value:nth-of-type(1)', element=soup)
        tender_data['stage'] = get_text('span.card-section__info-value:nth-of-type(2)', element=soup)
        tender_data['purchase_method'] = get_text('span.card-section__info-value:nth-of-type(3)', element=soup)


        tender_data['max_contract_price'] = parse_price(get_text('span.price-block__value', element=soup))
        tender_data['currency'] = get_text('span.price-block__currency', element=soup)

        tender_data['publication_date'] = get_text('span.publication-date__value', element=soup)
        tender_data['start_date'] = get_text('span.start-date__value', element=soup)
        tender_data['end_date'] = get_text('span.end-date__value', element=soup)

        # Заказчик
        tender_data['customer_name'] = get_text('span.customer-info__name', element=soup)
        tender_data['customer_inn'] = get_text('span.customer-info__inn', element=soup).replace('ИНН: ', '')
        tender_data['customer_kpp'] = get_text('span.customer-info__kpp', element=soup).replace('КПП: ', '')
        customer_link_elem = soup.select_one('a.customer-info__link')
        if customer_link_elem and 'href' in customer_link_elem.attrs:
            tender_data['customer_link'] = f"https://zakupki.gov.ru{customer_link_elem['href']}" if customer_link_elem['href'].startswith('/') else customer_link_elem['href']


        region_elem = soup.select_one('div.card-section__info-block span.fz-44-info__value:contains("Российская Федерация")')
        if region_elem:

            region_parent = region_elem.find_parent('div')
            if region_parent:
                all_spans_in_block = region_parent.select('span')
                # Попробуем найти span, который следует за span с "Российская Федерация"
                # или собрать весь текст в этом блоке и извлечь город/регион.
                # Это очень специфично для структуры сайта.
                full_address_text = region_parent.get_text(strip=True)
                # Очень грубый парсинг: ищем после "Место поставки:" или "Регион:"
                match = re.search(r'(?:Регион|Место поставки):\s*([^,]+(?:,\s*[^,]+)*)', full_address_text, re.IGNORECASE)
                if match:
                    tender_data['region'] = match.group(1).strip()
            # Более простой вариант: если есть прямой селектор:
            # tender_data['region'] = get_text('div.delivery-place__region', element=soup)

        # Обеспечения (заявки, контракта)
        tender_data['application_security_amount'] = parse_price(get_text('span.application-security__amount', element=soup))
        tender_data['application_security_percent'] = parse_price(get_text('span.application-security__percent', element=soup).replace('%', ''))
        tender_data['contract_security_amount'] = parse_price(get_text('span.contract-security__amount', element=soup))
        tender_data['contract_security_percent'] = parse_price(get_text('span.contract-security__percent', element=soup).replace('%', ''))


        quantity_indeterm_elem = soup.find(lambda tag: tag.name == 'span' and 'Неопределенное количество' in tag.get_text())
        if quantity_indeterm_elem:
            tender_data['quantity_indeterminable'] = 'Да'


        tender_data['total_initial_sum'] = tender_data['max_contract_price']


        purchase_object_elements = soup.select('div.purchase-object-item')
        for obj_elem in purchase_object_elements:
            obj_name = get_text('span.item-name', element=obj_elem)
            obj_code_position = get_text('span.okpd2-code', element=obj_elem)
            obj_ktru_link_elem = obj_elem.select_one('a.ktru-link')
            obj_ktru_link = f"https://zakupki.gov.ru{obj_ktru_link_elem['href']}" if obj_ktru_link_elem and 'href' in obj_ktru_link_elem.attrs else ''

            characteristics_dict = {}
            characteristics_block = obj_elem.select_one('div.characteristics-block')
            if characteristics_block:

                dl_elements = characteristics_block.select('dl > dt, dl > dd')
                current_key = None
                for el in dl_elements:
                    if el.name == 'dt':
                        current_key = el.get_text(strip=True)
                    elif el.name == 'dd' and current_key:
                        characteristics_dict[current_key] = el.get_text(strip=True)
                        current_key = None


            obj_unit_of_measurement = get_text('span.unit-measure', element=obj_elem)
            obj_initial_price_per_unit = parse_price(get_text('span.price-per-unit', element=obj_elem))
            obj_cost = parse_price(get_text('span.item-total-price', element=obj_elem))

            tender_data['purchase_objects'].append({
                'item_name': obj_name,
                'code_position': obj_code_position,
                'ktru_link': obj_ktru_link,
                'characteristics': characteristics_dict,
                'unit_of_measurement': obj_unit_of_measurement,
                'initial_price_per_unit': obj_initial_price_per_unit,
                'cost': obj_cost
            })


        contract_terms_elem = soup.select_one('div.common-info__block span.section__title:contains("Условия контракта") + div.section__value')
        if contract_terms_elem:
             tender_data['contract_terms_raw'] = contract_terms_elem.get_text(strip=True)


        payment_conditions_elem = soup.select_one('div.common-info__block span.section__title:contains("Условия оплаты") + div.section__value')
        if payment_conditions_elem:
            tender_data['payment_conditions_raw'] = payment_conditions_elem.get_text(strip=True)


        description_block_text = get_text('div.fz44-info-block__text', element=soup)
        if description_block_text:
            tender_data['azs_network_raw'] = description_block_text



        logger.info(f"Парсинг тендера {tender_platform_id} завершен.")
        return tender_data
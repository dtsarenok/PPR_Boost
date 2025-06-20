# src/database/db_manager.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from src.database.models import Base, Tender, Company, PurchaseObject
from config.settings import DATABASE_URL
from datetime import datetime
import pandas as pd
from contextlib import contextmanager
import logging
import json

logger = logging.getLogger(__name__)


class DBManager:
    def __init__(self):
        self.engine = create_engine(DATABASE_URL)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self):
        try:
            Base.metadata.create_all(self.engine)
            logger.info("Таблицы базы данных успешно созданы или уже существуют.")
        except Exception as e:
            logger.error(f"Ошибка при создании таблиц базы данных: {e}")

    @contextmanager
    def get_session(self):
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Сессия откачена из-за ошибки: {e}")
            raise
        finally:
            session.close()

    def add_or_update_tender(self, session: Session, tender_data: dict):
        tender_platform_id = tender_data.get('tender_id')
        if not tender_platform_id:
            logger.warning("Ошибка: Данные тендера не содержат 'tender_id'. Невозможно добавить или обновить.")
            return None

        tender_obj = session.query(Tender).filter_by(tender_id=tender_platform_id).first()

        tender_model_keys = {c.name for c in Tender.__table__.columns}

        purchase_objects_data = tender_data.pop('purchase_objects', [])

        if tender_obj:
            logger.info(f"Обновление существующего тендера: {tender_obj.tender_id}")
            for key, value in tender_data.items():
                if key in tender_model_keys and key not in ['id',
                                                            'last_updated']:
                    if key in ['publication_date', 'start_date', 'end_date'] and value:
                        try:

                            setattr(tender_obj, key, datetime.strptime(value, '%d.%m.%Y %H:%M'))
                        except ValueError:
                            logger.warning(
                                f"Не удалось распарсить дату '{value}' для поля '{key}' в тендере {tender_platform_id}. Сохранение как None.")
                            setattr(tender_obj, key, None)
                    else:
                        setattr(tender_obj, key, value)


            for obj in list(
                    tender_obj.purchase_objects):
                session.delete(obj)
            session.flush()

        else:
            logger.info(f"Добавление нового тендера: {tender_platform_id}")
            filtered_tender_data = {k: v for k, v in tender_data.items() if k in tender_model_keys}

            # Преобразование строковых дат в объекты datetime для нового тендера
            for date_col in ['publication_date', 'start_date', 'end_date']:
                if date_col in filtered_tender_data and filtered_tender_data[date_col]:
                    try:
                        filtered_tender_data[date_col] = datetime.strptime(filtered_tender_data[date_col],
                                                                           '%d.%m.%Y %H:%M')
                    except ValueError:
                        logger.warning(
                            f"Не удалось распарсить дату '{filtered_tender_data[date_col]}' для поля '{date_col}' в тендере {tender_platform_id}. Сохранение как None.")
                        filtered_tender_data[date_col] = None

            # Устанавливаем значения по умолчанию для булевых полей, если они отсутствуют
            for bool_col in ['is_sme', 'is_processed', 'is_relevant', 'is_won']:
                if bool_col not in filtered_tender_data:
                    filtered_tender_data[bool_col] = False

            tender_obj = Tender(**filtered_tender_data)
            session.add(tender_obj)

        session.flush()

        for po_data in purchase_objects_data:
            characteristics_json = json.dumps(po_data.get('characteristics', {}), ensure_ascii=False)

            purchase_object = PurchaseObject(
                tender=tender_obj,
                code_position=po_data.get('code_position'),
                ktru_link=po_data.get('ktru_link'),
                item_name=po_data.get('item_name'),
                unit_of_measurement=po_data.get('unit_of_measurement'),
                initial_price_per_unit=po_data.get('initial_price_per_unit'),
                cost=po_data.get('cost'),
                characteristics=characteristics_json
            )
            session.add(purchase_object)

        return tender_obj

    def add_or_update_company(self, session: Session, company_data: dict):
        company_inn = company_data.get('inn')
        if not company_inn:
            logger.warning("Ошибка: Данные компании не содержат 'inn'. Невозможно добавить или обновить.")
            return None

        company_obj = session.query(Company).filter_by(inn=company_inn).first()

        company_model_keys = {c.name for c in Company.__table__.columns}

        if company_obj:
            logger.info(f"Компания обновлена: {company_obj.name} (ИНН: {company_inn})")
            for key, value in company_data.items():
                if key in company_model_keys and key not in ['id', 'last_updated']:
                    if key == 'registration_date' and value:
                        try:

                            setattr(company_obj, key, datetime.strptime(value, '%d.%m.%Y'))
                        except ValueError:
                            logger.warning(
                                f"Не удалось распарсить дату '{value}' для поля '{key}' для компании {company_inn}. Сохранение как None.")
                            setattr(company_obj, key, None)
                    else:
                        setattr(company_obj, key, value)
        else:
            logger.info(f"Компания добавлена: {company_data.get('name')} (ИНН: {company_inn})")
            filtered_company_data = {k: v for k, v in company_data.items() if k in company_model_keys}

            if 'registration_date' in filtered_company_data and filtered_company_data['registration_date']:
                try:
                    filtered_company_data['registration_date'] = datetime.strptime(
                        filtered_company_data['registration_date'], '%d.%m.%Y')
                except ValueError:
                    logger.warning(
                        f"Не удалось распарсить дату '{filtered_company_data['registration_date']}' для поля 'registration_date' для компании {company_inn}. Сохранение как None.")
                    filtered_company_data['registration_date'] = None

            for bool_col in ['is_sme', 'is_customer', 'is_supplier']:
                if bool_col not in filtered_company_data:
                    filtered_company_data[bool_col] = False

            company_obj = Company(**filtered_company_data)
            session.add(company_obj)
        session.flush()
        return company_obj

    def get_all_tenders_for_processing(self) -> pd.DataFrame:
        with self.get_session() as session:

            tenders_with_companies = session.query(Tender, Company). \
                outerjoin(Company, Tender.customer_inn == Company.inn). \
                all()

            records = []
            for tender_obj, company_obj in tenders_with_companies:
                tender_dict = {c.name: getattr(tender_obj, c.name) for c in tender_obj.__table__.columns}


                for k, v in tender_dict.items():
                    if isinstance(v, datetime):
                        tender_dict[k] = v.isoformat()

                # Добавление данных PurchaseObject
                tender_dict['purchase_objects'] = []
                for po in tender_obj.purchase_objects:
                    po_dict = {c.name: getattr(po, c.name) for c in po.__table__.columns}
                    # Десериализация характеристик
                    po_dict['characteristics'] = json.loads(po.characteristics) if po.characteristics else {}
                    tender_dict['purchase_objects'].append(po_dict)

                if company_obj:
                    company_dict = {c.name: getattr(company_obj, c.name) for c in company_obj.__table__.columns}
                    for k, v in company_dict.items():
                        if isinstance(v, datetime):  # Сериализация DateTime объектов
                            company_dict[k] = v.isoformat()
                        if k not in ['id', 'inn']:
                            tender_dict[f'company_{k}'] = v

                records.append(tender_dict)

            return pd.DataFrame(records)

    def get_latest_evaluated_tenders(self, limit=10) -> list[dict]:
        with self.get_session() as session:
            tenders = session.query(Tender). \
                filter(Tender.probability.isnot(None)). \
                order_by(Tender.publication_date.desc()). \
                limit(limit).all()

            result = []
            for tender in tenders:
                tender_dict = {c.name: getattr(tender, c.name) for c in tender.__table__.columns}

                # Сериализация DateTime объектов для JSON-совместимости
                for k, v in tender_dict.items():
                    if isinstance(v, datetime):
                        tender_dict[k] = v.isoformat()

                # Добавление связанных PurchaseObject
                tender_dict['purchase_objects'] = []
                for po in tender.purchase_objects:
                    po_dict = {c.name: getattr(po, c.name) for c in po.__table__.columns}
                    po_dict['characteristics'] = json.loads(po.characteristics) if po.characteristics else {}
                    tender_dict['purchase_objects'].append(po_dict)

                result.append(tender_dict)
            return result
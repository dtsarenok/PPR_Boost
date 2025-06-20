# src/database/models.py

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func # Для автоматического заполнения времени

Base = declarative_base()


class Tender(Base):
    __tablename__ = 'tenders'
    id = Column(Integer, primary_key=True)
    tender_id = Column(String, unique=True, nullable=False)
    title = Column(String)
    customer = Column(String)
    customer_inn = Column(String, ForeignKey('companies.inn'), nullable=False)
    company_rel = relationship("Company", back_populates="tenders", primaryjoin="Tender.customer_inn == Company.inn")

    start_date = Column(DateTime)
    end_date = Column(DateTime)
    publication_date = Column(DateTime)
    price = Column(Float)
    link = Column(String)
    platform = Column(String)
    region = Column(String)
    description = Column(String) # Для текстового анализа

    # Новые/обновленные поля для ML и анализа (важны для фильтрации)
    probability = Column(Float, nullable=True)
    recommendations = Column(String, nullable=True)
    is_won = Column(Boolean, default=False)
    is_processed = Column(Boolean, default=False)
    last_processed_at = Column(DateTime, nullable=True)

    contract_duration_days = Column(Integer, nullable=True) # Для фильтра по сроку
    payment_type_prepayment = Column(Boolean, default=False) # Для фильтра по типу оплаты
    prepayment_percentage = Column(Float, nullable=True) # Для фильтра по проценту предоплаты
    payment_deferral_days = Column(Integer, nullable=True) # Для фильтра по отсрочке платежа

    # Сырые текстовые поля, из которых можно извлекать признаки
    contract_terms_raw = Column(String, nullable=True)
    payment_conditions_raw = Column(String, nullable=True)
    azs_network_raw = Column(String, nullable=True)


    azs_gazpromneft_required = Column(Boolean, default=False)
    azs_lukoil_required = Column(Boolean, default=False)
    azs_rosneft_required = Column(Boolean, default=False)
    azs_bashneft_required = Column(Boolean, default=False)
    azs_tatneft_required = Column(Boolean, default=False)
    azs_surgutneftegaz_required = Column(Boolean, default=False)
    azs_neftegazholding_required = Column(Boolean, default=False)
    azs_irkutskoil_required = Column(Boolean, default=False)
    azs_alians_required = Column(Boolean, default=False)


    fuel_type = Column(String, nullable=True)


class Company(Base):
    __tablename__ = 'companies'

    inn = Column(String, primary_key=True, index=True, nullable=False) # ИНН компании
    name = Column(String, nullable=True) # Название компании

    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    def __repr__(self):
        return f"<Company(inn='{self.inn}', name='{self.name[:30]}...')>"
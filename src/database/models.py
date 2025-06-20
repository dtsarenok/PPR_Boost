# database/models.py
from sqlalchemy import Column, Integer, String, Float, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime
from datetime import datetime
Base = declarative_base()

class Tender(Base):
    __tablename__ = 'tenders'

    id = Column(Integer, primary_key=True)
    tender_id_platform = Column(String, unique=True, nullable=False, index=True)
    link = Column(String, nullable=True) # Ссылка на тендер
    status = Column(String, nullable=True) # Статус тендера
    stage = Column(String, nullable=True) # Этап тендера
    purchase_method = Column(String, nullable=True) # Способ определения поставщика
    customer_name = Column(String, nullable=True) # Наименование заказчика
    customer_inn = Column(String, nullable=True) # ИНН заказчика
    customer_kpp = Column(String, nullable=True) # КПП заказчика
    customer_link = Column(String, nullable=True) # Ссылка на заказчика
    publish_date = Column(String, nullable=True) # Дата публикации
    start_date = Column(String, nullable=True) # Дата начала подачи заявок
    end_date = Column(String, nullable=True) # Дата окончания подачи заявок
    max_contract_price = Column(Float, nullable=True)
    currency = Column(String, nullable=True) # Валюта
    contract_security_percent = Column(Float, nullable=True) # Размер обеспечения исполнения контракта %
    contract_security_amount = Column(Float, nullable=True) # Размер обеспечения исполнения контракта (сумма)
    application_security_percent = Column(Float, nullable=True) # Размер обеспечения заявки %
    application_security_amount = Column(Float, nullable=True) # Размер обеспечения заявки (сумма)
    quantity_indeterminable = Column(Boolean, nullable=True)
    total_initial_sum = Column(Float, nullable=True) # Общая начальная сумма цен единиц товара

    purchase_objects = relationship("PurchaseObject", back_populates="tender", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Tender(id={self.id}, tender_id_platform='{self.tender_id_platform}', status='{self.status}')>"

class Company(Base):
    __tablename__ = 'companies'

    id = Column(Integer, primary_key=True)
    inn = Column(String, unique=True, nullable=False, index=True) # ИНН компании
    name = Column(String)
    kpp = Column(String)
    is_sme = Column(Boolean) # Признак МСП (Малое и среднее предпринимательство)
    revenue_mln_rub = Column(Float) # Выручка в млн. руб.
    employees = Column(Integer)
    last_updated = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f"<Company(inn='{self.inn}', name='{self.name[:30]}...')>"

class PurchaseObject(Base):
    __tablename__ = 'purchase_objects'

    id = Column(Integer, primary_key=True)
    tender_id = Column(Integer, ForeignKey('tenders.id')) # Внешний ключ к таблице tenders
    code_position = Column(String, nullable=True) # Код позиции
    ktru_link = Column(String, nullable=True) # Ссылка КТРУ
    item_name = Column(String, nullable=True) # Наименование товара, работы, услуги
    unit_of_measurement = Column(String, nullable=True) # Единица измерения
    initial_price_per_unit = Column(Float, nullable=True) # Начальная цена за единицу
    cost = Column(Float, nullable=True) # Стоимость (общая для данной позиции)

    characteristics = Column(Text, nullable=True)

    tender = relationship("Tender", back_populates="purchase_objects")

    def __repr__(self):
        return f"<PurchaseObject(id={self.id}, item_name='{self.item_name}', cost={self.cost})>"
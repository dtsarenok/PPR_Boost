# app.py
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from flask import Flask, render_template
import pandas as pd
from src.database.db_manager import DBManager
from src.database.models import Tender, Company
from config.settings import DATABASE_URL, MODELS_PATH

app = Flask(__name__)


db_manager = DBManager()

@app.route('/')
def index():

    session = db_manager.get_session()
    try:

        tenders_query = session.query(Tender).filter(
            Tender.is_won.is_(None),
            Tender.probability.isnot(None)
        ).order_by(Tender.probability.desc()).all()

        tenders_data = []
        for tender in tenders_query:
            tenders_data.append({
                'id': tender.id,
                'title': tender.title,
                'nmck': tender.nmck,
                'customer_name': tender.customer_name,
                'customer_inn': tender.customer_inn,
                'details_url': tender.details_url,
                'probability': tender.probability,
                'recommendations': tender.recommendations,
                'publish_date': tender.publish_date.strftime('%Y-%m-%d') if tender.publish_date else 'N/A',
                'is_sme': tender.is_sme,
                'contract_duration_days': tender.contract_duration_days,
                'payment_type_prepayment': tender.payment_type_prepayment,
                'prepayment_percentage': tender.prepayment_percentage,
                'payment_deferral_days': tender.payment_deferral_days,
                'azs_gazpromneft_required': tender.azs_gazpromneft_required,
                'azs_lukoil_required': tender.azs_lukoil_required,
                'azs_rosneft_required': tender.azs_rosneft_required,
                'azs_bashneft_required': tender.azs_bashneft_required,
                'azs_tatneft_required': tender.azs_tatneft_required,
                'azs_surgutneftegaz_required': tender.azs_surgutneftegaz_required,
                'azs_neftegazholding_required': tender.azs_neftegazholding_required,
                'azs_irkutskoil_required': tender.azs_irkutskoil_required,
                'azs_alians_required': tender.azs_alians_required,
            })
        tenders_df = pd.DataFrame(tenders_data)

        display_columns = [
            'probability', 'recommendations', 'title', 'nmck', 'customer_name',
            'publish_date', 'details_url', 'is_sme',
            'contract_duration_days', 'payment_type_prepayment', 'prepayment_percentage',
            'payment_deferral_days', 'azs_gazpromneft_required', 'azs_lukoil_required',
            'azs_rosneft_required', 'azs_bashneft_required', 'azs_tatneft_required',
            'azs_surgutneftegaz_required', 'azs_neftegazholding_required',
            'azs_irkutskoil_required', 'azs_alians_required'
        ]


        cols_to_display = [col for col in display_columns if col in tenders_df.columns]
        tenders_display_df = tenders_df[cols_to_display].copy()



        table_headers = [
            "Вероятность", "Рекомендация", "Название тендера", "НМЦК", "Заказчик",
            "Дата публикации", "Ссылка", "МСП",
            "Срок (дни)", "Предоплата", "Процент предоплаты", "Отсрочка (дни)",
            "АЗС Газпромнефть", "АЗС Лукойл", "АЗС Роснефть", "АЗС Башнефть",
            "АЗС Татнефть", "АЗС Сургутнефтегаз", "АЗС Нефтегазхолдинг",
            "АЗС Иркутскнефтепродукт", "АЗС Альянс"
        ]
        table_data = []
        for index, row in tenders_display_df.iterrows():
            row_list = []
            for col_name in cols_to_display:
                value = row[col_name]
                if col_name == 'probability':
                    row_list.append(f"{value:.2f}")
                elif col_name == 'nmck':
                    row_list.append(f"{value:,.2f} руб.")
                elif col_name == 'details_url':
                    row_list.append(f'<a href="{value}" target="_blank">Ссылка</a>')
                elif isinstance(value, bool):
                    row_list.append('Да' if value else 'Нет')
                elif pd.isna(value):
                    row_list.append('N/A')
                else:
                    row_list.append(value)
            table_data.append(row_list)


        return render_template('index.html', headers=table_headers, data=table_data)
    except Exception as e:
        return f"Ошибка при загрузке данных: {e}", 500
    finally:
        session.close()

if __name__ == '__main__':

    os.makedirs(MODELS_PATH, exist_ok=True)
    app.run(debug=True, host='0.0.0.0', port=5000)
# src/reporting/insights_generator.py
import numpy as np

class InsightsGenerator:
    def generate_recommendations(self, tender_data: dict, probability: float):
        recommendations = []


        if probability >= 0.8:
            recommendations.append("🏆 Высокий потенциал успеха! Рекомендуется активное участие и проработка сильных сторон ППР.")
        elif probability >= 0.6:
            recommendations.append("👍 Хороший потенциал. Внимательно изучите условия и подчеркните наши конкурентные преимущества.")
        elif probability >= 0.4:
            recommendations.append("🤔 Средний потенциал. Требуется детальный анализ конкурентов и глубокая проработка предложения.")
        else:
            recommendations.append("📉 Низкий потенциал. Участие не рекомендуется, если нет стратегических причин или уникальных условий для нас.")

        # Рекомендации по НМЦК
        nmck = tender_data.get('nmck', 0)
        if nmck > 5000000:
            recommendations.append(f"💰 Высокий НМЦК ({nmck:,.0f} руб.). Возможно, стоит предложить индивидуальные условия или пакет услуг.")
        elif nmck < 500000 and nmck > 0:
            recommendations.append(f"💸 Низкий НМЦК ({nmck:,.0f} руб.). Оцените рентабельность и возможность быстрого закрытия сделки.")

        # Рекомендации по срокам контракта
        duration = tender_data.get('contract_duration_days')
        if duration and duration > 365 * 1.5: # Более 1.5 лет
            recommendations.append(f"📅 Долгосрочный контракт (около {round(duration/365, 1)} лет). Обеспечит стабильность потока платежей.")
        elif duration and duration < 90: # Менее 3 месяцев
             recommendations.append(f"⏱️ Краткосрочный контракт ({duration} дней). Требует быстрой реакции и оперативной подготовки.")

        # Рекомендации по условиям оплаты
        if tender_data.get('payment_type_prepayment') and tender_data.get('prepayment_percentage', 0) > 0:
            prepayment_percent = tender_data.get('prepayment_percentage', 0)
            recommendations.append(f"💳 Требуется предоплата ({prepayment_percent}%). Учитывайте влияние на кэш-флоу и доступность средств.")
        elif tender_data.get('payment_type_postpayment') and tender_data.get('payment_deferral_days', 0) > 0:
            deferral_days = tender_data.get('payment_deferral_days', 0)
            recommendations.append(f"🗓️ Постоплата до {deferral_days} дней. Оцените риски задержек платежей и кредитоспособность заказчика.")
        else:
            recommendations.append("💰 Стандартные условия оплаты. Уточните детали для минимизации рисков.")

        # Рекомендации по сети АЗС
        required_azs = tender_data.get('required_azs_networks', [])
        if required_azs and "любая" not in required_azs:
            recommendations.append(f"⛽ Тендер требует наличия АЗС сетей: {', '.join(required_azs)}. Убедитесь в полном покрытии ППР в указанных регионах.")
        else:
            recommendations.append("🌍 Требования к сети АЗС не указаны явно. Возможно, есть гибкость в выборе.")

        # Дополнительные инсайты на основе данных о компании
        company_revenue_log = tender_data.get('company_revenue_log', 0)
        if company_revenue_log > np.log1p(10**9):
             recommendations.append("🏢 Заказчик - крупная компания с высоким оборотом, что снижает риски неплатежей.")
        elif tender_data.get('company_is_sme', False):
             recommendations.append("❗ Заказчик является субъектом МСП. Согласно политике, мы не работаем с МСП.")


        # Если нет конкретных рекомендаций
        if len(recommendations) == 0:
            recommendations.append("Дополнительных рекомендаций нет. Тендер требует стандартного подхода.")

        return "\n".join(recommendations)
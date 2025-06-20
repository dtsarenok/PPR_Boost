# telegram_bot.py (в корневой директории проекта)
import sys
import os
import logging
import subprocess
import asyncio

import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode


from src.database.db_manager import DBManager
from src.database.models import Tender
from src.reporting.insights_generator_bot import (InsightsGenerator)
from config.settings import TELEGRAM_BOT_TOKEN, MAJOR_AZS_NETWORKS, \
    TENDER_KEYWORDS_FUEL


logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)


db_manager = DBManager()
insights_generator = InsightsGenerator()


print(f"DEBUG_BOT: Type of InsightsGenerator class: {type(InsightsGenerator)}")
print(f"DEBUG_BOT: Module where InsightsGenerator class is defined: {InsightsGenerator.__module__}")
try:
    print(f"DEBUG_BOT: Path to InsightsGenerator module: {sys.modules[InsightsGenerator.__module__].__file__}")
except AttributeError:
    print("DEBUG_BOT: Could not determine file path for InsightsGenerator module (might be built-in or dynamic).")
print(f"DEBUG_BOT: Type of insights_generator instance: {type(insights_generator)}")
if hasattr(insights_generator, 'get_tenders_for_analysis'):
    print("DEBUG_BOT: insights_generator instance HAS 'get_tenders_for_analysis' method.")
else:
    print("DEBUG_BOT: insights_generator instance DOES NOT HAVE 'get_tenders_for_analysis' method.")
    print("DEBUG_BOT: Listing all attributes/methods of insights_generator instance:")
    for attr_name in dir(insights_generator):
        if not attr_name.startswith('_'):
            print(f"  - {attr_name}")





def run_main_analysis_in_thread():
    python_executable = sys.executable

    main_script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'main.py')

    # Проверка существования main.py
    if not os.path.exists(main_script_path):
        logger.error(f"Файл main.py не найден по пути: {main_script_path}")
        return False

    try:
        logger.info(f"Запуск main.py: {python_executable} {main_script_path}")

        process = subprocess.Popen(
            [python_executable, main_script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate()

        if process.returncode == 0:
            logger.info("Анализ main.py завершен успешно.")
            logger.info(f"Stdout main.py:\n{stdout}")
            if stderr:
                logger.warning(f"Stderr main.py:\n{stderr}")
            return True
        else:
            logger.error(f"Ошибка при запуске main.py (код выхода: {process.returncode}):")
            logger.error(f"Stderr: {stderr}")
            logger.error(f"Stdout: {stdout}")
            return False
    except Exception as e:
        logger.error(f"Неожиданная ошибка при запуске main.py: {e}", exc_info=True)
        return False




async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет приветственное сообщение и основные команды."""
    welcome_message = (
        "Привет! Я твой Sales Smart Leads бот. "
        "Я помогу тебе находить перспективные тендеры и давать по ним рекомендации.\n\n"
        "Доступные команды:\n"
        "/leads - Показать список перспективных тендеров (без фильтров)\n"
        "/filter_tenders - Настроить и применить фильтры для поиска тендеров\n"
        "/run_analysis - Запустить новый анализ тендеров\n"
        "/help - Показать это сообщение снова"
    )
    await update.message.reply_text(welcome_message)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет сообщение с помощью."""
    await start(update, context)


async def leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список перспективных тендеров (без фильтров)."""
    try:
        await update.message.reply_text("Загружаю перспективные тендеры...")
        all_tenders_df = insights_generator.get_tenders_for_analysis(processed_only=True)

        if all_tenders_df.empty:
            await update.message.reply_text(
                "Пока нет обработанных перспективных тендеров. Попробуйте запустить /run_analysis.")
            return


        if 'probability' in all_tenders_df.columns:
            top_tenders = insights_generator.sort_tenders(all_tenders_df, sort_by='probability', ascending=False).head(
                10)
        else:
            logger.warning(
                "Колонка 'probability' отсутствует в DataFrame. Отображаю первые 10 тендеров без сортировки.")
            top_tenders = all_tenders_df.head(10)

        if top_tenders.empty:
            await update.message.reply_text(
                "Не удалось найти перспективные тендеры после сортировки (или после извлечения).")
            return

        formatted_messages = insights_generator.format_tenders_for_telegram(top_tenders)

        for msg in formatted_messages:
            for chunk in [msg[i:i + 4096] for i in range(0, len(msg), 4096)]:
                await update.message.reply_text(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)
            await asyncio.sleep(0.1)

    except Exception as e:
        logger.error(f"Ошибка при получении списка тендеров: {e}", exc_info=True)
        await update.message.reply_text(f"Произошла ошибка при загрузке тендеров: {e}")


async def run_analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Запускает полный цикл анализа тендеров."""
    await update.message.reply_text(
        "Запускаю новый анализ тендеров... Это может занять несколько минут. Я сообщу о завершении.")
    # Запускаем в отдельном потоке, чтобы не блокировать основной поток бота
    success = await asyncio.to_thread(run_main_analysis_in_thread)
    await send_analysis_result(update, success)


async def send_analysis_result(update: Update, success: bool):
    if success:
        await update.message.reply_text(
            "Анализ завершен успешно! Используйте /leads или /filter_tenders для просмотра новых тендеров.")
    else:
        await update.message.reply_text("Анализ завершился с ошибкой. Проверьте логи сервера.")


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает неизвестные команды."""
    await update.message.reply_text("Извините, я не понял эту команду. Используйте /help для списка команд.")



# Состояния для диалога фильтрации
FILTER_STATE_START = 0
FILTER_STATE_PRICE_MIN = 1
FILTER_STATE_PRICE_MAX = 2
FILTER_STATE_REGION = 3
FILTER_STATE_FUEL_TYPE = 4
FILTER_STATE_CONTRACT_DURATION_MIN = 5
FILTER_STATE_CONTRACT_DURATION_MAX = 6
FILTER_STATE_PAYMENT_TYPE = 7
FILTER_STATE_PREPAYMENT_PERCENTAGE_MIN = 8
FILTER_STATE_PAYMENT_DEFERRAL_MAX = 9
FILTER_STATE_AZS_NETWORKS = 10
FILTER_STATE_EXCLUDE_SME = 11
FILTER_STATE_MIN_PROBABILITY = 12
FILTER_STATE_RECENT_DAYS = 13
FILTER_STATE_SEARCH_TEXT = 14
FILTER_STATE_SORT_BY = 15
FILTER_STATE_FINAL = 16


async def filter_tenders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):

    logger.info("Пользователь начал настройку фильтров.")

    context.user_data['filters'] = {}
    context.user_data['filter_state'] = FILTER_STATE_START


    if update.message:
        sent_message = await update.message.reply_text(
            "Начнем настройку фильтров для тендеров. Вы можете пропускать шаги, если фильтр не нужен.\n\n"
        )
        context.user_data['filter_message_id'] = sent_message.message_id

    await ask_price_min(update.message, context)


async def ask_price_min(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    prompt = "Введите минимальную цену (число, например, 1000000) или 'пропустить':"
    context.user_data['filter_state'] = FILTER_STATE_PRICE_MIN
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt
        )
    else:
        await message.reply_text(prompt)


async def ask_max_price(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    prompt = "Введите максимальную цену (число, например, 5000000) или 'пропустить':"
    context.user_data['filter_state'] = FILTER_STATE_PRICE_MAX
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt
        )
    else:
        await message.reply_text(prompt)


async def handle_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id
    current_state = context.user_data.get('filter_state', FILTER_STATE_START)

    logger.info(f"Обработка коллбэка фильтра: {data}, текущее состояние: {current_state}")


    if data.startswith('region_'):
        region = data.split('_', 1)[1]
        if region == 'skip':
            context.user_data['filters'].pop('regions', None)
            context.user_data['filter_state'] = FILTER_STATE_FUEL_TYPE
            await ask_fuel_type(query.message, context, edit_message=True)
        elif region == 'done':
            context.user_data['filter_state'] = FILTER_STATE_FUEL_TYPE
            await ask_fuel_type(query.message, context, edit_message=True)
        else:
            selected_regions = context.user_data['filters'].get('regions', [])
            if region in selected_regions:
                selected_regions.remove(region)
            else:
                selected_regions.append(region)
            context.user_data['filters']['regions'] = selected_regions
            await ask_region(query.message, context, edit_message=True)  # Обновляем сообщение с кнопками

    elif data.startswith('fuel_type_'):
        fuel_type = data.split('_', 1)[1]
        if fuel_type == 'skip':
            context.user_data['filters'].pop('fuel_types', None)
            context.user_data['filter_state'] = FILTER_STATE_CONTRACT_DURATION_MIN
            await ask_contract_duration_min(query.message, context, edit_message=True)
        elif fuel_type == 'done':
            context.user_data['filter_state'] = FILTER_STATE_CONTRACT_DURATION_MIN
            await ask_contract_duration_min(query.message, context, edit_message=True)
        else:
            selected_fuel_types = context.user_data['filters'].get('fuel_types', [])
            if fuel_type in selected_fuel_types:
                selected_fuel_types.remove(fuel_type)
            else:
                selected_fuel_types.append(fuel_type)
            context.user_data['filters']['fuel_types'] = selected_fuel_types
            await ask_fuel_type(query.message, context, edit_message=True)

    elif data == 'skip_contract_duration':
        context.user_data['filters'].pop('min_contract_duration_days', None)
        context.user_data['filters'].pop('max_contract_duration_days', None)
        context.user_data['filter_state'] = FILTER_STATE_PAYMENT_TYPE
        await ask_payment_type(query.message, context, edit_message=True)

    elif data.startswith('payment_option_'):
        option = data.split('_', 2)[2]
        if option == 'prepayment':
            context.user_data['filters']['prepayment_required'] = True
            context.user_data['filter_state'] = FILTER_STATE_PREPAYMENT_PERCENTAGE_MIN
            await query.edit_message_text("Введите минимальный процент предоплаты (число, 0-100) или 'пропустить':")
        elif option == 'no_prepayment':
            context.user_data['filters']['prepayment_required'] = False
            context.user_data['filters'].pop('min_prepayment_percentage', None)
            context.user_data['filter_state'] = FILTER_STATE_PAYMENT_DEFERRAL_MAX
            await query.edit_message_text(
                "Введите максимальное количество дней отсрочки платежа (число) или 'пропустить':")
        elif option == 'any':
            context.user_data['filters'].pop('prepayment_required', None)
            context.user_data['filters'].pop('min_prepayment_percentage', None)
            context.user_data['filters'].pop('max_payment_deferral_days', None)
            context.user_data['filter_state'] = FILTER_STATE_AZS_NETWORKS
            await ask_azs_networks(query.message, context, edit_message=True)

    elif data.startswith('azs_network_'):
        network_name = data.split('_', 2)[2]
        if network_name == 'skip':
            context.user_data['filters'].pop('azs_networks', None)
            context.user_data['filter_state'] = FILTER_STATE_EXCLUDE_SME
            await ask_exclude_sme(query.message, context, edit_message=True)
        elif network_name == 'done':
            context.user_data['filter_state'] = FILTER_STATE_EXCLUDE_SME
            await ask_exclude_sme(query.message, context, edit_message=True)
        else:
            selected_azs = context.user_data['filters'].get('azs_networks', [])
            if network_name in selected_azs:
                selected_azs.remove(network_name)
            else:
                selected_azs.append(network_name)
            context.user_data['filters']['azs_networks'] = selected_azs
            await ask_azs_networks(query.message, context, edit_message=True)

    elif data == 'set_exclude_sme_true':
        context.user_data['filters']['exclude_sme'] = True
        context.user_data['filter_state'] = FILTER_STATE_MIN_PROBABILITY
        await query.edit_message_text(
            "Введите минимальную вероятность выигрыша (число от 0.0 до 1.0) или 'пропустить':")
    elif data == 'set_exclude_sme_false':
        context.user_data['filters']['exclude_sme'] = False
        context.user_data['filter_state'] = FILTER_STATE_MIN_PROBABILITY
        await query.edit_message_text(
            "Введите минимальную вероятность выигрыша (число от 0.0 до 1.0) или 'пропустить':")
    elif data == 'skip_exclude_sme':
        context.user_data['filters'].pop('exclude_sme', None)
        context.user_data['filter_state'] = FILTER_STATE_MIN_PROBABILITY
        await query.edit_message_text(
            "Введите минимальную вероятность выигрыша (число от 0.0 до 1.0) или 'пропустить':")

    elif data == 'skip_recent_days_btn':
        context.user_data['filters'].pop('recent_days', None)
        context.user_data['filter_state'] = FILTER_STATE_SEARCH_TEXT
        await ask_search_text(query.message, context, edit_message=True)

    elif data == 'skip_search_text_btn':  # Новая кнопка
        context.user_data['filters'].pop('search_text', None)
        context.user_data['filter_state'] = FILTER_STATE_SORT_BY
        await ask_sort_by(query.message, context, edit_message=True)

    elif data.startswith('sort_by_'):
        sort_option = data.split('_', 2)[2]
        if sort_option == 'skip':
            context.user_data['filters'].pop('sort_by', None)
            context.user_data['filters'].pop('sort_ascending', None)
        else:
            parts = sort_option.split('_')
            sort_by_col = parts[0]
            sort_ascending = True if parts[1] == 'asc' else False
            context.user_data['filters']['sort_by'] = sort_by_col
            context.user_data['filters']['sort_ascending'] = sort_ascending

        context.user_data['filter_state'] = FILTER_STATE_FINAL
        await show_filtered_tenders(query.message, context)


async def handle_filter_message(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message_text = update.message.text.strip().lower()
    chat_id = update.message.chat_id
    current_state = context.user_data.get('filter_state')

    logger.info(f"Обработка текстового сообщения: '{message_text}', текущее состояние: {current_state}")

    if message_text == 'пропустить' or message_text == '/пропустить':

        if current_state == FILTER_STATE_PRICE_MIN:
            context.user_data['filters'].pop('min_price', None)
            context.user_data['filter_state'] = FILTER_STATE_PRICE_MAX
            await ask_max_price(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_PRICE_MAX:
            context.user_data['filters'].pop('max_price', None)
            context.user_data['filter_state'] = FILTER_STATE_REGION
            await ask_region(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_CONTRACT_DURATION_MIN:
            context.user_data['filters'].pop('min_contract_duration_days', None)
            context.user_data['filter_state'] = FILTER_STATE_CONTRACT_DURATION_MAX
            await ask_contract_duration_max(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_CONTRACT_DURATION_MAX:
            context.user_data['filters'].pop('max_contract_duration_days', None)
            context.user_data['filter_state'] = FILTER_STATE_PAYMENT_TYPE
            await ask_payment_type(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_PREPAYMENT_PERCENTAGE_MIN:
            context.user_data['filters'].pop('min_prepayment_percentage', None)
            context.user_data['filter_state'] = FILTER_STATE_PAYMENT_DEFERRAL_MAX
            await update.message.reply_text(
                "Введите максимальное количество дней отсрочки платежа (число) или 'пропустить':")

        elif current_state == FILTER_STATE_PAYMENT_DEFERRAL_MAX:
            context.user_data['filters'].pop('max_payment_deferral_days', None)
            context.user_data['filter_state'] = FILTER_STATE_AZS_NETWORKS
            await ask_azs_networks(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_MIN_PROBABILITY:
            context.user_data['filters'].pop('min_probability', None)
            context.user_data['filter_state'] = FILTER_STATE_RECENT_DAYS
            await ask_recent_days(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_RECENT_DAYS:
            context.user_data['filters'].pop('recent_days', None)
            context.user_data['filter_state'] = FILTER_STATE_SEARCH_TEXT
            await ask_search_text(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_SEARCH_TEXT:
            context.user_data['filters'].pop('search_text', None)
            context.user_data['filter_state'] = FILTER_STATE_SORT_BY
            await ask_sort_by(update.message, context, edit_message=True)
        else:
            await update.message.reply_text("Неизвестное состояние или команда 'пропустить' не применима здесь.")
        return


    try:
        if current_state == FILTER_STATE_PRICE_MIN:
            value = float(re.sub(r'[^\d.]', '', message_text))
            context.user_data['filters']['min_price'] = value
            context.user_data['filter_state'] = FILTER_STATE_PRICE_MAX
            await ask_max_price(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_PRICE_MAX:
            value = float(re.sub(r'[^\d.]', '', message_text))
            context.user_data['filters']['max_price'] = value
            context.user_data['filter_state'] = FILTER_STATE_REGION
            await ask_region(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_CONTRACT_DURATION_MIN:
            value = int(message_text)
            context.user_data['filters']['min_contract_duration_days'] = value
            context.user_data['filter_state'] = FILTER_STATE_CONTRACT_DURATION_MAX
            await ask_contract_duration_max(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_CONTRACT_DURATION_MAX:
            value = int(message_text)
            context.user_data['filters']['max_contract_duration_days'] = value
            context.user_data['filter_state'] = FILTER_STATE_PAYMENT_TYPE
            await ask_payment_type(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_PREPAYMENT_PERCENTAGE_MIN:
            value = float(message_text)
            if not (0 <= value <= 100):
                raise ValueError("Процент должен быть от 0 до 100.")
            context.user_data['filters']['min_prepayment_percentage'] = value
            context.user_data['filter_state'] = FILTER_STATE_PAYMENT_DEFERRAL_MAX
            await update.message.reply_text(  # Здесь reply_text, так как это запрос на ввод
                "Введите максимальное количество дней отсрочки платежа (число) или 'пропустить':")
        elif current_state == FILTER_STATE_PAYMENT_DEFERRAL_MAX:
            value = int(message_text)
            context.user_data['filters']['max_payment_deferral_days'] = value
            context.user_data['filter_state'] = FILTER_STATE_AZS_NETWORKS
            await ask_azs_networks(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_MIN_PROBABILITY:
            value = float(message_text)
            if not (0.0 <= value <= 1.0):
                raise ValueError("Вероятность должна быть от 0.0 до 1.0.")
            context.user_data['filters']['min_probability'] = value
            context.user_data['filter_state'] = FILTER_STATE_RECENT_DAYS
            await ask_recent_days(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_RECENT_DAYS:
            value = int(message_text)
            context.user_data['filters']['recent_days'] = value
            context.user_data['filter_state'] = FILTER_STATE_SEARCH_TEXT
            await ask_search_text(update.message, context, edit_message=True)
        elif current_state == FILTER_STATE_SEARCH_TEXT:
            context.user_data['filters']['search_text'] = message_text
            context.user_data['filter_state'] = FILTER_STATE_SORT_BY
            await ask_sort_by(update.message, context, edit_message=True)
        else:
            await update.message.reply_text(
                "Пожалуйста, используйте кнопки или введите числовое значение, как указано.")
            return

    except ValueError as ve:
        await update.message.reply_text(
            f"Неверный формат или значение: {ve}. Пожалуйста, введите корректное число или 'пропустить'.")
    except Exception as e:
        logger.error(f"Ошибка при обработке числового ввода: {e}", exc_info=True)
        await update.message.reply_text("Произошла ошибка при обработке вашего ввода.")


async def ask_region(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    try:
        with db_manager.get_session() as session:

            all_available_regions = [r[0] for r in session.query(Tender.region).distinct().all() if r[0] is not None]
            if not all_available_regions:
                all_available_regions = [
                    "Москва", "Московская область", "Санкт-Петербург", "Ленинградская область",
                    "Республика Татарстан", "Свердловская область", "Краснодарский край",
                    "Новосибирская область", "Ростовская область", "Иркутская область", "Республика Башкортостан"
                ]
    except Exception as e:
        logger.error(f"Ошибка при получении регионов из БД: {e}. Используем дефолтные.", exc_info=True)
        all_available_regions = [
            "Москва", "Московская область", "Санкт-Петербург", "Ленинградская область",
            "Республика Татарстан", "Свердловская область", "Краснодарский край",
            "Новосибирская область", "Ростовская область", "Иркутская область", "Республика Башкортостан"
        ]

    selected_regions = context.user_data['filters'].get('regions', [])
    keyboard_rows = []


    for region in sorted(all_available_regions):
        text = f"✅ {region}" if region in selected_regions else region
        keyboard_rows.append([InlineKeyboardButton(text, callback_data=f'region_{region}')])

    keyboard_rows.append([
        InlineKeyboardButton("Готово (Далее)", callback_data='region_done'),
        InlineKeyboardButton("Пропустить", callback_data='region_skip')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    current_selection_text = ", ".join(selected_regions) if selected_regions else "не выбраны"
    prompt = f"Выберите регион(ы) (выбранные: {current_selection_text}):"


    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def ask_fuel_type(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    all_available_fuel_types = list(set([k.title() for k in TENDER_KEYWORDS_FUEL]))

    if "ДТ" not in all_available_fuel_types: all_available_fuel_types.append("ДТ")
    if "Бензин" not in all_available_fuel_types: all_available_fuel_types.append("Бензин")


    try:
        with db_manager.get_session() as session:
            db_fuel_types = [t[0] for t in session.query(Tender.fuel_type).distinct().all() if t[0] is not None]
            #
            all_available_fuel_types = sorted(list(set(all_available_fuel_types + db_fuel_types)))
    except Exception as e:
        logger.warning(f"Не удалось получить типы топлива из БД: {e}. Используем только ключевые слова.", exc_info=True)

    selected_fuel_types = context.user_data['filters'].get('fuel_types', [])
    keyboard_rows = []

    for fuel_type in all_available_fuel_types:
        text = f"✅ {fuel_type}" if fuel_type in selected_fuel_types else fuel_type
        keyboard_rows.append([InlineKeyboardButton(text, callback_data=f'fuel_type_{fuel_type}')])

    keyboard_rows.append([
        InlineKeyboardButton("Готово (Далее)", callback_data='fuel_type_done'),
        InlineKeyboardButton("Пропустить", callback_data='fuel_type_skip')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    current_selection_text = ", ".join(selected_fuel_types) if selected_fuel_types else "не выбраны"
    prompt = f"Выберите тип(ы) топлива (выбранные: {current_selection_text}):"

    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def ask_contract_duration_min(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    prompt = "Введите минимальную длительность контракта в днях (число) или 'пропустить':"
    context.user_data['filter_state'] = FILTER_STATE_CONTRACT_DURATION_MIN
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt
        )
    else:
        await message.reply_text(prompt)


async def ask_contract_duration_max(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    prompt = "Введите максимальную длительность контракта в днях (число) или 'пропустить':"
    context.user_data['filter_state'] = FILTER_STATE_CONTRACT_DURATION_MAX
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt
        )
    else:
        await message.reply_text(prompt)


async def ask_payment_type(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):
    """Спрашивает тип оплаты."""
    keyboard = [
        [InlineKeyboardButton("Предоплата", callback_data='payment_option_prepayment')],
        [InlineKeyboardButton("Без предоплаты", callback_data='payment_option_no_prepayment')],
        [InlineKeyboardButton("Любой тип оплаты", callback_data='payment_option_any')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    prompt = "Выберите тип оплаты:"
    context.user_data['filter_state'] = FILTER_STATE_PAYMENT_TYPE
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def ask_azs_networks(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    selected_azs = context.user_data['filters'].get('azs_networks', [])
    keyboard_rows = []

    for network in sorted(MAJOR_AZS_NETWORKS):
        text = f"✅ {network}" if network in selected_azs else network
        keyboard_rows.append([InlineKeyboardButton(text, callback_data=f'azs_network_{network}')])

    keyboard_rows.append([
        InlineKeyboardButton("Готово (Далее)", callback_data='azs_network_done'),
        InlineKeyboardButton("Пропустить", callback_data='azs_network_skip')
    ])

    reply_markup = InlineKeyboardMarkup(keyboard_rows)

    current_selection_text = ", ".join(selected_azs) if selected_azs else "не выбраны"
    prompt = f"Выберите требуемые АЗС сети (выбранные: {current_selection_text}):"

    context.user_data['filter_state'] = FILTER_STATE_AZS_NETWORKS
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def ask_exclude_sme(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    keyboard = [
        [InlineKeyboardButton("Исключить МСП", callback_data='set_exclude_sme_true')],
        [InlineKeyboardButton("Включить МСП", callback_data='set_exclude_sme_false')],
        [InlineKeyboardButton("Пропустить", callback_data='skip_exclude_sme')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    prompt = "Исключить тендеры для субъектов МСП?"
    context.user_data['filter_state'] = FILTER_STATE_EXCLUDE_SME
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def ask_min_probability(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):
    """Спрашивает минимальную вероятность выигрыша."""
    prompt = "Введите минимальную вероятность выигрыша (число от 0.0 до 1.0) или 'пропустить':"
    context.user_data['filter_state'] = FILTER_STATE_MIN_PROBABILITY
    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt
        )
    else:
        await message.reply_text(prompt)


async def ask_recent_days(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    prompt = "Показывать тендеры, опубликованные за последние N дней? Введите число (например, 7) или 'пропустить':"
    context.user_data['filter_state'] = FILTER_STATE_RECENT_DAYS


    keyboard = [[InlineKeyboardButton("Пропустить", callback_data='skip_recent_days_btn')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def ask_search_text(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):

    prompt = "Введите ключевые слова для поиска в заголовке/описании или 'пропустить':"
    context.user_data['filter_state'] = FILTER_STATE_SEARCH_TEXT

    keyboard = [[InlineKeyboardButton("Пропустить", callback_data='skip_search_text_btn')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def ask_sort_by(message, context: ContextTypes.DEFAULT_TYPE, edit_message: bool = False):
    """Спрашивает, как сортировать результаты."""
    keyboard = [
        [InlineKeyboardButton("По вероятности (убыв.)", callback_data='sort_by_probability_desc')],
        [InlineKeyboardButton("По цене (убыв.)", callback_data='sort_by_price_desc')],
        [InlineKeyboardButton("По дате публикации (убыв.)", callback_data='sort_by_publication_date_desc')],
        [InlineKeyboardButton("Не сортировать (показать результаты)", callback_data='sort_by_skip')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    prompt = "Как отсортировать результаты?"
    context.user_data['filter_state'] = FILTER_STATE_SORT_BY

    if edit_message and context.user_data.get('filter_message_id'):
        await context.bot.edit_message_text(
            chat_id=message.chat_id,
            message_id=context.user_data['filter_message_id'],
            text=prompt,
            reply_markup=reply_markup
        )
    else:
        sent_message = await message.reply_text(prompt, reply_markup=reply_markup)
        context.user_data['filter_message_id'] = sent_message.message_id


async def show_filtered_tenders(message_or_query_message, context: ContextTypes.DEFAULT_TYPE):

    if isinstance(message_or_query_message, CallbackQuery):
        message = message_or_query_message.message

    else:
        message = message_or_query_message

    user_filters = context.user_data.get('filters', {})
    logger.info(f"Применяю фильтры: {user_filters}")

    await context.bot.send_message(
        chat_id=message.chat_id,
        text="Применяю ваши фильтры и загружаю тендеры...",
        parse_mode=ParseMode.HTML
    )

    try:

        all_tenders_df = insights_generator.get_tenders_for_analysis(processed_only=True)

        if all_tenders_df.empty:
            await context.bot.send_message(
                chat_id=message.chat_id,
                text="В базе данных нет обработанных тендеров. Попробуйте запустить /run_analysis."
            )
            context.user_data['filter_state'] = FILTER_STATE_FINAL  # Сброс состояния
            context.user_data.pop('filters', None)
            context.user_data.pop('filter_message_id', None)
            return


        filtered_df = insights_generator.filter_tenders(all_tenders_df, **user_filters)


        sort_by_col = user_filters.get('sort_by')
        sort_ascending = user_filters.get('sort_ascending', False)
        if sort_by_col:
            filtered_df = insights_generator.sort_tenders(filtered_df, sort_by=sort_by_col, ascending=sort_ascending)

        if filtered_df.empty:
            await context.bot.send_message(
                chat_id=message.chat_id,
                text="По вашим критериям тендеры не найдены. Попробуйте изменить фильтры."
            )
        else:

            max_results = 10
            display_df = filtered_df.head(max_results)
            formatted_messages = insights_generator.format_tenders_for_telegram(display_df)

            for msg in formatted_messages:
                for chunk in [msg[i:i + 4096] for i in range(0, len(msg), 4096)]:
                    await context.bot.send_message(
                        chat_id=message.chat_id,
                        text=chunk,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                await asyncio.sleep(0.1)

            if len(filtered_df) > max_results:
                await context.bot.send_message(
                    chat_id=message.chat_id,
                    text=f"Найдено всего {len(filtered_df)} тендеров. Показаны первые {max_results}. "
                         f"Для более глубокого анализа используйте другие инструменты."
                )

    except Exception as e:
        logger.error(f"Ошибка при показе отфильтрованных тендеров: {e}", exc_info=True)
        await context.bot.send_message(
            chat_id=message.chat_id,
            text=f"Произошла ошибка при получении отфильтрованных тендеров: {e}"
        )
    finally:

        context.user_data['filter_state'] = FILTER_STATE_FINAL
        context.user_data.pop('filters', None)
        context.user_data.pop('filter_message_id', None)



def main():
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Токен Telegram бота не найден. Убедитесь, что он установлен в config/settings.py или .env.")
        sys.exit(1)

    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("leads", leads))
    application.add_handler(CommandHandler("run_analysis", run_analysis_command))
    application.add_handler(CommandHandler("filter_tenders", filter_tenders_command))


    application.add_handler(CallbackQueryHandler(handle_filter_callback))


    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_filter_message))


    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    logger.info("Бот запущен. Ожидание сообщений...")
    application.run_polling()


if __name__ == "__main__":
    main()
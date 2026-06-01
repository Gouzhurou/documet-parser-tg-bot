"""
Telegram-бот для парсинга строительной документации.
Принимает файлы Excel, Word, изображения и возвращает JSON с таблицами и метаданными.
"""

import os
from pathlib import Path
from datetime import datetime

import telebot
from telebot.types import Message, Document
from dotenv import load_dotenv

from document_parser import (
    parse_file,
    is_supported_file,
    ParseResult, export_to_json,
)

load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
TESSERACT_PATH = os.getenv("TESSERACT_PATH", r"C:\Program Files\Tesseract-OCR\tesseract.exe")

bot = telebot.TeleBot(TOKEN)

# Папка для временных файлов
DOWNLOADS_DIR = Path("downloads")
DOWNLOADS_DIR.mkdir(exist_ok=True)

# Основные команды
commands = [
    telebot.types.BotCommand("start", "Запуск бота"),
    telebot.types.BotCommand("help", "Справка по форматам"),
    telebot.types.BotCommand("formats", "Поддерживаемые форматы"),
]

bot.set_my_commands(commands)

def format_result_summary(result: ParseResult, original_filename: str) -> str:
    """
    Форматирует результат парсинга в краткую сводку для отправки пользователю.
    """
    if not result.success:
        return f"Ошибка при обработке файла: {result.error}"

    lines = [
        f"Файл: `{original_filename}`",
        f"Успешно обработан",
        f"Найдено таблиц: {len(result.tables)}",
    ]

    for i, table in enumerate(result.tables, 1):
        lines.append(f"\n Таблица {i}: _{table.sheet_name}_")
        lines.append(f"\tСтолбцов: {len(table.headers)}")
        lines.append(f"\tСтрок данных: {len(table.rows)}")

    return "\n".join(lines)


def cleanup_files(*paths: Path):
    """Удаляет временные файлы."""
    for path in paths:
        try:
            if path.exists():
                os.unlink(path)
        except Exception:
            pass


@bot.message_handler(commands=['start'])
def handle_start(message: Message):
    """Приветственное сообщение."""
    welcome_text = (
        "Привет! Я бот для парсинга строительной документации.\n\n"
        "Отправьте мне файл, и я извлеку из него:\n"
        "• Таблицы с данными\n"
        "• Метаданные (название, объект, заказчик, подрядчик, дата и т.д.)\n\n"
        "Поддерживаемые форматы:\n"
        "• Excel: .xls, .xlsx, .xlsm\n"
        "• Word: .docx, .doc\n"
        "• Изображения: .jpg, .jpeg, .png, .tiff, .tif, .bmp\n\n"
        "В ответ вы получите:\n"
        "• Краткую сводку о распарсенном документе\n"
        "• JSON-файл с полными данными таблиц\n\n"
        "Используйте /help для справки или /formats для списка форматов."
    )

    bot.reply_to(message, welcome_text)


@bot.message_handler(commands=['help'])
def handle_help(message: Message):
    """Справка."""
    help_text = (
        "Как пользоваться ботом:\n\n"
        "1. Отправьте файл (Excel, Word или изображение)\n"
        "2. Бот обработает файл и пришлёт результат\n\n"
        "Форматы файлов:\n"
        "• Excel: .xls, .xlsx, .xlsm\n"
        "• Word: .docx, .doc\n"
        "• Изображения: .jpg, .jpeg, .png, .tiff, .tif, .bmp\n\n"
        "Что извлекается:\n"
        "• Таблицы (строки и столбцы)\n"
        "• Метаданные (название, объект, заказчик, подрядчик, дата и т.д.)\n"
        "Результат:\n"
        "• Текстовое описание\n"
        "• JSON-файл с данными"
    )

    bot.reply_to(message, help_text)


@bot.message_handler(commands=['formats'])
def handle_formats(message: Message):
    """Список поддерживаемых форматов."""
    formats_text = (
        "Поддерживаемые форматы файлов:\n\n"
        "Excel:\n"
        "• .xls — Excel 97-2003\n"
        "• .xlsx — Excel 2007+\n"
        "• .xlsm — Excel с макросами\n\n"
        "Word:\n"
        "• .docx — Word 2007+\n"
        "• .doc — Word 97-2003\n\n"
        "Изображения:\n"
        "• .jpg, .jpeg — фотографии\n"
        "• .png — скриншоты\n"
        "• .tiff, .tif — сканы\n"
        "• .bmp — bitmap\n\n"
        "Для изображений используется OCR (Tesseract). Качество зависит от читаемости текста."
    )

    bot.reply_to(message, formats_text)


@bot.message_handler(content_types=['document'])
def handle_document(message: Message):
    """Обработка загруженного документа."""
    document: Document = message.document
    file_name = document.file_name
    # TODO: добавить предобработку плохих названий (со спецсимволами)
    ext = Path(file_name).suffix.lower()

    if not is_supported_file(file_name):
        bot.reply_to(
            message,
            f"Формат `{ext}` не поддерживается.\n"
            f"Используйте /formats для просмотра списка поддерживаемых форматов.",
        )
        return

    status_msg = bot.reply_to(
        message,
        f"Скачиваю файл...\n📄 {file_name}",
    )

    try:
        file_info = bot.get_file(document.file_id)
        downloaded = bot.download_file(file_info.file_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = DOWNLOADS_DIR / f"{timestamp}_{file_name}"

        with open(temp_path, 'wb') as f:
            f.write(downloaded)

        bot.edit_message_text(
            f"Обрабатываю файл...\n{file_name}\n\nПожалуйста, подождите...",
            message.chat.id,
            status_msg.message_id,
        )

        result = parse_file(str(temp_path))
        summary = format_result_summary(result, file_name)
        json_path = f"{Path(file_name).stem}_result.json"
        export_to_json(result, json_path)

        bot.edit_message_text(
            summary,
            message.chat.id,
            status_msg.message_id,
        )

        with open(json_path, 'rb') as f:
            bot.send_document(
                message.chat.id,
                f,
                caption=f"JSON-результат парсинга: _{file_name}_",
                visible_file_name=f"{Path(file_name).stem}_result.json"
            )

        cleanup_files(temp_path, Path(json_path))

    except FileNotFoundError as e:
        bot.edit_message_text(
            f"Файл не найден: {e}",
            message.chat.id,
            status_msg.message_id
        )
    except ValueError as e:
        bot.edit_message_text(
            f"Ошибка формата файла: {e}",
            message.chat.id,
            status_msg.message_id
        )
    except Exception as e:
        bot.edit_message_text(
            f"Непредвиденная ошибка:\n```\n{str(e)}\n```",
            message.chat.id,
            status_msg.message_id,
        )

        try:
            cleanup_files(temp_path)
        except:
            pass


@bot.message_handler(content_types=['photo'])
def handle_photo(message: Message):
    """Обработка фото (сжатые изображения)."""
    # Берём фото в максимальном разрешении
    photo = message.photo[-1]

    status_msg = bot.reply_to(
        message,
        "Скачиваю фото...",
    )

    try:
        file_info = bot.get_file(photo.file_id)
        downloaded = bot.download_file(file_info.file_path)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        temp_path = DOWNLOADS_DIR / f"{timestamp}_photo.jpg"

        with open(temp_path, 'wb') as f:
            f.write(downloaded)

        bot.edit_message_text(
            "Обрабатываю фото...",
            message.chat.id,
            status_msg.message_id,
        )

        result = parse_file(str(temp_path))
        summary = format_result_summary(result, "photo.jpg")
        json_path = "result.json"
        export_to_json(result, json_path)

        bot.edit_message_text(
            summary,
            message.chat.id,
            status_msg.message_id,
        )

        with open(json_path, 'rb') as f:
            bot.send_document(
                message.chat.id,
                f,
                caption="JSON-результат парсинга фото",
                visible_file_name="photo_result.json"
            )

        cleanup_files(temp_path, json_path)

    except Exception as e:
        bot.edit_message_text(
            f"Ошибка при обработке фото:\n{str(e)}",
            message.chat.id,
            status_msg.message_id
        )


if __name__ == "__main__":
    print("=" * 50)
    print("Бот для парсинга строительной документации")
    print("=" * 50)
    print(f"Папка загрузок: {DOWNLOADS_DIR.absolute()}")
    print("Бот запущен. Ожидание сообщений...")
    print("=" * 50)

    bot.infinity_polling()
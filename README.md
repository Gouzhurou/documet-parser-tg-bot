# documet-parser-tg-bot

Телеграм бот, предназначенный для демонстрации работы библиотеки document-parser.

## Начало использования 

1. Подтянуть зависимости из requirements.txt

```commandline
pip install -r requirements.txt
```

2. Скачать установщик Tesseract OCR с https://github.com/UB-Mannheim/tesseract/wiki

3. Установить, запомнить путь (например, C:\Program Files\Tesseract-OCR\tesseract.exe для Windows)

4. В файле .env указать свои токен, созданный в BotFather, и путь до tesseract.exe

5. Необходим установленный Microsoft Word для парсинга файлов формата .doc

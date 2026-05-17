# NBK Realty Bot

Telegram-бот для первичного анализа окружения объекта недвижимости.

## Что делает

1. Получает адрес.
2. Через Яндекс Геокодер получает координаты.
3. Через 2GIS Places API ищет организации в радиусе 500 м.
4. Возвращает:
   - координаты;
   - продуктовые сети;
   - ПВЗ;
   - аптеки;
   - QSR/кафе;
   - медицину;
   - банки;
   - услуги;
   - простой скоринг локации.

## Установка

```bash
cd nbk_realty_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Открой `.env` и вставь ключи:

```txt
TELEGRAM_BOT_TOKEN=...
YANDEX_API_KEY=...
DGIS_API_KEY=...
```

## Запуск

```bash
python bot.py
```

После запуска открой своего бота в Telegram и отправь адрес.

## Пример

```txt
Москва, Арбат 24
```


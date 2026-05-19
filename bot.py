import os
import telebot
import requests

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
DGIS_API_KEY = os.getenv("DGIS_API_KEY") or os.getenv("2GIS_API_KEY")
bot = telebot.TeleBot(TOKEN)


def geocode(address):
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": YANDEX_API_KEY,
        "geocode": address,
        "format": "json"
    }

    response = requests.get(url, params=params).json()
print(response)

    pos = response["response"]["GeoObjectCollection"]["featureMember"][0]["GeoObject"]["Point"]["pos"]

    lon, lat = pos.split()

    return lat, lon


def search_places(lat, lon):
    url = "https://catalog.api.2gis.com/3.0/items"

    params = {
        "q": "магазин",
        "location": f"{lon},{lat}",
        "radius": 500,
        "key": DGIS_API_KEY
    }

    response = requests.get(url, params=params).json()

    results = []

    if "result" in response and "items" in response["result"]:
        for item in response["result"]["items"][:10]:
            name = item.get("name", "Без названия")
            results.append(name)

    return results


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Отправь адрес объекта")


@bot.message_handler(func=lambda m: True)
def handle(message):
    try:
        address = message.text

        lat, lon = geocode(address)

        places = search_places(lat, lon)

        text = f"📍 {address}\n\n"

        text += "Что найдено рядом:\n\n"

        for p in places:
            text += f"• {p}\n"

        bot.send_message(message.chat.id, text)

    except Exception as e:
        bot.send_message(message.chat.id, f"Ошибка: {e}")


bot.infinity_polling()

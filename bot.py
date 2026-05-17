import os
import math
import requests
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
YANDEX_API_KEY = os.getenv("YANDEX_API_KEY")
DGIS_API_KEY = os.getenv("DGIS_API_KEY")

if not TELEGRAM_BOT_TOKEN:
    raise RuntimeError("Нет TELEGRAM_BOT_TOKEN в .env")
if not YANDEX_API_KEY:
    raise RuntimeError("Нет YANDEX_API_KEY в .env")
if not DGIS_API_KEY:
    raise RuntimeError("Нет DGIS_API_KEY в .env")


CATEGORIES = {
    "Продуктовые сети": ["Пятёрочка", "Пятерочка", "Чижик", "Магнит", "ВкусВилл", "Дикси", "Перекрёсток", "Перекресток"],
    "Алкоголь / FMCG": ["Красное Белое", "Красное&Белое", "Бристоль", "Винлаб"],
    "ПВЗ / маркетплейсы": ["Ozon", "Wildberries", "Яндекс Маркет"],
    "Аптеки": ["аптека"],
    "Кафе / QSR": ["Вкусно и точка", "Burger King", "KFC", "Ростикс", "Додо Пицца", "Шаурма", "кофейня"],
    "Медицина": ["медцентр", "клиника", "стоматология", "лаборатория"],
    "Банки / финансы": ["банк", "банкомат"],
    "Красота / услуги": ["салон красоты", "барбершоп", "парикмахерская"],
}


def geocode_yandex(address: str):
    url = "https://geocode-maps.yandex.ru/1.x/"
    params = {
        "apikey": YANDEX_API_KEY,
        "geocode": address,
        "format": "json",
        "lang": "ru_RU",
        "results": 1,
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    members = data["response"]["GeoObjectCollection"]["featureMember"]
    if not members:
        return None
    geo = members[0]["GeoObject"]
    pos = geo["Point"]["pos"]  # "lon lat"
    lon, lat = map(float, pos.split())
    found_address = geo["metaDataProperty"]["GeocoderMetaData"].get("text", address)
    return lon, lat, found_address


def search_2gis(query: str, lon: float, lat: float, radius: int = 500, page_size: int = 10):
    url = "https://catalog.api.2gis.com/3.0/items"
    params = {
        "q": query,
        "location": f"{lon},{lat}",
        "radius": radius,
        "key": DGIS_API_KEY,
        "page_size": page_size,
        "fields": "items.point,items.address_name,items.address_comment,items.rubrics,items.name",
    }
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    data = r.json()
    items = data.get("result", {}).get("items", [])
    result = []
    for item in items:
        point = item.get("point") or {}
        item_lon = point.get("lon")
        item_lat = point.get("lat")
        dist = None
        if item_lon and item_lat:
            dist = haversine_m(lat, lon, item_lat, item_lon)
        result.append({
            "name": item.get("name", ""),
            "address": item.get("address_name", ""),
            "comment": item.get("address_comment", ""),
            "distance": dist,
        })
    result.sort(key=lambda x: x["distance"] if x["distance"] is not None else 999999)
    return result


def haversine_m(lat1, lon1, lat2, lon2):
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return round(2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def score_location(summary_counts):
    score = 0
    score += min(summary_counts.get("Продуктовые сети", 0) * 8, 24)
    score += min(summary_counts.get("ПВЗ / маркетплейсы", 0) * 5, 15)
    score += min(summary_counts.get("Аптеки", 0) * 5, 15)
    score += min(summary_counts.get("Кафе / QSR", 0) * 4, 12)
    score += min(summary_counts.get("Медицина", 0) * 4, 12)
    score += min(summary_counts.get("Банки / финансы", 0) * 3, 9)
    score += min(summary_counts.get("Красота / услуги", 0) * 3, 9)
    score += min(summary_counts.get("Алкоголь / FMCG", 0) * 2, 4)
    return min(score, 100)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "NBK Realty Bot готов.\n\n"
        "Пришли адрес объекта, например:\n"
        "Москва, Арбат 24\n\n"
        "Я верну координаты и анализ окружения 2GIS в радиусе 500 м."
    )


async def handle_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    address = update.message.text.strip()
    await update.message.reply_text("Проверяю адрес и окружение...")

    try:
        geo = geocode_yandex(address)
        if not geo:
            await update.message.reply_text("Не нашёл координаты по этому адресу. Попробуй написать адрес подробнее.")
            return

        lon, lat, found_address = geo
        summary_counts = {}
        blocks = []

        for group, queries in CATEGORIES.items():
            seen = set()
            found = []
            for q in queries:
                try:
                    items = search_2gis(q, lon, lat, radius=500, page_size=5)
                    for it in items:
                        key = (it["name"], it["address"])
                        if key not in seen:
                            seen.add(key)
                            found.append(it)
                except Exception:
                    continue

            found = found[:8]
            summary_counts[group] = len(found)

            if found:
                lines = []
                for item in found[:5]:
                    dist = f"{item['distance']} м" if item["distance"] is not None else "н/д"
                    comment = f", {item['comment']}" if item["comment"] else ""
                    lines.append(f"— {item['name']} | {item['address']}{comment} | {dist}")
                blocks.append(f"*{group}* — {len(found)}\n" + "\n".join(lines))
            else:
                blocks.append(f"*{group}* — 0")

        score = score_location(summary_counts)

        if score >= 70:
            conclusion = "Сильная коммерческая локация: высокая насыщенность сетями и услугами."
        elif score >= 40:
            conclusion = "Средняя локация: есть коммерческое окружение, нужно дополнительно проверить трафик и вход."
        else:
            conclusion = "Слабая или недостаточно насыщенная локация: нужна ручная проверка трафика, фасада и спроса."

        text = (
            f"*Адрес:* {found_address}\n"
            f"*Координаты:* `{lat:.6f}, {lon:.6f}`\n"
            f"*Радиус анализа:* 500 м\n"
            f"*Скоринг:* {score}/100\n\n"
            + "\n\n".join(blocks)
            + f"\n\n*Вывод:* {conclusion}"
        )

        await update.message.reply_markdown(text)

    except Exception as e:
        await update.message.reply_text(f"Ошибка при анализе: {e}")


def main():
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_address))
    app.run_polling()


if __name__ == "__main__":
    main()

import time
import threading
import cloudscraper
from bs4 import BeautifulSoup
import telebot
from telebot import types
from flask import Flask

# === МИНИ ВЕБ-СЕРВЕР ДЛЯ ОБМАНА RENDER ===
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Бот Oikotie активен и работает!"

def run_flask():
    # Запускаем веб-сервер на порту 10000 (стандарт для Render)
    flask_app.run(host='0.0.0.0', port=10000)
# =======================================

class OikotieInteractiveBot:
    def __init__(self, url: str, tg_token: str, chat_id: int):
        self.url = url
        self.chat_id = chat_id
        self.bot = telebot.TeleBot(tg_token)
        self.seen_apartments = set()
        self.scraper = cloudscraper.create_scraper()
        self.preload_current_apartments()

    def preload_current_apartments(self):
        print("[Старт] Сканирую Oikotie для наполнения базы данных...")
        try:
            response = self.scraper.get(self.url)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                cards = soup.find_all('div', class_='cards-v2__card') or soup.find_all('article')
                for card in cards:
                    link_tag = card.find('a', href=True)
                    if link_tag:
                        link = link_tag['href']
                        apartment_id = link.split('/')[-1]
                        if apartment_id:
                            self.seen_apartments.add(apartment_id)
                print(f"[Старт] База успешно инициализирована. Запомнено квартир: {len(self.seen_apartments)}")
            else:
                print(f"[Старт Ошибка] Статус: {response.status_code}")
        except Exception as e:
            print(f"[Старт Ошибка] {e}")

    def create_keyboard(self):
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn = types.KeyboardButton("🔍 Найти новые квартиры")
        markup.add(btn)
        return markup

    def check_and_get_new(self) -> list:
        new_apartments_list = []
        try:
            response = self.scraper.get(self.url)
            if response.status_code != 200:
                return [f"Ошибка Oikotie: статус {response.status_code}"]

            soup = BeautifulSoup(response.text, 'html.parser')
            cards = soup.find_all('div', class_='cards-v2__card') or soup.find_all('article')
            
            if not cards:
                return []

            for card in cards:
                link_tag = card.find('a', href=True)
                if not link_tag:
                    continue
                    
                link = link_tag['href']
                if not link.startswith('http'):
                    link = "https://asunnot.oikotie.fi" + link
                
                apartment_id = link.split('/')[-1]
                if not apartment_id:
                    continue

                if apartment_id not in self.seen_apartments:
                    self.seen_apartments.add(apartment_id)
                    
                    price_tag = card.find(class_='ot-card__price') or card.find(text=lambda t: '€' in t)
                    price = price_tag.text.strip() if price_tag else "Не указана"
                    
                    location_tag = card.find(class_='ot-card__title')
                    location = location_tag.text.strip() if location_tag else "Регион Хельсинки"
                    
                    apartment_info = f"📍 {location} | 💰 {price}\n🔗 {link}"
                    new_apartments_list.append(apartment_info)
                    
            return new_apartments_list
        except Exception as e:
            return [f"Ошибка парсинга: {e}"]


OIKOTIE_URL = "https://asunnot.oikotie.fi/vuokra-asunnot?pagination=1&locations=%5B%5B39,6,%22Espoo%22%5D,%5B64,6,%22Helsinki%22%5D%5D&cardType=101&price%5Bmax%5D=715&size%5Bmin%5D=23&secondarySearchType=1&priceAvailable%5B%5D=1&constructionYear%5Bmin%5D=2000"
TELEGRAM_TOKEN = "8587670418:AAHo1Ndxob0ACRJACNVxZVdrcH2HUQqW3Zg"
MY_CHAT_ID = 5635905785 

app = OikotieInteractiveBot(url=OIKOTIE_URL, tg_token=TELEGRAM_TOKEN, chat_id=MY_CHAT_ID)
bot = app.bot

@bot.message_handler(commands=['start'])
def welcome(message):
    if message.chat.id == app.chat_id:
        bot.send_message(message.chat.id, "Привет! Я твой поисковик жилья на Oikotie.", reply_markup=app.create_keyboard())

@bot.message_handler(func=lambda message: message.text == "🔍 Найти новые квартиры")
def handle_search_button(message):
    if message.chat.id != app.chat_id:
        return
    bot.send_message(message.chat.id, "🔄 Проверяю Oikotie, подожди секунду...")
    new_housing = app.check_and_get_new()
    
    if not new_housing:
        bot.send_message(message.chat.id, "📭 Новых квартир пока нет. Попробуй позже!")
    elif "Ошибка" in new_housing[0]:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {new_housing[0]}")
    else:
        result_text = "🚨 **НАЙДЕНЫ НОВЫЕ КВАРТИРЫ!** 🚨\n\n" + "\n\n---\n\n".join(new_housing)
        bot.send_message(message.chat.id, result_text, parse_mode="Markdown")


if __name__ == "__main__":
    # 1. Запускаем веб-сервер Flask в фоновом потоке для Render
    threading.Thread(target=run_flask, daemon=True).start()
    
    # 2. Запускаем самого бота
    print("Бот успешно запущен и ждет нажатия кнопки в Телеграме...")
    bot.polling(none_stop=True)


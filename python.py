import cloudscraper
from bs4 import BeautifulSoup
import telebot
from telebot import types

class OikotieInteractiveBot:
    def __init__(self, url: str, tg_token: str, chat_id: int):
        self.url = url
        self.chat_id = chat_id
        
        # Инициализируем Telegram-бота через библиотеку telebot
        self.bot = telebot.TeleBot(tg_token)
        
        # База данных в памяти для ID квартир, которые мы уже видели
        self.seen_apartments = set()
        
        # Обход защиты Cloudflare
        self.scraper = cloudscraper.create_scraper()
        
        # Сразу делаем первый "холостой" запуск при создании объекта, 
        # чтобы запомнить текущие квартиры на сайте
        self.preload_current_apartments()

    def preload_current_apartments(self):
        """Холостой запуск: собирает текущие квартиры, чтобы не считать их новыми"""
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
                print(f"[Старт Ошибка] Не удалось подключиться к Oikotie, статус: {response.status_code}")
        except Exception as e:
            print(f"[Старт Ошибка] {e}")

    def create_keyboard(self):
        """Создает красивую кнопку внизу экрана Телеграма"""
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        btn = types.KeyboardButton("🔍 Найти новые квартиры")
        markup.add(btn)
        return markup

    def check_and_get_new(self) -> list:
        """Заходит на сайт и возвращает СПИСОК всех новых найденных квартир"""
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

                # Если этого ID нет в базе — это новинка!
                if apartment_id not in self.seen_apartments:
                    self.seen_apartments.add(apartment_id) # Запоминаем её
                    
                    # Собираем инфо о цене и локации
                    price_tag = card.find(class_='ot-card__price') or card.find(text=lambda t: '€' in t)
                    price = price_tag.text.strip() if price_tag else "Не указана"
                    
                    location_tag = card.find(class_='ot-card__title')
                    location = location_tag.text.strip() if location_tag else "Регион Хельсинки"
                    
                    # Добавляем в наш список новинок красивую строчку
                    apartment_info = f"📍 {location} | 💰 {price}\n🔗 {link}"
                    new_apartments_list.append(apartment_info)
                    
            return new_apartments_list

        except Exception as e:
            return [f"Ошибка парсинга: {e}"]


OIKOTIE_URL = "https://asunnot.oikotie.fi/vuokra-asunnot?pagination=1&locations=%5B%5B39,6,%22Espoo%22%5D,%5B64,6,%22Helsinki%22%5D%5D&cardType=101&price%5Bmax%5D=715&size%5Bmin%5D=23&secondarySearchType=1&priceAvailable%5B%5D=1&constructionYear%5Bmin%5D=2000"
TELEGRAM_TOKEN = "8587670418:AAGeoW3uwdUCIYFPvtgN3UJqd_8fmAAItHk"
MY_CHAT_ID = 5635905785 

# Создаем объект нашего интерактивного бота
app = OikotieInteractiveBot(url=OIKOTIE_URL, tg_token=TELEGRAM_TOKEN, chat_id=MY_CHAT_ID)

# Создаем глобальный объект бота для обработки сообщений библиотекой telebot
bot = app.bot

@bot.message_handler(commands=['start'])
def welcome(message):
    """Реагирует на команду /start и показывает кнопку"""
    if message.chat.id == app.chat_id:
        bot.send_message(
            message.chat.id, 
            "Привет! Я твой поисковик жилья на Oikotie. Нажми на кнопку ниже, чтобы проверить обновления.", 
            reply_markup=app.create_keyboard()
        )

@bot.message_handler(func=lambda message: message.text == "🔍 Найти новые квартиры")
def handle_search_button(message):
    """Срабатывает, когда ты нажимаешь на кнопку поиска"""
    if message.chat.id != app.chat_id:
        return # Игнорируем чужих пользователей, если кто-то найдет твоего бота
        
    bot.send_message(message.chat.id, "🔄 Проверяю Oikotie, подожди секунду...")
    
    # Запускаем метод поиска новинок
    new_housing = app.check_and_get_new()
    
    if not new_housing:
        bot.send_message(message.chat.id, "📭 Новых квартир пока нет. Попробуй позже!")
    elif "Ошибка" in new_housing[0]:
        bot.send_message(message.chat.id, f"❌ Произошла ошибка: {new_housing[0]}")
    else:
        # Склеиваем все найденные квартиры в один большой текст
        result_text = "🚨 **НАЙДЕНЫ НОВЫЕ КВАРТИРЫ!** 🚨\n\n" + "\n\n---\n\n".join(new_housing)
        bot.send_message(message.chat.id, result_text, parse_mode="Markdown", disable_web_page_preview=False)


if __name__ == "__main__":
    print("Выполнено")
    # Запуск бесконечного прослушивания сообщений от Телеграма
    bot.polling(none_stop=True)
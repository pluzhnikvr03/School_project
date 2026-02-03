import telebot
from telebot import types
import config
import database

# Создаем объект бота
API_TOKEN = config.token
bot = telebot.TeleBot(API_TOKEN)

# Создаем базу данных при запуске
database.create_database()

# Словари для хранения состояний
user_states = {}
pending_actions = {}


# Создание кнопок
def create_keyboard(book_id, has_book=False):
    keyboard = types.InlineKeyboardMarkup()

    if has_book:
        keyboard.row(
            types.InlineKeyboardButton("✅ Вернуть книгу", callback_data=f"return_{book_id}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        )
    else:
        keyboard.row(
            types.InlineKeyboardButton("✅ Взять книгу", callback_data=f"take_{book_id}"),
            types.InlineKeyboardButton("❌ Отмена", callback_data="cancel")
        )

    return keyboard


# Обработка кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_buttons(call):
    user_id = call.from_user.id
    bot.answer_callback_query(call.id)

    if not database.is_user_registered(user_id):
        bot.send_message(call.message.chat.id, "Сначала зарегистрируйтесь через /start")
        return

    if call.data == "cancel":
        bot.delete_message(call.message.chat.id, call.message.message_id)
        return

    if call.data.startswith("take_"):
        book_id = call.data.replace("take_", "")

        if database.take_book(user_id, book_id):
            bot.edit_message_text(
                f"📚 Книга {book_id} успешно взята!",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.edit_message_text(
                f"❌ Ошибка при взятии книги {book_id}",
                call.message.chat.id,
                call.message.message_id
            )

    elif call.data.startswith("return_"):
        book_id = call.data.replace("return_", "")

        if database.return_book(user_id, book_id):
            bot.edit_message_text(
                f"📚 Книга {book_id} успешно возвращена!",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.edit_message_text(
                f"❌ Ошибка при возврате книги {book_id}",
                call.message.chat.id,
                call.message.message_id
            )


# Обработка команд
@bot.message_handler(commands=['start'])
def start_command(message):
    user_id = message.from_user.id

    if database.is_user_registered(user_id):
        bot.reply_to(message,
                     "Привет! Наведи камеру на QR-код с учебника для работы с книгой.")
    else:
        user_states[user_id] = True
        bot.reply_to(message,
                     "Добро пожаловать! Для регистрации введи:\n"
                     "Фамилия Имя Класс\n\n"
                     "Пример: Иванов Иван 10А")


@bot.message_handler(commands=['books'])
def books_command(message):
    user_id = message.from_user.id

    if not database.is_user_registered(user_id):
        bot.reply_to(message, "Сначала зарегистрируйся через /start")
        return

    books = database.get_user_books(user_id)

    if not books:
        bot.reply_to(message, "У тебя пока нет книг")
        return

    book_list = []
    for book in books:
        book_id, status, date = book
        status_text = "на руках" if status == "taken" else "возвращена"
        book_list.append(f"• {book_id} ({status_text}, {date})")

    bot.reply_to(message, "📚 Твои книги:\n\n" + "\n".join(book_list))


# Обработка регистрации
@bot.message_handler(func=lambda message: user_states.get(message.from_user.id, False))
def handle_registration(message):
    user_id = message.from_user.id
    text = message.text.strip()

    parts = text.split()
    if len(parts) < 3:
        bot.reply_to(message,
                     "Неверный формат. Нужно: Фамилия Имя Класс\n"
                     "Пример: Иванов Иван 10А")
        return

    name = ' '.join(parts[:2])
    user_class = parts[-1]

    if database.register_user(user_id, name, user_class):
        del user_states[user_id]
        bot.reply_to(message,
                     f"✅ Регистрация успешна!\n"
                     f"Привет, {name}!\n"
                     f"Твой класс: {user_class}\n\n"
                     f"Теперь можешь сканировать QR-коды с учебников.")
    else:
        bot.reply_to(message, "❌ Ошибка регистрации. Возможно, ты уже зарегистрирован.")


# Обработка QR-кодов
@bot.message_handler(func=lambda message: True)
def handle_qr_code(message):
    user_id = message.from_user.id
    book_id = message.text.strip()

    if not database.is_user_registered(user_id):
        bot.reply_to(message, "Сначала зарегистрируйся через /start")
        return

    has_book = database.user_has_book(user_id, book_id)
    keyboard = create_keyboard(book_id, has_book)

    if has_book:
        text = f"📚 Книга {book_id} уже у тебя. Вернуть?"
    else:
        text = f"📚 Найдена книга: {book_id}. Взять?"

    bot.reply_to(message, text, reply_markup=keyboard)


# Запуск бота
if __name__ == '__main__':
    print("🤖 Бот запущен!")
    print("📂 База данных: library.db")
    print("🔗 Используй /start в боте")
    bot.infinity_polling()
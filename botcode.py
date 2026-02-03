import telebot
import config
from telebot import types

bot = telebot.TeleBot(config.token)

# База данных пользователей
users_db = {}  # {user_id: {'name': 'имя', 'class': '10v', 'books': []}}
books_bd = {}  # {user_id: [book_id]}
# Состояние для отслеживания
user_registration_state = {} # пользователь в процессе регистрации
user_pending_action = {} # {user_id: 'book_id'}

# Создает инлайн-клавиатуру
def create_inline_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Взять книгу", callback_data="take"),
        types.InlineKeyboardButton("Вернуть книгу", callback_data="return")
    )

    return keyboard


# Обработчик нажатий на inline-кнопки
@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    user_id = call.from_user.id

    # Обязательно отвечаем на callback (убирает "часики" на кнопке)
    bot.answer_callback_query(call.id)
    # Если пользователь не зарегистрирован, предлагаем начать с /start
    if user_id not in users_db:
        bot.send_message(call.message.chat.id, "Сначала зарегистрируйтесь через /start")
        return

    book_id = user_pending_action[user_id]

    # Обработка кнопки "Взять книгу"
    if call.data == "take":
        if user_id not in books_bd:
            books_bd[user_id] = []
        books_bd[user_id].append(book_id)
        bot.send_message(call.message.chat.id, f"книга взята! {books_bd[user_id]}")

    # Обработка кнопки "Вернуть книгу"
    elif call.data == "return":
        if book_id in books_bd[user_id]:
            books_bd[user_id].remove(book_id)
            bot.send_message(call.message.chat.id, f"вы вернули книгу {books_bd[user_id]}")


# Обработчик команды /start
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id
    if user_id in users_db:
        user_name = users_db[user_id]['name']
        bot.reply_to(message, f"Привет, {user_name}!\nОтсканируйте qr для взятия или сдачи книги")
    else:
        user_registration_state[user_id] = True
        bot.reply_to(message, "Добро пожаловать!\nВведите ваше ФИО и класс обучения:")


# Обработчик регистрации пользователя
@bot.message_handler(func=lambda message: user_registration_state.get(message.from_user.id, False))
def handle_registration(message):
    user_id = message.from_user.id
    n = ' '.join(message.text.split()[:3])
    k = message.text.split()[-1]

    # Регистрируем пользователя
    users_db[user_id] = {
        'name': n,
        'class': k,
        'books': [],  # пустой список книг
    }

    # Удаляем пользователя из состояния регистрации
    del user_registration_state[user_id]
    bot.reply_to(message, f"Регистрация завершена!\nДобро пожаловать в библиотеку, {n}\nОтсканируйте qr для взятия или сдачи книги!")


# Обработчик всех остальных сообщений
@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id

    # Если пользователь не зарегистрирован, предлагаем начать с /start
    if user_id not in users_db:
        bot.reply_to(message, "Для начала работы используйте команду /start")
    if message.text.isdigit():
        book_id = message.text
        user_pending_action[user_id] = book_id
        bot.reply_to(message, "выберете действие:", reply_markup=create_inline_keyboard())


bot.infinity_polling()

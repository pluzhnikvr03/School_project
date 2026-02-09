import telebot
token='8281529454:AAEPnPyn1HwsOzMXuBHo47i6LTFC3wPLTtU'
from telebot import types

bot = telebot.TeleBot(token)

# База данных пользователей
users_db = {}  # {user_id: {'name': 'имя', 'class/subject': '10v/математика', 'role': 'student/teacher', 'books': []}}
books_bd = {}  # {user_id: [book_id]}

# Состояния для отслеживания
user_pending_action = {}  # {user_id: 'book_id'}
user_waiting_for_data = {}  # {user_id: True} - ожидает ввода ФИО и данных
user_data_temp = {}  # {user_id: {'name': '...', 'additional': '...'}} - временное хранение данных
teacher = {} # {user_id: False}
teacher[1615187103] = True


# Создает клавиатуру для выбора роли
def create_role_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Ученик", callback_data="role_student"),
        types.InlineKeyboardButton("Учитель", callback_data="role_teacher")
    )
    return keyboard


# Создает инлайн-клавиатуру
def create_inline_keyboard():
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Взять книгу", callback_data="take"),
        types.InlineKeyboardButton("Вернуть книгу", callback_data="return")
    )
    return keyboard


@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    user_id = call.from_user.id

    # Отвечаем на callback (убирает "часики" на кнопке)
    bot.answer_callback_query(call.id)

    # Обработка выбора роли
    if call.data.startswith("role_"):
        role = call.data.split("_")[1]  # "student" или "teacher"

        # Получаем временно сохраненные данные
        if user_id not in user_data_temp:
            bot.send_message(call.message.chat.id, "Ошибка! Начните регистрацию заново: /start")
            return

        temp_data = user_data_temp[user_id]
        name = temp_data['name']
        additional = temp_data['additional']

        # Регистрируем пользователя в зависимости от выбранной роли
        if role == "student":
            users_db[user_id] = {
                'name': name,
                'class': additional,
                'role': 'student',
                'books': [],
            }
            welcome_message = f"Регистрация завершена!\nОтсканируйте QR для работы с книгами!"
            teacher[user_id] = True
        else:  # teacher
            users_db[user_id] = {
                'name': name,
                'subject': additional,
                'role': 'teacher',
                'books': [],
            }
            welcome_message = f"Ваша заявка отправлена на подтверждение администратору.\nОжидайте!"
            if user_id not in teacher:
                teacher[user_id] = False


        # Инициализируем список книг
        books_bd[user_id] = []

        # Очищаем временные данные
        if user_id in user_data_temp:
            del user_data_temp[user_id]

        bot.send_message(call.message.chat.id, welcome_message)
        return

    # Обработка кнопок взятия/возврата книг
    if user_id not in users_db:
        bot.send_message(call.message.chat.id, "Сначала зарегистрируйтесь через /start")
        return

    if user_id not in user_pending_action:
        bot.send_message(call.message.chat.id, "Сначала введите ID книги")
        return

    book_id = user_pending_action[user_id]

    # Обработка кнопки "Взять книгу"
    if call.data == "take":
        if user_id not in books_bd:
            books_bd[user_id] = []

        if book_id in books_bd[user_id]:
            bot.send_message(call.message.chat.id, f"Книга уже у вас!")
        else:
            books_bd[user_id].append(book_id)
            bot.send_message(call.message.chat.id, f"Вы взяли книгу!")

    # Обработка кнопки "Вернуть книгу"
    elif call.data == "return":
        if user_id not in books_bd or book_id not in books_bd[user_id]:
            bot.send_message(call.message.chat.id, f"У вас нет такой книги")
        else:
            books_bd[user_id].remove(book_id)
            bot.send_message(call.message.chat.id, f"Вы вернули книгу")

    # Очищаем временное хранилище
    if user_id in user_pending_action:
        del user_pending_action[user_id]


@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_id = message.from_user.id

    if user_id in users_db:
        user_info = users_db[user_id]
        user_name = user_info['name']

        if user_info['role'] == 'student':
            user_class = user_info['class']
            bot.reply_to(message,
                         f"Привет!\nОтсканируйте QR для работы с книгами")
        else:  # teacher
            user_subject = user_info['subject']
            bot.reply_to(message,
                         f"Привет!\nОтсканируйте QR для работы с книгами")
    else:
        user_waiting_for_data[user_id] = True
        bot.reply_to(message, f"""*Регистрация*
        
Введите ваши данные в формате:
• *Для ученика:* Фамилия Имя Отчество Класс
• *Для учителя:* Фамилия Имя Отчество Предмет

*Примеры:*
Иванов Иван Иванович 10А
Петрова Анна Сергеевна математика

*Введите ваши данные:*""", parse_mode='Markdown')


@bot.message_handler(func=lambda message: user_waiting_for_data.get(message.from_user.id, False))
def handle_user_data_input(message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Разделяем текст на части
    parts = text.split()

    if len(parts) < 4:  # Минимум 4 слова: Фамилия Имя Отчество Класс/Предмет
        bot.reply_to(message,
                     "Недостаточно данных!\nВведите: *Фамилия Имя Отчество Класс* или *Фамилия Имя Отчество Предмет*\n\nПример: Иванов Иван Иванович 10А",
                     parse_mode='Markdown')
        return

    # ФИО - первые три слова
    name = ' '.join(parts[:3])
    # Остальное - класс или предмет
    additional = ' '.join(parts[3:])

    # Сохраняем временные данные
    user_data_temp[user_id] = {
        'name': name,
        'additional': additional
    }

    # Убираем состояние ожидания данных
    del user_waiting_for_data[user_id]

    # Показываем выбор роли
    bot.reply_to(message, f"""
Выберите вашу роль:""",
                 reply_markup=create_role_keyboard(), parse_mode='Markdown')


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    user_id = message.from_user.id

    # Если пользователь не зарегистрирован
    if user_id not in users_db:
        # Проверяем, не находится ли он в процессе регистрации
        if user_id not in user_waiting_for_data and user_id not in user_data_temp:
            bot.reply_to(message, "Для начала работы используйте команду /start")
        return

    # Если введено число (ID книги)
    if message.text.isdigit():
        book_id = message.text

        # Сохраняем ID книги во временное хранилище
        user_pending_action[user_id] = book_id

        # Получаем информацию о пользователе для персонализированного сообщения
        user_info = users_db[user_id]

        if teacher[user_id]:
            bot.reply_to(message, f"""
            Выберите действие:""",
                         reply_markup=create_inline_keyboard(), parse_mode='Markdown')

        else:
            bot.reply_to(message, f"""
                        Дождитесь подтвеждения заявки""")
    else:
        if teacher[user_id]:
            bot.reply_to(message, f"""
            Отсканируйте QR для работы с книгами""")

        else:
            bot.reply_to(message, f"""
                        Дождитесь подтвеждения заявки""")


bot.infinity_polling()

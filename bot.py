import telebot
from telebot import types

token = '8281529454:AAEPnPyn1HwsOzMXuBHo47i6LTFC3wPLTtU'
from database import *

create_database()

bot = telebot.TeleBot(token)

# СОСТОЯНИЯ для управления диалогом
user_waiting_for_data = {}  # {user_id: True} - ожидает ввода данных
user_data_temp = {}  # {user_id: {'fio': '...', 'additional': '...'}}
user_pending_action = {}  # {user_id: 'qr_code'} - хранит QR-код
teacher_status = {}  # {user_id: True/False} - True для учителей, False для учеников
teacher_status[1615187103] = True

# ========== ИНЛАЙН КЛАВИАТУРЫ ==========

def create_role_keyboard():
    """Создает клавиатуру для выбора роли"""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.row(
        types.InlineKeyboardButton("Ученик", callback_data="role_student"),
        types.InlineKeyboardButton("Учитель", callback_data="role_teacher")
    )
    return keyboard


def create_book_action_keyboard(qr_code):
    """Создает клавиатуру с выбором действия для книги"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("Взять", callback_data=f"take_{qr_code}"),
        types.InlineKeyboardButton("Вернуть", callback_data=f"return_{qr_code}")
    )
    return keyboard


# ========== ОБРАБОТЧИКИ КОМАНД ==========

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    if user_id not in teacher_status:
        teacher_status[user_id] = False

    if is_user_registered(user_id):
        # Проверяем статус учителя
        if teacher_status[user_id]:
            if teacher_status[user_id]:
                bot.send_message(
                    message.chat.id,
                    f"Привет!\nОтсканируйте QR для работы с книгами",
                    parse_mode='Markdown'
                )
            else:
                bot.send_message(
                    message.chat.id,
                    f"Ожидайте подтверждения администратора!",
                    parse_mode='Markdown'
                )
        else:
            bot.send_message(
                message.chat.id,
                f"Привет!\nЖдем подтверждения заявки",
                parse_mode='Markdown'
            )
    else:
        welcome_text = f"""
Привет!

Добро пожаловать в электронную библиотеку школы №192!

Для начала работы необходимо зарегистрироваться.

Введите ваши данные в формате:
Для ученика: Фамилия Имя Отчество Класс
Для учителя: Фамилия Имя Отчество Предмет

Примеры:
Иванов Иван Иванович 10А
Петрова Анна Сергеевна математика

Введите ваши данные:
        """
        user_waiting_for_data[user_id] = True
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode='Markdown'
        )


# ========== ОБРАБОТЧИК РЕГИСТРАЦИИ ==========

@bot.message_handler(func=lambda message: user_waiting_for_data.get(message.from_user.id, False))
def handle_registration_data(message):
    user_id = message.from_user.id
    text = message.text.strip()
    parts = text.split()

    if len(parts) < 4:
        error_text = """
Недостаточно данных!

Введите: Фамилия Имя Отчество Класс* или *Фамилия Имя Отчество Предмет

Примеры:
Иванов Иван Иванович 10А
Петрова Анна Сергеевна математика

Попробуйте еще раз:
        """
        bot.send_message(message.chat.id, error_text, parse_mode='Markdown')
        return

    fio = ' '.join(parts[:3])
    additional = ' '.join(parts[3:])

    # Сохраняем временные данные
    user_data_temp[user_id] = {
        'fio': fio,
        'additional': additional
    }

    # Убираем состояние ожидания данных
    del user_waiting_for_data[user_id]

    # Показываем выбор роли
    bot.reply_to(message,
                 "Выберите вашу роль:",
                 reply_markup=create_role_keyboard())


# ========== ОБРАБОТЧИКИ INLINE-КНОПОК ==========

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    user_id = call.from_user.id
    callback_data = call.data
    bot.answer_callback_query(call.id)

    # Обработка выбора роли
    if callback_data.startswith("role_"):
        role = callback_data.split("_")[1]  # "student" или "teacher"

        if user_id not in user_data_temp:
            bot.send_message(call.message.chat.id, "Ошибка! Начните регистрацию заново: /start")
            return

        temp_data = user_data_temp[user_id]
        fio = temp_data['fio']
        additional = temp_data['additional']

        # Регистрируем пользователя в зависимости от выбранной роли
        if role == "student":
            # Для ученика additional = класс
            if register_user(user_id, fio, additional):
                success_text = f"""
Регистрация завершена!

Отсканируйте QR для работы с книгами!
                """
                teacher_status[user_id] = True
            else:
                error_text = "Ошибка регистрации! Возможно, вы уже зарегистрированы."
                bot.send_message(call.message.chat.id, error_text, parse_mode='Markdown')
                return

        else:  # teacher
            # Для учителя additional = предмет
            # В текущей структуре БД нет поля для предмета, используем классное поле
            if register_user(user_id, fio, f"Учитель: {additional}"):
                if teacher_status[user_id]:
                    success_text = f"""
Регистрация завершена!

Отсканируйте QR для работы с книгами!
                """
                else:
                    success_text = f"""
Ожидайте подтверждения администратора!
                """
            else:
                error_text = "Ошибка регистрации!"
                bot.send_message(call.message.chat.id, error_text, parse_mode='Markdown')
                return

        # Очищаем временные данные
        if user_id in user_data_temp:
            del user_data_temp[user_id]

        bot.edit_message_text(
            success_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        return

    # Обработка взятия книги
    if callback_data.startswith("take_"):
        qr_code = callback_data.replace("take_", "")

        if take_book(user_id, qr_code):
            success_text = f"""
Книга взята!
            """
            bot.edit_message_text(
                success_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            error_text = f"""
Книга уже взята или не найдена.
            """
            bot.edit_message_text(
                error_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )

        if user_id in user_pending_action:
            del user_pending_action[user_id]
        return

    # Обработка возврата книги
    if callback_data.startswith("return_"):
        qr_code = callback_data.replace("return_", "")

        if return_book(user_id, qr_code):
            success_text = f"""
Книга возвращена!
            """
            bot.edit_message_text(
                success_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:
            error_text = f"""
Не удалось вернуть книгу
Книга не числится за вами.
            """
            bot.edit_message_text(
                error_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )

        if user_id in user_pending_action:
            del user_pending_action[user_id]
        return


# ========== ОБРАБОТЧИК QR-КОДОВ ==========

@bot.message_handler(func=lambda message: True)
def handle_all_messages(message):
    user_id = message.from_user.id

    # Если пользователь не зарегистрирован
    if not is_user_registered(user_id):
        if user_id not in user_waiting_for_data and user_id not in user_data_temp:
            bot.send_message(message.chat.id, "Для начала работы используйте команду /start")
        return

    # Проверяем статус учителя
    if not teacher_status.get(user_id, False):
        # Проверяем, не ученик ли это (ученики всегда имеют доступ)
        # В текущей реализации все зарегистрированные пользователи имеют доступ
        # Можно добавить логику проверки: если в поле class есть "Учитель:", то проверяем teacher_status
        pass

    # Если сообщение похоже на QR-код (не команда, не пустое)
    text = message.text.strip()
    if text and not text.startswith('/'):
        # Сохраняем QR-код
        user_pending_action[user_id] = text

        # Получаем информацию о книге
        book_info = get_book_info(text)

        if not book_info:
            bot.reply_to(message, f"Книга не найдена.", parse_mode='Markdown')
            if user_id in user_pending_action:
                del user_pending_action[user_id]
            return

        book_text = f"""
*ИНФОРМАЦИЯ О КНИГЕ*

*Код:* `{book_info['qr_code']}`
*Название:* {book_info['subject']}
*Автор:* {book_info['author']}
*Год:* {book_info['year']}

Выберите действие:
        """

        bot.reply_to(
            message,
            book_text,
            parse_mode='Markdown',
            reply_markup=create_book_action_keyboard(text)
        )


# ========== ЗАПУСК БОТА ==========

bot.infinity_polling(timeout=60, long_polling_timeout=60)

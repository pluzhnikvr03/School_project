import telebot
from telebot import types
import config  # берем токен из config.py
from database import *

create_database()

bot = telebot.TeleBot(config.token)

# СОСТОЯНИЯ для управления диалогом
user_waiting_for_data = {}  # {user_id: True} - ожидает ввода данных
user_data_temp = {}  # {user_id: {'fio': '...', 'additional': '...'}}
user_pending_action = {}  # {user_id: 'qr_code'} - хранит QR-код
teacher_status = {}  # {user_id: True/False} - True для учителей, False для учеников
ADMIN_ID = 8523221712  # временный админ (tg bleb)


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
        types.InlineKeyboardButton("Вернуть", callback_data=f"return_{qr_code}"),
        types.InlineKeyboardButton("Кому принадлежит?", callback_data=f"who_{qr_code}")
    )
    return keyboard


def remove_keyboard():
    """
    Создает "пустую" клавиатуру, которая убирает все кнопки
    """
    return types.ReplyKeyboardRemove()

def create_confirm_keyboard(teacher_id):
    """Создает клавиатуру для подтверждения учителя"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("Подтвердить", callback_data=f"confirm_{teacher_id}"),
        types.InlineKeyboardButton("Отклонить", callback_data=f"reject_{teacher_id}")
    )
    return keyboard


# ========== ОБРАБОТЧИКИ КОМАНД ==========

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id

    # ПОЛУЧАЕМ QR-КОД ИЗ КОМАНДЫ (если есть)
    qr_code = None
    if len(message.text.split()) > 1:
        # Если пришли с QR: /start TEST-001
        qr_code = message.text.split()[1]

    teacher_status[user_id] = False

    if is_user_registered(user_id):
        # Проверяем разрешение из БД
        if check_user_permit(user_id):
            # ЕСЛИ ЕСТЬ QR-КОД - СРАЗУ ОБРАБАТЫВАЕМ
            if qr_code:
                fake_msg = types.Message(
                    message_id=0,
                    from_user=message.from_user,
                    date=message.date,
                    chat=message.chat,
                    content_type='text',
                    options=[],
                    json_string=''
                )
                fake_msg.text = qr_code
                handle_all_messages(fake_msg)
            else:
                # ЕСЛИ НЕТ QR - ПОКАЗЫВАЕМ ПРИВЕТСТВИЕ
                bot.send_message(
                    message.chat.id,
                    f"Привет!\nОтсканируйте QR для работы с книгами",
                    parse_mode='Markdown',
                    reply_markup=remove_keyboard()
                )

        else:
            bot.send_message(
                message.chat.id,
                f"Регистрация завершена\n\nОжидайте подтверждения администратора!",
                parse_mode='Markdown',
                reply_markup=remove_keyboard()
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
            parse_mode='Markdown',
            reply_markup=remove_keyboard()
        )


@bot.message_handler(commands=['books'])
def handle_my_books(message):
    user_id = message.from_user.id

    # Проверяем регистрацию
    if not is_user_registered(user_id):
        bot.reply_to(message, "Сначала зарегистрируйтесь через /start")
        return

    # Получаем книги пользователя из базы данных
    books = get_user_current_books(user_id)

    if not books:
        bot.reply_to(message, "У вас пока нет книг.")
        return

    text = "ВАШИ КНИГИ:\n\n"

    for book in books:
        subject = book[0]  # Название книги
        issue_date = book[3]  # Дата выдачи

        text += f"{subject}\n"
        text += f"Взята: {issue_date}\n\n"

    bot.reply_to(message, text, parse_mode='Markdown')



# ========== ОБРАБОТЧИК РЕГИСТРАЦИИ ==========

@bot.message_handler(func=lambda message: user_waiting_for_data.get(message.from_user.id, False))
def handle_registration_data(message):
    user_id = message.from_user.id
    text = message.text.strip()
    parts = text.split()
    if user_id not in teacher_status:
        teacher_status[user_id] = False
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

    # ЗАЩИТА ОТ СТАРЫХ CALLBACK
    try:
        bot.answer_callback_query(call.id)
    except Exception as e:
        print(f"Старый callback: {e}")
        try:
            bot.send_message(
                call.message.chat.id,
                "Это сообщение устарело. Нажмите /start",
                reply_markup=remove_keyboard()
            )
        except:
            pass
        return

    # ===== 1. КНОПКИ ПОДТВЕРЖДЕНИЯ УЧИТЕЛЯ (НОВЫЕ) =====
    if callback_data.startswith("confirm_") or callback_data.startswith("reject_"):
        admin_id = call.from_user.id

        # Проверяем, что это админ
        if admin_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "У вас нет прав администратора!")
            return

        # Получаем ID учителя из callback_data
        if callback_data.startswith("confirm_"):
            teacher_id = int(callback_data.replace("confirm_", ""))
            permit = True
            action = "подтверждена"

            # Обновляем статус в БД
            conn = sqlite3.connect('library.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET permit = ? WHERE tg_id = ?', (permit, teacher_id))
            conn.commit()
            conn.close()

            # Уведомляем учителя об одобрении
            bot.send_message(
                teacher_id,
                "Ваша заявка одобрена!\n\n"
                "Теперь вы можете пользоваться библиотекой.\n"
                "Отправьте /start для начала работы.",
                parse_mode='Markdown'
            )
        else:
            teacher_id = int(callback_data.replace("reject_", ""))
            permit = False
            action = "отклонена"

            if delete_user(teacher_id):
                # Уведомляем учителя об отклонении
                bot.send_message(
                    teacher_id,
                    "Ваша заявка отклонена.\n\n"
                    "Обратитесь к администратору для уточнения причины.\n"
                    "Вы можете зарегистрироваться снова через /start",
                    parse_mode='Markdown'
                )
            else:
                bot.send_message(
                    admin_id,
                    f"Не удалось удалить пользователя {teacher_id} (возможно, его уже нет в БД)",
                    parse_mode='Markdown'
                )


        # Сообщение админу
        bot.edit_message_text(
            f"Заявка {action}!",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)
        return

    # ===== 2. ВЫБОР РОЛИ (УЧЕНИК/УЧИТЕЛЬ) =====
    if callback_data.startswith("role_"):
        role = callback_data.split("_")[1]

        if user_id not in user_data_temp:
            bot.send_message(call.message.chat.id, "Ошибка! Начните регистрацию заново: /start")
            return

        temp_data = user_data_temp[user_id]
        fio = temp_data['fio']
        additional = temp_data['additional']

        if role == "student":
            if register_user(user_id, fio, additional, "student", True):
                success_text = f"""
Регистрация завершена!

Отсканируйте QR для работы с книгами!
                """
                teacher_status[user_id] = False
            else:
                bot.send_message(call.message.chat.id, "Ошибка регистрации!", parse_mode='Markdown')
                return
        else:  # teacher
            if register_user(user_id, fio, f"Учитель: {additional}", "teacher", False):
                success_text = f"""
Заявка отправлена!

Ваша регистрация ожидает подтверждения администратора.
Мы уведомим вас, когда заявка будет одобрена.
                """

                # Отправляем уведомление админу
                bot.send_message(
                    ADMIN_ID,
                    f"Новая заявка на регистрацию учителя!\n\n"
                    f"ФИО: {fio}\n"
                    f"Предмет: {additional}\n"
                    f"Telegram ID: {user_id}\n"
                    f"Username: @{call.from_user.username or 'нет'}",
                    reply_markup=create_confirm_keyboard(user_id)
                )
            else:
                bot.send_message(call.message.chat.id, "Ошибка регистрации!", parse_mode='Markdown')
                return

        if user_id in user_data_temp:
            del user_data_temp[user_id]

        bot.edit_message_text(
            success_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )
        return

    # ===== 3. ВЗЯТИЕ КНИГИ =====
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
Книга уже взята вами или кем-то другим.
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

    # ===== 4. ВОЗВРАТ КНИГИ =====
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

    # ===== 5. КНОПКА "КОМУ ПРИНАДЛЕЖИТ?" =====
    if callback_data.startswith("who_"):
        qr_code = callback_data.replace("who_", "")

        # Получаем информацию о владельце книги
        owner = get_book_owner_info(qr_code)
        user_status = get_user_status(user_id)  # 'student' или 'teacher'

        # Книга свободна
        if not owner:
            # Для УЧИТЕЛЯ — полная информация
            if user_status == 'teacher':
                info_text = f"""
Информация o книге:

Книга свободна!
                            """

            # Для УЧЕНИКА
            else:  # student
                info_text = f"""
Эта не твоя книга!
Отнеси ее учителю.
                                """

        else:
            fio, class_name, owner_tg_id, issue_date = owner

            # Для УЧИТЕЛЯ — полная информация
            if user_status == 'teacher':
                if owner_tg_id == user_id:
                    # Это ЕГО книга
                    info_text = f"""
Это ваш учебник!

Взят: {issue_date}
Не забудьте вернуть вовремя!
                                    """
                else:
                    info_text = f"""
Информация o книге:

Книга принадлежит:
ФИО: {fio}
Класс: {class_name}
Взята: {issue_date}
                    """

            # Для УЧЕНИКА
            else:  # student
                if owner_tg_id == user_id:
                    # Это ЕГО книга
                    info_text = f"""
Это ваш учебник!

Взят: {issue_date}
Не забудьте вернуть вовремя!
                    """
                else:
                    # Чужая книга
                    info_text = f"""
Эта не твоя книга!
Отнеси ее учителю.
                    """

        # Показываем информацию
        bot.edit_message_text(
            info_text,
            call.message.chat.id,
            call.message.message_id,
            parse_mode='Markdown'
        )

        bot.answer_callback_query(call.id)
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
ИНФОРМАЦИЯ О КНИГЕ

Код: `{book_info['qr_code']}`
Название: {book_info['subject']}
Автор: {book_info['author']}
Год: {book_info['year']}

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


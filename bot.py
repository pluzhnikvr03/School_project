import telebot
from telebot import types
from database import *  # импортируем ВСЕ функции из database.py

create_database()  # создаем базу данных

bot = telebot.TeleBot(token)

# состояния для отслеживания
user_waiting_for_data = {}  # {user_id: True} - ожидает ввода ФИО и класса
user_data_temp = {}  # {user_id: {'fio': '...', 'class': '...'}} - временное хранение данных
user_pending_qr = {}  # {user_id: 'qr_code'} - временное хранение данных
user_context = {}  # {user_id: 'action'} - контекст действия (take/return)


# Создает главную клавиатуру меню
def create_main_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "Мои книги",  # Показать все книги пользователя
        "Взять книгу",  # Начать процесс взятия книги
        "Вернуть книгу",  # Начать процесс возврата книги
    ]
    keyboard.add(*buttons)
    return keyboard


# Создает клавиатуру для отмены действия
def create_cancel_keyboard():
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("Отмена")
    return keyboard


# Создает инлайн-клавиатуру для подтверждения действий
def create_confirmation_keyboard(action, qr_code):
    keyboard = types.InlineKeyboardMarkup()
    if action == 'take':
        keyboard.row(
            types.InlineKeyboardButton("Да, взять книгу", callback_data=f"confirm_take_{qr_code}"),
            types.InlineKeyboardButton("Отмена", callback_data="cancel_action")
        )
    elif action == 'return':
        keyboard.row(
            types.InlineKeyboardButton("Да, вернуть книгу", callback_data=f"confirm_return_{qr_code}"),
            types.InlineKeyboardButton("Отмена", callback_data="cancel_action")
        )
    return keyboard



# обработка /start
@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id
    first_name = message.from_user.first_name
    # проверяем, зарегистрирован ли пользователь в базе данных
    if is_user_registered(user_id):  # пользователь уже зарегистрирован - показываем меню
        welcome_text = f"""
    Привет, {first_name}!

Добро пожаловать в электронную библиотеку школы №192!
Выберите действие на клавиатуре ниже:
• Мои книги - посмотреть взятые книги
• Взять книгу - взять новый учебник
• Вернуть книгу - вернуть учебник


Чтобы взять или вернуть книгу:
1. Отсканируйте QR-код на учебнике
2. Отправьте код боту
3. Подтвердите действие"""
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )
    else:  # новый пользователь - начинаем регистрацию
        welcome_text = f"""
    Привет, {first_name}!

Добро пожаловать в электронную библиотеку школы №192!
Для начала работы необходимо зарегистрироваться.

Введите ваши данные в формате:
Для ученика: Фамилия Имя Отчество Класс
Для учителя: Фамилия Имя Отчество Предмет

Примеры:
Иванов Иван Иванович 10А
Петрова Анна Сергеевна математика
Теперь введите ваши данные:
        """
        user_waiting_for_data[user_id] = True
        bot.send_message(
            message.chat.id,
            welcome_text,
            parse_mode='Markdown',
            reply_markup=types.ReplyKeyboardRemove()  # Убираем клавиатуру
        )

# взятие книги
@bot.message_handler(func=lambda message: message.text == "Взять книгу")
def handle_take_book_menu(message):
    user_id = message.from_user.id

    # проверяем регистрацию
    if not is_user_registered(user_id):
        bot.send_message(
            message.chat.id,
            "Вы не зарегистрированы! Используйте /start для регистрации.",
            reply_markup=create_main_keyboard()
        )
        return
    
    user_context[user_id] = 'take'  # устанавливаем состояние "взять книгу"

    instruction_text = """
Инструкция:
1. Найдите QR-код на учебнике (обычно на форзаце)
2. Отсканируйте его камерой телефона
3. Отправьте полученный код мне

Код выглядит примерно так: MATH-001

Отправьте QR-код книги:
    """
    bot.send_message(
        message.chat.id,
        instruction_text,
        parse_mode='Markdown',
        reply_markup=create_cancel_keyboard()  # клавиатура с кнопкой "Отмена"
    )

# возврат книги
@bot.message_handler(func=lambda message: message.text == "Вернуть книгу")
def handle_return_book_menu(message):
    user_id = message.from_user.id

    # проверяем регистрацию
    if not is_user_registered(user_id):
        bot.send_message(
            message.chat.id,
            "Вы не зарегистрированы! Используйте /start для регистрации.",
            reply_markup=create_main_keyboard()
        )
        return

    user_context[user_id] = 'return'  # устанавливаем состояние "вернуть книгу"

    instruction_text = """
Инструкция:
1. Найдите QR-код на учебнике (обычно на обложке)
2. Отсканируйте его камерой телефона
3. Отправьте полученный код мне

Код выглядит примерно так: MATH-001

Отправьте QR-код книги:
    """
    bot.send_message(
        message.chat.id,
        instruction_text,
        parse_mode='Markdown',
        reply_markup=create_cancel_keyboard()  # клавиатура с кнопкой "Отмена"
    )

# обработчик кнопки "Отмена"
@bot.message_handler(func=lambda message: message.text == "Отмена")
def handle_cancel(message):
   user_id = message.from_user.id

    # Очищаем все состояния пользователя
    if user_id in user_waiting_for_data:
        del user_waiting_for_data[user_id]
    if user_id in user_data_temp:
        del user_data_temp[user_id]
    if user_id in user_pending_qr:
        del user_pending_qr[user_id]
    if user_id in user_context:
        del user_context[user_id]

    cancel_text = """
Действие отменено

Вы вернулись в главное меню.
Выберите нужное действие на клавиатуре ниже.
    """
    bot.send_message(
        message.chat.id,
        cancel_text,
        parse_mode='Markdown',
        reply_markup=create_main_keyboard()
    )


# обработка регистрации
@bot.message_handler(func=lambda message: user_waiting_for_data.get(message.from_user.id, False))
def handle_registration_data(message):
   user_id = message.from_user.id
    text = message.text.strip()
    parts = text.split() # разделяем текст на части

    if len(parts) < 4:  # проверяем, что введено минимум 4 слова (ФИО + класс)
        error_text = """
Недостаточно данных!

Введите ваши данные в формате:
Для ученика: Фамилия Имя Отчество Класс
Для учителя: Фамилия Имя Отчество Предмет

Примеры:
Иванов Иван Иванович 10А
Петрова Анна Сергеевна математика
Теперь введите ваши данные:
        """
        bot.send_message(
            message.chat.id,
            error_text,
            parse_mode='Markdown'
        )
        return

    fio = ' '.join(parts[:3])  # извлекаем ФИО (первые три слова)
    user_class = ' '.join(parts[3:])  # извлекаем класс (все остальные слова)

    user_data_temp[user_id] = {  # сохраняем временные данные
        'fio': fio,
        'class': user_class
    }
    
    del user_waiting_for_data[user_id]  # убираем состояние ожидания данных
    if register_user(user_id, fio, user_class):  # регистрируем пользователя в БАЗЕ ДАННЫХ
        success_text = f"""
РЕГИСТРАЦИЯ УСПЕШНО ЗАВЕРШЕНА!

Ваши данные:
ФИО: {fio}
Класс: {user_class}

Теперь вы можете пользоваться библиотекой!
Доступные действия:
Взять книгу - получить учебник
Вернуть книгу - сдать учебник

Выберите действие на клавиатуре ниже 
        """
        bot.send_message(
            message.chat.id,
            success_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

        if user_id in user_data_temp:  # очищаем временные данные
            del user_data_temp[user_id]
    else:  # ошибка регистрации (возможно, пользователь уже существует)
        error_text = """
ОШИБКА РЕГИСТРАЦИИ

Возможно, вы уже зарегистрированы.
Используйте /start для входа в систему.

Если проблема повторяется, обратитесь к библиотекарю.
        """
        bot.send_message(
            message.chat.id,
            error_text,
            parse_mode='Markdown',
            reply_markup=create_main_keyboard()
        )

# обработка qr-кодов
@bot.message_handler(func=lambda message: message.from_user.id in user_context)
def handle_qr_code_input(message):
    user_id = message.from_user.id
    qr_code = message.text.strip()
    action = user_context.get(user_id)

    if not qr_code:  # проверяем, что введен непустой код
        bot.send_message(
            message.chat.id,
            "Пожалуйста, введите QR-код книги.",
            reply_markup=create_cancel_keyboard()
        )
        return

    user_pending_qr[user_id] = qr_code  # сохраняем QR-код
    book_info = get_book_info(qr_code)  # получаем информацию о книге из БАЗЫ ДАННЫХ

    if not book_info:  # книга не найдена в базе
        error_text = f"""
КНИГА НЕ НАЙДЕНА

Книга с кодом {qr_code} не зарегистрирована в библиотеке.

Попробуйте:
1. Проверить правильность кода
2. Отсканировать QR-код еще раз
3. Обратиться к классному руководителю или библиотекарю
        """
        bot.send_message(
            message.chat.id,
            error_text,
            parse_mode='Markdown',
            reply_markup=create_cancel_keyboard()
        )
        return

    # формируем информацию о книге
    book_text = f"""
ИНФОРМАЦИЯ О КНИГЕ

Код: {book_info['qr_code']}
Название: {book_info['subject']}
Автор: {book_info['author']}
Год издания: {book_info['year']}
    """
    if action == 'take':  # процесс взятия книги
        if not is_book_available(qr_code):  # проверяем, доступна ли книга
            # книга уже взята
            book_text += "\n\nКнига уже взята. Обратитесь к классному руководителю или библиотекарю."

            bot.send_message(
                message.chat.id,
                book_text,
                parse_mode='Markdown',
                reply_markup=create_cancel_keyboard()
            )
            return

        # книга доступна - предлагаем взять
        book_text += f"""
Книга никем не занята.
Хотите взять её?"""
        bot.send_message(
            message.chat.id,
            book_text,
            parse_mode='Markdown',
            reply_markup=create_confirmation_keyboard('take', qr_code)
        )

    elif action == 'return':  # процесс возврата книги
        if not user_has_book(user_id, qr_code):  # проверяем, есть ли книга у пользователя
            # книга не у этого пользователя
            book_text += f"""
Эта книга не ваша."""
            bot.send_message(
                message.chat.id,
                book_text,
                parse_mode='Markdown',
                reply_markup=create_cancel_keyboard()
            )
            return

        # книга у пользователя - предлагаем вернуть
        book_text += f"""
Эта книга ваша.
Хотите вернуть её?"""
        bot.send_message(
            message.chat.id,
            book_text,
            parse_mode='Markdown',
            reply_markup=create_confirmation_keyboard('return', qr_code)
        )

# обработка inline-кнопок
@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):user_id = call.from_user.id
    callback_data = call.data
    bot.answer_callback_query(call.id)

    if callback_data == "cancel_action":  # отмена действия
        bot.edit_message_text(
            "Действие отменено.",
            call.message.chat.id,
            call.message.message_id
        )

        if user_id in user_context:  # очищаем состояния
            del user_context[user_id]
        if user_id in user_pending_qr:
            del user_pending_qr[user_id]

        bot.send_message(  # возвращаем в главное меню
            call.message.chat.id,
            "Вы вернулись в главное меню.",
            reply_markup=create_main_keyboard()
        )
        return

    if callback_data.startswith("confirm_take_"):  # обработка подтверждения взятия книги
        qr_code = callback_data.replace("confirm_take_", "")
        if take_book(user_id, qr_code):  # пытаемся взять книгу через базу данных
            success_text = f"""
КНИГА УСПЕШНО ВЫДАНА!
Код книги: {qr_code}
Дата выдачи: сегодня

Не забудьте вернуть книгу в хорошем состоянии!
"""
            bot.edit_message_text(
                success_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:  # ошибка при взятии книги
            error_text = f"""
НЕ УДАЛОСЬ ВЗЯТЬ КНИГУ
Книга с кодом {qr_code} не была выдана.

Попробуйте снова или обратитесь к классному руководителю или библиотекарю.
            """
            bot.edit_message_text(
                error_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )

        if user_id in user_context:  # очищаем состояния
            del user_context[user_id]
        if user_id in user_pending_qr:
            del user_pending_qr[user_id]

        bot.send_message(  # показываем главное меню
            call.message.chat.id,
            "Выберите следующее действие:",
            reply_markup=create_main_keyboard()
        )

    elif callback_data.startswith("confirm_return_"):  # обработка подтверждения возврата книги
        qr_code = callback_data.replace("confirm_return_", "")
        if return_book(user_id, qr_code):  # пытаемся вернуть книгу через БАЗУ ДАННЫХ
            success_text = f"""
КНИГА УСПЕШНО ВОЗВРАЩЕНА!
Код книги: {qr_code}
Дата возврата: сегодня
"""
            bot.edit_message_text(
                success_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )
        else:  # ошибка при возврате книги
            error_text = f"""
НЕ УДАЛОСЬ ВЕРНУТЬ КНИГУ
Книга с кодом {qr_code} не была возвращена.

Попробуйте снова или обратитесь к классному руководителю или библиотекарю.
            """
            bot.edit_message_text(
                error_text,
                call.message.chat.id,
                call.message.message_id,
                parse_mode='Markdown'
            )

        if user_id in user_context:  # очищаем состояния
            del user_context[user_id]
        if user_id in user_pending_qr:
            del user_pending_qr[user_id]

        # Показываем главное меню
        bot.send_message(
            call.message.chat.id,
            "Выберите следующее действие:",
            reply_markup=create_main_keyboard()
        )

# ЗАПУСК БОТА 
if __name__ == "__main__":
    print("БИБЛИОТЕЧНЫЙ БОТ ЗАПУЩЕН")
    print("Статус: Ожидание сообщений...")
    print("Для остановки нажмите Ctrl+C")
    try:
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
    except KeyboardInterrupt:
        print("\nБот остановлен пользователем")
    except Exception as e:
        print(f"\nОшибка при работе бота: {e}")

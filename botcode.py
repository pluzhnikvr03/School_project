import telebot
from telebot import types # импортируем типы данных для создания кнопок и клавиатур
import config  # берем токен из config.py
from database import *  # импортируем все функции из database.py

create_database() # создаем базу данных при запуске (таблицы создадутся, если их нет)

bot = telebot.TeleBot(config.token)

# СОСТОЯНИЯ для управления диалогом
user_waiting_for_data = {}  # {user_id: True} - ожидает ввода данных для регистрации
user_data_temp = {}  # {user_id: {'fio': '...', 'additional': '...'}} - временное хранение введенных ФИО и класса/предмета
user_pending_action = {}  # {user_id: 'qr_code'} - хранит QR-код
# Состояния для учителя
teacher_acting_for = {}  # {teacher_id: student_tg_id} - учитель действует за ученика
teacher_temp_data = {}   # {teacher_id: {'step': 'waiting_class', ...}} - временные данные для выбора ученика
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
    user_id = message.from_user.id # получаем ID пользователя

    # ПОЛУЧАЕМ QR-КОД ИЗ КОМАНДЫ (если есть)
    qr_code = None # инициализируем переменную для QR-кода
    if len(message.text.split()) > 1:
        # Если пришли с QR: /start TEST-001
        qr_code = message.text.split()[1]

    if is_user_registered(user_id): # проверяем, есть ли пользователь в базе данных
        # Проверяем разрешение из БД
        if check_user_permit(user_id): # проверяем, имеет ли пользователь доступ (permit = True)
            # ЕСЛИ ЕСТЬ QR-КОД - СРАЗУ ОБРАБАТЫВАЕМ
            if qr_code: # если QR-код был передан
                fake_msg = types.Message( # создаем искусственное сообщение
                    message_id=0,
                    from_user=message.from_user,
                    date=message.date,
                    chat=message.chat,
                    content_type='text',
                    options=[],
                    json_string=''
                )
                fake_msg.text = qr_code # записываем в текст сообщения наш QR-код
                handle_all_messages(fake_msg) # передаем это искусственное сообщение в обработчик всех сообщений
            else:
                # ЕСЛИ НЕТ QR - ПОКАЗЫВАЕМ ПРИВЕТСТВИЕ
                bot.send_message(
                    message.chat.id,
                    f"Привет!\nОтсканируйте QR для работы с книгами"
                )

        else:
            bot.send_message(
                message.chat.id,
                f"Регистрация завершена\n\nОжидайте подтверждения администратора!"
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
        user_waiting_for_data[user_id] = True # помечаем, что пользователь ожидает ввода данных
        bot.send_message(
            message.chat.id,
            welcome_text
        )


@bot.message_handler(commands=['books'])
def handle_my_books(message):
    """Показывает книги, которые сейчас на руках у пользователя"""
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

    bot.reply_to(message, text)


@bot.message_handler(commands=['help'])
def handle_act_start(message):
    """Команда для учителя - начать помощь ученику"""
    user_id = message.from_user.id

    # Проверяем, что это учитель
    if get_user_status(user_id) != 'teacher':
        bot.reply_to(message, "Эта команда только для учителей!")
        return

    # Получаем список всех классов
    conn = sqlite3.connect('library.db') # подключаемся к базе данных
    cursor = conn.cursor() # создаем курсор
    cursor.execute('SELECT DISTINCT class FROM users WHERE class NOT LIKE "Учитель:%" ORDER BY class') # SQL-запрос для получения уникальных классов учеников (исключая учителей)
    classes = cursor.fetchall() # получаем все результаты
    conn.close() # закрываем соединение

    if not classes: # если классов нет
        bot.reply_to(message, "В системе пока нет учеников")
        return

    # Создаём клавиатуру с классами
    keyboard = types.InlineKeyboardMarkup(row_width=3) # создаем клавиатуру
    buttons = [] # создаем пустой список для кнопок
    for class_name in classes: # перебираем все классы
        buttons.append(types.InlineKeyboardButton( # добавляем кнопку для каждого класса
            class_name[0], # текст кнопки - название класса
            callback_data=f"help_class_{class_name[0]}" # callback_data = "help_class_10А"
        ))
    keyboard.add(*buttons) # добавляем все кнопки в клавиатуру (оператор * распаковывает список)
    keyboard.add(types.InlineKeyboardButton("Отмена", callback_data="help_cancel")) # добавляем кнопку отмены

    teacher_temp_data[user_id] = {'step': 'waiting_class'}  # запоминаем, что учитель на шаге выбора класса

    bot.reply_to(
        message,
        "Выберите класс ученика:",
        reply_markup=keyboard # прикрепляем клавиатуру к сообщению
    )


@bot.message_handler(commands=['status'])
def handle_act_status(message):
    """Показывает, за кого сейчас действует учитель"""
    user_id = message.from_user.id

    if user_id in teacher_acting_for: # если учитель сейчас в режиме помощи
        student_id = teacher_acting_for[user_id] # получаем ID ученика

        conn = sqlite3.connect('library.db') # подключаемся к базе
        cursor = conn.cursor() # создаем курсор
        cursor.execute('SELECT FIO, class FROM users WHERE tg_id = ?', (student_id,)) # ищем ФИО и класс ученика
        fio, class_name = cursor.fetchone() # получаем результат
        conn.close() # закрываем соединение

        bot.reply_to(
            message,
            f"Вы действуете за ученика:\n{fio}\n{class_name}"
        )
    else:
        bot.reply_to(message, "Вы действуете от своего имени")


@bot.message_handler(commands=['stop_help'])
def handle_stop_help(message):
    """Выход из режима помощи"""
    user_id = message.from_user.id

    if user_id in teacher_acting_for: # если учитель в режиме помощи
        student_id = teacher_acting_for[user_id]

        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute('SELECT FIO FROM users WHERE tg_id = ?', (student_id,))
        fio = cursor.fetchone()[0] # получаем ФИО
        conn.close()

        del teacher_acting_for[user_id] # удаляем запись из словаря (выходим из режима)
        bot.reply_to(
            message,
            f"Вы вышли из режима помощи для ученика {fio}"
        )
    else:
        bot.reply_to(message, "Вы и так не в режиме помощи")


# ========== ОБРАБОТЧИК РЕГИСТРАЦИИ ==========

@bot.message_handler(func=lambda message: user_waiting_for_data.get(message.from_user.id, False))
def handle_registration_data(message):
    user_id = message.from_user.id
    text = message.text.strip() # получаем текст сообщения и удаляем лишние пробелы
    parts = text.split() # разбиваем текст на слова по пробелам

    if len(parts) < 4: # если слов меньше 4 (нужно минимум Фамилия Имя Отчество + класс/предмет)
        error_text = """
Недостаточно данных!

Введите: Фамилия Имя Отчество Класс или Фамилия Имя Отчество Предмет

Примеры:
Иванов Иван Иванович 10А
Петрова Анна Сергеевна математика

Попробуйте еще раз:
        """
        bot.send_message(message.chat.id, error_text)
        return

    fio = ' '.join(parts[:3]) # первые 3 слова объединяем в ФИО
    additional = ' '.join(parts[3:]) # остальные слова объединяем в класс или предмет

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
    callback_data = call.data # получаем callback_data из нажатой кнопки

    # ЗАЩИТА ОТ СТАРЫХ CALLBACK
    try:
        bot.answer_callback_query(call.id) # обязательно отвечаем на callback (убирает "часики")
    except Exception as e: # если произошла ошибка (старый callback)
        print(f"Старый callback: {e}") # выводим ошибку в консоль
        try:
            bot.send_message(
                call.message.chat.id,
                "Это сообщение устарело. Нажмите /start"
            )
        except:
            pass # если и это не удалось - игнорируем
        return

    # ===== ОБРАБОТЧИКИ ДЛЯ /help =====
    if callback_data.startswith("help_class_"): # если callback начинается с "help_class_"
        # Учитель выбрал класс
        class_name = callback_data.replace("help_class_", "") # извлекаем название класса

        # Получаем учеников этого класса
        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute('''
                SELECT tg_id, FIO FROM users 
                WHERE class = ? AND status = 'student'
                ORDER BY FIO
            ''', (class_name,)) # SQL-запрос для получения учеников выбранного класса
        students = cursor.fetchall() # получаем всех учеников
        conn.close()

        if not students: # если учеников нет
            bot.answer_callback_query(call.id, "В этом классе нет учеников")
            return

        # Создаем клавиатуру с учениками
        keyboard = types.InlineKeyboardMarkup(row_width=1) # создаем клавиатуру
        for tg_id, fio in students: # перебираем всех учеников
            short_name = ' '.join(fio.split()[:2]) # берем только Фамилию и Имя
            keyboard.add(types.InlineKeyboardButton(
                f"{short_name}",
                callback_data=f"help_student_{tg_id}" # callback_data = "help_student_123456789"
            ))

        keyboard.add(types.InlineKeyboardButton("Назад к классам", callback_data="help_back_to_classes"))
        keyboard.add(types.InlineKeyboardButton("Отмена", callback_data="help_cancel"))

        teacher_temp_data[user_id] = {'step': 'waiting_student', 'class': class_name} # запоминаем, что учитель на шаге выбора ученика

        bot.edit_message_text( # редактируем предыдущее сообщение (заменяем текст)
            f"Класс {class_name}\n\nВыберите ученика:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard # прикрепляем новую клавиатуру
        )
        return

    if callback_data.startswith("help_student_"): # если callback начинается с "help_student_"
        # Учитель выбрал ученика
        student_id = int(callback_data.replace("help_student_", "")) # извлекаем ID ученика и преобразуем в int

        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute('SELECT FIO, class FROM users WHERE tg_id = ?', (student_id,)) # получаем ФИО и класс ученика
        fio, class_name = cursor.fetchone() # получаем результат
        conn.close()

        # Запоминаем, за кого действует учитель
        teacher_acting_for[user_id] = student_id

        if user_id in teacher_temp_data: # если есть временные данные
            del teacher_temp_data[user_id] # удаляем их

        success_text = f"""
Режим помощи ученику активирован!
Ученик: {fio}
Класс: {class_name}

Теперь все операции с книгами будут выполняться для этого ученика.

Команды:
/stop_help — вернуться в обычный режим
/status — посмотреть текущего ученика
        """

        bot.edit_message_text( # редактируем предыдущее сообщение
            success_text,
            call.message.chat.id,
            call.message.message_id
        )
        return

    if callback_data == "help_back_to_classes": # если нажата кнопка "Назад к классам"
        # Возврат к выбору классов
        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT class FROM users WHERE class NOT LIKE "Учитель:%" ORDER BY class') # получаем список классов
        classes = cursor.fetchall() # получаем результат
        conn.close()

        # Создаем клавиатуру с классами
        keyboard = types.InlineKeyboardMarkup(row_width=3)
        buttons = []
        for class_name in classes:
            buttons.append(types.InlineKeyboardButton(
                class_name[0],
                callback_data=f"help_class_{class_name[0]}"
            ))
        keyboard.add(*buttons)
        keyboard.add(types.InlineKeyboardButton("Отмена", callback_data="help_cancel"))

        bot.edit_message_text(
            "Выберите класс ученика:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        return

    if callback_data == "help_cancel": # если нажата кнопка "Отмена"
        # Отмена действия
        if user_id in teacher_temp_data: # если есть временные данные
            del teacher_temp_data[user_id]

        bot.edit_message_text( # редактируем сообщение
            "Действие отменено.",
            call.message.chat.id,
            call.message.message_id
        )
        return


    # ===== КНОПКИ ПОДТВЕРЖДЕНИЯ УЧИТЕЛЯ =====
    if callback_data.startswith("confirm_") or callback_data.startswith("reject_"):
        admin_id = call.from_user.id

        # Проверяем, что это админ
        if admin_id != ADMIN_ID:
            bot.answer_callback_query(call.id, "У вас нет прав администратора!")
            return

        # Получаем ID учителя из callback_data
        if callback_data.startswith("confirm_"): # если подтверждение
            teacher_id = int(callback_data.replace("confirm_", "")) # извлекаем ID учителя
            permit = True # разрешение = True
            action = "подтверждена"

            # Обновляем статус в БД
            conn = sqlite3.connect('library.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET permit = ? WHERE tg_id = ?', (permit, teacher_id)) # обновляем поле permit
            conn.commit() # сохраняем изменения
            conn.close()

            # Уведомляем учителя об одобрении
            bot.send_message(
                teacher_id,
                "Ваша заявка одобрена!\n\n"
                "Теперь вы можете пользоваться библиотекой.\n"
                "Отправьте /start для начала работы."
            )
        else:
            teacher_id = int(callback_data.replace("reject_", ""))
            action = "отклонена"

            if delete_user(teacher_id): # удаляем пользователя из БД
                # Уведомляем учителя об отклонении
                bot.send_message(
                    teacher_id,
                    "Ваша заявка отклонена.\n\n"
                    "Обратитесь к администратору для уточнения причины.\n"
                    "Вы можете зарегистрироваться снова через /start"
                )
            else: # если не удалось удалить (пользователь не найден)
                bot.send_message(
                    admin_id,
                    f"Не удалось удалить пользователя {teacher_id} (возможно, его уже нет в БД)"
                )


        # Сообщение админу
        bot.edit_message_text( # редактируем сообщение с заявкой
            f"Заявка {action}!",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id) # отвечаем на callback
        return

    # ===== ВЫБОР РОЛИ (УЧЕНИК/УЧИТЕЛЬ) =====
    if callback_data.startswith("role_"):
        role = callback_data.split("_")[1] # извлекаем роль

        if user_id not in user_data_temp: # если нет временных данных
            bot.send_message(call.message.chat.id, "Ошибка! Начните регистрацию заново: /start")
            return

        temp_data = user_data_temp[user_id] # получаем временные данные
        fio = temp_data['fio'] # извлекаем ФИО
        additional = temp_data['additional'] # извлекаем класс или предмет

        if role == "student":
            if register_user(user_id, fio, additional, "student", True): # регистрируем с permit = True
                success_text = f"""
Регистрация завершена!

Отсканируйте QR для работы с книгами!
                """
            else:
                bot.send_message(call.message.chat.id, "Ошибка регистрации!")
                return
        else:  # teacher
            if register_user(user_id, fio, f"Учитель: {additional}", "teacher", False): # регистрируем с permit = False
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
                    reply_markup=create_confirm_keyboard(user_id) # прикрепляем клавиатуру с кнопками подтверждения
                )
            else:
                bot.send_message(call.message.chat.id, "Ошибка регистрации!")
                return

        if user_id in user_data_temp: # очищаем временные данные
            del user_data_temp[user_id]

        bot.edit_message_text( # редактируем сообщение с выбором роли
            success_text,
            call.message.chat.id,
            call.message.message_id
        )
        return

    # ===== ВЗЯТИЕ КНИГИ =====
    if callback_data.startswith("take_"):
        qr_code = callback_data.replace("take_", "") # извлекаем QR-код

        # Определяем, от чьего имени брать книгу (учитель или ученик)
        acting_user_id = teacher_acting_for.get(user_id, user_id) # если учитель в режиме помощи, берем ID ученика, иначе ID самого пользователя

        if take_book(acting_user_id, qr_code): # пытаемся взять книгу
            success_text = f"""
Книга взята!
            """
            bot.edit_message_text(
                success_text,
                call.message.chat.id,
                call.message.message_id
            )
        else:
            error_text = f"""
Книга уже взята вами или кем-то другим.
            """
            bot.edit_message_text(
                error_text,
                call.message.chat.id,
                call.message.message_id
            )

        if user_id in user_pending_action: # очищаем временное хранилище QR-кода
            del user_pending_action[user_id]
        return

    # ===== ВОЗВРАТ КНИГИ =====
    if callback_data.startswith("return_"):
        qr_code = callback_data.replace("return_", "") # извлекаем QR-код

        acting_user_id = teacher_acting_for.get(user_id, user_id) # определяем, от чьего имени возвращать

        if return_book(acting_user_id, qr_code): # пытаемся вернуть книгу
            success_text = f"""
Книга возвращена!
            """
            bot.edit_message_text(
                success_text,
                call.message.chat.id,
                call.message.message_id
            )
        else:
            error_text = f"""
Не удалось вернуть книгу
Книга не числится за вами.
            """
            bot.edit_message_text(
                error_text,
                call.message.chat.id,
                call.message.message_id
            )

        if user_id in user_pending_action: # очищаем временное хранилище QR-кода
            del user_pending_action[user_id]
        return

    # ===== КНОПКА "КОМУ ПРИНАДЛЕЖИТ?" =====
    if callback_data.startswith("who_"):
        qr_code = callback_data.replace("who_", "") # извлекаем QR-код

        # Получаем информацию о владельце книги
        owner = get_book_owner_info(qr_code) # вызываем функцию из database.py
        user_status = get_user_status(user_id)  # 'student' или 'teacher'

        # Книга свободна
        if not owner:
            # Для УЧИТЕЛЯ — полная информация
            if user_status == 'teacher':
                info_text = f"""
Информация o книге:

Книга свободна!
                            """

            else:  # student
                info_text = f"""
Эта не твоя книга!
Отнеси ее учителю.
                            """

        else: # если книга у кого-то
            fio, class_name, owner_tg_id, issue_date = owner # распаковываем данные

            # Для УЧИТЕЛЯ — полная информация
            if user_status == 'teacher':
                if owner_tg_id == user_id:
                    # Это ЕГО книга
                    info_text = f"""
Это ваш учебник!

Взят: {issue_date}
Не забудьте вернуть вовремя!
                                    """
                else: # если книга другого ученика
                    info_text = f"""
Информация o книге:

Книга принадлежит:
ФИО: {fio}
Класс: {class_name}
Взята: {issue_date}
                    """

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
            call.message.message_id
        )

        bot.answer_callback_query(call.id) # отвечаем на callback
        return


# ========== ОБРАБОТЧИК QR-КОДОВ ==========

@bot.message_handler(func=lambda message: True) # ловит ВСЕ сообщения (самый последний обработчик)
def handle_all_messages(message):
    """Обрабатывает все остальные сообщения (QR-коды, случайный текст)"""
    user_id = message.from_user.id

    # Если пользователь не зарегистрирован
    if not is_user_registered(user_id):
        if user_id not in user_waiting_for_data and user_id not in user_data_temp: # и не в процессе регистрации
            bot.send_message(message.chat.id, "Для начала работы используйте команду /start")
        return

    # Если сообщение похоже на QR-код (не команда, не пустое)
    text = message.text.strip() # получаем текст сообщения
    if text and not text.startswith('/'): # если не пусто и не начинается с /
        user_pending_action[user_id] = text # сохраняем в словарь QR-код для этого пользователя

        # Получаем информацию о книге
        book_info = get_book_info(text) # вызываем функцию из database.py

        if not book_info:
            bot.reply_to(message, f"Книга не найдена.")
            if user_id in user_pending_action: # очищаем временное хранилище
                del user_pending_action[user_id]
            return

        book_text = f"""
ИНФОРМАЦИЯ О КНИГЕ

Код: {book_info['qr_code']}
Название: {book_info['subject']}
Автор: {book_info['author']}
Год: {book_info['year']}

Выберите действие:
        """

        bot.reply_to( # отвечаем
            message,
            book_text,
            reply_markup=create_book_action_keyboard(text) # прикрепляем клавиатуру с кнопками
        )


# ========== ЗАПУСК БОТА ==========

bot.infinity_polling(timeout=60, long_polling_timeout=60) # запускаем бота в режиме бесконечного опроса
# timeout=60 - таймаут на запрос к Telegram
# long_polling_timeout=60 - максимальное время ожидания ответа

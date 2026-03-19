import telebot
from telebot import types  # импортируем типы данных для создания кнопок и клавиатур
import config  # берем токен и ID админа из config.py
from database import *  # импортируем все функции из database.py
import excel_importer  # импортируем файл, который автоматически заносит книги в базу данных из Excel-файла
import os  # библиотека для работы с файлами
from datetime import datetime


create_database()  # создаем базу данных при запуске (таблицы создадутся, если их нет)

bot = telebot.TeleBot(config.token)

# СОСТОЯНИЯ для управления диалогом
user_waiting_for_data = {}  # {user_id: True} - ожидает ввода данных для регистрации
user_data_temp = {}  # {user_id: {'fio': '...', 'additional': '...'}} - временное хранение введенных ФИО и класса/предмета
user_pending_action = {}  # {user_id: 'qr_code'} - хранит QR-код
# Состояния для учителя
teacher_acting_for = {}  # {tФeacher_id: student_tg_id} - учитель действует за ученика
teacher_temp_data = {}  # {teacher_id: {'step': 'waiting_class', ...}} - временные данные для выбора ученика


# ========== ИНЛАЙН КЛАВИАТУРЫ ==========

def create_role_keyboard():
    """Создает клавиатуру для выбора роли"""
    keyboard = types.InlineKeyboardMarkup()  # создаем пустую inline-клавиатуру
    keyboard.row(  # добавляем ряд с двумя кнопками
        types.InlineKeyboardButton("Ученик", callback_data="role_student"),
        types.InlineKeyboardButton("Учитель", callback_data="role_teacher")
    )
    return keyboard


def create_book_action_keyboard(qr_code, user_status):
    """
    Создает клавиатуру с учетом роли пользователя
    - Для учеников: только «Взять» и «Кому принадлежит?»
    - Для учителей: все три кнопки (включая «Вернуть»)
    """
    keyboard = types.InlineKeyboardMarkup(row_width=2)  # создаем клавиатуру с двумя кнопками в ряду

    # Кнопки, доступные всем
    buttons = [
        types.InlineKeyboardButton("Взять", callback_data=f"take_{qr_code}"),
        types.InlineKeyboardButton("Кому принадлежит?", callback_data=f"who_{qr_code}")
    ]

    # Кнопка «Вернуть» только для учителей
    if user_status == 'teacher':
        buttons.append(types.InlineKeyboardButton("Вернуть", callback_data=f"return_{qr_code}"))

    keyboard.add(*buttons)
    return keyboard


def create_confirm_keyboard(teacher_id):
    """Создает клавиатуру для подтверждения учителя"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)  # создаем клавиатуру с двумя кнопками в ряду
    keyboard.add(
        types.InlineKeyboardButton("Подтвердить", callback_data=f"confirm_{teacher_id}"),
        # при нажатии вернется "confirm_IDучителя"
        types.InlineKeyboardButton("Отклонить", callback_data=f"reject_{teacher_id}")
        # при нажатии вернется "reject_IDучителя"
    )
    return keyboard


# ========== ОБРАБОТЧИКИ КОМАНД ==========

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.from_user.id  # получаем ID пользователя

    # ПОЛУЧАЕМ QR-КОД ИЗ КОМАНДЫ (если есть)
    qr_code = None  # инициализируем переменную для QR-кода
    # message.text.split() разбивает текст сообщения на слова по пробелам
    # Например: "/start TEST-001" -> ["/start", "TEST-001"]
    if len(message.text.split()) > 1:  # если в сообщении есть пробел (значит есть параметр)
        # Если пришли с QR: /start TEST-001
        qr_code = message.text.split()[1]

    if is_user_registered(user_id):  # проверяем, есть ли пользователь в базе данных
        # Проверяем разрешение из БД
        if check_user_permit(user_id):  # проверяем, имеет ли пользователь доступ (permit = True)
            # ЕСЛИ ЕСТЬ QR-КОД - СРАЗУ ОБРАБАТЫВАЕМ
            if qr_code:  # если QR-код был передан

                # Создаем искусственное (фейковое) сообщение, чтобы передать QR-код в обработчик handle_all_messages
                # Это нужно, чтобы при сканировании QR не отправлять код отдельно, а обработать сразу

                fake_msg = types.Message(  # создаем искусственное сообщение
                    message_id=0,  # ID сообщения = 0 (неважно, это искусственный объект)
                    from_user=message.from_user,  # копируем отправителя из оригинального сообщения
                    date=message.date,  # копируем дату отправки
                    chat=message.chat,  # копируем информацию о чате
                    content_type='text',  # тип содержимого - текст
                    options=[],  # пустые опции (обязательный параметр)
                    json_string=''  # пустая JSON-строка (обязательный параметр)
                )
                fake_msg.text = qr_code  # записываем в текст сообщения наш QR-код
                handle_all_messages(fake_msg)  # передаем это искусственное сообщение в обработчик всех сообщений
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
Регистрируйтесь под собственным именем. Его будут видеть учителя!

Введите ваши данные в формате:
Для ученика: Фамилия Имя Отчество Класс
Для учителя: Фамилия Имя Отчество Предмет

Примеры:
Иванов Иван Иванович 10А
Петрова Анна Сергеевна математика

Введите ваши данные:
        """
        user_waiting_for_data[user_id] = True  # помечаем, что пользователь ожидает ввода данных
        bot.send_message(
            message.chat.id,
            welcome_text
        )


@bot.message_handler(commands=['books'])
def handle_my_books(message):
    """Показывает книги на руках"""
    user_id = message.from_user.id
    user_status = get_user_status(user_id)

    # ===== ПРОВЕРКА РЕГИСТРАЦИИ =====
    if not is_user_registered(user_id):
        bot.reply_to(message, "Сначала зарегистрируйтесь через /start")
        return

    # ===== ОПРЕДЕЛЯЕМ, ЧЬИ КНИГИ ПОКАЗЫВАТЬ =====
    # Если учитель в режиме помощи — показываем книги ученика
    if user_id in teacher_acting_for:
        target_id = teacher_acting_for[user_id]  # ID ученика
        target_name = "выбранного ученика"
    else:
        # Если не в режиме помощи — показываем свои книги
        target_id = user_id
        target_name = "вас"

    # ===== ПОЛУЧАЕМ СПИСОК КНИГ =====
    books = get_user_current_books(target_id)

    if not books:
        bot.reply_to(message, f"У {target_name} нет книг.")
        return

    # ===== ФОРМИРУЕМ ТЕКСТ СООБЩЕНИЯ =====
    if user_id in teacher_acting_for:
        text = f"КНИГИ {target_name.upper()}:\n\n"
    else:
        text = "ВАШИ КНИГИ:\n\n"
        
    for book in books:
        subject = book[0]          # Название книги
        issue_date = book[3]        # Дата выдачи
        text += f"{subject}\nВзята: {issue_date}\n\n"

    # ===== КНОПКА ДЛЯ УЧИТЕЛЯ (МАССОВАЯ СДАЧА) =====
    keyboard = None
    if user_status == 'teacher':  # только для учителей
        keyboard = types.InlineKeyboardMarkup()
        keyboard.add(types.InlineKeyboardButton(
            "Сдать все книги", 
            callback_data=f"return_all_{target_id}"
        ))

    # ===== ОТПРАВЛЯЕМ СООБЩЕНИЕ =====
    bot.send_message(
        message.chat.id,
        text,
        reply_markup=keyboard
    )

@bot.message_handler(commands=['help'])
def handle_act_start(message):
    """Команда для учителя - начать помощь ученику"""
    user_id = message.from_user.id

    # Проверяем, что это учитель
    if get_user_status(user_id) != 'teacher':
        bot.reply_to(message, "Эта команда только для учителей!")
        return

    # Получаем список всех классов
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()  # создаем курсор
    cursor.execute(
        'SELECT DISTINCT class FROM users WHERE class NOT LIKE "Учитель:%" ORDER BY class')  # SQL-запрос для получения уникальных классов учеников (исключая учителей)
    classes = cursor.fetchall()  # получаем все результаты
    conn.close()  # закрываем соединение

    if not classes:  # если классов нет
        bot.reply_to(message, "В системе пока нет учеников")
        return

    # Создаём клавиатуру с классами
    keyboard = types.InlineKeyboardMarkup(row_width=3)  # создаем клавиатуру
    buttons = []  # создаем пустой список для кнопок
    for class_name in classes:  # перебираем все классы
        buttons.append(types.InlineKeyboardButton(  # добавляем кнопку для каждого класса
            class_name[0],  # текст кнопки - название класса
            callback_data=f"help_class_{class_name[0]}"  # callback_data = "help_class_10А"
        ))
    keyboard.add(*buttons)  # добавляем все кнопки в клавиатуру (оператор * распаковывает список)
    keyboard.add(types.InlineKeyboardButton("Отмена", callback_data="help_cancel"))  # добавляем кнопку отмены

    teacher_temp_data[user_id] = {'step': 'waiting_class'}  # запоминаем, что учитель на шаге выбора класса

    bot.reply_to(
        message,
        "Выберите класс ученика:",
        reply_markup=keyboard  # прикрепляем клавиатуру к сообщению
    )


@bot.message_handler(commands=['status'])
def handle_act_status(message):
    """Показывает, за кого сейчас действует учитель"""
    user_id = message.from_user.id

    if user_id in teacher_acting_for:  # если учитель сейчас в режиме помощи
        student_id = teacher_acting_for[user_id]  # получаем ID ученика

        conn = sqlite3.connect('library.db')  # подключаемся к базе
        cursor = conn.cursor()  # создаем курсор
        cursor.execute('SELECT FIO, class FROM users WHERE tg_id = ?', (student_id,))  # ищем ФИО и класс ученика
        fio, class_name = cursor.fetchone()  # получаем результат
        conn.close()  # закрываем соединение

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

    if user_id in teacher_acting_for:  # если учитель в режиме помощи
        student_id = teacher_acting_for[user_id]

        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute('SELECT FIO FROM users WHERE tg_id = ?', (student_id,))
        fio = cursor.fetchone()[0]  # получаем ФИО
        conn.close()

        del teacher_acting_for[user_id]  # удаляем запись из словаря (выходим из режима)
        bot.reply_to(
            message,
            f"Вы вышли из режима помощи для ученика {fio}"
        )
    else:
        bot.reply_to(message, "Вы и так не в режиме помощи")


@bot.message_handler(commands=['update_id'])
def handle_update_teacher(message):
    """Обновляет Telegram ID пользователя"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Эта функция только для админа!")
        return

    try:
        old_id, new_id = message.text.split()[1:]
        old_id = int(old_id)
        new_id = int(new_id)

        success, msg = update_tg_id(old_id, new_id)
        bot.reply_to(message, msg)
    except:
        bot.reply_to(message, "Использование: /update_id старый ID новый ID")
        bot.reply_to(message, "Telegram ID можно узнать у бота @userinfobot или посмотреть в профиле")


@bot.message_handler(commands=['reregistaration'])
def handle_reregistaration(message):
    """
    Полный сброс состояния пользователя.
    Позволяет начать регистрацию заново, если что-то зависло.
    """
    user_id = message.from_user.id

    # Очищаем все состояния пользователя
    cleared = []

    if user_id in user_waiting_for_data:
        del user_waiting_for_data[user_id]
        cleared.append("ожидание данных")

    if user_id in user_data_temp:
        del user_data_temp[user_id]
        cleared.append("временные данные")

    if user_id in user_pending_action:
        del user_pending_action[user_id]
        cleared.append("ожидание QR")

    if user_id in teacher_acting_for:
        del teacher_acting_for[user_id]
        cleared.append("режим помощи")

    if user_id in teacher_temp_data:
        del teacher_temp_data[user_id]
        cleared.append("выбор ученика")

    # Формируем сообщение о результате
    if cleared:
        result_text = f"Сброшены состояния: {', '.join(cleared)}.\n\nТеперь можете начать заново с команды /start"
    else:
        result_text = "У вас не было активных состояний. Можете нажимать /start"

    # Отправляем результат и сразу запускаем регистрацию
    bot.send_message(
        message.chat.id,
        result_text
    )

    # Автоматически запускаем /start
    handle_start(message)


@bot.message_handler(commands=['import_books'])
def handle_import_books(message):
    """Команда для администратора: начать импорт книг из Excel"""
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "Эта функция только для администратора!")
        return

    bot.reply_to(
        message,
        "Отправьте мне Excel-файл со списком учебников.\n\n"
        "Я сам разберу его, добавлю книги в базу и создам QR-коды."
    )


# функция отправления PDF-файла со всеми QR-кодами
@bot.message_handler(commands=['get_pdf'])
def handle_get_pdf(message):
    """Отправляет PDF со всеми QR-кодами"""
    if message.from_user.id != ADMIN_ID:  # проверяем, что команду отправил администратор
        bot.reply_to(message, "Эта функция только для администратора!")
        return

    # проверяем, существует ли папка qrcodes и есть ли в ней хоть один файл
    # os.path.exists('qrcodes') — True, если папка есть
    # len(os.listdir('qrcodes')) — количество файлов в папке
    if not os.path.exists('qrcodes') or len(os.listdir('qrcodes')) == 0:
        bot.reply_to(message, "Папка qrcodes/ пуста. Сначала импортируйте книги.\nДля этого используйте команду /import_books")
        return

    #  отправляем первое сообщение, чтобы пользователь знал, что бот работает
    # сохраняем это сообщение в переменную msg, чтобы потом его отредактировать
    msg = bot.reply_to(message, "Создаю PDF...")

    try:
        # создаем имя файла
        # datetime.now().strftime('%Y%m%d') — текущая дата в формате ГГГГММДД
        # например: 20260318.pdf
        pdf_filename = f"qrcodes_{datetime.now().strftime('%Y%m%d')}.pdf"

        # вызываем функцию создания PDF-файла
        # функция лежит в файле excel_importer.py
        # она создаст PDF с QR-кодами и сохранит его под именем pdf_filename
        excel_importer.create_qr_pdf(pdf_filename)

        # отправляем PDF пользователю
        # открываем созданный файл для чтения в бинарном режиме ('rb')
        with open(pdf_filename, 'rb') as f:
            # отправляем файл как документ
            # chat.id — чат, куда отправляем
            # f — открытый файл
            # caption — подпись под файлом
            bot.send_document(
                message.chat.id,
                f,
                caption=f"QR-коды для печати"  # подпись под файлом
            )

        # удаляем временный PDF-файл, чтобы не засорять папку
        os.remove(pdf_filename)

        # удаляем предыдущее сообщение "Создаю PDF..."
        # чтобы в чате остался только сам файл, а не куча служебных сообщений
        bot.delete_message(msg.chat.id, msg.message_id)

    except Exception as e:  # при любой ошибке
        # перехватываем ошибку и показываем её пользователю
        # e — объект ошибки
        # редактируем сообщение "Создаю PDF..." и заменяем его на ошибку
        bot.edit_message_text(f"Ошибка: {e}", msg.chat.id, msg.message_id)

# ========== ОБРАБОТЧИК РЕГИСТРАЦИИ ==========

@bot.message_handler(func=lambda message: user_waiting_for_data.get(message.from_user.id, False))
def handle_registration_data(message):
    user_id = message.from_user.id
    text = message.text.strip()  # получаем текст сообщения и удаляем лишние пробелы
    parts = text.split()  # разбиваем текст на слова по пробелам

    if len(parts) < 4:  # если слов меньше 4 (нужно минимум Фамилия Имя Отчество + класс/предмет)
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

    fio = ' '.join(parts[:3])  # первые 3 слова объединяем в ФИО
    additional = ' '.join(parts[3:])  # остальные слова объединяем в класс или предмет

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
    bot.send_message(message.chat.id,
                 "Если бот не отвечает, начните регистрацию заново.\nДля этого выберите команду /reregistaration")


# ========== ОБРАБОТЧИКИ INLINE-КНОПОК ==========

@bot.callback_query_handler(func=lambda call: True)
def handle_inline_buttons(call):
    user_id = call.from_user.id
    callback_data = call.data  # получаем callback_data из нажатой кнопки

    # ЗАЩИТА ОТ СТАРЫХ CALLBACK
    try:
        bot.answer_callback_query(call.id)  # обязательно отвечаем на callback (убирает "часики")
    except Exception as e:  # если произошла ошибка (старый callback)
        print(f"Старый callback: {e}")  # выводим ошибку в консоль
        try:
            bot.send_message(
                call.message.chat.id,
                "Это сообщение устарело. Нажмите /start"
            )
        except:
            pass  # если и это не удалось - игнорируем
        return

    # ===== ОБРАБОТЧИКИ ДЛЯ /help =====
    if callback_data.startswith("help_class_"):  # если callback начинается с "help_class_"
        # Учитель выбрал класс
        class_name = callback_data.replace("help_class_", "")  # извлекаем название класса

        # Получаем учеников этого класса
        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute('''
                SELECT tg_id, FIO FROM users 
                WHERE class = ? AND status = 'student'
                ORDER BY FIO
            ''', (class_name,))  # SQL-запрос для получения учеников выбранного класса
        students = cursor.fetchall()  # получаем всех учеников
        conn.close()

        if not students:  # если учеников нет
            bot.answer_callback_query(call.id, "В этом классе нет учеников")
            return

        # Создаем клавиатуру с учениками
        keyboard = types.InlineKeyboardMarkup(row_width=1)  # создаем клавиатуру
        for tg_id, fio in students:  # перебираем всех учеников
            short_name = ' '.join(fio.split()[:2])  # берем только Фамилию и Имя
            keyboard.add(types.InlineKeyboardButton(
                f"{short_name}",
                callback_data=f"help_student_{tg_id}"  # callback_data = "help_student_123456789"
            ))

        keyboard.add(types.InlineKeyboardButton("Назад к классам", callback_data="help_back_to_classes"))
        keyboard.add(types.InlineKeyboardButton("Отмена", callback_data="help_cancel"))

        teacher_temp_data[user_id] = {'step': 'waiting_student',
                                      'class': class_name}  # запоминаем, что учитель на шаге выбора ученика

        bot.edit_message_text(  # редактируем предыдущее сообщение (заменяем текст)
            f"Класс {class_name}\n\nВыберите ученика:",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard  # прикрепляем новую клавиатуру
        )
        return

    if callback_data.startswith("help_student_"):  # если callback начинается с "help_student_"
        # Учитель выбрал ученика
        student_id = int(callback_data.replace("help_student_", ""))  # извлекаем ID ученика и преобразуем в int

        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute('SELECT FIO, class FROM users WHERE tg_id = ?', (student_id,))  # получаем ФИО и класс ученика
        fio, class_name = cursor.fetchone()  # получаем результат
        conn.close()

        # Запоминаем, за кого действует учитель
        teacher_acting_for[user_id] = student_id

        if user_id in teacher_temp_data:  # если есть временные данные
            del teacher_temp_data[user_id]  # удаляем их

        success_text = f"""
Режим помощи ученику активирован!
Ученик: {fio}
Класс: {class_name}

Теперь все операции с книгами будут выполняться для этого ученика.

Команды:
/stop_help — вернуться в обычный режим
/status — посмотреть текущего ученика
        """

        bot.edit_message_text(  # редактируем предыдущее сообщение
            success_text,
            call.message.chat.id,
            call.message.message_id
        )
        return

    if callback_data == "help_back_to_classes":  # если нажата кнопка "Назад к классам"
        # Возврат к выбору классов
        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()
        cursor.execute(
            'SELECT DISTINCT class FROM users WHERE class NOT LIKE "Учитель:%" ORDER BY class')  # получаем список классов
        classes = cursor.fetchall()  # получаем результат
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

    if callback_data == "help_cancel":  # если нажата кнопка "Отмена"
        # Отмена действия
        if user_id in teacher_temp_data:  # если есть временные данные
            del teacher_temp_data[user_id]

        bot.edit_message_text(  # редактируем сообщение
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
        if callback_data.startswith("confirm_"):  # если подтверждение
            teacher_id = int(callback_data.replace("confirm_", ""))  # извлекаем ID учителя
            permit = True  # разрешение = True
            action = "подтверждена"

            # Обновляем статус в БД
            conn = sqlite3.connect('library.db')
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET permit = ? WHERE tg_id = ?', (permit, teacher_id))  # обновляем поле permit
            conn.commit()  # сохраняем изменения
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

            if delete_user(teacher_id):  # удаляем пользователя из БД
                # Уведомляем учителя об отклонении
                bot.send_message(
                    teacher_id,
                    "Ваша заявка отклонена.\n\n"
                    "Обратитесь к администратору для уточнения причины.\n"
                    "Вы можете зарегистрироваться снова через /start"
                )
            else:  # если не удалось удалить (пользователь не найден)
                bot.send_message(
                    admin_id,
                    f"Не удалось удалить пользователя {teacher_id} (возможно, его уже нет в БД)"
                )

        # Сообщение админу
        bot.edit_message_text(  # редактируем сообщение с заявкой
            f"Заявка {action}!",
            call.message.chat.id,
            call.message.message_id
        )
        bot.answer_callback_query(call.id)  # отвечаем на callback
        return

    # ===== ВЫБОР РОЛИ (УЧЕНИК/УЧИТЕЛЬ) =====
    if callback_data.startswith("role_"):
        role = callback_data.split("_")[1]  # извлекаем роль

        if user_id not in user_data_temp:  # если нет временных данных
            bot.send_message(call.message.chat.id, "Ошибка! Начните регистрацию заново: /start")
            return

        temp_data = user_data_temp[user_id]  # получаем временные данные
        fio = temp_data['fio']  # извлекаем ФИО
        additional = temp_data['additional']  # извлекаем класс или предмет

        if role == "student":
            if register_user(user_id, fio, additional, "student", True):  # регистрируем с permit = True
                success_text = f"""
Регистрация завершена!

Отсканируйте QR для работы с книгами!
                """
            else:
                bot.send_message(call.message.chat.id, "Ошибка регистрации!")
                return
        else:  # teacher
            if register_user(user_id, fio, f"Учитель: {additional}", "teacher", False):  # регистрируем с permit = False
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
                    f"Telegram ID: [{user_id}](tg://user?id={user_id})\n"
                    f"Username: @{call.from_user.username or 'нет'}",
                    parse_mode='Markdown',  # для создания ссылки в поле Telegram ID
                    reply_markup=create_confirm_keyboard(user_id)  # прикрепляем клавиатуру с кнопками подтверждения
                )
            else:
                bot.send_message(call.message.chat.id, "Ошибка регистрации!")
                return

        if user_id in user_data_temp:  # очищаем временные данные
            del user_data_temp[user_id]

        bot.edit_message_text(  # редактируем сообщение с выбором роли
            success_text,
            call.message.chat.id,
            call.message.message_id
        )
        return

    # ===== ВЗЯТИЕ КНИГИ =====
    if callback_data.startswith("take_"):
        qr_code = callback_data.replace("take_", "")  # извлекаем QR-код

        # Определяем, от чьего имени брать книгу (учитель или ученик)
        acting_user_id = teacher_acting_for.get(user_id,
                                                user_id)  # если учитель в режиме помощи, берем ID ученика, иначе ID самого пользователя

        if take_book(acting_user_id, qr_code):  # пытаемся взять книгу
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

        if user_id in user_pending_action:  # очищаем временное хранилище QR-кода
            del user_pending_action[user_id]
        return

    # ===== ВОЗВРАТ КНИГИ =====
    if callback_data.startswith("return_"):
        qr_code = callback_data.replace("return_", "")  # извлекаем QR-код

        acting_user_id = teacher_acting_for.get(user_id, user_id)  # определяем, от чьего имени возвращать

        if return_book(acting_user_id, qr_code):  # пытаемся вернуть книгу
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

        if user_id in user_pending_action:  # очищаем временное хранилище QR-кода
            del user_pending_action[user_id]
        return

    # ===== КНОПКА "КОМУ ПРИНАДЛЕЖИТ?" =====
    if callback_data.startswith("who_"):
        qr_code = callback_data.replace("who_", "")  # извлекаем QR-код

        # Получаем информацию о владельце книги
        owner = get_book_owner_info(qr_code)  # вызываем функцию из database.py
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

        else:  # если книга у кого-то
            fio, class_name, owner_tg_id, issue_date = owner  # распаковываем данные

            # Для УЧИТЕЛЯ — полная информация
            if user_status == 'teacher':
                if owner_tg_id == user_id:
                    # Это ЕГО книга
                    info_text = f"""
Это ваш учебник!

Взят: {issue_date}
Не забудьте вернуть вовремя!
                                    """
                else:  # если книга другого ученика
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

        bot.answer_callback_query(call.id)  # отвечаем на callback
        return

    # ===== МАССОВЫЙ ВОЗВРАТ КНИГ =====
    if callback_data == "return_all":
        # Проверяем, что это учитель
        if get_user_status(user_id) != 'teacher':
            bot.answer_callback_query(call.id, "Только учителя могут сдавать книги!")
            return

        # Определяем, за кого действуем
        acting_user_id = teacher_acting_for.get(user_id, user_id)  # проверка за кого действвует учитель (потом допишу)

        # Получаем информацию об ученике (если действуем за кого-то)
        target_name = "себя"
        if acting_user_id != user_id:
            conn = sqlite3.connect('library.db')
            cursor = conn.cursor()
            cursor.execute('SELECT FIO FROM users WHERE tg_id = ?', (acting_user_id,))
            result = cursor.fetchone()
            conn.close()
            if result:
                target_name = f"ученика {result[0]}"

        # Создаём клавиатуру подтверждения
        keyboard = types.InlineKeyboardMarkup(row_width=2)
        keyboard.add(
            types.InlineKeyboardButton("Да, сдать всё", callback_data=f"confirm_return_all_{acting_user_id}"),
            types.InlineKeyboardButton("Отмена", callback_data="cancel_return_all")
        )

        bot.edit_message_text(
            f"Подтверждение\n\n"
            f"Вы собираетесь сдать ВСЕ книги за {target_name}.\n"
            f"Продолжить?",
            call.message.chat.id,
            call.message.message_id,
            reply_markup=keyboard
        )
        return

    if callback_data.startswith("confirm_return_all_"):
        # Извлекаем ID пользователя, за которого сдаём
        target_id = int(callback_data.replace("confirm_return_all_", ""))

        success, count = return_all_books(target_id)

        if success:
            # Получаем имя для красивого ответа
            target_name = "себя"
            if target_id != user_id:
                conn = sqlite3.connect('library.db')
                cursor = conn.cursor()
                cursor.execute('SELECT FIO FROM users WHERE tg_id = ?', (target_id,))
                result = cursor.fetchone()
                conn.close()
                if result:
                    target_name = f"ученика {result[0]}"

            bot.edit_message_text(
                f"Успешно!\n\n"
                f"Сдано книг: {count}\n"
                f"За {target_name}",
                call.message.chat.id,
                call.message.message_id
            )
        else:
            bot.edit_message_text(
                "Ошибка\n\n"
                "Не удалось сдать книги. Возможно, их уже нет на руках.",
                call.message.chat.id,
                call.message.message_id,
            )
        return

    if callback_data == "cancel_return_all":
        bot.edit_message_text(
            "Cдача отменена.",
            call.message.chat.id,
            call.message.message_id
        )
        return


# ========== ОБРАБОТЧИКИ ФАЙЛОВ ==========
@bot.message_handler(content_types=['document'])
def handle_document(message):
    """Обрабатывает загруженный Excel-файл с книгами"""
    if message.from_user.id != ADMIN_ID:  # проверяем, что файл отправил администратор
        return

    print(f"Получен файл от пользователя {message.from_user.id}")  # пишем в консоль о получении файла
    print(f"ADMIN_ID = {ADMIN_ID}")  # пишем в консоль какой Telegram ID админа (для самопроверки)

    if message.from_user.id != ADMIN_ID:  # пишем в консоль о результате
        print("Не админ, игнорирую")
        return

    print("Админ, обрабатываю файл")  # пишем в консоль о результате

    # сразу отвечаем, чтобы пользователь понял, что бот работает
    msg = bot.reply_to(message, "Получаю файл...")

    try:
        # получаем информацию о файле по его file_id
        file_info = bot.get_file(message.document.file_id)
        # скачиваем файл
        downloaded_file = bot.download_file(file_info.file_path)
        filename = "temporary_books.xlsx"   # временное имя файла
        with open(filename, 'wb') as f:  # открываем файл для записи в бинарном режиме
            f.write(downloaded_file)     # записываем скачанные данные (на диск, т.к. скрипт excel_importer.py не умеет читать файлы из памяти — ему нужен физический файл на диске)

        # сообщаем, что файл получен и началась обработка
        bot.edit_message_text("Файл получен. Начинаю обработку. Это может занять несколько минут.",
                              msg.chat.id, msg.message_id)

        # вызываем функцию из excel_importer.py, передаём ей имя файла
        result = excel_importer.import_all_books_from_excel(filename)

        # проверяем, не вернулась ли ошибка (если есть ключ 'error' — значит что-то пошло не так)
        if 'error' in result:
            bot.send_message(msg.chat.id, f"Ошибка импорта: {result['error']}")
        else:
            bot.send_message(
                msg.chat.id,
                f"Загрузка завершена!\n\n"
                f"Книг добавлено: {result['added']}\n"
                f"Всего экземпляров: {result['copies']}\n"
                f"QR-кодов создано: {result['qrcodes']}\n"
                f"Время: {result['time']} сек\n\n"
                f"QR-коды сохранены в папке qrcodes/\n"
                f"Введите команду /get_pdf для их получения."
            )
            # удаляем старое сообщение "Создаю PDF..." если оно ещё существует
            try:
                bot.delete_message(msg.chat.id, msg.message_id)
            except:
                pass

    except Exception as e:
        # перехватываем любую ошибку и показываем её пользователю
        # str(e)[:200] — берём только первые 200 символов, чтобы не заспамить
        bot.edit_message_text(f"Ошибка: {str(e)[:200]}",
                              msg.chat.id, msg.message_id)


# ========== ОБРАБОТЧИК QR-КОДОВ ==========

@bot.message_handler(func=lambda message: True)  # ловит ВСЕ сообщения (самый последний обработчик)
def handle_all_messages(message):
    """Обрабатывает все остальные сообщения (QR-коды, случайный текст)"""
    user_id = message.from_user.id

    # Если пользователь не зарегистрирован
    if not is_user_registered(user_id):
        if user_id not in user_waiting_for_data and user_id not in user_data_temp:  # и не в процессе регистрации
            bot.send_message(message.chat.id, "Для начала работы используйте команду /start")
        return

    # Если сообщение похоже на QR-код (не команда, не пустое)
    text = message.text.strip()  # получаем текст сообщения
    if text and not text.startswith('/'):  # если не пусто и не начинается с /
        user_pending_action[user_id] = text  # сохраняем в словарь QR-код для этого пользователя

        # Получаем информацию о книге
        book_info = get_book_info(text)  # вызываем функцию из database.py

        if not book_info:
            bot.reply_to(message, f"Книга не найдена.")
            if user_id in user_pending_action:  # очищаем временное хранилище
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

        # Получаем статус пользователя
        user_status = get_user_status(user_id)  # 'student' или 'teacher'
        bot.reply_to(  # отвечаем
            message,
            book_text,
            reply_markup=create_book_action_keyboard(text, user_status)  # прикрепляем клавиатуру с кнопками
        )


# ========== ЗАПУСК БОТА ==========

bot.infinity_polling(timeout=60, long_polling_timeout=60)  # запускаем бота в режиме бесконечного опроса
# timeout=60 - таймаут на запрос к Telegram
# long_polling_timeout=60 - максимальное время ожидания ответа



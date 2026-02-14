import sqlite3  # библиотека для работы с базой данных SQLite


def create_database():  # создаем базу данных и таблицы
    conn = sqlite3.connect('library.db')  # создаем или подключаемся к уже созданному файлу базы данных "library.db"
    cursor = conn.cursor()  # создаем курсор (объект для выполнения sql команд)

    # таблица "users" (id пользователя, Telegram ID, ФИО, класс, статус(учитель/ученик), разрешение на использование)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         tg_id INTEGER UNIQUE NOT NULL,
         FIO TEXT NOT NULL,
         class TEXT NOT NULL,
         status TEXT NOT NULL,
         permit BOOLEAN NOT NULL
     )
     ''')

    # таблица "books" (id записи, id книги, предмет + класс книги, автор, год издания)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS books (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         qr_code TEXT UNIQUE NOT NULL,
         subject TEXT NOT NULL,
         author TEXT NOT NULL,
         year TEXT NOT NULL
     )
     ''')

    # таблица "records" (id записи, id пользователя(из users), id книги(из books), дата выдачи, дата сдачи)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        issue_date TEXT DEFAULT (date('now')),
        return_date TEXT
    )
    ''')

    conn.commit()  # сохраняем изменения
    conn.close()  # закрываем базу данных
    print("База данных создана")  # сообщаем о работоспособности системы(пишется при запуске botcode.py)


# функция проверки того зарегистрирован ли пользователь с данным Telegram ID
def is_user_registered(tg_id):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE tg_id = ?', (
    tg_id,))  # ищем пользователя с таким Telegram ID по всей таблице (? - место для подстановки значения; нужно во избежание уязвимостей)
    user = cursor.fetchone()  # получаем результат (если есть пользователь - вернется запись, если нет - None)
    conn.close()  # закрываем базу данных
    return user is not None  # возвращаем True если пользователь найден, False если нет


# функция регистрации нового пользователя
def register_user(tg_id, fio, user_class, status, permit=False):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    try:  # пробуем зарегистрировать пользователя
        # добавляем нового пользователя в таблицу users
        cursor.execute('INSERT INTO users (tg_id, FIO, class, status, permit) VALUES (?, ?, ?, ?, ?)',
                       # вставляем данные (tg_id, ФИО, класс, статус, разрешение подставляются вместо ?, ?, ?, ?, ?)
                       (tg_id, fio, user_class, status, permit))
        conn.commit()  # сохраняем изменения
        return True  # возвращаем True, если регистрация прошла успешно

    except:  # если в try выдало какую-либо ошибку, то выполняем это
        return False  # возвращаем False, если произошла ошибка (например, пользователь уже существует)

    finally:  # выполняем вне зависимости от получения ошибки(т.е. в любом случае)
        conn.close()  # закрываем базу данных


# функция удаления пользователя (например, при отклонении заявки администратором)
def delete_user(tg_id):  # Удаляет пользователя из базы данных; возвращает True если удаление успешно, False если пользователь не найден
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    try:  # выполняем SQL-запрос на удаление записи из таблицы users
        cursor.execute('DELETE FROM users WHERE tg_id = ?', (tg_id,))  # удаляем пользователя с данным Telegram ID (tg_id вставляется вместо ?)
        conn.commit()  # сохраняем изменения
        deleted = cursor.rowcount > 0  # количество строк, которые были затронуты запросом
        # если пользователь найден и удален: rowcount = 1, deleted = True
        # если пользователь не найден: rowcount = 0, deleted = False
        return deleted  # возвращаем True или False

    except Exception as e:  # если в try выдало какую-либо ошибку, то выполняем это
        print(f"Ошибка при удалении пользователя {tg_id}: {e}")
        return False  # возвращаем False (т.е. пользователь не удален из базы данных)

    finally:  # выполняем вне зависимости от получения ошибки(т.е. в любом случае)
        conn.close()  # закрываем базу данных


# функция проверки разрешения пользователя на пользование ботом
def check_user_permit(tg_id):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT permit FROM users WHERE tg_id = ?', (tg_id,))  # ищем какой permit у пользователя по его Telegram ID (tg_id вставляется вместо ?)
    result = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (True,) или (False,))
    conn.close()  # закрываем базу данных
    return result[0] if result else False
    # если result не None - возвращаем result[0] (permit)
    # если result is None (пользователь не найден) - возвращаем False


# функция получения статуса пользователя
def get_user_status(tg_id):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT status FROM users WHERE tg_id = ?', (tg_id,))  # ищем какой status у пользователя по его Telegram ID (tg_id вставляется вместо ?)
    result = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (True,) или (False,) или None)
    conn.close()  # закрываем базу данных
    return result[0] if result else None
    # если result не None - возвращаем result[0] (permit)
    # если result is None (пользователь не найден) - возвращаем False


# функция взятия книги
def take_book(tg_id, qr_code):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE tg_id = ?',
                   (tg_id,))  # находим id пользователя по его Telegram ID (tg_id вставляется вместо ?)
    user = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (id, tg_id, FIO, class) или None)
    cursor.execute('SELECT id FROM books WHERE qr_code = ?',
                   (qr_code,))  # находим id книги по ее QR-коду (qr_code вставляется вместо ?)
    book = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (qr_code,) или None)

    if not user or not book:  # если пользователь или книга не найдены - возвращаем False
        conn.close()  # закрываем базу данных
        return False

    # проверяем, не взята ли эта книга уже кем-то другим (просматриваем все записи в таблице records с данным id книги, у которых отсутствует дата возврата(return_date))
    cursor.execute('''
        SELECT * FROM records 
        WHERE book_id = ? AND return_date IS NULL
    ''', (book[0],))  # book[0] - id книги
    if cursor.fetchone():  # fetchone() получает первую найденную запись или None, если ничего не найдено
        conn.close()  # закрываем базу данных
        return False  # если книга уже кем-то взята - возвращаем False

    # cоздаем новую запись в таблице records о выдаче
    cursor.execute('INSERT INTO records (user_id, book_id) VALUES (?, ?)',
                   (user[0], book[0]))  # user[0] - id пользователя, book[0] - id книги

    # проверяем, сколько строк обновилось
    if cursor.rowcount == 0:
        conn.close()
        return False  # если ничего не обновилось - книга не у пользователя!

    conn.commit()  # сохраняем изменения
    conn.close()  # закрываем базу данных
    return True  # возвращаем True - книга успешно взята


# функция возврата книги
def return_book(tg_id, qr_code):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE tg_id = ?', (tg_id,))  # находим id пользователя
    user = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (id, tg_id, FIO, class) или None)
    cursor.execute('SELECT id FROM books WHERE qr_code = ?', (qr_code,))  # находим id книги
    book = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (qr_code,) или None)

    if not user or not book:  # если пользователь или книга не найдены - возвращаем False
        conn.close()  # закрываем базу данных
        return False

    # находим активную запись о выдаче этой книги этому пользователю и устанавливаем дату возврата на сегодня
    cursor.execute('''
        UPDATE records
        SET return_date = date('now')
        WHERE user_id = ? AND book_id = ? AND return_date IS NULL
    ''', (user[0], book[0]))  # user[0] - id пользователя, book[0] - id книги

    # проверяем, сколько строк обновилось
    if cursor.rowcount == 0:
        conn.close()
        return False  # если ничего не обновилось - книга не у пользователя!

    conn.commit()  # сохраняем изменения
    conn.close()  # закрываем соединение
    return True  # возвращаем True - книга успешно возвращена

# функция возврата информации о владельце книги
def get_book_owner_info(qr_code):  # qr_code - код книги, которую нужно проверить
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    # выполняем SQL-запрос к базе данных, соединяя три таблицы(users, books, records)
    # ищем учебник с конкретным qr-кодом и те записи о нем, в которых return_date IS NULL
    cursor.execute('''
        SELECT users.FIO, users.class, users.tg_id, records.issue_date
        FROM records
        JOIN users ON records.user_id = users.id
        JOIN books ON records.book_id = books.id
        WHERE books.qr_code = ? AND records.return_date IS NULL
    ''', (qr_code,))

    owner = cursor.fetchone()  # fetchone() получает первую найденную запись (FIO, class, tg_id, issue_date или None)
    conn.close()  # закрываем соединение в базой данных
    return owner  # возвращаем результат: кортеж с данными владельца или None


# функция возврата информации о книге по ее QR-коду
def get_book_info(qr_code):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()

    # ищем книгу по QR-коду
    cursor.execute('SELECT * FROM books WHERE qr_code = ?', (qr_code,))
    book = cursor.fetchone()  # берем все поля записи из таблицы books где qr_code = qr_code (возвращается в виде кортежа (id, qr_code, subject, author, year) или None)

    conn.close()  # закрываем базу данных

    if book:  # если книга найдена, возвращаем информацию в виде словаря
        return {
            'id': book[0],  # id книги
            'qr_code': book[1],  # qr-код
            'subject': book[2],  # предмет и название
            'author': book[3],  # автор
            'year': book[4]  # год издания
        }
    return None  # если книга не найдена, возвращаем None


# функция проверки доступна ли книга для выдачи (т.е не взял ли ее кто-то)
def is_book_available(qr_code):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()

    # находим id книги по QR-коду
    cursor.execute('SELECT id FROM books WHERE qr_code = ?', (qr_code,))
    book = cursor.fetchone()  # берем поле записи из таблицы books qr_code

    if not book:  # если книга не найдена - возвращаем False
        conn.close()  # закрываем базу данных
        return False

    # проверяем, есть ли активная запись о выдаче этой книги
    cursor.execute('''
        SELECT * FROM records 
        WHERE book_id = ? AND return_date IS NULL  # ищем записи в таблице выдачи книг, где id книги равен book[0] и дата возврата не установлена 
    ''', (book[0],))

    # если запись найдена - книга занята, если нет - доступна
    available = cursor.fetchone() is None  # если возвращается кортеж - False, если None - True

    conn.close()  # закрываем базу данных
    return available  # возвращаем True если книга свободна, False если занята


# функция проверяет, есть ли у пользователя указанная книга на руках
def user_has_book(tg_id, qr_code):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE tg_id = ?', (tg_id,))  # находим id пользователя
    user = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (id, tg_id, FIO, class) или None)
    cursor.execute('SELECT id FROM books WHERE qr_code = ?', (qr_code,))  # находим id книги
    book = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (qr_code,) или None)

    if not user or not book:  # если пользователь или книга не найдены - возвращаем False
        conn.close()  # закрываем базу данных
        return False

    # ищем активную запись о выдаче этой книги этому пользователю
    cursor.execute('''
        SELECT * FROM records 
        WHERE user_id = ? AND book_id = ? AND return_date IS NULL  # ищем записи в таблице выдачи книг, где id пользователя и id книги равны book[0] и user[0] соответствеено и дата возврата не установлена 
    ''', (user[0], book[0]))

    # проверяем, найдена ли такая запись
    has_book = cursor.fetchone() is not None  # если возвращается кортеж - True, если None - False

    conn.close()  # закрываем базу данных
    return has_book  # возвращаем True если книга у пользователя, False если нет


# функция возвращает все книги, которые брал пользователь
def get_user_books_history(tg_id):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    # ищем все записи о книгах этого пользователя
    # соединяем три таблицы: records, books и users
    cursor.execute('''                                       
            SELECT books.subject, books.author, books.year, records.issue_date, records.return_date
            FROM records
            JOIN books ON records.book_id = books.id
            JOIN users ON records.user_id = users.id
            WHERE users.tg_id = ?
            ORDER BY records.issue_date DESC
        ''', (tg_id,))


    books = cursor.fetchall()  # получаем все найденные записи
    conn.close()  # закрываем базу данных
    return books  # возвращаем список книг

# функция возвращает список всех книг, которые у пользователя на руках
def get_user_current_books(tg_id):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    # ищем записи о взятии книг этого пользователя
    # соединяем три таблицы: records, books и users
    cursor.execute('''                                       
        SELECT books.subject, books.author, books.year, records.issue_date
        FROM records
        JOIN books ON records.book_id = books.id
        JOIN users ON records.user_id = users.id
        WHERE users.tg_id = ? AND records.return_date IS NULL
        ORDER BY records.issue_date DESC
    ''', (tg_id,))
    books = cursor.fetchall()  # получаем все найденные записи
    conn.close()  # закрываем базу данных
    return books  # возвращаем список книг


# функция добавляет тестовые книги в базу и генерирует QR-коды
def add_books_to_database():
    # импорт делаем внутри функции, чтобы избежать циклических импортов и загружать модуль только при необходимости
    from qr_generator import generate_qr_for_book  # импортируем функцию генерации QR-кодов из отдельного файла

    # список учебников для добавления; каждая книга представлена в виде кортежа: (QR-код, название предмета, автор, год издания)
    books = [
        ("MATH-001", "Алгебра 10 класс", "Мерзляк", "2024"),  # Книга 1: Алгебра 10 класс
        ("HIST-002", "История 10 класс", "Мединский", "2023"),  # Книга 2: История 10 класс
        ("ENGL-003", "Английский язык 10 класс", "Афанасьева", "2018"),  # Книга 3: Английский язык 10 класс
        ("HIST-004", "История 8 класс", "Юдовская", "2019"),  # Книга 4: История 8 класс
        ("MATH-005", "Геометрия 10 класс", "Мерзляк", "2024"),  # Книга 5: Геометрия 10 класс
    ]
    # подключаемся к базе данных library.db
    conn = sqlite3.connect('library.db')  # создаем или подключаемся к существующей базе данных
    cursor = conn.cursor()  # создаем курсор для выполнения SQL-команд

    # проходим по всем книгам в списке
    for qr_code, subject, author, year in books:
        try:  # пытаемся выполнить операцию (на случай ошибок)
            # выполняем SQL-запрос на вставку книги в таблицу books
            # INSERT OR IGNORE - добавляет запись, только если книги с таким QR-кодом еще нет в базе; если книга уже есть - операция игнорируется
            cursor.execute('INSERT OR IGNORE INTO books (qr_code, subject, author, year) VALUES (?, ?, ?, ?)',
                           (qr_code, subject, author, year))
            # generate_qr_for_book() создаст файл qr_code.png в папке qrcodes/
            generate_qr_for_book(qr_code)  # генерируем QR-код для книги с помощью импортированной функции
            print(f"Добавлена книга: {subject}")  # Выводим сообщение об успешном добавлении

        except Exception as e:  # если произошла ошибка при добавлении книги
            print(f"Ошибка с {qr_code}: {e}")  # выводим сообщение об ошибке с информацией о QR-коде и тексте ошибки

    conn.commit()  # сохраняем все изменения в базе данных
    conn.close()  # закрываем базу данных
    print("\nКниги добавлены в базу данных!")  # выводим итоговое сообщение


# запуск программы (python database.py)
if __name__ == "__main__":  # выполнится ТОЛЬКО если запустить database.py напрямую
    create_database()  # вызываем функцию create_database(), которая создаст таблицы users, books, records
    add_books_to_database()  # добавляем тестовые книги в базу и генерируем QR-коды
    print("\nВСЁ ГОТОВО! Теперь можно запускать бота.")  # выводим сообщение о готовности системы

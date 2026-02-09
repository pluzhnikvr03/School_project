import sqlite3  # библиотека для работы с базой данных SQLite


def create_database(): # создаем базу данных и таблицы
    conn = sqlite3.connect('library.db') # создаем или подключаемся к уже созданному файлу базы данных "library.db"
    cursor = conn.cursor() # создаем курсор (объект для выполнения sql команд)

    # таблица "users" (id пользователя, Telegram ID, ФИО, класс)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
         id INTEGER PRIMARY KEY AUTOINCREMENT,
         tg_id INTEGER UNIQUE NOT NULL,
         FIO TEXT NOT NULL,
         class TEXT NOT NULL
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

    # таблица "records"
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,   # id записи, увеличивается автоматически
        user_id INTEGER NOT NULL,               # id пользователя из таблицы users (users.id)
        book_id INTEGER NOT NULL,               # id книги из таблицы books (books.id)
        issue_date TEXT DEFAULT (date('now')),  # дата взятия книги (дата ставится автоматически)
        return_date TEXT                        # дата возврата книги (NULL, если еще не сдана)
    )
    ''')
    
    conn.commit()  # сохраняем изменения
    conn.close()  # закрываем базу данных
    print("База данных создана")


# функция проверки того зарегистрирован ли пользователь с данным Telegram ID
def is_user_registered(tg_id):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE tg_id = ?', (tg_id,))  # ищем пользователя с таким Telegram ID по всей таблице (? - место для подстановки значения; нужно во избежании уязвимостей)
    user = cursor.fetchone()  # получаем результат (если есть пользователь - вернется запись, если нет - None)
    conn.close()  # закрываем базу данных
    return user is not None # возвращаем True если пользователь найден, False если нет


# функция регистрации нового пользователя
def register_user(tg_id, fio, user_class):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    try:  # пробуем зарегистрировать пользователя
        # добавляем нового пользователя в таблицу users
        cursor.execute('INSERT INTO users (tg_id, FIO, class) VALUES (?, ?, ?)',  # вставляем данные (tg_id, ФИО, класс подставляются вместо ?, ?, ?)
                      (tg_id, fio, user_class))
        conn.commit()  # сохраняем изменения
        return True  # возвращаем True, если регистрация прошла успешно
        
    except:  # если в try выдало какую-либо ошибку, то выполняем это
        return False  # возвращаем False, если произошла ошибка (например, пользователь уже существует)

    finally:  # выполняем вне зависимости от получения ошибки(т.е. в любом случае)
        conn.close()  # закрываем базу данных


# функция взятия книги
def take_book(tg_id, qr_code):
    conn = sqlite3.connect('library.db')  # подключаемся к базе данных
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE tg_id = ?', (tg_id,))  #  находим id пользователя по его Telegram ID (tg_id вставляется вместо ?)
    user = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (id, tg_id, FIO, class) или None)
    cursor.execute('SELECT id FROM books WHERE qr_code = ?', (qr_code,))  # находим id книги по ее QR-коду (qr_code вставляется вместо ?)
    book = cursor.fetchone()  # fetchone() получает первую найденную запись или None, если ничего не найдено (возвращается в виде кортежа (qr_code,) или None)
    
    if not user or not book:  # если пользователь или книга не найдены - возвращаем False
        conn.close()  # закрываем базу данных
        return False
    
    # проверяем, не взята ли эта книга уже кем-то другим
    cursor.execute('''
        SELECT * FROM records 
        WHERE book_id = ? AND return_date IS NULL  # ищем запись, где эта книга выдана (return_date IS NULL - дата возврата не установлена (т.е. книга на руках))
    ''', (book[0],))                               # book[0] - id книги
    if cursor.fetchone():  # если книга уже кем-то взята - возвращаем False
        conn.close()  # закрываем базу данных
        return False
        
    # создаем новую запись о выдаче книги
    cursor.execute('INSERT INTO records (user_id, book_id) VALUES (?, ?)',  # cоздаём новую запись в таблице records о выдаче
                  (user[0], book[0]))                                       # user[0] - id пользователя, book[0] - id книги
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
        UPDATE records                                             # обновляем таблицу records
        SET return_date = date('now')                              # ставим сегодняшнюю дату как дату возврата
        WHERE user_id = ? AND book_id = ? AND return_date IS NULL  # ищем активную запись
    ''', (user[0], book[0]))                                       # user[0] - id пользователя, book[0] - id книги
    
    conn.commit()  # сохраняем изменения
    conn.close()  # закрываем соединение
    return True  # возвращаем True - книга успешно возвращена


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
            'id': book[0],           # id книги
            'qr_code': book[1],      # qr-код
            'subject': book[2],      # предмет и название
            'author': book[3],       # автор
            'year': book[4]          # год издания
        }
    return None # если книга не найдена, возвращаем None


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

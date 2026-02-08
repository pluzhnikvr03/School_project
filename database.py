# библиотека для работы с базой данных SQLite
import sqlite3


def create_database(): # создаем базу данных и таблицы
    conn = sqlite3.connect('library.db') # создаем или подключаемся к уже созданному файлу базы данных "library.db"
    cursor = conn.cursor() # создаем курсор (объект для выполнения sql команд)

    # таблица "users"
    cursor.execute('''
     CREATE TABLE IF NOT EXISTS users (
         id INTEGER PRIMARY KEY AUTOINCREMENT,  # id пользователя, увеличивается автоматически
         tg_id INTEGER UNIQUE NOT NULL,         # Telegram ID пользователя (уникальный, обязательный)
         FIO TEXT NOT NULL,                     # ФИО пользователя (обязательное поле)
         class TEXT NOT NULL                    # класс пользователя (обязательное поле)
     )
     ''')

    # таблица "books"
    cursor.execute('''
     CREATE TABLE IF NOT EXISTS books (
         id INTEGER PRIMARY KEY AUTOINCREMENT,  # id записи, увеличивается автоматически
         qr_code TEXT UNIQUE NOT NULL,          # id книги (берется из QR-кода)
         subject TEXT NOT NULL,                 # предмет учебника
         author TEXT NOT NULL,                  # автор учебника
         year TEXT NOT NULL                     # год издания
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
        conn.close()  # закрываем соединение

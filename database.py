# Импортируем библиотеку для работы с базой данных SQLite
import sqlite3


# Создание базы данных и таблиц
def create_database():
    # Подключаемся к файлу базы данных 'library.db'
    # Если файла не существует, он будет создан автоматически
    conn = sqlite3.connect('library.db')

    # Создаем курсор - объект для выполнения sql команд
    cursor = conn.cursor()

    # Создаем таблицу "users" для хранения информации о пользователях
    cursor.execute('''
     CREATE TABLE IF NOT EXISTS users (
         id INTEGER PRIMARY KEY AUTOINCREMENT,  # id пользователя, увеличивается автоматически
         tg_id INTEGER UNIQUE NOT NULL,         # Telegram ID пользователя (уникальный, обязательный)
         name TEXT NOT NULL,                    # ФИО пользователя (обязательное поле)
         class TEXT NOT NULL                    # Класс пользователя (обязательное поле)
     )
     ''')

    # Создаем таблицу "user_books" для хранения записей о книгах пользователей
    cursor.execute('''
     CREATE TABLE IF NOT EXISTS user_books (
         id INTEGER PRIMARY KEY AUTOINCREMENT,      # id записи
         user_id INTEGER NOT NULL,                  # id пользователя из таблицы users
         book_id TEXT NOT NULL,                     # ID книги (берется из информации о QR-коде)
         status TEXT NOT NULL,                      # Статус: "taken" (взята) или "returned" (возвращена)
         date TEXT DEFAULT CURRENT_TIMESTAMP        # Дата (автоматически ставится текущая дата)
     )
     ''')

    # Сохраняем изменения в базе данных
    conn.commit()
    # Закрываем соединение с базой данных
    conn.close()
    print("✅ База данных создана")


# Функции работы с базой данных
def is_user_registered(tg_id):
    # Проверяем, зарегистрирован ли пользователь с данным Telegram id
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    # SQL запрос для поиска пользователя по tg_id
    # ? - placeholder для безопасной подстановки значения
    cursor.execute('SELECT * FROM users WHERE tg_id = ?', (tg_id,))

    # Получаем первую найденную запись (или None если не найдено)
    user = cursor.fetchone()

    # Закрываем соединение
    conn.close()

    # Возвращаем True если пользователь найден, False если нет
    return user is not None


def register_user(tg_id, name, user_class):
    # Регистрирует нового пользователя в системе
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    try:
        # SQL-запрос для добавления нового пользователя
        cursor.execute('INSERT INTO users (tg_id, name, class) VALUES (?, ?, ?)',
                       (tg_id, name, user_class))

        # Сохраняем изменения
        conn.commit()

        # Возвращаем True если регистрация успешна
        return True

    except sqlite3.IntegrityError:
        # Конкретная ошибка: возникает когда пытаемся добавить пользователя с существующим tg_id
        # (нарушение UNIQUE ограничения)
        return False

    except Exception as e:
        # Другие возможные ошибки (например, проблемы с подключением к БД)
        print(f"Ошибка при регистрации пользователя: {e}")
        return False

    finally:
        # Этот блок выполняется ВСЕГДА, даже если была ошибка
        conn.close()


def get_user_books(tg_id):
    # Получает список всех книг пользователя
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    # Сначала находим ID пользователя в таблице users
    cursor.execute('SELECT id FROM users WHERE tg_id = ?', (tg_id,))

    # Получаем результат запроса
    user = cursor.fetchone()

    # Если пользователь найден
    if user:
        # Получаем все книги этого пользователя из таблицы user_books
        # user[0] - это id пользователя (первый элемент кортежа)
        cursor.execute('SELECT book_id, status, date FROM user_books WHERE user_id = ?',
                       (user[0],))

        # Получаем ВСЕ записи о книгах пользователя
        books = cursor.fetchall()
    else:
        # Если пользователь не найден, возвращаем пустой список
        books = []

    conn.close()

    # Возвращаем список книг
    # Каждая книга - кортеж: (book_id, status, date)
    return books


def take_book(tg_id, book_id):
    # Пользователь берет книгу (создает запись о взятии)
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    # Находим ID пользователя
    cursor.execute('SELECT id FROM users WHERE tg_id = ?', (tg_id,))
    user = cursor.fetchone()

    # Если пользователь найден
    if user:
        try:
            # Создаем запись в таблице user_books
            # status = 'taken' - книга взята
            cursor.execute('INSERT INTO user_books (user_id, book_id, status) VALUES (?, ?, ?)',
                           (user[0], book_id, 'taken'))

            # Сохраняем изменения
            conn.commit()

            # Успех
            result = True
        except Exception as e:
            # Обрабатываем возможные ошибки (например, проблемы с БД)
            print(f"Ошибка при взятии книги: {e}")
            result = False
    else:
        # Пользователь не найден - ошибка
        result = False

    conn.close()

    # Возвращаем результат операции
    return result


def return_book(tg_id, book_id):
    # Пользователь возвращает книгу
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    # Находим ID пользователя
    cursor.execute('SELECT id FROM users WHERE tg_id = ?', (tg_id,))
    user = cursor.fetchone()

    # Если пользователь найден
    if user:
        try:
            # Обновляем запись о книге
            # статус с 'taken' меняется на 'returned' только для той книги, которая сейчас "взята"
            cursor.execute('''
                UPDATE user_books 
                SET status = 'returned' 
                WHERE user_id = ? AND book_id = ? AND status = 'taken'
            ''', (user[0], book_id))

            # Сохраняем изменения
            conn.commit()

            # Успех
            result = True
        except Exception as e:
            # Обрабатываем возможные ошибки
            print(f"Ошибка при возврате книги: {e}")
            result = False
    else:
        # Пользователь не найден - ошибка
        result = False

    conn.close()

    # Возвращаем результат операции
    return result


def user_has_book(tg_id, book_id):
    # Проверяет, есть ли у пользователя указанная книга "на руках"
    conn = sqlite3.connect('library.db')
    cursor = conn.cursor()

    # Находим ID пользователя
    cursor.execute('SELECT id FROM users WHERE tg_id = ?', (tg_id,))
    user = cursor.fetchone()

    # Если пользователь найден
    if user:
        # Ищем запись где:
        # - user_id = ID пользователя
        # - book_id = ID книги
        # - status = 'taken' (книга еще не возвращена)
        cursor.execute('''
            SELECT * FROM user_books 
            WHERE user_id = ? AND book_id = ? AND status = 'taken'
        ''', (user[0], book_id))

        # Проверяем, найдена ли хотя бы одна запись
        has_book = cursor.fetchone() is not None
    else:
        # Пользователь не найден - у него точно нет книг
        has_book = False

    conn.close()

    # Возвращаем True если книга у пользователя, False если нет
    return has_book
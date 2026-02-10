import qrcode  # библиотека для создания QR-кодов
import os  # библиотека для работы с файловой системой (создание папок, проверка существования)


# основная функция для создания QR-кода
def generate_qr_code(qr_data, folder="qrcodes"):  # qr_data - данные, которые будут закодированы в QR-код; folder - название папки, куда сохранять QR-код (qrcodes)
    if not os.path.exists(folder):  # создаем папку, если её нет
        os.makedirs(folder)  # makedirs создает папку и все промежуточные папки, если их нет
    
    qr = qrcode.make(str(qr_data))  # создаем QR-код из переданных данных
    filename = f"{qr_data}.png"  # формируем имя файла: используем данные QR-кода + расширение .png
    filepath = os.path.join(folder, filename)  # формируем полный путь к файлу: папка + имя файла; os.path.join() соединяет пути для любой операционной системы
    qr.save(filepath)  # сохраняем QR-код как изображение PNG
    
    return filepath  # возвращаем путь к сохраненному файлу


# функция, которая извлекает QR-код из разного формата данных о книге и генерирует QR-код (удобно, если данные о книгах в разных форматах)
def generate_qr_for_book(book_info, folder="qrcodes"):  # book_info - информация о книге в любом формате; folder - папка для сохранения QR-кода
    if isinstance(book_info, dict):  # если передан словарь
        qr_data = book_info.get('qr_code', book_info.get('id', 'unknown'))
    elif isinstance(book_info, (list, tuple)):  # если передан список или кортеж
        qr_data = book_info[0]  # берем первый элемент как QR-код
    else:  # если передана просто строка или число
        qr_data = str(book_info)  # преобразуем в строку
    
    return generate_qr_code(qr_data, folder)  # вызываем основную функцию генерации QR-кода с извлеченными данными


# функция генерирует QR-коды для списка книг
def generate_all_qr_codes(books_list, folder="qrcodes"):  # books_list - список книг в любом формате; folder - папка для сохранения всех QR-кодов
    created_files = []  # создаем пустой список для хранения путей к созданным файлам
    for book in books_list:  # проходим по всем книгам в списке
        try:  # пытаемся сгенерировать QR-код для текущей книги
            filename = generate_qr_for_book(book, folder)
            created_files.append(filename)  # если успешно, добавляем путь к файлу в список
            print(f"Создан QR-код: {os.path.basename(filename)}")  # выводим сообщение об успехе (os.path.basename() извлекает только имя файла из полного пути)
        except Exception as e:  # если произошла ошибка, выводим сообщение
            print(f"Ошибка для {book}: {e}")  # {book} - информация о книге, {e} - текст ошибки
    
    return created_files  # возвращаем список всех созданных файлов

if __name__ == "__main__":  # блок для тестирования модуля при прямом запуске (полезно для проверки, что все функции работают правильно)
    
    test_books = [                                     # cоздаем тестовые данные для проверки
        ("TEST-001", "Английский язык 10", "Афанасьева", "2018"),       # Кортеж
        {"qr_code": "TEST-002", "subject": "История новго времени 8"},  # Словарь
        "TEST-003",                                                     # Просто строка
    ]
    
    print("ТЕСТИРОВАНИЕ QR-ГЕНЕРАТОРА")
    print("=" * 40)
    
    # Генерируем тестовые QR-коды
    print("\nГенерируем тестовые QR-коды...")
    files = generate_all_qr_codes(test_books)  # вызываем функцию для генерации всех QR-кодов
    
    # выводим результаты тестирования
    print("\n" + "=" * 40)
    print(f"Создано {len(files)} QR-кодов в папке qrcodes/")
    print("\nПроверьте файлы:")
    
    # выводим список созданных файлов
    for file in files:
        print(f"{os.path.basename(file)}")  # выводим только имя файла (без пути к папке)
    
    print("\nТестирование завершено! Модуль работает корректно.")

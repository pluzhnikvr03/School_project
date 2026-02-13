import qrcode  # библиотека для создания QR-кодов
import os  # библиотека для работы с файловой системой (создание папок, проверка существования)


# основная функция для создания QR-кода
def generate_qr_code(qr_data,
                     folder="qrcodes"):  # qr_data - данные, которые будут закодированы в QR-код; folder - название папки, куда сохранять QR-код (qrcodes)
    if not os.path.exists(folder):  # создаем папку, если её нет
        os.makedirs(folder)  # makedirs создает папку и все промежуточные папки, если их нет

    qr = qrcode.make(str(qr_data))  # создаем QR-код из переданных данных
    filename = f"{qr_data}.png"  # формируем имя файла: используем данные QR-кода + расширение .png
    filepath = os.path.join(folder,
                            filename)  # формируем полный путь к файлу: папка + имя файла; os.path.join() соединяет пути для любой операционной системы
    qr.save(filepath)  # сохраняем QR-код как изображение PNG

    return filepath  # возвращаем путь к сохраненному файлу


# функция, которая извлекает QR-код из разного формата данных о книге и генерирует QR-код (удобно, если данные о книгах в разных форматах)
def generate_qr_for_book(book_info,
                         folder="qrcodes"):  # book_info - информация о книге в любом формате; folder - папка для сохранения QR-кода
    BOT_USERNAME = "library192_bot"  # имя бота через username

    if isinstance(book_info, dict):  # если передан словарь
        qr_data = book_info.get('qr_code', book_info.get('id', 'unknown'))
    elif isinstance(book_info, (list, tuple)):  # если передан список или кортеж
        qr_data = book_info[0]  # берем первый элемент как QR-код
    else:  # если передана просто строка или число
        qr_data = str(book_info)  # преобразуем в строку

    link = f"https://t.me/library192_bot?start={qr_data}" # формируем ссылку на бота с кодом книги (qr_data — код книги)

    # проверяем, есть ли папка qrcodes/. если нет — создаём её.
    if not os.path.exists(folder):
        os.makedirs(folder)

    # Генерируем QR-код из ссылки
    qr = qrcode.make(link)  # берём ссылку и превращаем её в QR-код.
    filename = f"{qr_data}.png"  # создаём имя файла типа TEST-001.png
    filepath = os.path.join(folder, filename)  # сохраняем путь к файлу (cклеиваем папку и имя файла: qrcodes/TEST-001.png)
    qr.save(filepath)  # сохраняем картинку

    return filepath  # возвращаем путь к файлу

# функция генерирует QR-коды для списка книг
def generate_all_qr_codes(books_list,
                          folder="qrcodes"):  # books_list - список книг в любом формате; folder - папка для сохранения всех QR-кодов
    created_files = []  # создаем пустой список для хранения путей к созданным файлам
    for book in books_list:  # проходим по всем книгам в списке
        try:  # пытаемся сгенерировать QR-код для текущей книги
            filename = generate_qr_for_book(book, folder)
            created_files.append(filename)  # если успешно, добавляем путь к файлу в список
            print(
                f"Создан QR-код: {os.path.basename(filename)}")  # выводим сообщение об успехе (os.path.basename() извлекает только имя файла из полного пути)
        except Exception as e:  # если произошла ошибка, выводим сообщение
            print(f"Ошибка для {book}: {e}")  # {book} - информация о книге, {e} - текст ошибки

    return created_files  # возвращаем список всех созданных файлов

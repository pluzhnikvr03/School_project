import qrcode  # библиотека для создания QR-кодов
import os  # библиотека для работы с файловой системой (создание папок, проверка существования)
from PIL import Image  # библиотека для работы с изображениями (нужна для вставки логотипа в QR-код)


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


# функция, которая извлекает QR-код из разного формата данных о книге и генерирует QR-код с логотипом школы (удобно, если данные о книгах в разных форматах)
def generate_qr_for_book(book_info,
                         folder="qrcodes"):  # book_info - информация о книге в любом формате; folder - папка для сохранения QR-кода
    if isinstance(book_info, dict):  # если передан словарь
        qr_data = book_info.get('qr_code', book_info.get('id', 'unknown'))
    elif isinstance(book_info, (list, tuple)):  # если передан список или кортеж
        qr_data = book_info[0]  # берем первый элемент как QR-код
    else:  # если передана просто строка или число
        qr_data = str(book_info)  # преобразуем в строку

    link = f"https://t.me/library192_bot?start={qr_data}" # формируем ссылку на tg-бота с кодом книги (qr_data — код книги)

    # Проверяем, есть ли папка qrcodes/. Если нет — создаём её.
    if not os.path.exists(folder):
        os.makedirs(folder)

    # создаём QR-код с высоким уровнем коррекции (для возможности добавить логотип)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)  # создаём QR-код, который сможет восстановиться, даже если до 30% его площади будет испорчено (закрыто логотипом)
    qr.add_data(link)  # кладём внутрь QR-кода ссылку на tg-бота
    qr.make(fit=True)  # программа автоматически подбирает минимальный размер QR-кода, в который поместятся все наши данные
    img = qr.make_image(fill_color="black", back_color="white").convert('RGB')  # создаем картинку QR-кода

    # добавляем логотип школы в центр (если файл существует)
    logo_path = "logo.png"  # путь к файлу с логотипом (лежит в папке с проектом)
    if os.path.exists(logo_path):
        try:  # пробуем добавить логотип в центр QR-кода
            logo = Image.open(logo_path)  # открываем файл с логотипом и загружаем его в память как изображение, с которым можно работать
            # уменьшаем логотип до подходящего размера (QR-код с высоким уровнем коррекции может восстановить до 30% повреждённой информации)
            logo.thumbnail((170, 170))
            # рассчитываем позицию для центра
            # img.size[0] - ширина QR, logo.size[0] - ширина логотипа, (img.size[0] - logo.size[0]) - свободное место
            pos = ((img.size[0] - logo.size[0]) // 2, (img.size[1] - logo.size[1]) // 2)
            # Вставляем логотип
            # img.paste(что вставляем, куда вставляем(координаты), прозрачность(чтобы фон логотипа не закрашивал QR))
            # logo.mode == 'RGBA' - проверяем, есть ли у логотипа прозрачный фон. Если есть — используем его как маску (прозрачные части не закрасят QR), если нет — вставляем как есть
            img.paste(logo, pos, mask=logo if logo.mode == 'RGBA' else None)
            print(f"Логотип добавлен в QR-код {qr_data}")
        except Exception as e:  # выводим ошибку, если не получилось
            print(f"Не удалось добавить логотип для {qr_data}: {e}")

    filename = f"{qr_data}.png"  # создаём имя файла типа TEST-001.png
    filepath = os.path.join(folder, filename)  # сохраняем путь к файлу (Склеиваем папку и имя файла: qrcodes/TEST-001.png)
    img.save(filepath)  # сохраняем картинку

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

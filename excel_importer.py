import pandas as pd  # библиотека для работы с таблицами (Excel, CSV); даем ей никнейм, чтобы было легче использовать
import sqlite3  # библиотека для работы с базой данных SQLite
import os  # библиотека для работы с файлами
import time  # библиотека для замера времени выполнения
from qr_generator import generate_qr_for_book  # функция создания QR-кодов
from datetime import datetime  # библиотека для работы с датой и временем
from reportlab.lib.pagesizes import A4  # узнаем размер А4 листа для размещения на нем QR-кодов
from reportlab.pdfgen import canvas  # инструмент для рисования PDF (создаем "холст")
from reportlab.lib.utils import ImageReader  # чтение картинок (PNG, JPG) для вставки в PDF


# функция работы с файлом из Excel и создания QR кодов
def import_all_books_from_excel(filename):  # filename - путь к файлу Excel, который нам передадут
    """
    Главная функция импорта для библиотекаря.
    Берёт Excel-файл, находит колонки, группирует книги и создаёт QR-коды.
    """
    start_time = time.time()  # запоминаем время начала для подсчёта длительности(запускаем "секундомер")

    # словарь для результата: сколько всего уникальных книг, всего экземпляров, QR-кодов, время
    result = {'added': 0, 'copies': 0, 'qrcodes': 0, 'time': 0}

    # ключ: "класс|предмет|автор|год"; значение: {'class':..., 'subject':..., 'count':...}
    # т.е. все учебники по алгебре 7 класса в одну стопку, по физике 8 класса — в другую и т.д.
    books_dict = {}  # словарь для группировки одинаковых книг

    try:  # пробуем обработать файл и поработать с ним
        excel_file = pd.ExcelFile(filename)  # открываем Excel-файл и создаём специальный объект excel_file
        conn = sqlite3.connect('library.db')  # подключаемся к базе данных
        cursor = conn.cursor()  # создаём курсор для SQL-запросов

        # проходим по всем листам Excel-файла
        for sheet_name in excel_file.sheet_names:  # sheet_name - название листа(н-р: 1-4, 5-9, 10-11)
            print(f"Обрабатываю лист: {sheet_name}")  # печатаем в консоль для отслеживания процесса

            # пропускаем лист с учебными пособиями (их будем обрабатывать отдельно, так как у файла другая логика)
            if 'пособия' in sheet_name.lower():
                print(f"Лист '{sheet_name}' пропущен (учебные пособия)")
                continue  # пропускаем всё остальное в цикле и переходим к следующему листу

            # читаем текущий лист в pandas DataFrame (таблица в памяти)
            df = pd.read_excel(excel_file, sheet_name=sheet_name)
            # pd.read_excel читает данные с конкретного листа и превращает их в DataFrame
            # это как лист Excel, который мы целиком помещаем в память компьютера. у него есть строки и колонки, и мы можем с ним работать
            # сохраняем этот DataFrame в переменную df (стандартное имя для DataFrame в pandas)
            # sheet_name=sheet_name - открываем конкретную страницу файла и читаем ее

            # жёсткая привязка колонок для основных листов
            if sheet_name in ['1-4', '5-9', '10-11']:
                class_col = 'Класс'
                subject_col = 'Предмет'
                author_col = 'Автор и заглавие'
                year_col = 'Год изд.'
                count_col = 'Кол. пост. 43а'  # или другая колонка с количеством
                
                print(f"✅ Использую жёсткие колонки для листа {sheet_name}")
                # пропускаем автоматический поиск
            else:
                # для остальных листов (например, пособия) используем автоматический поиск
                # автоматический поиск нужных колонок
                # автоматический поиск нужных колонок
                # ищем колонки по их названиям (регистр не учитываем, так как он не важен)
                class_col = subject_col = author_col = year_col = count_col = None
                # создаём пять переменных и пока кладём в них None. туда мы сохраним настоящие названия колонок, когда найдём их
                for col in df.columns:  # перебираем все названия колонок
                    col_str = str(col).lower()  # приводим к нижнему регистру
                    if 'класс' in col_str:
                        class_col = col  # берем название колонки, превращаем его в строку и делаем все буквы маленькими, чтобы не путать "Класс" и "класс"
                    elif 'предмет' in col_str:  # предмет
                        subject_col = col
                    elif ('автор' in col_str or 'заглавие' in col_str) and not 'кол' in col_str:  # автор
                        author_col = col
                    elif 'год' in col_str:  # год издания
                        year_col = col
                    elif 'кол' in col_str and ('пост' in col_str or 'экз' in col_str or 'количество' in col_str):  # количество экзмпляров
                        count_col = col

            # ===== ОТЛАДКА =====
            print(f"Найденные колонки:")
            print(f"  Класс: {class_col}")
            print(f"  Предмет: {subject_col}")
            print(f"  Автор: {author_col}")
            print(f"  Год: {year_col}")
            print(f"  Количество: {count_col}")

            if not all([class_col, subject_col, author_col, year_col, count_col]):
                print(f"⚠️ Не все колонки найдены на листе {sheet_name}, пропускаем...")
                print(f"Доступные колонки: {list(df.columns)}")
                continue

            # если на листе есть все нужные колонки, обрабатываем его
            if all([class_col, subject_col, author_col, year_col, count_col]):  # если хотя бы одна осталась None, то этот лист нам не подходит, и мы его пропускаем
                # проходим по каждой строке листа
                for idx, row in df.iterrows():
                    # df.iterrows() позволяет пройтись по каждой строке листа (DataFrame) по очереди
                    # idx — номер строки, row — сама строка со всеми её колонками
                    try:  # пробуем прочитать одну строчку из Excel-файла и вытащить оттуда информацию об одной книге
                        # извлекаем данные из ячеек и чистим от лишних пробелов
                        class_num = str(row[class_col]).strip()  # класс
                        subject = str(row[subject_col]).strip()  # предмет
                        author = str(row[author_col]).strip()  # автор
                        year = str(row[year_col]).strip()  # год
                        # берем из строки (row) значение в колонке, имя которой мы сохранили в class_col
                        # превращаем это значение в строку и убираем лишние пробелы в начале и конце

                        # проверка, что автор не является числом:
                        # author_val = str(row[author_col]).strip()
                        # if author_val.replace('.', '').replace(',', '').isdigit():
                            # print(f"Пропущена строка: автор похож на число ({author_val})")
                             # continue

                        # пытаемся получить количество экземпляров
                        count = 0  # для удобства предполагаем, что пока что экземпляров 0
                        if pd.notna(row[count_col]):  # если ячейка не пустая
                            # pd.notna() — специальная функция pandas, которая проверяет, есть ли в ячейке что-то осмысленно
                            try:  # пытаемся превратить данные из ячейки в целое число
                                count = int(float(row[count_col]))  # преобразуем в целое число
                            except:  # в случае любой ошибки
                                pass  # если не получилось — оставляем 0

                        # жёсткая защита от мусора
                        # проверяем, что количество не супер большое
                        if count > 500:
                            print(f"Пропущена строка {idx}: слишком много экземпляров ({count})")
                            continue

                        # проверяем, что год не пустой и не равен 0
                        if pd.isna(year) or str(year).strip() in ['', '0'] or int(float(year)) < 1900:
                            print(f"Пропущена строка {idx}: неверный год ({year})")
                            continue

                        # проверяем, что автор не является числом
                        if str(author).replace('.', '').replace(',', '').isdigit():
                            print(f"Пропущена строка {idx}: автор похож на число ({author})")
                            continue

                        # проверяем, что класс, предмет и автор не пустые и не NaN
                        if (pd.isna(class_num) or pd.isna(subject) or pd.isna(author) or 
                            str(class_num).strip() in ['', 'nan', 'None'] or
                            str(subject).strip() in ['', 'nan', 'None'] or
                            str(author).strip() in ['', 'nan', 'None'] or
                            'сумма' in str(subject).lower()):
                            print(f"Пропущена строка {idx}: неполные данные")
                            continue

                        # проверяем, есть ли осмысленные данные: количество больше нуля, и мы смогли получить предмет, автора и класс
                        if count > 0 and subject and author and class_num:
                            # создаём уникальный ключ для группировки
                            key = f"{class_num}|{subject}|{author}|{year}"

                            # если такая книга уже есть в словаре, значит, мы уже встречали эту книгу
                            # тогда мы просто добавляем количество экземпляров к уже существующей стопке
                            if key in books_dict:
                                books_dict[key]['count'] += count  # добавляем количество
                            else:  # если такой стопки ещё нет, мы её создаём
                                # создаём новую запись в словаре
                                # кладём в словарь по ключу key новый словарь с данными об этой книге
                                books_dict[key] = {'class': class_num, 'subject': subject,
                                                   'author': author, 'year': year, 'count': count}
                    except Exception as e:  # в случае ошибки выводим место и ее название
                        # idx — номер строки
                        print(f"Ошибка в строке {idx}: {e}")


        # добавление книг в базу и генерация QR-кодов
        print(f"\nНайдено уникальных книг: {len(books_dict)}")  # выводим в консоль, сколько разных названий мы насобирали

        # проходим по всем собранным книгам
        for key, book in books_dict.items():  # key — ключ (строка), book — это словарь с данными
            copies = book['count']  # количество экземпляров этой книги
            result['added'] += 1  # увеличиваем счётчик уникальных книг
            result['copies'] += copies  # увеличиваем счётчик экземпляров
            print(f"\nКнига: {book['subject']}, экз.: {copies}")

            # цикл для создания QR-кода для каждого отдельного экземпляра
            for copy_num in range(1, copies + 1):
                # генерация уникального QR-кода
                # берём первые 4 буквы предмета
                subject_code = book['subject'][:4].upper().replace(' ', '_')
                # берём первые 3 буквы первой фамилии автора
                if book['author'].split():  # если у автора есть хотя бы одно слово
                    author_code = book['author'].split()[0][:3].upper()
                else:  # если автор не указан или пустой
                    author_code = 'AUT'
                # формируем код: ПРЕДМЕТ-КЛАСС-АВТОР-НОМЕР_ЭКЗЕМПЛЯРА
                qr_code = f"{subject_code}-{book['class']}-{author_code}-{copy_num:03d}"
                # {copy_num:03d} означает, что номер экземпляра будет трёхзначным (001 - 999)

                try:  # пытаемся добавить книги в базу данных и сгенерировать QR-коды
                    # добавляем книгу в базу данных (SQL-запрос на добавление новой записи в таблицу books)
                    cursor.execute('''
                        INSERT INTO books (qr_code, subject, author, year, class)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (qr_code, book['subject'], book['author'], book['year'], book['class']))

                    # генерируем QR-код с логотипом
                    generate_qr_for_book(qr_code)  # вызываем функцию, которая создаёт картинку с QR-кодом и сохраняет её в папку
                    result['qrcodes'] += 1  # увеличиваем счётчик QR-кодов

                except sqlite3.IntegrityError:  # если такой QR-код уже есть в базе — пропускаем
                    print(f"QR {qr_code} уже существует")
                    continue

        conn.commit()  # сохраняем все изменения в базе данных
        conn.close()  # закрываем соединение
        result['time'] = round(time.time() - start_time, 1)  # считаем затраченное время
        return result  # возвращаем результат

    except Exception as e:  # если произошла любая ошибка
        print(f"Ошибка импорта: {e}")
        return {'error': str(e)}  # возвращаем сообщение об ошибке и печатаем ее в консоль


# функция создания PDF с QR-кодами
def create_qr_pdf(output_filename="qrcodes.pdf"):
    """
    Создаёт PDF с QR-кодами по 30 штук на листе A4
    """
    # создаем PDF документ
    # canvas - "холст", на котором мы будем рисовать
    # pagesize=A4 - устанавливаем размер страницы как стандартный лист A4
    c = canvas.Canvas(output_filename, pagesize=A4)

    # получаем ширину и высоту листа A4 в pt (1 pt = 0.35 мм)
    width, height = A4  # width = 595 pt, height = 842 pt

    # настраиваем расположение
    # размещаем QR-коды сеткой 5 * 6 (30 штук на одном листе)
    cols, rows = 5, 6  # 5 колонок, 6 рядов

    # размер одного QR-кода в pt (100 pt ≈ 35 мм)
    # это оптимальный размер для удобного сканирования
    qr_size = 100

    # отступы от краёв листа (чтобы QR-коды не прилипали к краям)
    margin_x, margin_y = 50, 50  # отступы слева/справа и сверху/снизу

    # вычисляем шаг между QR-кодами
    # (ширина листа - 2 отступа) / на количество колонок
    step_x = (width - 2 * margin_x) / cols
    # (высота листа - 2 отступа) / на количество рядов
    step_y = (height - 2 * margin_y) / rows

    # получаем список всех QR-кодов
    # проверяем, существует ли папка qrcodes
    if not os.path.exists('qrcodes'):
        return None  # если папки нет - выходим

    # получаем список всех файлов в папке qrcodes
    all_files = os.listdir('qrcodes')

    # создаем пустой список, куда будем складывать только PNG-файлы
    png_files = []

    # проходим по каждому файлу в папке
    for file in all_files:
        # проверяем, заканчивается ли имя файла на .png
        if file.endswith('.png'):
            # если да — добавляем его в список PNG-файлов
            png_files.append(file)

    # сортируем список по алфавиту
    qr_files = sorted(png_files)

    # если нет ни одного QR-кода - выходим
    if not qr_files:
        return None

    # суммарное количество QR-кодов
    total_qrs = len(qr_files)

    # вычисляем количество страниц
    # (total_qrs + кол-во на странице - 1) // кол-во на странице
    # формула округляет результат вверх (н-р: 31 // 30 = 2 страницы)
    pages = (total_qrs + cols * rows - 1) // (cols * rows)

    # создаем каждую страницу
    # page = 0, 1, 2... пока не сделаем все страницы
    for page in range(pages):
        # верхняя часть(ставим дату для удобства)
        # пишем дату создания (чтобы легче отличать версии)
        c.setFont("Helvetica", 8)
        current_date = datetime.now().strftime('%d.%m.%Y')
        c.drawString(width - 100, height - 20, f"от {current_date}")

        # нижний колонтитул (номер страницы)
        # устанавливаем жирный шрифт, чтобы номер бросался в глаза
        c.setFont("Helvetica-Bold", 10)
        # рисуем номер страницы внизу по центру
        # 30 pt от нижнего края — оптимально для глаз
        c.drawString(width / 2 - 50, 30, f"Страница {page + 1} из {pages}")


        # расставляем QR-коды на странице
        # проходим по всем ячейкам сетки (30 на странице)
        for i in range(cols * rows):
            # вычисляем индекс текущего QR-кода в общем списке
            # page * 30 + i - номер QR-кода на этой странице
            idx = page * cols * rows + i

            # если вышли за пределы списка QR-кодов - прекращаем
            if idx >= total_qrs:
                break

            # берём файл с QR-кодом по индексу
            qr_file = qr_files[idx]

            # вычисляем позицию в сетке
            col = i % cols  # номер колонки (0, 1, 2, 3, 4)
            row = i // cols  # номер ряда (0, 1, 2, 3, 4, 5)

            # вычисляем координаты для вставки QR-кода
            # X координата: отступ слева + (номер колонки * шаг) + центрирование
            # (step_x - qr_size) / 2 - чтобы QR был по центру ячейки, а не слева
            x = margin_x + col * step_x + (step_x - qr_size) / 2

            # Y координата: от верха листа - отступ - (номер ряда+1)*шаг + центрирование
            # row + 1 потому что ряд 0 - это первый ряд сверху
            y = height - margin_y - (row + 1) * step_y + (step_y - qr_size) / 2

            # вставляем QR-код
            # составляем полный путь к файлу: папка qrcodes + имя файла
            img_path = os.path.join('qrcodes', qr_file)

            # ImageReader - специальный класс для чтения картинок
            img = ImageReader(img_path)

            # рисуем картинку в PDF по координатам (x, y) с размером qr_size
            c.drawImage(img, x, y, width=qr_size, height=qr_size)

            # добавляем текст под QR-кодом (название файла)
            # устанавливаем маленький шрифт (6 pt)
            c.setFont("Helvetica", 6)

            # убираем расширение .png из имени файла
            code_name = qr_file.replace('.png', '')

            # если имя слишком длинное (больше 20 символов) - обрезаем
            if len(code_name) > 20:
                # обрезаем до 17 символов и добавляем троеточие (для красоты)
                code_name = code_name[:17] + "..."

            # рисуем текст под QR-кодом (y - 8 означает на 8 pt ниже QR)
            c.drawString(x, y - 8, code_name)

        # переход к новой странице
        # если это не последняя страница, создаём новую
        if page < pages - 1:
            c.showPage()  # сообщаем команду "показать текущую страницу и начать новую"

    # сохраняем PDF-файл
    c.save()

    # возвращаем имя созданного файла
    return output_filename

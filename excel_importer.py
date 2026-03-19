import pandas as pd  # библиотека для работы с таблицами (Excel, CSV); даем ей никнейм, чтобы было легче использовать
import sqlite3  # библиотека для работы с базой данных SQLite
import os  # библиотека для работы с файлами
import time  # библиотека для замера времени выполнения
from datetime import datetime  # библиотека для работы с датой и временем
from qr_generator import generate_qr_for_book  # функция создания QR-кодов
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


            if sheet_name in ['1-4', '5-9', '10-11']:  # составляем жесткие колонки для основных листов, чтобы не было путаницы
                class_col = 'Класс'
                subject_col = 'Предмет'
                author_col = 'Автор и заглавие'
                year_col = 'Год изд.'

                print(f"Использую жёсткие колонки для листа {sheet_name}")
                print(f"Класс: {class_col}")  # класс
                print(f"Предмет: {subject_col}")  # предмет
                print(f"Автор: {author_col}")  # автор
                print(f"Год: {year_col}")  # год

                has_all_columns = True  # помечаем, что все колонки найдены
            else:  # для остальных листов (например, "Учебн.пособия")
                # автоматический поиск для других листов
                class_col = subject_col = author_col = year_col = count_col = None
                for col in df.columns:  # перебираем все колонки в листе
                    col_str = str(col).lower()  # приводим название колонки к нижнему регистру

                    if 'класс' in col_str:
                        class_col = col  # если в названии есть "класс" — это колонка с классом
                    elif 'предмет' in col_str:
                        subject_col = col  # если "предмет" — колонка с предметом
                    elif 'автор' in col_str or 'заглавие' in col_str:
                        author_col = col  # если "автор" или "заглавие" — колонка с автором
                    elif 'год' in col_str:
                        year_col = col  # если "год" — колонка с годом
                    elif 'кол' in col_str or 'количество' in col_str:
                        count_col = col  # если "кол" или "количество" — колонка с количеством

                    # проверяем, все ли колонки нашлись
                has_all_columns = all([class_col, subject_col, author_col, year_col, count_col])

            # заполнение пустых классов (на случай долбоебизма тех, кто составляет накладную)
            if 'Класс' in df.columns:
                print(f"Заполняю пустые классы...")
                filled = 0

                # проходим по всем строкам
                for i in range(len(df)):
                    # если класс пустой
                    if pd.isna(df.loc[i, 'Класс']) or str(df.loc[i, 'Класс']).strip() == '':
                        # берём предмет из текущей строки
                        current_subject = df.loc[i, 'Предмет'] if 'Предмет' in df.columns else ''

                        # ищем предыдущую строку с классом
                        prev_class = None
                        prev_subject = None
                        for j in range(i - 1, -1, -1):
                            if pd.notna(df.loc[j, 'Класс']) and str(df.loc[j, 'Класс']).strip() != '':
                                prev_class = df.loc[j, 'Класс']
                                prev_subject = df.loc[j, 'Предмет'] if 'Предмет' in df.columns else ''
                                break

                        # ищем следующую строку с классом
                        next_class = None
                        next_subject = None
                        for j in range(i + 1, len(df)):
                            if pd.notna(df.loc[j, 'Класс']) and str(df.loc[j, 'Класс']).strip() != '':
                                next_class = df.loc[j, 'Класс']
                                next_subject = df.loc[j, 'Предмет'] if 'Предмет' in df.columns else ''
                                break

                        # принимаем решение
                        if prev_class is not None and prev_subject == current_subject:
                            # Тот же предмет, что и сверху → берём предыдущий класс
                            df.loc[i, 'Класс'] = prev_class
                            filled += 1
                            print(f"Строка {i}: класс = {prev_class} (тот же предмет, что выше)")
                        elif next_class is not None and next_subject == current_subject:
                            # тот же предмет, что и снизу → берём следующий класс
                            df.loc[i, 'Класс'] = next_class
                            filled += 1
                            print(f"Строка {i}: класс = {next_class} (тот же предмет, что ниже)")
                        elif prev_class is not None:
                            # предмет не совпадает, но есть предыдущий класс
                            df.loc[i, 'Класс'] = prev_class
                            filled += 1
                            print(f"Строка {i}: класс = {prev_class} (по предыдущему)")
                        elif next_class is not None:
                            # предмет не совпадает, но есть следующий класс
                            df.loc[i, 'Класс'] = next_class
                            filled += 1
                            print(f"Строка {i}: класс = {next_class} (по следующему)")

                print(f"Заполнено {filled} пустых классов")

                # проходим по каждой строке листа
            for idx, row in df.iterrows():
                # df.iterrows() позволяет пройтись по каждой строке листа (DataFrame) по очереди
                # idx — номер строки, row — сама строка со всеми её колонками
                try:  # пробуем прочитать одну строчку из Excel-файла и вытащить оттуда информацию об одной книге
                    # извлекаем данные из ячеек и чистим от лишних пробелов
                    # берём значение из Excel
                    raw_value = row[class_col]
                    # превращаем в строку и убираем лишние пробелы
                    raw_value = str(raw_value).strip()
                    # если строка состоит только из цифр (может быть с точкой)
                    if raw_value.replace('.', '').isdigit():
                        # превращаем в целое число (отбрасываем .0)
                        class_num = str(int(float(raw_value)))  # класс
                    else:  # оставляем как есть
                        class_num = raw_value
                    subject = str(row[subject_col]).strip()  # предмет
                    author = str(row[author_col]).strip()  # автор
                    year = str(row[year_col]).strip()  # год
                    # берем из строки (row) значение в колонке, имя которой мы сохранили в class_col
                    # превращаем это значение в строку и убираем лишние пробелы в начале и конце

                    # пытаемся получить количество экземпляров
                    count = 0
                    if sheet_name in ['1-4', '5-9', '10-11']:
                        # для основных листов суммируем три колонки
                        for col_name in ['Кол. пост. 34а', 'Кол. пост. 39а', 'Кол. пост. 43а']:  # суммируем экземпляры всех зданий
                            if col_name in df.columns and pd.notna(row[col_name]):
                                try:
                                    count += int(float(row[col_name]))
                                except:
                                    pass
                    else:
                        # для остальных листов берём одну колонку
                        if pd.notna(row[count_col]):
                            try:
                                count = int(float(row[count_col]))
                            except:
                                pass

                    # проверяем, есть ли осмысленные данные
                    if count > 0 and subject and class_num:
                        # создаём уникальный ключ для группировки (БЕЗ АВТОРА!)
                        key = f"{class_num}|{subject}|{year}"

                        if key in books_dict:
                            books_dict[key]['count'] += count
                        else:
                            books_dict[key] = {
                                'class': class_num,
                                'subject': subject,
                                'author': author,
                                'year': year,
                                'count': count
                            }

                except Exception as e:  # в случае ошибки выводим место и ее название
                    # idx — номер строки
                    print(f"Ошибка в строке {idx}: {e}")


        # добавление книг в базу и генерация QR-кодов
        print(f"\nНайдено уникальных книг: {len(books_dict)}")  # выводим в консоль, сколько разных названий мы насобирали

        # проходим по всем собранным книгам
        for key, book in books_dict.items():  # key — ключ (строка), book — это словарь с данными
            copies = book['count']  # количество экземпляров этой книги
            # проверяем, не слишком ли много экземпляров (скорее всего итоговая строка)
            if copies > 500:
                print(f"Пропущена книга с {copies} экземплярами (возможно, итоговая строка)")
                continue  # пропускаем эту "книгу"
            result['added'] += 1  # увеличиваем счётчик уникальных книг
            result['copies'] += copies  # увеличиваем счётчик экземпляров
            print(f"\nКнига: {book['subject']} ({book['class']} класс), экз.: {copies}")

            new_qrs = 0  # счётчик реально созданных QR-кодов для этой книги
            # цикл для создания QR-кода для каждого отдельного экземпляра
            for copy_num in range(1, copies + 1):
                # генерация уникального QR-кода
                # берём первые 4 буквы предмета
                subject_code = book['subject'][:4].upper().replace(' ', '_')
                # формируем код: ПРЕДМЕТ-КЛАСС-НОМЕР_ЭКЗЕМПЛЯРА
                qr_code = f"{subject_code}-{book['class']}-{copy_num:03d}"
                # {copy_num:03d} означает, что номер экземпляра будет трёхзначным (001 - 999)

                cursor.execute('SELECT id FROM books WHERE qr_code = ?', (qr_code,))
                if cursor.fetchone():
                    continue  # молча пропускаем
                try:
                    cursor.execute('''
                    INSERT INTO books (qr_code, subject, author, year, class, copies)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (qr_code, book['subject'], book['author'], book['year'], book['class'], copies))
                    generate_qr_for_book(qr_code)
                    new_qrs += 1
                    result['qrcodes'] += 1

                except sqlite3.IntegrityError:
                    continue

            # после цикла показываем итог по книге
            if new_qrs == 0:
                print(f"Все {copies} QR-кодов уже существуют")
            else:
                print(f"Создано {new_qrs} новых QR-кодов (из {copies})")

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
    print(f"СОЗДАЮ PDF: {output_filename}")
    print(f"Папка qrcodes существует: {os.path.exists('qrcodes')}")
    if os.path.exists('qrcodes'):
        files = os.listdir('qrcodes')
        print(f"Файлов в папке: {len(files)}")
        if files:
            print(f"Первые 5 файлов: {files[:5]}")
    else:
        print("Папки qrcodes НЕТ!")
        return None
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
        print(f"  Сейчас будем использовать datetime: {datetime}")
        print(f"  Тип datetime: {type(datetime)}")
        print(f"  Сам datetime: {datetime}")
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

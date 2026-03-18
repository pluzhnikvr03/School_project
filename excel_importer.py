import pandas as pd
import sqlite3
import os
import time
from qr_generator import generate_qr_for_book
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# функция работы с файлом из Excel и создания QR кодов
def import_all_books_from_excel(filename):
    """
    Главная функция импорта для библиотекаря.
    Берёт Excel-файл, находит колонки, группирует книги и создаёт QR-коды.
    """
    start_time = time.time()
    result = {'added': 0, 'copies': 0, 'qrcodes': 0, 'time': 0}
    books_dict = {}

    try:
        excel_file = pd.ExcelFile(filename)
        conn = sqlite3.connect('library.db')
        cursor = conn.cursor()

        for sheet_name in excel_file.sheet_names:
            print(f"\nОбрабатываю лист: {sheet_name}")

            # пропускаем лист с учебными пособиями
            if 'пособия' in sheet_name.lower():
                print(f"Лист '{sheet_name}' пропущен (учебные пособия)")
                continue

            df = pd.read_excel(excel_file, sheet_name=sheet_name)

            # ===== ЖЁСТКАЯ ПРИВЯЗКА КОЛОНОК ДЛЯ ОСНОВНЫХ ЛИСТОВ =====
            if sheet_name in ['1-4', '5-9', '10-11']:
                class_col = 'Класс'
                subject_col = 'Предмет'
                author_col = 'Автор и заглавие'
                year_col = 'Год изд.'
                
                print(f" Использую жёсткие колонки")
                print(f"  Класс: {class_col}")
                print(f"  Предмет: {subject_col}")
                print(f"  Автор: {author_col}")
                print(f"  Год: {year_col}")
                print(f"  Количество: суммируются 34а, 39а, 43а")
                
                has_all_columns = True
                
            else:
                # автоматический поиск для других листов
                class_col = subject_col = author_col = year_col = count_col = None
                for col in df.columns:
                    col_str = str(col).lower()
                    if 'класс' in col_str:
                        class_col = col
                    elif 'предмет' in col_str:
                        subject_col = col
                    elif ('автор' in col_str or 'заглавие' in col_str) and not 'кол' in col_str:
                        author_col = col
                    elif 'год' in col_str:
                        year_col = col
                    elif 'кол' in col_str and ('пост' in col_str or 'экз' in col_str or 'количество' in col_str):
                        count_col = col

                print(f"  Автоматический поиск")
                print(f"  Класс: {class_col}")
                print(f"  Предмет: {subject_col}")
                print(f"  Автор: {author_col}")
                print(f"  Год: {year_col}")
                print(f"  Количество: {count_col}")
                
                has_all_columns = all([class_col, subject_col, author_col, year_col, count_col])

            if not has_all_columns:
                print(f" Не все колонки найдены, пропускаем лист")
                continue

            # ===== ОБРАБОТКА СТРОК =====
            for idx, row in df.iterrows():
                try:
                    class_num = str(row[class_col]).strip()
                    subject = str(row[subject_col]).strip()
                    author = str(row[author_col]).strip()
                    year = str(row[year_col]).strip()

                    # получаем количество экземпляров
                    count = 0
                    
                    # Для основных листов суммируем три колонки
                    if sheet_name in ['1-4', '5-9', '10-11']:
                        for col_name in ['Кол. пост. 34а', 'Кол. пост. 39а', 'Кол. пост. 43а']:
                            if col_name in df.columns and pd.notna(row[col_name]):
                                try:
                                    count += int(float(row[col_name]))
                                except:
                                    pass
                    else:
                        # Для остальных листов берём одну колонку
                        if pd.notna(row[count_col]):
                            try:
                                count = int(float(row[count_col]))
                            except:
                                pass

                    # проверки
                    if count > 500:
                        print(f" Строка {idx}: слишком много экземпляров ({count})")
                        continue

                    if pd.isna(year) or str(year).strip() in ['', '0'] or int(float(year)) < 1900:
                        print(f" Строка {idx}: неверный год ({year})")
                        continue

                    if str(author).replace('.', '').replace(',', '').isdigit():
                        print(f" Строка {idx}: автор похож на число ({author})")
                        continue

                    if (pd.isna(class_num) or pd.isna(subject) or pd.isna(author) or 
                        str(class_num).strip() in ['', 'nan', 'None'] or
                        str(subject).strip() in ['', 'nan', 'None'] or
                        str(author).strip() in ['', 'nan', 'None'] or
                        'сумма' in str(subject).lower()):
                        print(f" Строка {idx}: неполные данные")
                        continue

                    # добавляем в словарь
                    if count > 0 and subject and author and class_num:
                        key = f"{class_num}|{subject}|{author}|{year}"
                        if key in books_dict:
                            books_dict[key]['count'] += count
                        else:
                            books_dict[key] = {'class': class_num, 'subject': subject,
                                               'author': author, 'year': year, 'count': count}
                except Exception as e:
                    print(f"Ошибка в строке {idx}: {e}")

        # добавление книг в базу и генерация QR-кодов
        print(f"\n Найдено уникальных книг: {len(books_dict)}")

        for key, book in books_dict.items():
            copies = book['count']
            result['added'] += 1
            result['copies'] += copies
            print(f"\nКнига: {book['subject']}, экз.: {copies}")

            for copy_num in range(1, copies + 1):
                subject_code = book['subject'][:4].upper().replace(' ', '_')
                if book['author'].split():
                    author_code = book['author'].split()[0][:3].upper()
                else:
                    author_code = 'AUT'
                qr_code = f"{subject_code}-{book['class']}-{author_code}-{copy_num:03d}"

                try:
                    cursor.execute('''
                        INSERT INTO books (qr_code, subject, author, year, class)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (qr_code, book['subject'], book['author'], book['year'], book['class']))

                    generate_qr_for_book(qr_code)
                    result['qrcodes'] += 1

                except sqlite3.IntegrityError:
                    print(f"QR {qr_code} уже существует")
                    continue

        conn.commit()
        conn.close()
        result['time'] = round(time.time() - start_time, 1)
        return result

    except Exception as e:
        print(f"Ошибка импорта: {e}")
        return {'error': str(e)}


# функция создания PDF с QR-кодами
def create_qr_pdf(output_filename="qrcodes.pdf"):
    c = canvas.Canvas(output_filename, pagesize=A4)
    width, height = A4

    cols, rows = 5, 6
    qr_size = 100
    margin_x, margin_y = 50, 50

    step_x = (width - 2 * margin_x) / cols
    step_y = (height - 2 * margin_y) / rows

    if not os.path.exists('qrcodes'):
        return None

    qr_files = sorted([f for f in os.listdir('qrcodes') if f.endswith('.png')])
    if not qr_files:
        return None

    total_qrs = len(qr_files)
    pages = (total_qrs + cols * rows - 1) // (cols * rows)

    for page in range(pages):
        c.setFont("Helvetica", 8)
        current_date = datetime.now().strftime('%d.%m.%Y')
        c.drawString(width - 100, height - 20, f"от {current_date}")

        c.setFont("Helvetica-Bold", 10)
        c.drawString(width / 2 - 50, 30, f"Страница {page + 1} из {pages}")

        for i in range(cols * rows):
            idx = page * cols * rows + i
            if idx >= total_qrs:
                break

            qr_file = qr_files[idx]
            col = i % cols
            row = i // cols

            x = margin_x + col * step_x + (step_x - qr_size) / 2
            y = height - margin_y - (row + 1) * step_y + (step_y - qr_size) / 2

            img_path = os.path.join('qrcodes', qr_file)
            img = ImageReader(img_path)
            c.drawImage(img, x, y, width=qr_size, height=qr_size)

            c.setFont("Helvetica", 6)
            code_name = qr_file.replace('.png', '')
            if len(code_name) > 20:
                code_name = code_name[:17] + "..."
            c.drawString(x, y - 8, code_name)

        if page < pages - 1:
            c.showPage()

    c.save()
    return output_filename

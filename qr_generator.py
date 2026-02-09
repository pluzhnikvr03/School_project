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
        qr_data = book_info[0]  
    else:
        qr_data = str(book_info)
    
    
    return generate_qr_code(qr_data, folder)

def generate_all_qr_codes(books_list, folder="qrcodes"):
  created_files = []
    
    for book in books_list:
        try:
            filename = generate_qr_for_book(book, folder)
            created_files.append(filename)
            print(f"Создан QR-код: {os.path.basename(filename)}")
        except Exception as e:
            print(f"Ошибка для {book}: {e}")
    
    return created_files

if __name__ == "__main__":
  
    print("\nГенерируем тестовые QR-коды...")
    files = generate_all_qr_codes(test_books)
    
    # Результат
    print("\n" + "=" * 40)
    print(f"🎉 Создано {len(files)} QR-кодов в папке 'qrcodes/'")
    print("\nПроверьте файлы:")
    for file in files:
        print(f"{os.path.basename(file)}")

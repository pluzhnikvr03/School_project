# create_qr_now.py
print("🚀 СОЗДАЮ QR-КОДЫ ПРЯМО СЕЙЧАС!")

from qr_generator import generate_qr_for_book

# Все QR-коды, которые должны быть
books = [
    "TEST-001",
    "TEST-002",
    "TEST-003",
    "TEST-004",
    "TEST-005"
]

print("\n📁 Создаю QR-коды...")
for qr_code in books:
    try:
        # Создаем QR-код
        result = generate_qr_for_book(qr_code)
        print(f"✅ Создан: {qr_code} -> {result}")
    except Exception as e:
        print(f"❌ Ошибка с {qr_code}: {e}")

print("\n🎯 ВСЁ ГОТОВО!")
print("QR-коды в папке 'qrcodes/'")
print("Теперь запускай бота!")

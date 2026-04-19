import pickle
import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/drive.file'  # разрешение на загрузку файлов на Диск
]

def get_gmail_service():
    creds = None
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            # Запускаем сервер на порту 8080, но не открываем браузер автоматически
            creds = flow.run_local_server(port=8080, open_browser=False)
            print("Авторизация завершена, токен сохранён")

        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds

if __name__ == '__main__':
    print("Запуск авторизации...")
    creds = get_gmail_service()
    print("Токен сохранён в token.pickle!")

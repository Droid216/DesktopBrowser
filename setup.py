from setuptools import setup

APP = ['main.py']  # Замените 'main.py' на основной файл вашего приложения
DATA_FILES = []    # Укажите дополнительные файлы, такие как иконки и конфигурации, если нужны

packages = [
    'selenium', 'webdriver_manager', 'PyQt5', 'sqlalchemy', 'psycopg2', 'pyodbc', 'pyautogui',
    'cryptography', 'seleniumwire', 'undetected_chromedriver', 'requests',
    'objc', 'blinker'
]

OPTIONS = {
    'packages': packages,
    'excludes': ['rubicon'],  # Исключите ненужные модули
    'plist': {
        'CFBundleName': 'ProxyBrowser',          # Имя приложения
        'CFBundleDisplayName': 'ProxyBrowser',   # Имя, отображаемое в macOS
        'CFBundleIdentifier': 'com.example.ProxyBrowser',  # Уникальный идентификатор приложения
        'CFBundleVersion': '0.1.0',
        'CFBundleShortVersionString': '0.1.0'
    },
}

setup(
    app=APP,
    data_files=DATA_FILES,
    options={'py2app': OPTIONS},
    setup_requires=['py2app'],
)

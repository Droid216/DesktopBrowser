import os
import json
import threading
import pyautogui
import webbrowser
from contextlib import suppress

from PyQt5 import QtWidgets, QtGui, QtCore
from selenium.common.exceptions import WebDriverException, NoSuchWindowException, InvalidSessionIdException

from log_api import logger
from database.db import DbConnection
from config import ICON_PATH, INFO_ICON_PATH, NAME
from web_driver.wd import WebDriver, AuthException


class BrowserApp(QtWidgets.QWidget):
    browser_loaded = QtCore.pyqtSignal(bool)
    error_message = QtCore.pyqtSignal(str)

    def __init__(self, user: str, group: str, db_conn: DbConnection):
        super().__init__()
        self.info_icon = None
        self.auto_checkbox = None
        self.launch_button = None
        self.market_select = None
        self.marketplace_select = None
        self.credentials_file = 'credentials.json'

        self.setWindowTitle(NAME)

        self.user = user
        self.group = group

        self.setWindowIcon(QtGui.QIcon(ICON_PATH))

        screen_width, screen_height = pyautogui.size()
        x_position = (screen_width - 400) // 2
        y_position = (screen_height - 100) // 2

        self.setGeometry(x_position, y_position, 400, 100)
        self.web_drivers = []

        self.db_conn = db_conn
        self.markets = self.db_conn.info(group)

        self.browser_loaded.connect(self.on_browser_loaded)
        self.error_message.connect(self.on_error_message)

        self.init_ui()
        self.load_credentials()

    def init_ui(self):

        marketplaces = sorted(list({m.marketplace for m in self.markets}))

        self.marketplace_select = QtWidgets.QComboBox()
        self.marketplace_select.addItems(marketplaces)
        self.marketplace_select.currentTextChanged.connect(self.update_markets)

        self.market_select = QtWidgets.QComboBox()
        self.update_markets()

        self.launch_button = QtWidgets.QPushButton("Запуск браузера")
        self.launch_button.clicked.connect(self.launch_browser)

        form_layout = QtWidgets.QFormLayout()
        form_layout.addRow("Выберите маркетплейс:", self.marketplace_select)
        form_layout.addRow("Выберите рынок:", self.market_select)

        self.auto_checkbox = QtWidgets.QCheckBox("Автоматическая авторизация", self)
        self.auto_checkbox.stateChanged.connect(self.default_text_button)
        self.auto_checkbox.setChecked(True)

        self.info_icon = QtWidgets.QToolButton(self)
        self.info_icon.setIcon(QtGui.QIcon(INFO_ICON_PATH))
        self.info_icon.setToolTip("Если установлена галочка\n"
                                  "при запуске браузера будет\n"
                                  "включена автоматическая\n"
                                  "авторизация в ЛК.\n"
                                  "Если Вы уже авторизованы\n"
                                  "уберите галочку либо\n"
                                  "дождитесь входа в ЛК.")
        self.info_icon.setCursor(QtGui.QCursor(QtCore.Qt.WhatsThisCursor))
        self.info_icon.setIconSize(QtCore.QSize(16, 16))

        auto_auth_layout = QtWidgets.QHBoxLayout()
        auto_auth_layout.addWidget(self.auto_checkbox)
        auto_auth_layout.addWidget(self.info_icon)
        auto_auth_layout.addStretch()

        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(form_layout)
        layout.addLayout(auto_auth_layout)
        layout.addWidget(self.launch_button)

        self.launch_button.setEnabled(True)
        self.default_text_button()

        self.setLayout(layout)

    def default_text_button(self) -> None:
        if self.launch_button.isEnabled():
            if self.auto_checkbox.isChecked():
                self.launch_button.setText("🤖Запуск браузера С автоматической авторизацией🤖")
            else:
                self.launch_button.setText("🖐🏻Запуск браузера БЕЗ автоматической авторизациии🖐🏻")

    def update_markets(self):
        selected_marketplace = self.marketplace_select.currentText()

        filtered_companies = sorted([m.name_company for m in self.markets if m.marketplace == selected_marketplace])

        self.market_select.clear()
        self.market_select.addItems(filtered_companies)

    def launch_browser(self):
        self.launch_button.setEnabled(False)
        self.launch_button.setText('Загружаю браузер...')
        threading.Thread(target=self.launch_browser_thread, daemon=True).start()

    def launch_browser_thread(self):
        marketplace = self.marketplace_select.currentText()
        name_company = self.market_select.currentText()
        auto = self.auto_checkbox.isChecked()
        try:
            market = self.db_conn.get_market(marketplace=marketplace, name_company=name_company)
        except RuntimeError as er:
            try:
                text = f"{str(er)}"
                logger.error(description=text)
            except Exception as e:
                text = str(e)
            QtWidgets.QMessageBox.critical(self, "Ошибка", text + '\nПроверте интернет соединение')
            self.browser_loaded.emit(True)
            return
        self.cleanup_inactive_drivers()
        browser_id = f"{market.connect_info.phone}_{market.marketplace.lower()}"
        log_startswith = f"{market.marketplace} - {market.name_company}: "
        try:
            with suppress(NoSuchWindowException, InvalidSessionIdException):
                if browser_id not in [driver.browser_id for driver in self.web_drivers]:
                    web_driver = WebDriver(market=market,
                                           user=self.user,
                                           auto=auto,
                                           db_conn=self.db_conn)
                    self.web_drivers.append(web_driver)
                    url = market.marketplace_info.link
                    if market.marketplace == 'Ozon':
                        url += '?localization_language_code=ru'
                    web_driver.load_url(url=url)
        except WebDriverException as e:
            if "cannot find Chrome binary" in str(e):
                logger.error(user=self.user, description=f"Нет установленного Chrome")
                self.browser_loaded.emit(False)
                return
            elif "session not created" in str(e):
                logger.error(user=self.user, description=f"Неудалось запустить сессию")
                self.error_message.emit(f"Неудалось запустить сессию.\n\nВозможно открыта ещё одна версия программы")
            else:
                logger.error(user=self.user, description=f"{log_startswith}Ошибка WebDriver. {str(e).splitlines()[0]}")
                self.error_message.emit(str(e))
        except AuthException as e:
            self.error_message.emit(str(e))
        except Exception as e:
            logger.error(user=self.user, description=f"{log_startswith}Ошибка браузера. {str(e).splitlines()[0]}")

        self.browser_loaded.emit(True)

    def on_browser_loaded(self, success):
        if not success:
            QtWidgets.QMessageBox.critical(None, "Ошибка", "Не удалось запустить Chrome. Пожалуйста, установите его.")
            webbrowser.open("https://www.google.com/chrome/")
        self.launch_button.setEnabled(True)
        self.default_text_button()

    @staticmethod
    def on_error_message(text):
        if text:
            QtWidgets.QMessageBox.critical(None, 'Ошибка автоматизации', text)

    def cleanup_inactive_drivers(self):
        self.web_drivers = [driver for driver in self.web_drivers if driver.is_browser_active()]

    def save_credentials(self):
        if os.path.exists(self.credentials_file):
            with open(self.credentials_file, 'r') as f:
                try:
                    credentials = json.load(f)
                except json.JSONDecodeError:
                    credentials = {}
        else:
            credentials = {}
        credentials.update({
            "marketplace": self.marketplace_select.currentText(),
            "name_company": self.market_select.currentText(),
            "auto": self.auto_checkbox.isChecked()
        })
        with open(self.credentials_file, 'w') as f:
            json.dump(credentials, f, indent=4)

    def load_credentials(self):
        if os.path.exists(self.credentials_file):
            with open(self.credentials_file, 'r') as f:
                credentials = json.load(f)
                marketplace = credentials.get("marketplace", "")
                name_company = credentials.get("name_company", "")
                auto = credentials.get("auto", True)

                index_marketplace = self.marketplace_select.findText(marketplace)
                if index_marketplace != -1:
                    self.marketplace_select.setCurrentIndex(index_marketplace)
                    index_name_company = self.market_select.findText(name_company)
                    if index_name_company != -1:
                        self.market_select.setCurrentIndex(index_name_company)
                    else:
                        self.market_select.setCurrentIndex(0)
                else:
                    self.marketplace_select.setCurrentIndex(0)
                    self.market_select.setCurrentIndex(0)

                self.auto_checkbox.setChecked(auto)

    def closeEvent(self, event):
        self.save_credentials()
        self.cleanup_inactive_drivers()
        for driver in self.web_drivers:
            driver.quit()
        logger.info(user=self.user, description=f"Выход из приложения")
        event.accept()

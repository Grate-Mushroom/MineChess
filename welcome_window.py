"""Класс приветственного окна со списком сохранённых партий."""

from PyQt5 import QtWidgets, QtCore, QtGui
from welcome_ui import Ui_WelcomeWindow
from new_game_ui import Ui_NewGameDialog
import database as db


class NewGameDialog(QtWidgets.QDialog):
    """Диалоговое окно настроек новой партии."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_NewGameDialog()
        self.ui.setupUi(self)

    def get_game_data(self):
        """Возвращает введённые настройки."""
        return {
            "name": self.ui.editName.text() or "Без названия",
            "difficulty": self.ui.comboDifficulty.currentIndex(),
            "time_limit": self.ui.spinTime.value()
        }


class WelcomeWindow(QtWidgets.QMainWindow):
    """Главное приветственное окно."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_WelcomeWindow()
        self.ui.setupUi(self)

        # Подключаем кнопки
        self.ui.btnNewGame.clicked.connect(self.open_new_game_dialog)
        self.ui.btnContinue.clicked.connect(self.continue_game)
        self.ui.btnDelete.clicked.connect(self.delete_game)
        self.ui.btnExit.clicked.connect(self.close)

        # Горячие клавиши через QShortcut (безопаснее, чем keyPressEvent)
        self.shortcut_delete = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Delete), self)
        self.shortcut_delete.activated.connect(self.delete_game)

        self.shortcut_enter = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Return), self)
        self.shortcut_enter.activated.connect(self.continue_game)

        # Загружаем список игр
        self.load_games()

    def load_games(self):
        """Загружает список партий из БД."""
        self.ui.listGames.clear()
        games = db.get_all_games()

        if not games:
            self.ui.listGames.addItem("Нет сохранённых партий")
            self.ui.btnContinue.setEnabled(False)
            self.ui.btnDelete.setEnabled(False)
            return

        self.ui.btnContinue.setEnabled(True)
        self.ui.btnDelete.setEnabled(True)

        for game_id, name, difficulty, time_limit, created_at in games:
            difficulty_names = ["Легко", "Средне", "Сложно"]
            diff_text = difficulty_names[difficulty] if difficulty < len(difficulty_names) else "Неизвестно"
            item_text = f"{name} | {diff_text} | {time_limit} мин | {created_at}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setData(32, game_id)  # Qt.UserRole = 32
            self.ui.listGames.addItem(item)

    def open_new_game_dialog(self):
        """Открывает диалог новой партии."""
        dialog = NewGameDialog(self)

        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            data = dialog.get_game_data()
            # Сохраняем в БД
            game_id = db.create_game(data["name"], data["difficulty"], data["time_limit"])
            # Запускаем игру БЕЗ загрузки состояния (новая партия)
            self.start_game(game_id, data, load_saved=False)

    def continue_game(self):
        """Продолжить выбранную партию — сразу открывает игру с сохранённым состоянием."""
        selected = self.ui.listGames.currentItem()
        if not selected or selected.text() == "Нет сохранённых партий":
            QtWidgets.QMessageBox.warning(self, "Внимание", "Выберите партию из списка")
            return

        game_id = selected.data(32)
        if game_id is None:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Партия не найдена")
            return

        game_data = db.get_game_by_id(game_id)

        if game_data:
            # Запускаем игру С загрузкой сохранённого состояния
            self.start_game(game_id, game_data, load_saved=True)
        else:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Партия не найдена в базе данных")

    def delete_game(self):
        """Удалить выбранную партию."""
        selected = self.ui.listGames.currentItem()
        if not selected or selected.text() == "Нет сохранённых партий":
            QtWidgets.QMessageBox.warning(self, "Внимание", "Выберите партию для удаления")
            return

        game_id = selected.data(32)
        if game_id is None:
            QtWidgets.QMessageBox.warning(self, "Ошибка", "Партия не найдена")
            return

        reply = QtWidgets.QMessageBox.question(
            self, "Подтверждение",
            f"Удалить партию '{selected.text()}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            db.delete_game(game_id)
            self.load_games()

    def start_game(self, game_id, data, load_saved=False):
        """Запускает главное игровое окно."""
        # Импортируем здесь, чтобы избежать циклического импорта
        from main import MainWindow

        self.game_window = MainWindow(game_id, data, load_saved=load_saved)
        self.game_window.show()
        self.hide()  # Скрываем приветственное окно
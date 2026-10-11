"""Главное игровое окно шахмат с минами."""

import os
import random
import sys
import json

from PyQt5 import QtCore, QtGui, QtWidgets

from board_ui import Ui_MainWindow
from chess_engine import ChessBoard, Piece, WHITE, BLACK
import database as db

def resource_path(relative_path):
    """Возвращает абсолютный путь к ресурсу с учётом запуска из .exe."""
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

FILES = "abcdefgh"
START_SECONDS = 630
MINES_COUNT = 4
EXPLOSION_PENALTY = 60
LABEL_WHITE = "Белых"
LABEL_BLACK = "Чёрных"
PIECE_SYMBOLS = {"K": "♚", "Q": "♛", "R": "♜", "B": "♝", "N": "♞", "P": "♟"}

STYLE_SELECTED = "background-color: rgb(255, 213, 79);"
STYLE_MOVE = "background-color: rgb(129, 199, 132);"
STYLE_OPENED = "background-color: rgb(110, 155, 185);"

# Количество мин в зависимости от сложности
DIFFICULTY_MINES = {0: 4, 1: 8, 2: 12}


def _sign(value):
    """Знак числа: -1, 0 или 1."""
    return (value > 0) - (value < 0)


class MainWindow(QtWidgets.QMainWindow):
    """Главное окно: шахматы с минами, часы сторон и таблица ходов."""

    def __init__(self, game_id=None, game_data=None, load_saved=False):
        super().__init__()
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        # Параметры игры
        self.game_id = game_id
        self.game_data = game_data or {"name": "Игра", "difficulty": 0, "time_limit": 10}
        self.mines_count = DIFFICULTY_MINES.get(self.game_data["difficulty"], 4)

        # Инициализация игрового состояния
        self.engine = ChessBoard()
        self.squares = {}
        self.square_by_button = {}
        self.number_labels = {}
        self.icons = {}
        self.selected = None
        self.game_over = False
        self.elapsed = 0
        self.white_left = self.game_data["time_limit"] * 60
        self.black_left = self.game_data["time_limit"] * 60
        self.mines = set()
        self.flags = set()
        self.opened = set()
        self.move_count = 0

        # Таймер
        self.clock = QtCore.QTimer(self)
        self.clock.setInterval(1000)
        self.clock.timeout.connect(self._tick)

        # Инициализация интерфейса
        self._collect_squares()
        self._load_icons()

        # Меню
        self.ui.a_new.triggered.connect(self._on_new_game_action)
        self.ui.a_exit.triggered.connect(self.close)

        # Загрузка сохранённого состояния или новая игра
        if load_saved and game_id:
            state_json = db.get_game_state(game_id)
            if state_json:
                state = json.loads(state_json)
                self.load_state(state)
            else:
                self.new_game()
        else:
            self.new_game()

    def _collect_squares(self):
        """Собирает кнопки доски и создаёт поверх каждой лейбл для цифры."""
        for row in range(8):
            for col in range(8):
                item = self.ui.gridLayout.itemAtPosition(row, col + 1)
                if item is not None and item.widget() is not None:
                    button = item.widget()
                    button.setIconSize(QtCore.QSize(60, 60))
                    button.setText("")
                    pos = (row, col)
                    self.squares[pos] = button
                    self.square_by_button[button] = pos
                    label = QtWidgets.QLabel(button)
                    label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignBottom)
                    label.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
                    label.setStyleSheet("color: rgb(220, 0, 0); font-weight: bold; font-size: 20px; background: transparent;")
                    label.setGeometry(button.rect())
                    label.show()
                    self.number_labels[pos] = label
                    button.installEventFilter(self)
                    button.clicked.connect(lambda checked, r=row, c=col: self._on_square_click(r, c))

    def _load_icons(self):
        """Загружает картинки фигур, мины и флажка из папки assets."""
        for color in ("w", "b"):
            for piece_type in "PNRBQK":
                path = resource_path(os.path.join("assets", f"{color}{piece_type}.png"))
                if os.path.exists(path):
                    self.icons[color + piece_type] = QtGui.QIcon(path)
        mine_path = resource_path(os.path.join("assets", "mine.png"))
        flag_path = resource_path(os.path.join("assets", "flag.png"))
        self.mine_icon = QtGui.QIcon(mine_path) if os.path.exists(mine_path) else QtGui.QIcon()
        self.flag_icon = QtGui.QIcon(flag_path) if os.path.exists(flag_path) else QtGui.QIcon()

    def new_game(self):
        """Сброс партии, часов, мин и таблицы ходов."""
        self.engine = ChessBoard()
        self.selected = None
        self.game_over = False
        self.elapsed = 0
        self.white_left = self.game_data["time_limit"] * 60
        self.black_left = self.game_data["time_limit"] * 60
        self.flags = set()
        self.opened = set()
        self.move_count = 0

        for row in range(8):
            for col in range(8):
                if self.engine.get_piece(row, col) is not None:
                    self.opened.add((row, col))

        self._place_mines()
        self.ui.tbl_history.setRowCount(0)
        self._update_clocks()
        self._update_turn_labels()
        self._redraw_board()
        self.clock.start()

        # Сохраняем начальное состояние
        self.save_state()

    def _place_mines(self):
        """Расставляет мины поровну по четырём четвертям поля."""
        self.mines = set()
        per_quadrant = self.mines_count // 4
        quadrants = [
            [(r, c) for r in range(0, 4) for c in range(0, 4)],
            [(r, c) for r in range(0, 4) for c in range(4, 8)],
            [(r, c) for r in range(4, 8) for c in range(0, 4)],
            [(r, c) for r in range(4, 8) for c in range(4, 8)],
        ]
        for quadrant in quadrants:
            empty = [pos for pos in quadrant if pos not in self.opened]
            if len(empty) >= per_quadrant:
                self.mines.update(random.sample(empty, per_quadrant))

    def eventFilter(self, source, event):
        """Правая кнопка мыши — установка/снятие флажка; resize — растянуть лейбл."""
        if event.type() == QtCore.QEvent.MouseButtonPress:
            if event.button() == QtCore.Qt.RightButton:
                pos = self.square_by_button.get(source)
                if pos is not None:
                    self._toggle_flag(pos)
                    return True
        elif event.type() == QtCore.QEvent.Resize:
            pos = self.square_by_button.get(source)
            if pos is not None:
                self.number_labels[pos].setGeometry(source.rect())
        return super().eventFilter(source, event)

    def keyPressEvent(self, event):
        """Обработка нажатий клавиш клавиатуры."""
        if event.key() == QtCore.Qt.Key_N:
            # N — сохранить текущую игру и открыть диалог новой игры
            self._on_new_game_action()
        elif event.key() == QtCore.Qt.Key_K:
            # K — сохранить и выйти из приложения
            self.save_state()
            self.close()
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Сохраняет состояние при закрытии окна."""
        if not self.game_over and self.game_id:
            self.save_state()
        super().closeEvent(event)

    def save_state(self):
        """Сохраняет текущее состояние игры в БД."""
        if not self.game_id or self.game_over:
            return

        # Сериализуем доску
        board_data = []
        for row in range(8):
            row_data = []
            for col in range(8):
                piece = self.engine.board[row][col]
                if piece:
                    row_data.append({
                        "type": piece.type,
                        "color": piece.color,
                        "has_moved": piece.has_moved
                    })
                else:
                    row_data.append(None)
            board_data.append(row_data)

        state = {
            "board": board_data,
            "turn": self.engine.turn,
            "mines": [list(m) for m in self.mines],
            "flags": [list(f) for f in self.flags],
            "opened": [list(o) for o in self.opened],
            "white_left": self.white_left,
            "black_left": self.black_left,
            "elapsed": self.elapsed,
            "move_count": self.move_count
        }

        db.save_game_state(self.game_id, json.dumps(state, ensure_ascii=False))

    def load_state(self, state):
        """Восстанавливает состояние игры из словаря."""
        # Восстанавливаем доску
        for row in range(8):
            for col in range(8):
                data = state["board"][row][col]
                if data:
                    piece = Piece(data["type"], data["color"])
                    piece.has_moved = data["has_moved"]
                    self.engine.board[row][col] = piece
                else:
                    self.engine.board[row][col] = None

        # Восстанавливаем параметры
        self.engine.turn = state["turn"]
        self.mines = set(tuple(m) for m in state["mines"])
        self.flags = set(tuple(f) for f in state["flags"])
        self.opened = set(tuple(o) for o in state["opened"])
        self.white_left = state["white_left"]
        self.black_left = state["black_left"]
        self.elapsed = state["elapsed"]
        self.move_count = state["move_count"]
        self.selected = None
        self.engine.valid_moves = []
        self.game_over = False

        # Загружаем историю ходов в таблицу
        self._load_history_from_db()

        # Обновляем интерфейс
        self._update_clocks()
        self._update_turn_labels()
        self._redraw_board()
        self.clock.start()

    def _load_history_from_db(self):
        """Загружает историю ходов из БД в таблицу."""
        table = self.ui.tbl_history
        table.setRowCount(0)

        if not self.game_id:
            return

        moves = db.get_moves(self.game_id)
        for move_number, elapsed_time, piece, from_pos, to_pos in moves:
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QtWidgets.QTableWidgetItem(elapsed_time))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(piece))
            table.setItem(row, 2, QtWidgets.QTableWidgetItem(f"{from_pos}, {to_pos}"))
        table.scrollToBottom()

    def _on_new_game_action(self):
        """Сохраняет текущую игру и открывает диалог создания новой."""
        self.save_state()
        self._open_new_game_dialog()

    def _open_new_game_dialog(self):
        """Открывает диалог настроек новой партии."""
        from welcome_window import NewGameDialog

        # Останавливаем таймер, пока открыт диалог
        self.clock.stop()

        dialog = NewGameDialog(self)
        result = dialog.exec_()

        if result == QtWidgets.QDialog.Accepted:
            data = dialog.get_game_data()
            game_id = db.create_game(data["name"], data["difficulty"], data["time_limit"])

            # Переключаем окно на новую игру
            self.game_id = game_id
            self.game_data = data
            self.mines_count = DIFFICULTY_MINES.get(data["difficulty"], 4)
            self.new_game()
        else:
            # Пользователь отменил — продолжаем текущую игру
            self.clock.start()

    def _toggle_flag(self, pos):
        """Флажок ставится только на закрытые клетки."""
        if pos in self.opened:
            return
        if pos in self.flags:
            self.flags.discard(pos)
        else:
            self.flags.add(pos)
        self._redraw_board()

    def _on_square_click(self, row, col):
        """Обработка клика левой кнопкой мыши по клетке доски."""
        if self.game_over:
            return
        piece = self.engine.get_piece(row, col)
        if self.selected is not None and (row, col) in self.engine.valid_moves:
            self._do_move(self.selected, (row, col))
            return
        if piece is not None and piece.color == self.engine.turn:
            self.selected = (row, col)
            self.engine.valid_moves = self.engine.get_valid_moves(row, col)
        else:
            self.selected = None
            self.engine.valid_moves = []
        self._redraw_board()

    def _move_path(self, piece, from_pos, to_pos):
        """Клетки, через которые фигура проходит мимо (без клетки приземления)."""
        r1, c1 = from_pos
        r2, c2 = to_pos
        dr = _sign(r2 - r1)
        dc = _sign(c2 - c1)
        if piece.type in ("R", "B", "Q"):
            path = []
            r, c = r1 + dr, c1 + dc
            while (r, c) != (r2, c2):
                path.append((r, c))
                r += dr
                c += dc
            return path
        if piece.type == "P" and abs(r2 - r1) == 2:
            return [(r1 + dr, c1)]
        return []

    def _do_move(self, from_pos, to_pos):
        """Выполняет ход с учётом мин: взрыв, превращение ферзя в ладью, прыжки."""
        piece = self.engine.get_piece(from_pos[0], from_pos[1])
        piece_type = piece.type
        piece_color = piece.color
        first_move = not piece.has_moved
        through = self._move_path(piece, from_pos, to_pos)
        self.engine.make_move(from_pos[0], from_pos[1], to_pos[0], to_pos[1])

        actual_to = to_pos
        flash_square = None
        jump_over = first_move and piece_type == "P"
        hit = None
        if not jump_over:
            for square in through:
                if square in self.mines:
                    hit = square
                    break
        if hit is None and to_pos in self.mines:
            hit = to_pos

        if hit is not None:
            self.mines.discard(hit)
            self.engine.board[to_pos[0]][to_pos[1]] = None
            flash_square = hit
            if piece_color == WHITE:
                self.white_left -= EXPLOSION_PENALTY
            else:
                self.black_left -= EXPLOSION_PENALTY
            self._update_clocks()
            if piece_type == "Q":
                rook = Piece("R", piece_color)
                rook.has_moved = True
                self.engine.board[hit[0]][hit[1]] = rook
                actual_to = hit
            else:
                actual_to = hit
                if piece_type == "K":
                    self.opened.add(from_pos)
                    self.opened.add(hit)
                    self._add_history_row(piece, from_pos, actual_to)
                    self._redraw_board()
                    self._flash_mine(hit)
                    winner = "Чёрные" if piece_color == WHITE else "Белые"
                    self._finish(f"Король взорвался на мине! Победили {winner}!")
                    return

        self.opened.add(from_pos)
        self.opened.add(actual_to)
        if piece_type == "K" and abs(to_pos[1] - from_pos[1]) == 2:
            rook_from = (from_pos[0], 7 if to_pos[1] == 6 else 0)
            rook_to = (from_pos[0], 5 if to_pos[1] == 6 else 3)
            self.opened.add(rook_from)
            self.opened.add(rook_to)

        self._add_history_row(piece, from_pos, actual_to)
        self.selected = None
        self.engine.valid_moves = []
        self._redraw_board()
        if flash_square is not None:
            self._flash_mine(flash_square)
        self._update_turn_labels()

        # Проверка конца игры
        if self.white_left <= 0:
            self._finish("Время белых вышло. Победили Чёрные!")
        elif self.black_left <= 0:
            self._finish("Время чёрных вышло. Победили Белые!")
        elif self.engine.is_checkmate():
            self._finish(f"Мат. Победили {'Белые' if self.engine.turn == BLACK else 'Чёрные'}!")
        elif not self._has_any_move():
            self._finish("Пат. Ничья!")
        else:
            # Сохраняем состояние только если игра продолжается
            self.save_state()

    def _flash_mine(self, pos):
        """Показывает мины в момент взрыва."""
        self.squares[pos].setIcon(self.mine_icon)
        QtCore.QTimer.singleShot(700, self._redraw_board)

    def _neighbor_mines(self, pos):
        """Количество мин в восьми соседних клетках."""
        row, col = pos
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                if (row + dr, col + dc) in self.mines:
                    count += 1
        return count

    def _has_any_move(self):
        """Есть ли у стороны, чей сейчас ход, хоть один легальный ход."""
        for row in range(8):
            for col in range(8):
                piece = self.engine.get_piece(row, col)
                if piece and piece.color == self.engine.turn:
                    if self.engine.get_valid_moves(row, col):
                        return True
        return False

    def _finish(self, message):
        """Останавливает часы, вскрывает мины и показывает итог партии."""
        self.game_over = True
        self.clock.stop()

        # Помечаем игру как завершённую и удаляем сохранённое состояние
        if self.game_id:
            db.mark_game_finished(self.game_id)

        for pos in self.mines:
            self.squares[pos].setIcon(self.mine_icon)

        QtWidgets.QMessageBox.information(self, "Игра окончена", message)

    def _add_history_row(self, piece, from_pos, to_pos):
        """Добавляет ход в таблицу и в БД."""
        self.move_count += 1

        # Добавляем в таблицу интерфейса
        table = self.ui.tbl_history
        row = table.rowCount()
        table.insertRow(row)
        table.setItem(row, 0, QtWidgets.QTableWidgetItem(self._fmt_seconds(self.elapsed)))
        prefix = "б" if piece.color == WHITE else "ч"
        table.setItem(row, 1, QtWidgets.QTableWidgetItem(prefix + PIECE_SYMBOLS[piece.type]))
        coords = f"{self._coord(from_pos)}, {self._coord(to_pos)}"
        table.setItem(row, 2, QtWidgets.QTableWidgetItem(coords))
        table.scrollToBottom()

        # Сохраняем ход в БД
        if self.game_id:
            db.add_move(
                self.game_id,
                self.move_count,
                self._fmt_seconds(self.elapsed),
                prefix + PIECE_SYMBOLS[piece.type],
                self._coord(from_pos),
                self._coord(to_pos)
            )

    def _coord(self, pos):
        """Преобразует (ряд, колонку) в шахматную нотацию: e2, g1 и т.д."""
        row, col = pos
        return FILES[col] + str(8 - row)

    def _tick(self):
        """Одна секунда: общее время партии и часы стороны, чей ход."""
        self.elapsed += 1
        if self.engine.turn == WHITE:
            self.white_left -= 1
        else:
            self.black_left -= 1
        self._update_clocks()
        if self.white_left <= 0:
            self._finish("Время белых вышло. Победили Чёрные!")
        elif self.black_left <= 0:
            self._finish("Время чёрных вышло. Победили Белые!")

    def _update_clocks(self):
        """Таймер белых стоит справа внизу, таймер чёрных — справа вверху."""
        self.ui.black_time.setText(self._fmt_seconds(self.white_left))
        self.ui.white.setText(self._fmt_seconds(self.black_left))

    def _update_turn_labels(self):
        """Видна только надпись стороны, чей ход; текст стирается, а не скрывается."""
        if self.engine.turn == WHITE:
            self.ui.white_time.setText("")
            self.ui.black.setText(LABEL_WHITE)
        else:
            self.ui.white_time.setText(LABEL_BLACK)
            self.ui.black.setText("")

    def _redraw_board(self):
        """Подсветка, светлые открытые клетки, цифры сапёра, флажки и фигуры."""
        for (row, col), button in self.squares.items():
            pos = (row, col)
            if self.selected == pos:
                style = STYLE_SELECTED
            elif pos in self.engine.valid_moves:
                style = STYLE_MOVE
            elif pos in self.opened:
                style = STYLE_OPENED
            else:
                style = ""
            button.setStyleSheet(style)
            count = self._neighbor_mines(pos) if pos in self.opened else 0
            self.number_labels[pos].setText(str(count) if count > 0 else "")
            if pos in self.flags and pos not in self.opened:
                button.setIcon(self.flag_icon)
                continue
            piece = self.engine.get_piece(row, col)
            if piece is None:
                button.setIcon(QtGui.QIcon())
            else:
                key = ("w" if piece.color == WHITE else "b") + piece.type
                button.setIcon(self.icons.get(key, QtGui.QIcon()))

    def _fmt_seconds(self, total):
        """Формат времени мм:сс."""
        minutes, seconds = divmod(max(total, 0), 60)
        return f"{minutes:02d}:{seconds:02d}"


if __name__ == "__main__":
    # Инициализируем БД при запуске
    db.init_db()

    app = QtWidgets.QApplication(sys.argv)

    # Запускаем приветственное окно
    from welcome_window import WelcomeWindow
    window = WelcomeWindow()
    window.show()

    sys.exit(app.exec_())
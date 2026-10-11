"""Модуль для работы с базой данных игры."""

import sqlite3
import os
import sys
from datetime import datetime


def get_db_path():
    """Возвращает путь к файлу базы данных рядом с исполняемым файлом."""
    if getattr(sys, 'frozen', False):
        # Запуск из .exe
        base_path = os.path.dirname(sys.executable)
    else:
        # Запуск из скрипта
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, "minechess.db")


DB_NAME = get_db_path()


def init_db():
    """Инициализация базы данных и создание таблиц."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Таблица 1: Сохранённые партии (добавлено поле state)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            difficulty INTEGER DEFAULT 0,
            time_limit INTEGER DEFAULT 10,
            created_at TEXT,
            is_finished INTEGER DEFAULT 0,
            state TEXT
        )
    ''')

    # Миграция: добавить столбец state если таблица была создана раньше
    try:
        cursor.execute("ALTER TABLE games ADD COLUMN state TEXT")
    except sqlite3.OperationalError:
        pass  # Столбец уже существует

    # Таблица 2: История ходов для каждой партии
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS move_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id INTEGER,
            move_number INTEGER,
            elapsed_time TEXT,
            piece TEXT,
            from_pos TEXT,
            to_pos TEXT,
            FOREIGN KEY (game_id) REFERENCES games (id) ON DELETE CASCADE
        )
    ''')

    conn.commit()
    conn.close()


def create_game(name, difficulty, time_limit):
    """Создаёт новую партию и возвращает её ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO games (name, difficulty, time_limit, created_at, is_finished, state) VALUES (?, ?, ?, ?, 0, NULL)",
        (name, difficulty, time_limit, datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    game_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return game_id


def get_all_games():
    """Возвращает список всех незавершённых партий."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, difficulty, time_limit, created_at FROM games WHERE is_finished = 0 ORDER BY created_at DESC"
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def get_game_by_id(game_id):
    """Возвращает данные партии по ID."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, difficulty, time_limit FROM games WHERE id = ?", (game_id,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0],
            "name": row[1],
            "difficulty": row[2],
            "time_limit": row[3]
        }
    return None


def delete_game(game_id):
    """Удаляет партию и её историю."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM move_history WHERE game_id = ?", (game_id,))
    cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()


def save_game_state(game_id, state_json):
    """Сохраняет состояние игры (JSON) в БД."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE games SET state = ?, is_finished = 0 WHERE id = ?", (state_json, game_id))
    conn.commit()
    conn.close()


def get_game_state(game_id):
    """Возвращает сохранённое состояние игры (JSON-строку)."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT state FROM games WHERE id = ?", (game_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        return row[0]
    return None


def mark_game_finished(game_id):
    """Помечает игру как завершённую и очищает сохранённое состояние."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE games SET is_finished = 1, state = NULL WHERE id = ?", (game_id,))
    conn.commit()
    conn.close()


def add_move(game_id, move_number, elapsed_time, piece, from_pos, to_pos):
    """Добавляет ход в историю."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO move_history (game_id, move_number, elapsed_time, piece, from_pos, to_pos) VALUES (?, ?, ?, ?, ?, ?)",
        (game_id, move_number, elapsed_time, piece, from_pos, to_pos)
    )
    conn.commit()
    conn.close()


def get_moves(game_id):
    """Возвращает все ходы для партии."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT move_number, elapsed_time, piece, from_pos, to_pos FROM move_history WHERE game_id = ? ORDER BY move_number",
        (game_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows
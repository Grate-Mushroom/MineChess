# Константы цветов
WHITE = "white"
BLACK = "black"

class Piece:
    """Класс шахматной фигуры."""
    def __init__(self, piece_type, color):
        self.type = piece_type  # P, R, N, B, Q, K
        self.color = color
        self.has_moved = False

    def __repr__(self):
        return f"{self.color[0]}{self.type}"

class ChessBoard:
    """Движок шахмат: логика доски, правила, проверка шаха и мата."""
    
    def __init__(self):
        self.board = [[None for _ in range(8)] for _ in range(8)]
        self.turn = WHITE
        self.selected_pos = None
        self.valid_moves = []
        self.history = []
        self.init_board()

    def init_board(self):
        """Расстановка фигур в начале игры."""
        back_rank = ["R", "N", "B", "Q", "K", "B", "N", "R"]
        for c in range(8):
            self.board[0][c] = Piece(back_rank[c], BLACK)
            self.board[1][c] = Piece("P", BLACK)
            self.board[6][c] = Piece("P", WHITE)
            self.board[7][c] = Piece(back_rank[c], WHITE)

    def get_piece(self, row, col):
        if 0 <= row < 8 and 0 <= col < 8:
            return self.board[row][col]
        return None

    def is_enemy(self, row, col, color):
        piece = self.get_piece(row, col)
        return piece is not None and piece.color != color

    def is_empty(self, row, col):
        return self.get_piece(row, col) is None

    def get_valid_moves(self, row, col):
        """Возвращает список валидных ходов для фигуры с учетом шаха."""
        piece = self.get_piece(row, col)
        if not piece or piece.color != self.turn:
            return []
        
        moves = []
        r, c = row, col
        
        if piece.type == "P":
            direction = -1 if piece.color == WHITE else 1
            start_row = 6 if piece.color == WHITE else 1
            if self.is_empty(r + direction, c):
                moves.append((r + direction, c))
                if r == start_row and self.is_empty(r + 2 * direction, c):
                    moves.append((r + 2 * direction, c))
            for dc in [-1, 1]:
                if self.is_enemy(r + direction, c + dc, piece.color):
                    moves.append((r + direction, c + dc))
                    
        elif piece.type == "R":
            moves.extend(self._get_line_moves(r, c, piece.color, [(1,0), (-1,0), (0,1), (0,-1)]))
        elif piece.type == "B":
            moves.extend(self._get_line_moves(r, c, piece.color, [(1,1), (1,-1), (-1,1), (-1,-1)]))
        elif piece.type == "Q":
            moves.extend(self._get_line_moves(r, c, piece.color, [(1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1), (-1,1), (-1,-1)]))
        elif piece.type == "N":
            for dr, dc in [(2,1), (2,-1), (-2,1), (-2,-1), (1,2), (1,-2), (-1,2), (-1,-2)]:
                nr, nc = r + dr, c + dc
                if 0 <= nr < 8 and 0 <= nc < 8:
                    target = self.get_piece(nr, nc)
                    if target is None or target.color != piece.color:
                        moves.append((nr, nc))
        elif piece.type == "K":
            for dr in [-1, 0, 1]:
                for dc in [-1, 0, 1]:
                    if dr == 0 and dc == 0: continue
                    nr, nc = r + dr, c + dc
                    if 0 <= nr < 8 and 0 <= nc < 8:
                        target = self.get_piece(nr, nc)
                        if target is None or target.color != piece.color:
                            moves.append((nr, nc))
                            
        # Фильтрация ходов, оставляющих короля под шахом
        return [m for m in moves if self._is_move_legal(r, c, m[0], m[1])]

    def _get_line_moves(self, r, c, color, directions):
        moves = []
        for dr, dc in directions:
            nr, nc = r + dr, c + dc
            while 0 <= nr < 8 and 0 <= nc < 8:
                target = self.get_piece(nr, nc)
                if target is None:
                    moves.append((nr, nc))
                elif target.color != color:
                    moves.append((nr, nc))
                    break
                else:
                    break
                nr += dr
                nc += dc
        return moves

    def _is_move_legal(self, r1, c1, r2, c2):
        """Симуляция хода для проверки, не окажется ли король под шахом."""
        piece1 = self.board[r1][c1]
        piece2 = self.board[r2][c2]
        
        self.board[r2][c2] = piece1
        self.board[r1][c1] = None
        
        in_check = self.is_in_check(piece1.color)
        
        self.board[r1][c1] = piece1
        self.board[r2][c2] = piece2
        return not in_check

    def is_in_check(self, color):
        """Проверка, находится ли король указанного цвета под шахом."""
        king_pos = None
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p and p.type == "K" and p.color == color:
                    king_pos = (r, c)
                    break
            if king_pos: break
            
        if not king_pos: return False
        kr, kc = king_pos
        enemy_color = BLACK if color == WHITE else WHITE
        
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p and p.color == enemy_color:
                    raw_moves = []
                    if p.type == "P":
                        direction = -1 if p.color == WHITE else 1
                        for dc in [-1, 1]: raw_moves.append((r + direction, c + dc))
                    elif p.type == "R":
                        raw_moves.extend(self._get_line_moves(r, c, p.color, [(1,0), (-1,0), (0,1), (0,-1)]))
                    elif p.type == "B":
                        raw_moves.extend(self._get_line_moves(r, c, p.color, [(1,1), (1,-1), (-1,1), (-1,-1)]))
                    elif p.type == "Q":
                        raw_moves.extend(self._get_line_moves(r, c, p.color, [(1,0), (-1,0), (0,1), (0,-1), (1,1), (1,-1), (-1,1), (-1,-1)]))
                    elif p.type == "N":
                        for dr, dc in [(2,1), (2,-1), (-2,1), (-2,-1), (1,2), (1,-2), (-1,2), (-1,-2)]:
                            raw_moves.append((r + dr, c + dc))
                    elif p.type == "K":
                        for dr in [-1, 0, 1]:
                            for dc in [-1, 0, 1]:
                                if dr == 0 and dc == 0: continue
                                raw_moves.append((r + dr, c + dc))
                    if (kr, kc) in raw_moves:
                        return True
        return False

    def make_move(self, r1, c1, r2, c2):
        """Выполнение хода и передача очереди."""
        piece = self.board[r1][c1]
        captured = self.board[r2][c2]
        self.history.append({'from': (r1, c1), 'to': (r2, c2), 'piece': piece, 'captured': captured})
        
        self.board[r2][c2] = piece
        self.board[r1][c1] = None
        piece.has_moved = True
        
        # Превращение пешки в ферзя
        if piece.type == "P" and (r2 == 0 or r2 == 7):
            self.board[r2][c2] = Piece("Q", piece.color)
            
        self.turn = BLACK if self.turn == WHITE else WHITE
        self.selected_pos = None
        self.valid_moves = []
        return captured

    def undo_move(self):
        """Отмена последнего хода."""
        if not self.history: return False
        last = self.history.pop()
        r1, c1 = last['from']
        r2, c2 = last['to']
        self.board[r1][c1] = last['piece']
        self.board[r2][c2] = last['captured']
        self.turn = BLACK if self.turn == WHITE else WHITE
        return True

    def is_checkmate(self):
        """Проверка на мат."""
        if not self.is_in_check(self.turn):
            return False
        for r in range(8):
            for c in range(8):
                p = self.board[r][c]
                if p and p.color == self.turn:
                    if self.get_valid_moves(r, c):
                        return False
        return True
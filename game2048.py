import random
from typing import List, Tuple, Optional

SIZE = 4  # 棋盘大小：4x4
Board = List[List[int]]
Row = List[int]


def new_board() -> Board:
    """创建一个空棋盘。"""
    return [[0] * SIZE for _ in range(SIZE)]


def add_random_tile(board: Board) -> Optional[Tuple[int, int]]:
    """
    在空格随机生成一个 2 或 4
    返回生成的位置 (r, c)，如果棋盘已满返回 None
    """
    empty_cells = [
        (r, c)
        for r in range(SIZE)
        for c in range(SIZE)
        if board[r][c] == 0
    ]
    if not empty_cells:
        return None

    r, c = random.choice(empty_cells)
    board[r][c] = 4 if random.random() < 0.1 else 2
    return r, c


def random_start_board() -> Board:
    """新游戏初始棋盘：随机出现两个数字。"""
    board = new_board()
    add_random_tile(board)
    add_random_tile(board)
    return board


def compress_and_merge_row(row: Row) -> Tuple[Row, int]:
    """
    向左挤压并合并一行，同时返回本行增加的分数。
    例如: [2, 0, 2, 4] -> [4, 4, 0, 0], score_gain = 4
    """
    arr = [x for x in row if x != 0]
    new_row: Row = []
    score_gain = 0
    i = 0

    while i < len(arr):
        if i + 1 < len(arr) and arr[i] == arr[i + 1]:
            merged = arr[i] * 2
            new_row.append(merged)
            score_gain += merged
            i += 2
        else:
            new_row.append(arr[i])
            i += 1

    new_row += [0] * (len(row) - len(new_row))
    return new_row, score_gain


def move_left(board: Board) -> Tuple[Board, int]:
    """整盘向左移动。"""
    new_board_state: Board = []
    total_gain = 0
    for row in board:
        new_row, gain = compress_and_merge_row(row)
        new_board_state.append(new_row)
        total_gain += gain
    return new_board_state, total_gain


def reverse_rows(board: Board) -> Board:
    """每一行做反转。"""
    return [list(reversed(row)) for row in board]


def transpose(board: Board) -> Board:
    """矩阵转置。"""
    return [list(row) for row in zip(*board)]


def move_right(board: Board) -> Tuple[Board, int]:
    """整盘向右移动。"""
    reversed_board = reverse_rows(board)
    moved, gain = move_left(reversed_board)
    return reverse_rows(moved), gain


def move_up(board: Board) -> Tuple[Board, int]:
    """整盘向上移动。"""
    transposed = transpose(board)
    moved, gain = move_left(transposed)
    return transpose(moved), gain


def move_down(board: Board) -> Tuple[Board, int]:
    """整盘向下移动。"""
    transposed = transpose(board)
    moved, gain = move_right(transposed)
    return transpose(moved), gain


def can_move(board: Board) -> bool:
    """判断是否还能继续游戏。"""
    for r in range(SIZE):
        for c in range(SIZE):
            if board[r][c] == 0:
                return True

    for r in range(SIZE):
        for c in range(SIZE - 1):
            if board[r][c] == board[r][c + 1]:
                return True

    for c in range(SIZE):
        for r in range(SIZE - 1):
            if board[r][c] == board[r + 1][c]:
                return True

    return False


def get_max_tile(board: Board) -> int:
    """取得当前最大的数字。"""
    return max(max(row) for row in board)

from flask import Flask, render_template, request, session, redirect, url_for
from game2048 import (
    random_start_board,
    move_left,
    move_right,
    move_up,
    move_down,
    add_random_tile,
    can_move,
    get_max_tile,
)
import copy
import random

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_this_to_a_random_secret_key"

MAX_HISTORY = 20       # 撤回最多保存多少步
POISON_STEPS_LIMIT = 5 # 毒格子连续停留步数上限
POISON_CHANCE = 0.10   # 新生成数字成为毒格子的概率
COUNTDOWN_CHANCE = 0.10  # 新生成数字成为倒计时格子的概率


def copy_grid(grid):
    return [row[:] for row in grid]


def new_bool_grid():
    return [[False for _ in range(4)] for _ in range(4)]


def new_int_grid():
    return [[0 for _ in range(4)] for _ in range(4)]


def init_special_state(board):
    """初始化特殊格子相关状态。"""
    session["poison_active"] = new_bool_grid()     # 是否为毒格子
    session["poison_steps"] = new_int_grid()       # 当前连续停留步数
    session["countdown_active"] = new_bool_grid()  # 是否为倒计时格子
    session["last_values"] = copy_grid(board)      # 上一回合的数字，用于判断是否“未变化”


def start_new_game():
    """初始化一局新游戏。"""
    board = random_start_board()
    session["board"] = board
    session["score"] = 0
    session["game_over"] = False
    session["history"] = []
    init_special_state(board)


def apply_special_cells(board, poison_active, poison_steps,
                        countdown_active, last_values):
    """
    根据当前棋盘和上一回合记录，更新毒格子、倒计时格子的效果。
    说明：
    - 毒格子：非 0 且数字与上一回合相同，则连续停留步数 +1，
      达到上限后数字变为 0，毒格子消失。
    - 倒计时格子：只要格子里有数字，每回合数字减半，减到 0 后格子不再是倒计时格。
    """
    size = len(board)
    for r in range(size):
        for c in range(size):
            val = board[r][c]

            # 毒格子逻辑
            if poison_active[r][c]:
                if val != 0 and val == last_values[r][c]:
                    poison_steps[r][c] += 1
                else:
                    poison_steps[r][c] = 0

                if poison_steps[r][c] >= POISON_STEPS_LIMIT and val != 0:
                    board[r][c] = 0
                    poison_active[r][c] = False
                    poison_steps[r][c] = 0
                    val = 0  # 更新局部变量给下面倒计时使用

            # 倒计时格子逻辑（在毒格子处理之后）
            if countdown_active[r][c] and val > 0:
                val //= 2
                board[r][c] = val
                if val == 0:
                    countdown_active[r][c] = False

    # 更新 last_values，供下一回合比较
    for r in range(size):
        for c in range(size):
            last_values[r][c] = board[r][c]


def maybe_mark_special_cell(r, c, poison_active, poison_steps, countdown_active):
    """
    新生成数字后，按一定概率把该格子标记为毒格子或倒计时格子。
    """
    # 清除原有状态
    poison_active[r][c] = False
    poison_steps[r][c] = 0
    countdown_active[r][c] = False

    roll = random.random()
    if roll < POISON_CHANCE:
        poison_active[r][c] = True
        poison_steps[r][c] = 0
    elif roll < POISON_CHANCE + COUNTDOWN_CHANCE:
        countdown_active[r][c] = True


@app.route("/")
def index():
    if "board" not in session:
        start_new_game()

    board = session["board"]
    score = session.get("score", 0)
    game_over = session.get("game_over", False)
    history = session.get("history", [])
    high_score = session.get("high_score", 0)

    # 初始化特殊状态（兼容旧 session）
    if "poison_active" not in session or "last_values" not in session:
        init_special_state(board)

    poison_active = session.get("poison_active", new_bool_grid())
    countdown_active = session.get("countdown_active", new_bool_grid())

    max_tile = get_max_tile(board)

    return render_template(
        "index.html",
        board=board,
        score=score,
        max_tile=max_tile,
        game_over=game_over,
        high_score=high_score,
        can_undo=bool(history),
        poison_active=poison_active,
        countdown_active=countdown_active,
        max_history=MAX_HISTORY,
    )


@app.route("/move", methods=["POST"])
def move():
    direction = request.form.get("direction")
    board = session.get("board")
    score = session.get("score", 0)
    game_over = session.get("game_over", False)
    history = session.get("history", [])
    high_score = session.get("high_score", 0)
    poison_active = session.get("poison_active", new_bool_grid())
    poison_steps = session.get("poison_steps", new_int_grid())
    countdown_active = session.get("countdown_active", new_bool_grid())
    last_values = session.get("last_values", copy_grid(board))

    if board is None or game_over:
        return redirect(url_for("index"))

    moves = {
        "left": move_left,
        "right": move_right,
        "up": move_up,
        "down": move_down,
    }
    move_func = moves.get(direction)
    if move_func is None:
        return redirect(url_for("index"))

    # 原始棋盘副本（用于比较和写入 history）
    original_board = copy_grid(board)
    original_poison_active = copy_grid(poison_active)
    original_poison_steps = copy_grid(poison_steps)
    original_countdown_active = copy_grid(countdown_active)
    original_last_values = copy_grid(last_values)

    new_board, gain = move_func(board)

    if new_board != original_board:
        # 确实发生移动时，先把当前状态压入历史
        history.append({
            "board": original_board,
            "score": score,
            "poison_active": original_poison_active,
            "poison_steps": original_poison_steps,
            "countdown_active": original_countdown_active,
            "last_values": original_last_values,
        })
        if len(history) > MAX_HISTORY:
            history.pop(0)

        # 先结算上回合遗留的毒格子 / 倒计时格子
        apply_special_cells(new_board, poison_active, poison_steps,
                            countdown_active, last_values)

        # 再生成新数字（以及可能的特殊格子）
        pos = add_random_tile(new_board)
        if pos is not None:
            r, c = pos
            maybe_mark_special_cell(r, c, poison_active, poison_steps, countdown_active)

        score += gain

    # 更新最高分
    if score > high_score:
        high_score = score

    game_over = not can_move(new_board)

    session["board"] = new_board
    session["score"] = score
    session["game_over"] = game_over
    session["history"] = history
    session["high_score"] = high_score
    session["poison_active"] = poison_active
    session["poison_steps"] = poison_steps
    session["countdown_active"] = countdown_active
    session["last_values"] = last_values

    return redirect(url_for("index"))


@app.route("/undo", methods=["POST"])
def undo():
    """撤回一步。"""
    history = session.get("history", [])
    if not history:
        return redirect(url_for("index"))

    last = history.pop()

    session["board"] = last["board"]
    session["score"] = last["score"]
    session["game_over"] = False
    session["poison_active"] = last["poison_active"]
    session["poison_steps"] = last["poison_steps"]
    session["countdown_active"] = last["countdown_active"]
    session["last_values"] = last["last_values"]
    session["history"] = history

    return redirect(url_for("index"))


@app.route("/reset", methods=["POST"])
def reset():
    """重新开始一局游戏（保留最高分）。"""
    high_score = session.get("high_score", 0)
    session.clear()
    session["high_score"] = high_score
    start_new_game()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)

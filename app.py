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
    SIZE,
)
from typing import List, Tuple, Optional, Dict, Any
import random
import time

app = Flask(__name__)
app.config["SECRET_KEY"] = "change_this_to_a_random_secret_key"

# 游戏配置常量
MAX_HISTORY = 20          # 撤回最多保存多少步
POISON_STEPS_LIMIT = 5    # 毒格子连续停留步数上限
POISON_CHANCE = 0.10      # 新生成数字成为毒格子的概率
COUNTDOWN_CHANCE = 0.10   # 新生成数字成为倒计时格子的概率

# 成就系统配置
ACHIEVEMENTS = {
    64: "初出茅庐",
    128: "小有成就",
    256: "渐入佳境",
    512: "登堂入室",
    1024: "炉火纯青",
    2048: "登峰造极",
    4096: "超凡入圣",
    8192: "神乎其技",
}

# 类型别名
Board = List[List[int]]
BoolGrid = List[List[bool]]
IntGrid = List[List[int]]
GameState = Dict[str, Any]


def copy_grid(grid: Board) -> Board:
    """深拷贝二维网格。"""
    return [row[:] for row in grid]


def new_bool_grid() -> BoolGrid:
    """创建新的布尔网格。"""
    return [[False] * SIZE for _ in range(SIZE)]


def new_int_grid() -> IntGrid:
    """创建新的整数网格。"""
    return [[0] * SIZE for _ in range(SIZE)]


def init_special_state(board: Board) -> None:
    """初始化特殊格子相关状态。"""
    session["poison_active"] = new_bool_grid()     # 是否为毒格子
    session["poison_steps"] = new_int_grid()       # 当前连续停留步数
    session["countdown_active"] = new_bool_grid()  # 是否为倒计时格子
    session["last_values"] = copy_grid(board)      # 上一回合的数字，用于判断是否"未变化"


def start_new_game() -> None:
    """初始化一局新游戏。"""
    board = random_start_board()
    session["board"] = board
    session["score"] = 0
    session["game_over"] = False
    session["history"] = []
    session["moves"] = 0  # 移动步数
    session["start_time"] = time.time()  # 游戏开始时间
    session["unlocked_achievements"] = session.get("unlocked_achievements", set())  # 已解锁成就
    init_special_state(board)


def apply_special_cells(
    board: Board,
    poison_active: BoolGrid,
    poison_steps: IntGrid,
    countdown_active: BoolGrid,
    last_values: Board,
) -> None:
    """
    根据当前棋盘和上一回合记录，更新毒格子、倒计时格子的效果。
    
    说明：
    - 毒格子：非 0 且数字与上一回合相同，则连续停留步数 +1，
      达到上限后数字变为 0，毒格子消失。
    - 倒计时格子：只要格子里有数字，每回合数字减半，减到 0 后格子不再是倒计时格。
    """
    for r in range(SIZE):
        for c in range(SIZE):
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
            last_values[r][c] = board[r][c]


def maybe_mark_special_cell(
    r: int,
    c: int,
    poison_active: BoolGrid,
    poison_steps: IntGrid,
    countdown_active: BoolGrid,
) -> None:
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


def get_game_state() -> Tuple[Board, int, bool, List[GameState], int, BoolGrid, BoolGrid, int, float, set]:
    """获取当前游戏状态。"""
    board = session.get("board")
    if board is None:
        start_new_game()
        board = session["board"]

    # 初始化特殊状态（兼容旧 session）
    if "poison_active" not in session or "last_values" not in session:
        init_special_state(board)

    # 初始化新字段（兼容旧 session）
    if "moves" not in session:
        session["moves"] = 0
    if "start_time" not in session:
        session["start_time"] = time.time()
    if "unlocked_achievements" not in session:
        session["unlocked_achievements"] = []

    # 将 list 转换为 set 以便使用
    unlocked_list = session.get("unlocked_achievements", [])
    unlocked_set = set(unlocked_list) if isinstance(unlocked_list, list) else set()

    return (
        session["board"],
        session.get("score", 0),
        session.get("game_over", False),
        session.get("history", []),
        session.get("high_score", 0),
        session.get("poison_active", new_bool_grid()),
        session.get("countdown_active", new_bool_grid()),
        session.get("moves", 0),
        session.get("start_time", time.time()),
        unlocked_set,
    )


@app.route("/")
def index():
    """游戏主页面。"""
    board, score, game_over, history, high_score, poison_active, countdown_active, moves, start_time, unlocked_achievements = get_game_state()
    
    max_tile = get_max_tile(board)
    elapsed_time = time.time() - start_time if start_time else 0
    
    # 检查新成就
    new_achievements = check_achievements(max_tile, unlocked_achievements)
    if new_achievements:
        session["unlocked_achievements"] = list(unlocked_achievements)
    
    # 获取统计信息
    stats = get_game_stats()
    
    # 格式化时间显示
    minutes = int(elapsed_time // 60)
    seconds = int(elapsed_time % 60)
    time_str = f"{minutes:02d}:{seconds:02d}"

    # 将 set 转换为 list 以便在模板中使用
    unlocked_achievements_list = list(unlocked_achievements)

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
        moves=moves,
        time_str=time_str,
        new_achievements=new_achievements,
        unlocked_achievements=unlocked_achievements_list,
        achievements=ACHIEVEMENTS,
        stats=stats,
        poison_steps_limit=POISON_STEPS_LIMIT,
    )


def save_game_state(
    board: Board,
    score: int,
    game_over: bool,
    history: List[GameState],
    high_score: int,
    poison_active: BoolGrid,
    poison_steps: IntGrid,
    countdown_active: BoolGrid,
    last_values: Board,
    moves: int = None,
    unlocked_achievements: set = None,
) -> None:
    """保存游戏状态到 session。"""
    update_dict = {
        "board": board,
        "score": score,
        "game_over": game_over,
        "history": history,
        "high_score": high_score,
        "poison_active": poison_active,
        "poison_steps": poison_steps,
        "countdown_active": countdown_active,
        "last_values": last_values,
    }
    if moves is not None:
        update_dict["moves"] = moves
    if unlocked_achievements is not None:
        # session 不能直接存储 set，需要转换为 list
        session["unlocked_achievements"] = list(unlocked_achievements)
    session.update(update_dict)


def create_history_entry(
    board: Board,
    score: int,
    poison_active: BoolGrid,
    poison_steps: IntGrid,
    countdown_active: BoolGrid,
    last_values: Board,
) -> GameState:
    """创建历史记录条目。"""
    return {
        "board": copy_grid(board),
        "score": score,
        "poison_active": copy_grid(poison_active),
        "poison_steps": copy_grid(poison_steps),
        "countdown_active": copy_grid(countdown_active),
        "last_values": copy_grid(last_values),
    }


def check_achievements(max_tile: int, unlocked_achievements: set) -> List[Tuple[int, str]]:
    """检查并返回新解锁的成就。"""
    new_achievements = []
    for threshold, name in ACHIEVEMENTS.items():
        if max_tile >= threshold and threshold not in unlocked_achievements:
            unlocked_achievements.add(threshold)
            new_achievements.append((threshold, name))
    return new_achievements


def get_game_stats() -> Dict[str, Any]:
    """获取游戏统计信息。"""
    total_games = session.get("total_games", 0)
    total_score = session.get("total_score", 0)
    total_moves = session.get("total_moves", 0)
    total_time = session.get("total_time", 0.0)
    
    avg_score = total_score / total_games if total_games > 0 else 0
    avg_moves = total_moves / total_games if total_games > 0 else 0
    
    return {
        "total_games": total_games,
        "total_score": total_score,
        "total_moves": total_moves,
        "total_time": total_time,
        "avg_score": int(avg_score),
        "avg_moves": int(avg_moves),
    }


# 移动方向映射
MOVE_DIRECTIONS = {
    "left": move_left,
    "right": move_right,
    "up": move_up,
    "down": move_down,
}


@app.route("/move", methods=["POST"])
def move():
    """处理移动操作。"""
    direction = request.form.get("direction")
    board, score, game_over, history, high_score, poison_active, countdown_active, moves, start_time, unlocked_achievements = get_game_state()
    
    if game_over:
        return redirect(url_for("index"))
    
    poison_steps = session.get("poison_steps", new_int_grid())
    last_values = session.get("last_values", copy_grid(board))

    move_func = MOVE_DIRECTIONS.get(direction)
    if move_func is None:
        return redirect(url_for("index"))

    # 保存当前状态到历史记录
    original_state = create_history_entry(
        board, score, poison_active, poison_steps, countdown_active, last_values
    )

    # 执行移动
    new_board, gain = move_func(board)

    if new_board != board:
        # 确实发生移动时，保存历史记录并增加步数
        history.append(original_state)
        if len(history) > MAX_HISTORY:
            history.pop(0)
        moves += 1

        # 结算上回合遗留的毒格子 / 倒计时格子
        apply_special_cells(new_board, poison_active, poison_steps,
                            countdown_active, last_values)

        # 生成新数字（以及可能的特殊格子）
        pos = add_random_tile(new_board)
        if pos is not None:
            r, c = pos
            maybe_mark_special_cell(r, c, poison_active, poison_steps, countdown_active)

        score += gain

    # 更新最高分和游戏状态
    high_score = max(score, high_score)
    game_over = not can_move(new_board)

    # 保存所有状态
    save_game_state(
        new_board, score, game_over, history, high_score,
        poison_active, poison_steps, countdown_active, last_values,
        moves=moves, unlocked_achievements=unlocked_achievements
    )

    return redirect(url_for("index"))


@app.route("/undo", methods=["POST"])
def undo():
    """撤回一步。"""
    history = session.get("history", [])
    if not history:
        return redirect(url_for("index"))

    last_state = history.pop()
    moves = session.get("moves", 0)
    if moves > 0:
        moves -= 1
    
    save_game_state(
        last_state["board"],
        last_state["score"],
        False,  # game_over
        history,
        session.get("high_score", 0),
        last_state["poison_active"],
        last_state["poison_steps"],
        last_state["countdown_active"],
        last_state["last_values"],
        moves=moves,
    )

    return redirect(url_for("index"))


@app.route("/reset", methods=["POST"])
def reset():
    """重新开始一局游戏（保留最高分和统计信息）。"""
    # 保存当前游戏统计
    if not session.get("game_over", False):
        # 如果游戏未结束就重置，不记录统计
        pass
    else:
        # 游戏结束时记录统计
        total_games = session.get("total_games", 0) + 1
        total_score = session.get("total_score", 0) + session.get("score", 0)
        total_moves = session.get("total_moves", 0) + session.get("moves", 0)
        start_time = session.get("start_time", time.time())
        elapsed_time = time.time() - start_time
        total_time = session.get("total_time", 0.0) + elapsed_time
        
        session["total_games"] = total_games
        session["total_score"] = total_score
        session["total_moves"] = total_moves
        session["total_time"] = total_time
    
    # 保留重要数据
    high_score = session.get("high_score", 0)
    unlocked_achievements = session.get("unlocked_achievements", [])
    total_games = session.get("total_games", 0)
    total_score = session.get("total_score", 0)
    total_moves = session.get("total_moves", 0)
    total_time = session.get("total_time", 0.0)
    
    session.clear()
    
    # 恢复重要数据
    session["high_score"] = high_score
    session["unlocked_achievements"] = unlocked_achievements
    session["total_games"] = total_games
    session["total_score"] = total_score
    session["total_moves"] = total_moves
    session["total_time"] = total_time
    
    start_new_game()
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True)

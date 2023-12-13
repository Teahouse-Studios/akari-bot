import math
import random
from typing import Awaitable, Callable, List, Tuple
from core.builtins import Bot
from core.component import module
from core.petal import gained_petal

tic_tac_toe = module('tic_tac_toe',
                     desc='{tic_tac_toe.help.desc}', developers=['Dianliang233'],
                     alias=['ttt', 'tictactoe'])
play_state = {}


def check_winner(board: List[List[int]]):
    # left-right diagonal
    if board[0][0] == board[1][1] == board[2][2] != 0:
        return board[0][0]
    # right-left diagonal
    elif board[0][2] == board[1][1] == board[2][0] != 0:
        return board[0][2]
    for i in range(3):
        # vertical
        if board[i][0] == board[i][1] == board[i][2] != 0:
            return board[i][0]
        # horizontal
        elif board[0][i] == board[1][i] == board[2][i] != 0:
            return board[0][i]
    return None


GameBoard = List[List[int]]
GameCallback = Callable[[List[List[int]]], Awaitable[Tuple[int]]]


class TerminationError(Exception):
    pass


async def game(msg: Bot.MessageSession,
               x_callback: GameCallback,
               o_callback: GameCallback) -> 0 | 1 | 2:
    # 0 = empty; 1 = x; 2 = o
    board = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    while True:
        if not play_state[msg.target.target_id]['active']:
            raise TerminationError
        x = await x_callback(board)
        board[x[0]][x[1]] = 1
        if winner := check_winner(board):
            return winner, board
        spaces = []
        for i in range(3):
            for j in range(3):
                if board[i][j] == 0:
                    spaces.append((i, j))
        if not spaces:
            return 0, board

        o = await o_callback(board)
        board[o[0]][o[1]] = 2
        if winner := check_winner(board):
            return winner, board
        spaces = []
        for i in range(3):
            for j in range(3):
                if board[i][j] == 0:
                    spaces.append((i, j))
        if not spaces:
            return 0, board


def format_board(board: GameBoard):
    return '\n'.join([' '.join(['Ｘ' if i == 1 else 'Ｏ' if i == 2 else '．' for i in row]) for row in board])


def generate_human_callback(msg: Bot.MessageSession, player: str):
    async def callback(board: List[List[int]]):
        await msg.send_message(format_board(board) + f'\n{msg.locale.t("tic_tac_toe.message.turn", player=player)}', quote=False)
        while True:
            if not play_state[msg.target.target_id]['active']:
                raise TerminationError
            wait = await msg.wait_anyone(timeout=3600)
            text = wait.as_display(text_only=True)
            if text == 'stop':
                raise TerminationError
            # remove space
            text = text.replace(' ', '')
            text = text.replace(',', '')
            if len(text) == 1:
                try:
                    digit = int(text)
                except ValueError:
                    continue
                x = (digit - 1) // 3
                y = (digit - 1) % 3
                if board[x][y] == 0:
                    return x, y
                else:
                    continue
            elif len(text) == 2:
                try:
                    x = int(text[0]) - 1
                    y = int(text[1]) - 1
                except ValueError:
                    continue
                if board[x][y] == 0:
                    return x, y
                else:
                    continue
            else:
                continue

    return callback


def is_move_left(board: GameBoard):
    for i in range(3):
        for j in range(3):
            if (board[i][j] == 0):
                return True
    return False


def evaluate(b: GameBoard, worst: bool = False) -> int:
    if worst:
        return 10 if check_winner(b) == 1 else -10 if check_winner(b) == 2 else 0
    return 10 if check_winner(b) == 2 else -10 if check_winner(b) == 1 else 0


def minimax(board: GameBoard, depth: int, is_max: bool, worst: bool = False):
    score = evaluate(board, worst=worst)
    player = 2
    opponent = 1

    if (score == 10):
        return score

    if (score == -10):
        return score

    if (not is_move_left(board)):
        return 0

    # If this maximizer's move
    if (is_max):
        best = -1000

        # Traverse all cells
        for i in range(3):
            for j in range(3):

                # Check if cell is empty
                if (board[i][j] == 0):

                    # Make the move
                    board[i][j] = player

                    # Call minimax recursively and choose
                    # the maximum value
                    best = max(best, minimax(board,
                                             depth + 1,
                                             not is_max, worst=worst))

                    # Undo the move
                    board[i][j] = 0
        return best

    # If this minimizer's move
    else:
        best = 1000

        # Traverse all cells
        for i in range(3):
            for j in range(3):

                # Check if cell is empty
                if (board[i][j] == 0):

                    # Make the move
                    board[i][j] = opponent

                    # Call minimax recursively and choose
                    # the minimum value
                    best = min(best, minimax(board, depth + 1, not is_max, worst=worst))

                    # Undo the move
                    board[i][j] = 0
        return best


def find_best_move(board, worst=False):
    player = 2
    # opponent = 1
    best_val = -1000
    best_move = (-1, -1)

    # Traverse all cells, evaluate minimax function for
    # all empty cells. And return the cell with optimal
    # value.
    for i in range(3):
        for j in range(3):

            # Check if cell is empty
            if (board[i][j] == 0):

                # Make the move
                board[i][j] = player
                # compute evaluation function for this
                # move.
                move_val = minimax(board, 0, False, worst=False)

                # Undo the move
                board[i][j] = 0

                # If the value of the current move is
                # more than the best value, then update
                # best/
                if (move_val > best_val):
                    best_move = (i, j)
                    best_val = move_val

    return best_move


async def master_bot_callback(board: GameBoard):
    return find_best_move(board)


async def noob_bot_callback(board: GameBoard):
    return find_best_move(board, worst=True)


async def expert_bot_callback(board: GameBoard):
    if random.randint(0, 4) == 0:
        return await random_bot_callback(board)
    return find_best_move(board)


async def random_bot_callback(board: GameBoard):
    random_spaces = []
    for i in range(3):
        for j in range(3):
            if board[i][j] == 0:
                random_spaces.append((i, j))
    return random.choice(random_spaces)


@tic_tac_toe.command('stop {{game.help.stop}}')
async def terminate(msg: Bot.MessageSession):
    state = play_state.get(msg.target.target_id, {})  # 尝试获取 play_state 中是否有此对象的游戏状态
    if state:  # 若有
        if state['active']:  # 检查是否为活跃状态
            play_state[msg.target.target_id]['active'] = False  # 标记为非活跃状态
            await msg.finish(msg.locale.t('game.message.stop'))
        else:
            await msg.finish(msg.locale.t('game.message.stop.none'))
    else:
        await msg.finish(msg.locale.t('game.message.stop.none'))


@tic_tac_toe.command('{{tic_tac_toe.help}}')
@tic_tac_toe.command('noob {{tic_tac_toe.noob.help}}')
@tic_tac_toe.command('expert {{tic_tac_toe.expert.help}}')
@tic_tac_toe.command('master {{tic_tac_toe.master.help}}')
async def ttt_with_bot(msg: Bot.MessageSession):
    if msg.parsed_msg:
        if 'expert' in msg.parsed_msg:
            game_type = 'expert'
            bot_callback = expert_bot_callback
        elif 'master' in msg.parsed_msg:
            game_type = 'master'
            bot_callback = master_bot_callback
        elif 'noob' in msg.parsed_msg:
            game_type = 'noob'
            bot_callback = noob_bot_callback
    else:
        game_type = 'random'
        bot_callback = random_bot_callback
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        await msg.finish(msg.locale.t('game.message.running'))
    play_state.update({msg.target.target_id: {'active': True}})

    try:
        winner, board = await game(msg, generate_human_callback(msg, 'X'), bot_callback)
    except TerminationError:
        return

    play_state[msg.target.target_id]['active'] = False
    g_msg = ''
    if winner == 0:
        await msg.finish(format_board(board) + '\n' + msg.locale.t('tic_tac_toe.message.draw'), quote=False)
    if winner == 1:
        if game_type == 'random' and (reward := await gained_petal(msg, 1)):
            g_msg = '\n' + reward
        if game_type == 'expert' and (reward := await gained_petal(msg, 2)):
            g_msg = '\n' + reward
    await msg.finish(format_board(board) + '\n' + msg.locale.t('tic_tac_toe.message.winner', winner='X' if winner == 1 else 'O') + g_msg, quote=False)


@tic_tac_toe.command('duo {{tic_tac_toe.duo.help}}')
async def ttt_multiplayer(msg: Bot.MessageSession):
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        await msg.finish(msg.locale.t('game.message.running'))
    play_state.update({msg.target.target_id: {'active': True}})

    try:
        winner, board = await game(msg, generate_human_callback(msg, 'X'), generate_human_callback(msg, 'O'))
    except TerminationError:
        return

    play_state[msg.target.target_id]['active'] = False
    if winner == 0:
        await msg.finish(format_board(board) + '\n' + msg.locale.t('tic_tac_toe.message.draw'), quote=False)
    await msg.finish(format_board(board) + '\n' + msg.locale.t('tic_tac_toe.message.winner', winner='X' if winner == 1 else 'O'), quote=False)

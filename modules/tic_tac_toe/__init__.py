import random
from typing import Awaitable, Callable, List
from core.builtins import Bot
from core.component import module
from core.utils.cooldown import CoolDown
from modules.core.su_utils import gained_petal

tic_tac_toe = module('tic_tac_toe',
                     desc='{ttt.help.desc}', developers=['Dianliang233'], alias={
                         'ttt': 'tic_tac_toe',
                         'tictactoe': 'tic_tac_toe',
                     })
play_state = {}


def check_winner(table: List[List[int]]):
    # left-right diagonal
    if table[0][0] == table[1][1] == table[2][2] != 0:
        return table[0][0]
    # right-left diagonal
    elif table[0][2] == table[1][1] == table[2][0] != 0:
        return table[0][2]
    for i in range(3):
        # vertical
        if table[i][0] == table[i][1] == table[i][2] != 0:
            return table[i][0]
        # horizontal
        elif table[0][i] == table[1][i] == table[2][i] != 0:
            return table[0][i]
    return None


GameTable = List[List[int]]
GameCallback = Callable[[List[List[int]]], Awaitable[tuple[int]]]


class TerminationError(Exception):
    pass


async def game(msg: Bot.MessageSession,
               x_callback: GameCallback,
               o_callback: GameCallback) -> 0 | 1 | 2:
    # 0 = empty; 1 = x; 2 = o
    table = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    while True:
        if not play_state[msg.target.target_id]['active']:
            raise TerminationError
        x = await x_callback(table)
        table[x[0]][x[1]] = 1
        if winner := check_winner(table):
            return winner, table
        spaces = []
        for i in range(3):
            for j in range(3):
                if table[i][j] == 0:
                    spaces.append((i, j))
        if not spaces:
            return 0, table

        o = await o_callback(table)
        table[o[0]][o[1]] = 2
        if winner := check_winner(table):
            return winner, table
        spaces = []
        for i in range(3):
            for j in range(3):
                if table[i][j] == 0:
                    spaces.append((i, j))
        if not spaces:
            return 0, table


def format_table(table: GameTable):
    return '\n'.join([' '.join(['Ｘ' if i == 1 else 'Ｏ' if i == 2 else '．' for i in row]) for row in table])


def generate_human_callback(msg: Bot.MessageSession, player: str):
    async def callback(table: List[List[int]]):
        await msg.send_message(format_table(table) + f'\n{msg.locale.t("ttt.turn.message", player=player)}', quote=False)
        while True:
            if not play_state[msg.target.target_id]['active']:
                raise TerminationError
            wait = await msg.wait_anyone()
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
                if table[x][y] == 0:
                    return x, y
                else:
                    continue
            elif len(text) == 2:
                try:
                    x = int(text[0]) - 1
                    y = int(text[1]) - 1
                except ValueError:
                    continue
                if table[x][y] == 0:
                    return x, y
                else:
                    continue
            else:
                continue

    return callback


async def expert_bot_callback(table: GameTable):
    # Win: If the player has two in a row, they can place a third to get three in a row.
    # Block: If the opponent has two in a row, the player must play the third themselves to block the opponent.
    for i in range(3):
        if table[i][0] == table[i][1] and table[i][2] == 0:
            return i, 2
        elif table[i][1] == table[i][2] and table[i][0] == 0:
            return i, 0
        elif table[i][0] == table[i][2] and table[i][1] == 0:
            return i, 1
    for i in range(3):
        if table[0][i] == table[1][i] and table[2][i] == 0:
            return 2, i
        elif table[1][i] == table[2][i] and table[0][i] == 0:
            return 0, i
        elif table[0][i] == table[2][i] and table[1][i] == 0:
            return 1, i
    if table[0][0] == table[1][1] and table[2][2] == 0:
        return 2, 2
    elif table[1][1] == table[2][2] and table[0][0] == 0:
        return 0, 0
    elif table[0][0] == table[2][2] and table[1][1] == 0:
        return 1, 1
    elif table[0][2] == table[1][1] and table[2][0] == 0:
        return 2, 0
    elif table[1][1] == table[2][0] and table[0][2] == 0:
        return 0, 2
    elif table[0][2] == table[2][0] and table[1][1] == 0:
        return 1, 1

    spaces = []
    for i in range(3):
        for j in range(3):
            if table[i][j] == 0:
                spaces.append((i, j))

    # first move
    if len(spaces) == 8:
        # 1 goes center
        if table[1][1] == 1:
            return random.choice([(0, 0), (0, 2), (2, 0), (2, 2)])
        # 1 goes corner/edge
        else:
            return 1, 1

    # second move
    if len(spaces) == 6:
        # 1 goes corner and 2 goes center and 1 goes corner, then 2 goes to any edge
        if table[1][1] == 2 and any([table[0][0] == table[2][2] == 1, table[0][2] == table[2][0] == 1]):
            return random.choice([(0, 1), (1, 0), (1, 2), (2, 1)])

    # prefer corner to edge
    corners = (0, 0), (0, 2), (2, 0), (2, 2)
    for corner in random.shuffle(corners):
        if corner in spaces:
            return corner
    edges = (0, 1), (1, 0), (1, 2), (2, 1)
    for edge in random.shuffle(edges):
        if edge in spaces:
            return edge
    return random.choice(spaces)


async def random_bot_callback(table: GameTable):
    random_spaces = []
    for i in range(3):
        for j in range(3):
            if table[i][j] == 0:
                random_spaces.append((i, j))
    return random.choice(random_spaces)


@tic_tac_toe.command('stop {{ttt.stop.help}}')
async def terminate(msg: Bot.MessageSession):
    state = play_state.get(msg.target.target_id, {})  # 尝试获取 play_state 中是否有此对象的游戏状态
    if state:  # 若有
        if state['active']:  # 检查是否为活跃状态
            play_state[msg.target.target_id]['active'] = False  # 标记为非活跃状态
            await msg.finish(msg.locale.t('ttt.stop.message'), quote=False)
        else:
            await msg.finish(msg.locale.t('ttt.stop.message.none'))
    else:
        await msg.finish(msg.locale.t('ttt.stop.message.none'))


@tic_tac_toe.command('{{ttt.bot.help}}')
@tic_tac_toe.command('expert {{ttt.expert.help}}')
async def ttt_with_bot(msg: Bot.MessageSession):
    if msg.target.target_from != 'TEST|Console':
        qc = CoolDown('fish', msg)
        c = qc.check(60)
        if c != 0:
            await msg.finish(msg.locale.t('message.cooldown', time=int(c), cd_time='60'))
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        return await terminate(msg)
    play_state.update({msg.target.target_id: {'active': True}})

    try:
        winner, table = await game(msg, generate_human_callback(msg, 'X'), expert_bot_callback if msg.parsed_msg else random_bot_callback)
    except TerminationError:
        return

    play_state[msg.target.target_id]['active'] = False
    if winner == 0:
        await msg.finish(msg.locale.t('ttt.draw'), quote=False)
    g_msg = '\n' + gained_petal(msg, 2) if winner == 1 and msg.parsed_msg else ''
    await msg.finish(format_table(table) + '\n' + msg.locale.t('ttt.winner', winner='X' if winner == 1 else 'O') + g_msg, quote=False)


@tic_tac_toe.command('duo {{ttt.duo.help}}')
async def ttt_multiplayer(msg: Bot.MessageSession):
    if msg.target.target_from != 'TEST|Console':
        qc = CoolDown('fish', msg)
        c = qc.check(60)
        if c != 0:
            await msg.finish(msg.locale.t('message.cooldown', time=int(c), cd_time='60'))
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        return await terminate(msg)
    play_state.update({msg.target.target_id: {'active': True}})

    try:
        winner, table = await game(msg, generate_human_callback(msg, 'X'), generate_human_callback(msg, 'O'))
    except TerminationError:
        return

    play_state[msg.target.target_id]['active'] = False
    if winner == 0:
        await msg.finish(msg.locale.t('ttt.draw'), quote=False)
    await msg.finish(format_table(table) + '\n' + msg.locale.t('ttt.winner', winner='X' if winner == 1 else 'O'), quote=False)

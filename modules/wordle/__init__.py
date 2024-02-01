from collections import Counter
from enum import Enum
from itertools import count
import os
import random
from typing import List
import unicodedata
from attr import define, field
from sympy import false
from core.builtins import Bot
from core.component import module
from core.petal import gained_petal

wordle = module('wordle',
                desc='{wordle.help.desc}', developers=['Dianliang233'],
                )
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'words.txt'), encoding='utf8') as handle:
    word_list = handle.read().splitlines()
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'answers.txt'), encoding='utf8') as handle:
    answers_list = handle.read().splitlines()
play_state = {}


class WordleState(Enum):
    GREEN = 0
    YELLOW = 1
    GREY = 2


@define
class WordleBoard:
    word: str
    board: List[str] = field(factory=list)

    def add_word(self, word: str):
        self.board.append(word)
        return self.test_board()

    def verify_word(self, word: str):
        return True if word in word_list else False

    def test_board(self):
        state: List[List[WordleState]] = []
        for row in self.board:
            state.append(self.test_word(row))
        return state

    def test_word(self, word: str):
        state: List[WordleState] = [
            WordleState.GREY,
            WordleState.GREY,
            WordleState.GREY,
            WordleState.GREY,
            WordleState.GREY]
        counter = Counter(self.word)

        for index, letter in enumerate(word):
            if letter == self.word[index]:
                state[index] = WordleState.GREEN
                counter[letter] -= 1

        for index, letter in enumerate(word):
            if letter != self.word[index] and letter in self.word and counter[letter] != 0:
                state[index] = WordleState.YELLOW
                counter[letter] -= 1

        return state

    def get_trials(self):
        return len(self.board) + 1

    def format_board(self):
        green = '🟩'
        yellow = '🟨'
        grey = '⬜'

        formatted = []
        board = self.test_board()
        for row_index, row in enumerate(board):
            letters = []
            squares = []
            for char_index, char in enumerate(row):
                letters.append(
                    unicodedata.lookup(
                        'FULLWIDTH LATIN CAPITAL LETTER ' +
                        self.board[row_index][char_index]))
                if char == WordleState.GREEN:
                    squares.append(green)
                elif char == WordleState.YELLOW:
                    squares.append(yellow)
                elif char == WordleState.GREY:
                    squares.append(grey)
            formatted.append(letters)
            formatted.append(squares)

        return '\n'.join(''.join(row) for row in formatted)

    def is_game_over(self):
        return True if len(self.board) == 0 or all(self.word == self.board[-1]) else False

    @staticmethod
    def from_random_word():
        return WordleBoard(random.choice(answers_list))


@wordle.command('{{wordle.help}}')
async def _(msg: Bot.MessageSession):
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        await msg.finish(msg.locale.t('game.message.running'))
    play_state.update({msg.target.target_id: {'active': True}})

    board = WordleBoard.from_random_word()

    await msg.send_message(msg.locale.t('wordle.message.start'))

    while board.get_trials() <= 6 and play_state[msg.target.target_id]['active'] and not board.is_game_over():
        if not play_state[msg.target.target_id]['active']:
            return
        wait = await msg.wait_next_message(timeout=3600)
        if not play_state[msg.target.target_id]['active']:
            return
        word = wait.as_display(text_only=True).strip().lower()
        if len(word) != 5:
            continue
        if not board.verify_word(word):
            await wait.send_message(msg.locale.t('wordle.message.not_a_word'))
            continue
        board.add_word(word)

        if not board.is_game_over():
            await wait.send_message(board.format_board())

    play_state[msg.target.target_id]['active'] = False
    g_msg = msg.locale.t('wordle.message.finish', answer=board.word)
    if board.board[-1] == board.word and (reward := await gained_petal(msg, 1)):
        g_msg = '\n' + reward
    await msg.finish(board.format_board() + '\n' + g_msg, quote=False)


@wordle.command('stop {{game.help.stop}}')
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

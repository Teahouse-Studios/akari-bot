import os
from enum import Enum
from typing import List

from attr import define, field
from collections import Counter
from PIL import Image, ImageDraw, ImageFont
import random
import unicodedata

from config import Config
from core.builtins import Bot, Plain, Image as BImage
from core.component import module
from core.logger import Logger
from core.petal import gained_petal
from core.utils.cooldown import CoolDown

text_mode = Config('wordle_disable_image')

wordle = module('wordle',
                desc='{wordle.help.desc}', developers=['Dianliang233', 'DoroWolf']
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

        formatted: List[List[str]] = []
        board = self.test_board()
        for row_index, row in enumerate(board):
            letters: List[str] = []
            squares: List[str] = []
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
        return True if len(self.board) != 0 and self.word == self.board[-1] else False

    @staticmethod
    def from_random_word():
        return WordleBoard(random.choice(answers_list))

    def reset_board(self):
        self.word = ""
        self.board = []


@define
class WordleBoardImage:
    image: Image.Image
    wordle_board: WordleBoard
    dark_theme: bool
    outline_color: tuple[int, int, int]
    background_color: str
    cell_size = 50
    margin = 10
    outline_width = 2
    rows = 6
    columns = 5
    green_color = (107, 169, 100)
    yellow_color = (201, 180, 88)
    grey_color = (120, 124, 126)
    font_path = 'assets/Noto Sans CJK Bold.otf'

    def __init__(self, wordle_board: WordleBoard, dark_theme: bool):
        self.wordle_board = wordle_board
        self.dark_theme = dark_theme
        self.outline_color = (58, 58, 60) if dark_theme else (211, 214, 218)
        self.background_color = 'black' if dark_theme else 'white'

        width = self.columns * (self.cell_size + self.margin) + self.margin
        height = self.rows * (self.cell_size + self.margin) + self.margin

        image = Image.new('RGB', (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        for row in range(self.rows):
            for col in range(self.columns):
                x = col * (self.cell_size + self.margin) + self.margin
                y = row * (self.cell_size + self.margin) + self.margin

                draw.rectangle((x, y, x + self.cell_size, y + self.cell_size),
                               fill=None, outline=self.outline_color, width=self.outline_width)

        self.image = image

    def update_board(self):
        draw = ImageDraw.Draw(self.image)
        font_size = int(self.cell_size * 0.8)
        font = ImageFont.truetype(self.font_path, font_size)

        for row_index, row in enumerate(self.wordle_board.test_board()):
            for col_index, square in enumerate(row):
                x = col_index * (self.cell_size + self.margin) + self.margin
                y = row_index * (self.cell_size + self.margin) + self.margin

                if square == WordleState.GREEN:
                    color = self.green_color
                elif square == WordleState.YELLOW:
                    color = self.yellow_color
                else:
                    color = self.grey_color

                draw.rectangle((x, y, x + self.cell_size, y + self.cell_size), fill=color, outline=None)

                letter = self.wordle_board.board[row_index][col_index].upper()
                _, _, width, height = draw.textbbox((0, 0), letter, font=font)
                text_position = (x + (self.cell_size - width) // 2, y + (self.cell_size - height) // 2 - 3)

                draw.text(text_position, letter, fill="white", font=font)


@wordle.command('{{wordle.help}}')
async def _(msg: Bot.MessageSession):
    if msg.target.target_id in play_state and play_state[msg.target.target_id]['active']:
        await msg.finish(msg.locale.t('game.message.running'))

    qc = CoolDown('wordle', msg, all=True)
    if not msg.target.target_from == 'TEST|Console' and not msg.check_super_user():
        c = qc.check(30)
        if c != 0:
            await msg.finish(msg.locale.t('message.cooldown', time=int(c), cd_time=30))

    board = WordleBoard.from_random_word()
    board_image = WordleBoardImage(wordle_board=board, dark_theme=msg.data.options.get('wordle_dark_theme'))

    play_state[msg.target.target_id] = {'answer': board.word, 'active': True}

    Logger.info(f'Answer: {board.word}')
    if text_mode:
        await msg.send_message(msg.locale.t('wordle.message.start'))
    else:
        await msg.send_message([BImage(board_image.image), Plain(msg.locale.t('wordle.message.start'))])

    while board.get_trials() <= 6 and play_state[msg.target.target_id]['active'] and not board.is_game_over():
        if not play_state[msg.target.target_id]['active']:
            return
        wait = await msg.wait_anyone(timeout=3600)
        if not play_state[msg.target.target_id]['active']:
            return
        word = wait.as_display(text_only=True).strip().lower()
        if len(word) != 5 or not (word.isalpha() and word.isascii()):
            continue
        if not board.verify_word(word):
            await wait.send_message(msg.locale.t('wordle.message.not_a_word'))
            continue
        board.add_word(word)
        board_image.update_board()
        await msg.sleep(2)  # 防冲突

        if not board.is_game_over() and board.get_trials() <= 6:
            Logger.info(f'{word} != {board.word}, attempt {board.get_trials() - 1}')
            if text_mode:
                await wait.send_message(board.format_board())
            else:
                await wait.send_message([BImage(board_image.image)])

    play_state[msg.target.target_id]['active'] = False
    attempt = board.get_trials() - 1
    g_msg = msg.locale.t('wordle.message.finish', answer=board.word)
    if board.board[-1] == board.word:
        g_msg = msg.locale.t('wordle.message.finish.success', attempt=attempt)
        petal = 2 if attempt <= 3 else 1
        if reward := await gained_petal(msg, petal):
            g_msg += '\n' + reward
    qc.reset()
    if text_mode:
        await msg.finish(board.format_board() + '\n' + g_msg, quote=False)
    else:
        await msg.finish([BImage(board_image.image), Plain(g_msg)], quote=False)


@wordle.command('stop {{game.help.stop}}')
async def terminate(msg: Bot.MessageSession):
    board = WordleBoard.from_random_word()
    qc = CoolDown('wordle', msg, all=True)
    state = play_state.get(msg.target.target_id, {})  # 尝试获取 play_state 中是否有此对象的游戏状态
    if state:
        if state['active']:  # 检查是否为活跃状态
            play_state[msg.target.target_id]['active'] = False
            board.reset_board()
            qc.reset()
            await msg.finish(msg.locale.t('wordle.message.stop', answer=state['answer']))
        else:
            await msg.finish(msg.locale.t('game.message.stop.none'))
    else:
        await msg.finish(msg.locale.t('game.message.stop.none'))

if not text_mode:
    @wordle.command('theme {{wordle.help.theme}}')
    async def _(msg: Bot.MessageSession):
        dark_theme = msg.data.options.get('wordle_dark_theme')

        if dark_theme:
            msg.data.edit_option('wordle_dark_theme', False)
            await msg.finish(msg.locale.t("wordle.message.theme.disable"))
        else:
            msg.data.edit_option('wordle_dark_theme', True)
            await msg.finish(msg.locale.t("wordle.message.theme.enable"))

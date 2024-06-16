import os
from enum import Enum
from typing import List, Optional

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
from core.utils.game import PlayState

text_mode = Config('wordle_disable_image', False)

wordle = module('wordle',
                desc='{wordle.help.desc}', developers=['Dianliang233', 'DoroWolf']
                )
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'words.txt'), encoding='utf8') as handle:
    word_list = handle.read().splitlines()
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'answers.txt'), encoding='utf8') as handle:
    answers_list = handle.read().splitlines()


class WordleState(Enum):
    GREEN = 0
    YELLOW = 1
    GREY = 2


@define
class WordleBoard:
    word: str
    board: List[str] = field(factory=list)

    def add_word(self, word: str, last_word: Optional[str] = None):
        if last_word:
            last_word_state = self.test_word(last_word)
            yellow_letters = {}
            for index, state in enumerate(last_word_state):
                if state == WordleState.YELLOW:
                    letter = last_word[index]
                    if letter not in yellow_letters:
                        yellow_letters[letter] = 0
                    yellow_letters[letter] += 1
            for letter, count in yellow_letters.items():
                if word.count(letter) < count:
                    return False

            for index, state in enumerate(last_word_state):
                if state == WordleState.GREEN and self.word[index] != word[index]:
                    return False

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
@wordle.command('hard {{wordle.help.hard}}')
async def _(msg: Bot.MessageSession):
    play_state = PlayState('wordle', msg, all=True)
    if play_state.check():
        await msg.finish(msg.locale.t('game.message.running'))

    qc = CoolDown('wordle', msg, all=True)
    if not msg.target.target_from == 'TEST|Console' and not msg.check_super_user():
        c = qc.check(150)
        if c != 0:
            await msg.finish(msg.locale.t('message.cooldown', time=int(150 - c)))

    board = WordleBoard.from_random_word()
    hard_mode = True if msg.parsed_msg else False
    last_word = None
    board_image = WordleBoardImage(wordle_board=board, dark_theme=msg.data.options.get('wordle_dark_theme'))

    play_state.enable()
    play_state.update(answer=board.word)
    Logger.info(f'Answer: {board.word}')
    if text_mode:
        start_msg = msg.locale.t('wordle.message.start')
        if hard_mode:
            start_msg += '\n' + msg.locale.t('wordle.message.hard')
    else:
        start_msg = [BImage(board_image.image), Plain(msg.locale.t('wordle.message.start'))]
        if hard_mode:
            start_msg.append(Plain(msg.locale.t('wordle.message.hard')))
    await msg.send_message(start_msg)

    while board.get_trials() <= 6 and play_state.check() and not board.is_game_over():
        if not play_state.check():
            return
        wait = await msg.wait_anyone(timeout=None)
        if not play_state.check():
            return
        word = wait.as_display(text_only=True).strip().lower()
        if len(word) != 5 or not (word.isalpha() and word.isascii()):
            continue
        if not board.verify_word(word):
            await wait.send_message(msg.locale.t('wordle.message.not_a_word'))
            continue
        if not board.add_word(word, last_word):
            await wait.send_message(msg.locale.t('wordle.message.hard.not_matched'))
            continue
        if hard_mode:
            last_word = word
        board_image.update_board()
        await msg.sleep(2)  # 防冲突

        if not board.is_game_over() and board.get_trials() <= 6:
            Logger.info(f'{word} != {board.word}, attempt {board.get_trials() - 1}')
            if text_mode:
                await wait.send_message(board.format_board())
            else:
                await wait.send_message([BImage(board_image.image)])

    play_state.disable()
    attempt = board.get_trials() - 1
    g_msg = msg.locale.t('wordle.message.finish', answer=board.word)
    if board.board[-1] == board.word:
        g_msg = msg.locale.t('wordle.message.finish.success', attempt=attempt)
        petal = 2 if attempt <= 3 else 1
        petal += 1 if hard_mode else 0
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
    play_state = PlayState('wordle', msg, all=True)
    qc = CoolDown('wordle', msg, all=True)
    if play_state.check():
        play_state.disable()
        board.reset_board()
        qc.reset()
        await msg.finish(msg.locale.t('wordle.message.stop', answer=play_state.check('answer')))
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

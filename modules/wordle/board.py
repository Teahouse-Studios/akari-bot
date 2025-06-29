import os
from collections import Counter
from enum import Enum
from typing import List, Optional

import unicodedata
from PIL import Image, ImageDraw, ImageFont
from attrs import define, field

from core.constants.path import assets_path, noto_sans_bold_path
from core.utils.random import Random

words_txt = os.path.join(assets_path, "modules", "wordle", "words.txt")
answers_txt = os.path.join(assets_path, "modules", "wordle", "answers.txt")
with open(words_txt, encoding="utf8") as handle:
    word_list = handle.read().splitlines()
with open(answers_txt, encoding="utf8") as handle:
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

    @staticmethod
    def verify_word(word: str):
        return word in word_list

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
            WordleState.GREY,
        ]
        counter = Counter(self.word)

        for index, letter in enumerate(word):
            if letter == self.word[index]:
                state[index] = WordleState.GREEN
                counter[letter] -= 1

        for index, letter in enumerate(word):
            if (
                letter != self.word[index]
                and letter in self.word
                and counter[letter] != 0
            ):
                state[index] = WordleState.YELLOW
                counter[letter] -= 1

        return state

    def get_trials(self):
        return len(self.board) + 1

    def format_board(self):
        green = "🟩"
        yellow = "🟨"
        grey = "⬜"

        formatted: List[List[str]] = []
        board = self.test_board()
        for row_index, row in enumerate(board):
            letters: List[str] = []
            squares: List[str] = []
            for char_index, char in enumerate(row):
                letters.append(
                    unicodedata.lookup(
                        "FULLWIDTH LATIN CAPITAL LETTER "
                        + self.board[row_index][char_index]
                    )
                )
                if char == WordleState.GREEN:
                    squares.append(green)
                elif char == WordleState.YELLOW:
                    squares.append(yellow)
                elif char == WordleState.GREY:
                    squares.append(grey)
            formatted.append(letters)
            formatted.append(squares)

        return "\n".join("".join(row) for row in formatted)

    def is_game_over(self):
        return bool(
            len(self.board) != 0
            and (self.word == self.board[-1] or len(self.board) >= 6)
        )

    @staticmethod
    def from_random_word():
        return WordleBoard(Random.choice(answers_list))

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

    def __init__(self, wordle_board: WordleBoard, dark_theme: bool):
        self.wordle_board = wordle_board
        self.dark_theme = dark_theme
        self.outline_color = (58, 58, 60) if dark_theme else (211, 214, 218)
        self.background_color = "black" if dark_theme else "white"

        width = self.columns * (self.cell_size + self.margin) + self.margin
        height = self.rows * (self.cell_size + self.margin) + self.margin

        image = Image.new("RGB", (width, height), self.background_color)
        draw = ImageDraw.Draw(image)

        for row in range(self.rows):
            for col in range(self.columns):
                x = col * (self.cell_size + self.margin) + self.margin
                y = row * (self.cell_size + self.margin) + self.margin

                draw.rectangle(
                    (x, y, x + self.cell_size, y + self.cell_size),
                    fill=None,
                    outline=self.outline_color,
                    width=self.outline_width,
                )

        self.image = image

    def update_board(self):
        draw = ImageDraw.Draw(self.image)
        font_size = int(self.cell_size * 0.8)
        font = ImageFont.truetype(noto_sans_bold_path, font_size)

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

                draw.rectangle(
                    (x, y, x + self.cell_size, y + self.cell_size),
                    fill=color,
                    outline=None,
                )

                letter = self.wordle_board.board[row_index][col_index].upper()
                _, _, width, height = draw.textbbox((0, 0), letter, font=font)
                text_position = (
                    x + (self.cell_size - width) // 2,
                    y + (self.cell_size - height) // 2 - 3,
                )

                draw.text(text_position, letter, fill="white", font=font)

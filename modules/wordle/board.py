from collections import Counter
from enum import Enum

import unicodedata
from PIL import Image, ImageDraw, ImageFont
from attrs import define, field

from core.constants.path import assets_path, noto_sans_bold_path
from core.utils.random import Random

words_txt = assets_path / "modules" / "wordle" / "words.txt"
answers_txt = assets_path / "modules" / "wordle" / "answers.txt"
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
    board: list[str] = field(factory=list)

    def add_word(self, word: str, last_word: str | None = None):
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
        state: list[list[WordleState]] = []
        for row in self.board:
            state.append(self.test_word(row))
        return state

    def test_word(self, word: str):
        state: list[WordleState] = [
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

        formatted: list[list[str]] = []
        board = self.test_board()
        for row_index, row in enumerate(board):
            letters: list[str] = []
            squares: list[str] = []
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
    board_image: Image.Image
    keyboard_image: Image.Image
    wordle_board: WordleBoard
    dark_theme: bool
    outline_color: tuple[int, int, int]
    background_color: str
    green_color: tuple[int, int, int]
    yellow_color: tuple[int, int, int]
    grey_color: tuple[int, int, int]
    light_grey_color: tuple[int, int, int]

    cell_size = 50
    margin = 10
    outline_width = 2
    rows = 6
    columns = 5

    keyboard_rows = [
        "QWERTYUIOP",
        "ASDFGHJKL",
        "ZXCVBNM",
    ]

    key_width = 40
    key_height = 55
    key_margin = 6

    def __init__(self, wordle_board: WordleBoard, dark_theme: bool):
        self.wordle_board = wordle_board
        self.dark_theme = dark_theme
        self.outline_color = (58, 58, 60) if dark_theme else (211, 214, 218)
        self.background_color = "black" if dark_theme else "white"

        self.green_color = (83, 141, 78) if dark_theme else (107, 169, 100)
        self.yellow_color = (181, 159, 59) if dark_theme else (201, 180, 88)
        self.grey_color = (58, 58, 60) if dark_theme else (120, 124, 126)
        self.light_grey_color = (129, 131, 132) if dark_theme else (211, 214, 218)

        board_width = self.columns * (self.cell_size + self.margin) + self.margin
        board_height = self.rows * (self.cell_size + self.margin) + self.margin

        board_image = Image.new("RGB", (board_width, board_height), self.background_color)
        board_draw = ImageDraw.Draw(board_image)

        for row in range(self.rows):
            for col in range(self.columns):
                x = col * (self.cell_size + self.margin) + self.margin
                y = row * (self.cell_size + self.margin) + self.margin

                board_draw.rectangle(
                    (x, y, x + self.cell_size, y + self.cell_size),
                    fill=None,
                    outline=self.outline_color,
                    width=self.outline_width,
                )

        self.board_image = board_image

        keyboard_rows_count = len(self.keyboard_rows)
        keyboard_width = (
            max(len(r) for r in self.keyboard_rows)
            * (self.key_width + self.key_margin)
            + self.key_margin
        )
        keyboard_height = (
            keyboard_rows_count * (self.key_height + self.key_margin)
            + self.key_margin
        )

        keyboard_image = Image.new(
            "RGB", (keyboard_width, keyboard_height), self.background_color
        )
        keyboard_draw = ImageDraw.Draw(keyboard_image)

        for row_index, row_keys in enumerate(self.keyboard_rows):
            row_width = (
                len(row_keys) * self.key_width
                + (len(row_keys) - 1) * self.key_margin
            )
            start_x = (keyboard_width - row_width) // 2
            y = self.key_margin + row_index * (self.key_height + self.key_margin)

            for col_index, letter in enumerate(row_keys):
                x = start_x + col_index * (self.key_width + self.key_margin)

                keyboard_draw.rectangle(
                    (x, y, x + self.key_width, y + self.key_height),
                    fill=self.light_grey_color,
                    outline=None,
                )

                font_size = int(self.key_height * 0.5)
                font = ImageFont.truetype(noto_sans_bold_path, font_size)

                _, _, w, h = keyboard_draw.textbbox((0, 0), letter, font=font)
                keyboard_draw.text(
                    (
                        x + (self.key_width - w) // 2,
                        y + (self.key_height - h) // 2 - 2,
                    ),
                    letter,
                    fill="white" if self.dark_theme else "black",
                    font=font,
                )
        self.keyboard_image = keyboard_image

    def update_board(self):
        draw = ImageDraw.Draw(self.board_image)
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
                _, _, w, h = draw.textbbox((0, 0), letter, font=font)

                draw.text(
                    (
                        x + (self.cell_size - w) // 2,
                        y + (self.cell_size - h) // 2 - 3,
                    ),
                    letter,
                    fill="white",
                    font=font,
                )

    def _collect_letter_states(self) -> dict[str, WordleState]:
        result: dict[str, WordleState] = {}

        for r, row in enumerate(self.wordle_board.test_board()):
            for c, state in enumerate(row):
                letter = self.wordle_board.board[r][c].upper()

                if letter not in result:
                    result[letter] = state
                else:
                    if state == WordleState.GREEN:
                        result[letter] = WordleState.GREEN
                    elif (
                        state == WordleState.YELLOW
                        and result[letter] != WordleState.GREEN
                    ):
                        result[letter] = WordleState.YELLOW

        return result

    def update_keyboard(self):
        draw = ImageDraw.Draw(self.keyboard_image)

        font_size = int(self.key_height * 0.5)
        font = ImageFont.truetype(noto_sans_bold_path, font_size)

        letter_states = self._collect_letter_states()

        keyboard_width, _ = self.keyboard_image.size

        for row_index, row_keys in enumerate(self.keyboard_rows):
            row_width = (
                len(row_keys) * self.key_width
                + (len(row_keys) - 1) * self.key_margin
            )

            start_x = (keyboard_width - row_width) // 2
            y = self.key_margin + row_index * (self.key_height + self.key_margin)

            for col_index, letter in enumerate(row_keys):
                x = start_x + col_index * (self.key_width + self.key_margin)

                state = letter_states.get(letter)

                if state == WordleState.GREEN:
                    color = self.green_color
                    text_color = "white"
                elif state == WordleState.YELLOW:
                    color = self.yellow_color
                    text_color = "white"
                elif state == WordleState.GREY:
                    color = self.grey_color
                    text_color = "white"
                else:
                    color = self.light_grey_color
                    text_color = "white" if self.dark_theme else "black"

                draw.rectangle(
                    (x, y, x + self.key_width, y + self.key_height),
                    fill=color,
                    outline=None
                )

                _, _, w, h = draw.textbbox((0, 0), letter, font=font)

                draw.text(
                    (
                        x + (self.key_width - w) // 2,
                        y + (self.key_height - h) // 2 - 2,
                    ),
                    letter,
                    fill=text_color,
                    font=font,
                )

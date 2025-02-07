from core.builtins import Bot, I18NContext, Image as BImage, Plain
from core.component import module
from core.config import Config
from core.logger import Logger
from core.utils.cooldown import CoolDown
from core.utils.game import PlayState, GAME_EXPIRED
from core.utils.petal import gained_petal
from .board import WordleBoard, WordleBoardImage

text_mode = Config("wordle_disable_image", False)

wordle = module(
    "wordle",
    desc="{wordle.help.desc}",
    doc=True,
    developers=["Dianliang233", "DoroWolf"],
)


@wordle.command("{{wordle.help}}")
@wordle.command("hard {{wordle.help.hard}}")
@wordle.command("[--multi] {{wordle.help}}", options_desc={"--multi": "{wordle.help.multi}"})
@wordle.command("hard [--multi] {{wordle.help.hard}}", options_desc={"--multi": "{wordle.help.multi}"})
async def _(msg: Bot.MessageSession):
    multiplayer = bool(msg.parsed_msg and "--multi" in msg.parsed_msg)
    play_state = PlayState("wordle", msg, multiplayer)
    if play_state.check():
        await msg.finish(msg.locale.t("game.message.running"))

    qc = CoolDown("wordle", msg, 180, whole_target=multiplayer)
    if not msg.target.client_name == "TEST" and not msg.check_super_user():
        c = qc.check()
        if c != 0:
            await msg.finish(msg.locale.t("message.cooldown", time=int(c)))

    _board = WordleBoard.from_random_word()
    hard_mode = bool(msg.parsed_msg and "hard" in msg.parsed_msg)
    last_word = None
    board_image = WordleBoardImage(
        wordle_board=_board, dark_theme=msg.data.options.get("wordle_dark_theme")
    )

    play_state.enable()
    play_state.update(answer=_board.word)
    Logger.info(f"Answer: {_board.word}")
    if text_mode:
        start_msg = msg.locale.t("wordle.message.start")
        if hard_mode:
            start_msg += "\n" + msg.locale.t("wordle.message.start.hard")
        if multiplayer:
            start_msg += "\n" + msg.locale.t("wordle.message.start.multi")
    else:
        start_msg = [BImage(board_image.image), I18NContext("wordle.message.start")]
        if hard_mode:
            start_msg.append(I18NContext("wordle.message.start.hard"))
        if multiplayer:
            start_msg.append(I18NContext("wordle.message.start.multi"))
    await msg.send_message(start_msg)

    while _board.get_trials() <= 6 and play_state.check() and not _board.is_game_over():
        wait = (await msg.wait_anyone(timeout=GAME_EXPIRED)) if multiplayer else (await msg.wait_next_message(timeout=GAME_EXPIRED))
        word = wait.as_display(text_only=True).strip().lower()
        if len(word) != 5 or not (word.isalpha() and word.isascii()):
            continue
        if not _board.verify_word(word):
            await wait.send_message(msg.locale.t("wordle.message.not_a_word"))
            continue
        if not _board.add_word(word, last_word):
            await wait.send_message(msg.locale.t("wordle.message.hard.not_matched"))
            continue
        if hard_mode:
            last_word = word
        board_image.update_board()

        if not _board.is_game_over() and _board.get_trials() <= 6:
            Logger.info(f"{word} != {_board.word}, attempt {_board.get_trials() - 1}")
            if text_mode:
                await wait.send_message(_board.format_board())
            else:
                await wait.send_message([BImage(board_image.image)])

    if _board.is_game_over():
        play_state.disable()
        attempt = _board.get_trials() - 1
        g_msg = msg.locale.t("wordle.message.finish", answer=_board.word)
        if _board.board[-1] == _board.word:
            g_msg = msg.locale.t("wordle.message.finish.success", attempt=attempt)
            if not multiplayer:
                petal = 2 if attempt <= 3 else 1
                petal += 1 if hard_mode else 0
                if reward := await gained_petal(msg, petal):
                    g_msg += "\n" + reward
        qc.reset()
        if text_mode:
            await msg.finish(_board.format_board() + "\n" + g_msg, quote=False)
        else:
            await msg.finish([BImage(board_image.image), Plain(g_msg)], quote=False)


@wordle.command("stop {{game.help.stop}}")
async def _(msg: Bot.MessageSession):
    play_state, target_play_state = PlayState("wordle", msg), PlayState("wordle", msg, True)
    qc = CoolDown("wordle", msg, 180)
    if play_state.check():
        play_state.disable()
        qc.reset()
        await msg.finish(
            msg.locale.t(
                "wordle.message.stop",
                answer=play_state.get("answer") if play_state.get("answer") else target_play_state.get("answer")
            )
        )
    else:
        await msg.finish(msg.locale.t("game.message.stop.none"))


@wordle.command("theme {{wordle.help.theme}}", load=not text_mode)
async def _(msg: Bot.MessageSession):
    dark_theme = msg.data.options.get("wordle_dark_theme")

    if dark_theme:
        msg.data.edit_option("wordle_dark_theme", False)
        await msg.finish(msg.locale.t("wordle.message.theme.disable"))
    else:
        msg.data.edit_option("wordle_dark_theme", True)
        await msg.finish(msg.locale.t("wordle.message.theme.enable"))

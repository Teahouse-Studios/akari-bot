from core.builtins import Bot, I18NContext, Image as BImage, Plain
from core.component import module
from core.config import Config
from core.logger import Logger
from core.utils.cooldown import CoolDown
from core.utils.game import PlayState, GAME_EXPIRED
from core.utils.petal import gained_petal
from .board import WordleBoard, WordleBoardImage

text_mode = Config("wordle_disable_image", False, table_name="module_wordle")

wordle = module(
    "wordle",
    desc="{wordle.help.desc}",
    doc=True,
    developers=["Dianliang233", "DoroWolf"],
)


@wordle.command()
@wordle.command("[--hard] [--trial] {{wordle.help}}",
                options_desc={"--hard": "{wordle.help.option.hard}",
                              "--trial": "{wordle.help.option.trial}"})
async def _(msg: Bot.MessageSession):
    hard_mode = bool(msg.parsed_msg and msg.parsed_msg.get("--hard", False))
    trial = bool(msg.parsed_msg and msg.parsed_msg.get("--trial", False))

    play_state = PlayState("wordle", msg)
    if play_state.check():
        await msg.finish(msg.locale.t("game.message.running"))
    if PlayState("wordle", msg).check():
        await msg.finish(msg.locale.t("wordle.message.occupied"))

    qc = CoolDown("wordle", msg, 180)
    if not msg.target.client_name == "TEST" and not msg.check_super_user():
        c = qc.check()
        if c != 0:
            await msg.finish(msg.locale.t("message.cooldown", time=int(c)))

    board = WordleBoard.from_random_word()
    last_word = None
    board_image = WordleBoardImage(
        wordle_board=board, dark_theme=msg.target_data.get("wordle_dark_theme")
    )

    play_state.enable()
    play_state.update(answer=board.word)
    Logger.info(f"Answer: {board.word}")
    start_msg = []
    if not text_mode:
        start_msg.append(BImage(board_image.image))
    start_msg.append(I18NContext("wordle.message.start"))
    if hard_mode:
        start_msg.append(I18NContext("wordle.message.start.hard"))
    if trial:
        start_msg.append(I18NContext("wordle.message.start.trial"))
    await msg.send_message(start_msg)

    while board.get_trials() <= 6 and play_state.check() and not board.is_game_over():
        if trial:
            wait = await msg.wait_next_message(timeout=GAME_EXPIRED)
        else:
            wait = await msg.wait_anyone(timeout=GAME_EXPIRED)
        word = wait.as_display(text_only=True).strip().lower()
        if len(word) != 5 or not (word.isalpha() and word.isascii()):
            continue
        if not board.verify_word(word):
            await wait.send_message(msg.locale.t("wordle.message.not_a_word"))
            continue
        if not board.add_word(word, last_word):
            await wait.send_message(msg.locale.t("wordle.message.hard.not_matched"))
            continue
        if hard_mode:
            last_word = word
        board_image.update_board()

        if not board.is_game_over() and board.get_trials() <= 6:
            Logger.info(f"{word} != {board.word}, attempt {board.get_trials() - 1}")
            if text_mode:
                await wait.send_message(board.format_board())
            else:
                await wait.send_message([BImage(board_image.image)])

    if board.is_game_over():
        play_state.disable()
        attempt = board.get_trials() - 1
        g_msg = msg.locale.t("wordle.message.finish", answer=board.word)
        if board.board[-1] == board.word:
            g_msg = msg.locale.t("wordle.message.finish.success", attempt=attempt)
            if trial:
                petal = 2 if attempt <= 3 else 1
                petal += 1 if hard_mode else 0
                if reward := await gained_petal(msg, petal):
                    g_msg += "\n" + reward
        qc.reset()
        if text_mode:
            await msg.finish(board.format_board() + "\n" + g_msg, quote=False)
        else:
            await msg.finish([BImage(board_image.image), Plain(g_msg)], quote=False)


@wordle.command("stop {{game.help.stop}}")
async def _(msg: Bot.MessageSession):
    play_state = PlayState("wordle", msg)
    if play_state.check():
        play_state.disable()
        CoolDown("wordle", msg, 180).reset()
        await msg.finish(msg.locale.t("wordle.message.stop", answer=play_state.get("answer")))
    else:
        await msg.finish(msg.locale.t("game.message.stop.none"))


@wordle.command("theme {{wordle.help.theme}}", load=not text_mode)
async def _(msg: Bot.MessageSession):
    dark_theme = msg.target_data.get("wordle_dark_theme")

    if dark_theme:
        await msg.target_info.edit_target_data("wordle_dark_theme", False)
        await msg.finish(msg.locale.t("wordle.message.theme.disable"))
    else:
        await msg.target_info.edit_target_data("wordle_dark_theme", True)
        await msg.finish(msg.locale.t("wordle.message.theme.enable"))

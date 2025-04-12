import asyncio
import io
import re
import traceback
from datetime import datetime
from typing import Optional
from PIL import Image as PImage

from tenacity import retry, stop_after_attempt
from rdkit import Chem
from rdkit.Chem import AllChem, Draw, rdMolDescriptors

from core.builtins import Bot, Image, I18NContext
from core.component import module
from core.logger import Logger
from core.utils.cache import random_cache_path
from core.utils.game import PlayState, GAME_EXPIRED
from core.utils.http import get_url
from core.utils.petal import gained_petal
from core.utils.random import Random
from .coloring import element_colors

ID_RANGE_MAX = 200000000  # 数据库增长速度很快，可手动在此修改 ID 区间

pubchem_link = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"

element_lists = [
    "He",
    "Li",
    "Be",
    "Ne",
    "Na",
    "Mg",
    "Al",
    "Si",
    "Cl",
    "Ar",
    "Ca",
    "Sc",
    "Ti",
    "Cr",
    "Mn",
    "Fe",
    "Co",
    "Ni",
    "Cu",
    "Zn",
    "Ga",
    "Ge",
    "As",
    "Se",
    "Br",
    "Kr",
    "Rb",
    "Sr",
    "Zr",
    "Nb",
    "Mo",
    "Tc",
    "Ru",
    "Rh",
    "Pd",
    "Ag",
    "Cd",
    "In",
    "Sn",
    "Sb",
    "Te",
    "Xe",
    "Cs",
    "Ba",
    "La",
    "Ce",
    "Pr",
    "Nd",
    "Pm",
    "Sm",
    "Eu",
    "Gd",
    "Tb",
    "Dy",
    "Ho",
    "Er",
    "Tm",
    "Yb",
    "Lu",
    "Hf",
    "Ta",
    "Re",
    "Os",
    "Ir",
    "Pt",
    "Au",
    "Hg",
    "Tl",
    "Pb",
    "Bi",
    "Po",
    "At",
    "Rn",
    "Fr",
    "Ra",
    "Ac",
    "Th",
    "Pa",
    "Np",
    "Pu",
    "Am",
    "Cm",
    "Bk",
    "Cf",
    "Es",
    "Fm",
    "Md",
    "No",
    "Lr",
    "Rf",
    "Db",
    "Sg",
    "Bh",
    "Hs",
    "Mt",
    "Ds",
    "Rg",
    "Cn",
    "Nh",
    "Fl",
    "Mc",
    "Lv",
    "Ts",
    "Og",
    "C",
    "H",
    "B",
    "K",
    "N",
    "O",
    "F",
    "P",
    "S",
    "V",
    "I",
    "U",
    "Y",
    "W",
]  # 元素列表，用于解析化学式（请不要手动修改当前的排序）


def parse_elements(formula: str) -> dict:
    elements = {}
    while True:
        if not formula:
            break
        for element in element_lists:
            if formula.startswith(element):
                formula = formula.removeprefix(element)
                if count := re.match("^([0-9]+).*$", formula):
                    elements[element] = int(count.group(1))
                    formula = formula.removeprefix(count.group(1))
                else:
                    elements[element] = 1
                break
        else:
            raise ValueError("Unknown element: " + formula)
    return elements


@retry(stop=stop_after_attempt(3), reraise=True)
async def search_pubchem(id: Optional[int] = None):
    if id:
        answer_id = id
    else:
        answer_id = Random.randint(1, ID_RANGE_MAX)
    answer_id = str(answer_id)
    Logger.info(f"PubChem CID: {answer_id}")
    get = await get_url(f"{pubchem_link}/compound/cid/{answer_id}/property/IsomericSMILES,Title/JSON", 200, fmt="json")
    if get:
        compound_info = get["PropertyTable"]["Properties"][0]
        smiles = compound_info["IsomericSMILES"]
        mol = Chem.MolFromSmiles(smiles)
        formula = rdMolDescriptors.CalcMolFormula(mol)
        elements = parse_elements(formula)
        return {
            "id": answer_id,
            "answer": formula,
            "smiles": smiles,
            "elements": elements,
        }


ccode = module(
    "chemical_code",
    developers=["OasisAkari", "DoroWolf"],
    desc="{chemical_code.help.desc}",
    doc=True,
    alias={
        "cc": "chemical_code",
        "cca": "chemical_code captcha",
        "chemicalcode": "chemical_code",
        "chemical_captcha": "chemical_code captcha",
        "chemicalcaptcha": "chemical_code captcha",
        "ccode": "chemical_code",
        "ccaptcha": "chemical_code captcha",
    },
)


@ccode.command("{{chemical_code.help}}")
async def _(msg: Bot.MessageSession):
    await chemical_code(msg)


@ccode.command("captcha {{chemical_code.help.captcha}}")
async def _(msg: Bot.MessageSession):
    await chemical_code(msg, captcha_mode=True)


@ccode.command("stop {{game.help.stop}}")
async def _(msg: Bot.MessageSession):
    play_state = PlayState("chemical_code", msg)
    if play_state.check():
        play_state.disable()
        await msg.finish(I18NContext("chemical_code.stop.message", answer=play_state.get("answer")),
                         quote=False,
                         )
    else:
        await msg.finish(I18NContext("game.message.stop.none"))


@ccode.command("<pcid> {{chemical_code.help.pcid}}")
async def _(msg: Bot.MessageSession, pcid: int):
    if int(pcid) < 0:
        await msg.finish(I18NContext("chemical_code.message.pcid.invalid"))
    elif int(pcid) == 0:  # 若 id 为 0，则随机
        await chemical_code(msg)
    else:
        await chemical_code(msg, pcid, random_mode=False)


async def chemical_code(
    msg: Bot.MessageSession, id: Optional[int] = None, random_mode=True, captcha_mode=False
):
    play_state = PlayState("chemical_code", msg)
    if play_state.check():
        await msg.finish(I18NContext("game.message.running"))
    else:
        play_state.enable()
    try:
        csr = await search_pubchem(id)
    except Exception:
        Logger.error(traceback.format_exc())
        play_state.disable()
        await msg.finish(I18NContext("chemical_code.message.error"))
    play_state.update(**csr)  # 储存并获取不同用户所需的信息
    Logger.info(f"Answer: {play_state.get("answer")}")

    mol = Chem.MolFromSmiles(play_state.get("smiles"))
    if not mol:
        play_state.disable()
        await msg.finish(I18NContext("chemical_code.message.error"))

    AllChem.Compute2DCoords(mol)

    num_atoms = mol.GetNumAtoms()
    size = max(num_atoms * 500 // 100, 500)

    drawer = Draw.rdMolDraw2D.MolDraw2DCairo(size, size)
    options = drawer.drawOptions()
    options.padding = min(0.2 * (10 / num_atoms), 0.2)
    options.setAtomPalette(element_colors)
    drawer.SetDrawOptions(options)
    drawer.DrawMolecule(mol)
    drawer.FinishDrawing()

    image_bytes = drawer.GetDrawingText()
    image = PImage.open(io.BytesIO(image_bytes))
    newpath = f"{random_cache_path()}.png"
    image.save(newpath)

    set_timeout = max(num_atoms // 30, 2)

    async def ans(msg: Bot.MessageSession, random_mode):
        wait = await msg.wait_next_message(timeout=GAME_EXPIRED)
        if play_state.check():
            if (wait_text := wait.as_display(text_only=True)) != play_state.get(
                "answer"
            ):
                if re.match(r"^[A-Za-z0-9]+$", wait_text):
                    try:
                        parse_ = parse_elements(wait_text)  # 解析消息中的化学元素
                        value = 0
                        for _, v in parse_.items():
                            value += v
                        v_ = num_atoms - value
                        if v_ < 0:
                            v_ = -v_
                        if v_ > 6:
                            await wait.send_message(I18NContext("chemical_code.message.incorrect.remind1"))
                        else:
                            if play_state.get("elements") == parse_:
                                await wait.send_message(I18NContext("chemical_code.message.incorrect.remind5"))
                            elif v_ <= 2:
                                missing_something = False
                                for i in play_state.get("elements"):
                                    if i not in parse_:
                                        await wait.send_message(I18NContext("chemical_code.message.incorrect.remind4"))
                                        missing_something = True
                                        break
                                if not missing_something:
                                    await wait.send_message(I18NContext("chemical_code.message.incorrect.remind3"))
                            else:
                                incorrect_list = []
                                for i in play_state.get("elements"):
                                    if i in parse_:
                                        if parse_[i] != play_state.get("elements")[i]:
                                            incorrect_list.append(i)
                                    else:
                                        await wait.send_message(I18NContext("chemical_code.message.incorrect.remind4"))
                                        incorrect_list = []
                                        break

                                if incorrect_list:
                                    incorrect_elements = "[I18N:message.delimiter]".join(incorrect_list)
                                    await wait.send_message(I18NContext("chemical_code.message.incorrect.remind2", elements=incorrect_elements))
                    except ValueError:
                        Logger.error(traceback.format_exc())

                Logger.info(f"{wait_text} != {play_state.get("answer")}")
                return await ans(wait, random_mode)
            send_ = [I18NContext("chemical_code.message.correct")]
            if random_mode:
                if g_msg := await gained_petal(wait, 1):
                    send_.append(g_msg)
            play_state.disable()
            await wait.finish(send_)

    async def timer(start):
        if play_state.check():
            if datetime.now().timestamp() - start > 60 * set_timeout:
                play_state.disable()
                await msg.finish(I18NContext("chemical_code.message.timeup", answer=play_state.get("answer")))
            else:
                await msg.sleep(1)  # 防冲突
                await timer(start)

    if not captcha_mode:
        await msg.send_message(
            [
                I18NContext("chemical_code.message.showid", id=play_state.get("id")),
                Image(newpath),
                I18NContext("chemical_code.message", times=set_timeout),
            ]
        )
        time_start = datetime.now().timestamp()

        await asyncio.gather(ans(msg, random_mode), timer(time_start))
    else:
        result = await msg.wait_next_message(
            [
                I18NContext("chemical_code.message.showid", id=play_state.get("id")),
                Image(newpath),
                I18NContext("chemical_code.message.captcha", times=set_timeout),
            ],
            timeout=GAME_EXPIRED,
            append_instruction=False,
        )
        if play_state.check():
            play_state.disable()
            if result.as_display(text_only=True) == play_state.get("answer"):
                send_ = [I18NContext("chemical_code.message.correct")]
                if g_msg := await gained_petal(msg, 2):
                    send_.append(g_msg)
                await result.finish(send_)
            else:
                await result.finish(I18NContext("chemical_code.message.incorrect", answer=play_state.get("answer")))

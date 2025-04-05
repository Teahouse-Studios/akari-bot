import orjson as json

from core.builtins import Bot, Image, Plain
from core.utils.http import get_url
from modules.cytoid.database.models import CytoidBindInfo


async def cytoid_profile(msg: Bot.MessageSession, username):
    if username:
        query_id = username.lower()
    else:
        bind_info = await CytoidBindInfo.get_or_none(sender_id=msg.target.sender_id)
        if not bind_info:
            await msg.finish(
                msg.locale.t("cytoid.message.user_unbound", prefix=msg.prefixes[0])
            )
        query_id = bind_info.username
    profile_url = f"http://services.cytoid.io/profile/{query_id}"
    try:
        profile = json.loads(await get_url(profile_url, 200))
    except ValueError as e:
        if str(e).startswith("404"):
            await msg.finish(msg.locale.t("cytoid.message.user_not_found"))
        else:
            raise e
    uid = profile["user"]["uid"]
    nick = profile["user"]["name"]
    avatar = profile["user"]["avatar"]["large"]
    basic_exp = profile["exp"]["basicExp"]
    level_exp = profile["exp"]["levelExp"]
    total_exp = profile["exp"]["totalExp"]
    current_level = profile["exp"]["currentLevel"]
    next_level_exp = profile["exp"]["nextLevelExp"]
    rating = profile["rating"]
    grade: dict = profile["grade"]
    grade_t = []
    max_ = grade.get("MAX")
    if max_:
        grade_t.append(f"MAX: {max_}")
    sss = grade.get("SSS")
    if sss:
        grade_t.append(f"SSS: {sss}")
    ss = grade.get("SS")
    if ss:
        grade_t.append(f"SS: {ss}")
    s = grade.get("S")
    if s:
        grade_t.append(f"S: {s}")
    aa = grade.get("AA")
    if aa:
        grade_t.append(f"AA: {aa}")
    a = grade.get("A")
    if a:
        grade_t.append(f"A: {a}")
    b = grade.get("B")
    if b:
        grade_t.append(f"B: {b}")
    c = grade.get("C")
    if c:
        grade_t.append(f"C: {c}")
    d = grade.get("D")
    if d:
        grade_t.append(f"D: {d}")
    f = grade.get("F")
    if f:
        grade_t.append(f"F: {f}")
    text = (
        f"UID: {uid}\n"
        + (f"Nickname: {nick}\n" if nick else "")
        + f"BasicExp: {basic_exp}\n"
        + f"LevelExp: {level_exp}\n"
        + f"TotalExp: {total_exp}\n"
        + f"CurrentLevel: {current_level}\n"
        + f"NextLevelExp: {next_level_exp}\n"
        + f"Rating: {rating}\n"
        + f"Grade: {", ".join(grade_t)}"
    )
    await msg.finish([Image(path=avatar), Plain(text)])

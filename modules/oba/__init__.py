import re
from datetime import datetime

from core.builtins import Bot, Image, Plain
from core.component import module
from core.utils.http import get_url

API = "https://bd.bangbang93.com/openbmclapi"
TOP_LIMIT = 10

oba = module("oba", desc="{oba.help.desc}", developers="WorldHim")


def size_convert(value):
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = 1024.0
    for _, unit in enumerate(units):
        if (value / size) < 1:
            return f"{value:.2f} {unit}"
        value /= size


async def latest_version():
    try:
        version = await get_url(f"{API}/metric/version", fmt="json")
        return f"{version.get("version")}@{version.get("_resolved").split("#")[1][:7]}"
    except Exception:
        return None


def search_cluster(clusterList: dict, key: str, value: str):
    result = []
    regex = re.compile(value, re.IGNORECASE)

    for (rank, node) in enumerate(clusterList, 1):
        if regex.search(node.get(key)):
            result.append((rank, node))
        elif "sponsor" in node and regex.search(node.get("sponsor").get(key)):
            result.append((rank, node))

    return result


@oba.command()
@oba.command("status {{oba.help.status}}")
async def _(msg: Bot.MessageSession):
    dashboard = await get_url(f"{API}/metric/dashboard", fmt="json")

    current_nodes = dashboard.get("currentNodes")
    load = f"{round(dashboard.get("load") * 100, 2)}%"
    bandwidth = dashboard.get("bandwidth")
    current_bandwidth = round(dashboard.get("currentBandwidth"), 2)
    hits = dashboard.get("hits")
    size = size_convert(dashboard.get("bytes"))
    version = await latest_version()

    msg_list = [msg.locale.t("oba.message.status.detail",
                             current_nodes=current_nodes,
                             load=load,
                             bandwidth=bandwidth,
                             current_bandwidth=current_bandwidth,
                             hits=hits,
                             size=size
                             )]
    if version:
        msg_list.append(msg.locale.t("oba.message.status.version", version=version))
    msg_list.append(
        msg.locale.t(
            "oba.message.query_time",
            query_time=msg.ts2strftime(
                datetime.now().timestamp(),
                timezone=False)))
    await msg.finish(msg_list)


@oba.command("node [<rank>] {{oba.help.rank}}")
async def _(msg: Bot.MessageSession, rank: int = 1):
    if rank < 1:
        await msg.finish(msg.locale.t("oba.message.node.invalid"))
    rank_list = await get_url(f"{API}/metric/rank", fmt="json")
    node = rank_list[rank - 1]
    status = "🟩" if node.get("isEnabled") else "🟥"
    name = node.get("name")
    _id = node.get("_id")
    hits = node.get("metric").get("hits")
    size = size_convert(node.get("metric").get("bytes"))

    msg_list = [status, msg.locale.t("oba.message.node", name=name, id=_id, hits=hits, size=size)]
    msg_list.append(
        msg.locale.t(
            "oba.message.query_time",
            query_time=msg.ts2strftime(
                datetime.now().timestamp(),
                timezone=False)))

    if "sponsor" not in node:
        await msg.finish(msg_list)
    else:
        await msg.send_message(msg_list)

        sponsor = node.get("sponsor")
        name = sponsor.get("name")
        url = sponsor.get("url")
        banner = sponsor.get("banner")

        send_msg = msg.locale.t("oba.message.sponsor", name=name, url=url)
        try:
            await msg.finish([Plain(send_msg), Image(banner)])
        except Exception:
            await msg.finish(send_msg)


@oba.command("top [<rank>] {{oba.help.top}}")
async def _(msg: Bot.MessageSession, rank: int = 1):
    rankList = await get_url(f"{API}/metric/rank", fmt="json")
    rank = 1 if rank <= 0 else rank

    node_list = []
    for i in range(rank - 1, rank - 1 + TOP_LIMIT):
        node = rankList[i]
        sponsor = node.get("sponsor", msg.locale.t("message.unknown"))
        try:
            sponsor_name = sponsor.get("name")
        except AttributeError:
            sponsor_name = msg.locale.t("message.unknown")

        try:
            status = "🟩" if node.get("isEnabled") else "🟥"
            name = node.get("name")
            _id = node.get("_id")
            hits = node.get("metric").get("hits")
            size = size_convert(node.get("metric").get("bytes"))
            node_list.append(f"{status} | {msg.locale.t("oba.message.top",
                                                        rank=i + 1,
                                                        name=name,
                                                        id=_id,
                                                        hits=hits,
                                                        size=size,
                                                        sponsor_name=sponsor_name)}")
        except KeyError:
            break

    node_list.append(msg.locale.t("message.collapse", amount=TOP_LIMIT))
    await msg.finish(node_list)


@oba.command("search <keyword> {{oba.help.search}}")
async def _(msg: Bot.MessageSession, keyword: str):
    rank_list = await get_url(f"{API}/metric/rank", fmt="json")

    match_list = search_cluster(rank_list, "name", keyword)

    node_list = []
    for rank, node in match_list:
        sponsor = node.get("sponsor", msg.locale.t("message.unknown"))
        try:
            sponsor_name = sponsor.get("name")
        except AttributeError:
            sponsor_name = msg.locale.t("message.unknown")

        try:
            status = "🟩" if node.get("isEnabled") else "🟥"
            name = node.get("name")
            _id = node.get("_id")
            hits = node.get("metric").get("hits")
            size = size_convert(node.get("metric").get("bytes"))
            node_list.append(f"{status} | {msg.locale.t("oba.message.top",
                                                        rank=rank,
                                                        name=name,
                                                        id=_id,
                                                        hits=hits,
                                                        size=size,
                                                        sponsor_name=sponsor_name)}")
        except KeyError:
            break

    if node_list:
        if len(node_list) > TOP_LIMIT:
            node_list = node_list[:TOP_LIMIT]
            node_list.append(msg.locale.t("message.collapse", amount=TOP_LIMIT))
        await msg.finish(node_list)
    else:
        await msg.finish(msg.locale.t("oba.message.search.not_found"))


@oba.command("sponsor {{oba.help.sponsor}}")
async def _(msg: Bot.MessageSession):
    sponsor = await get_url(f"{API}/sponsor", fmt="json")
    cluster = await get_url(f"{API}/sponsor/{str(sponsor["_id"])}", fmt="json")
    name = cluster.get("name")
    url = cluster.get("url")
    banner = cluster.get("banner")
    send_msg = msg.locale.t("oba.message.sponsor", name=name, url=url)
    try:
        await msg.finish([Plain(send_msg), Image(banner)])
    except Exception:
        await msg.finish(send_msg)

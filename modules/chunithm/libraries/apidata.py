import traceback
import ujson as json

from core.utils.http import post_url


async def get_record(msg, payload):
    url = f"https://www.diving-fish.com/api/chunithmprober/query/player"
    try:
        data = await post_url(url,
                              data=json.dumps(payload),
                              status_code=200,
                              headers={'Content-Type': 'application/json', 'accept': '*/*'}, fmt='json')
    except ValueError as e:
        if str(e).startswith('400'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("chunithm.message.user_unbound"))
            else:
                await msg.finish(msg.locale.t("chunithm.message.user_not_found"))
        elif str(e).startswith('403'):
            if "qq" in payload:
                await msg.finish(msg.locale.t("chunithm.message.forbidden.eula"))
            else:
                await msg.finish(msg.locale.t("chunithm.message.forbidden"))
        else:
            traceback.print_exc()

    return data
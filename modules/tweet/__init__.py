import re

import ujson as json

from config import Config
from core.builtins import Bot
from core.builtins.message import Image
from core.component import module
from core.dirty_check import check_bool, rickroll
from core.utils.http import download_to_cache, get_url

web_render_local = Config('web_render_local')
t = module('tweet', developers=['Dianliang233'], desc='{tweet.help.desc}')


@t.handle('<tweet> {{tweet.help}}')
async def _(msg: Bot.MessageSession, tweet: str):
    if tweet.isdigit():
        tweet_id = tweet
    else:
        match = re.search(r"status/(\d+)", tweet)
        if match:
            tweet_id = match.group(1)
        else:
            await msg.finish(msg.locale.t('tweet.message.error'))
    failed_request = await get_url('https://static-tweet.vercel.app/1', status_code=404)
    build_id = re.search(r'"buildId"\:"(.*?)"', failed_request).group(1)
    res = await get_url(f'https://static-tweet.vercel.app/_next/data/{build_id}/{tweet_id}.json')
    res_json = json.loads(res)
    if 'notFound' in res_json:
        await msg.finish(msg.locale.t('tweet.message.not_found'))
    else:
        if await check_bool(res_json['pageProps']['tweet']['text'], res_json['pageProps']['tweet']['user']['name'], res_json['pageProps']['tweet']['user']['screen_name']):
            message = await rickroll()
            await msg.finish(message)
        else:
            css = '''
                main {
                    justify-content: start !important;
                }

                main > div {
                    margin: 0 !important;
                    border: 0 !important;
                }

                article {
                    padding: .75rem 1rem;
                }

                footer {
                    display: none;
                }

                #__next > div {
                    height: auto;
                    padding: 0;
                }

                a[href^="https://twitter.com/intent/follow"],
                a[href^="https://help.twitter.com/en/twitter-for-websites-ads-info-and-privacy"],
                div[class^="tweet-replies"],
                button[aria-label="Copy link"],
                a[aria-label="Reply to this Tweet on Twitter"],
                span[class^="tweet-header_separator"] {
                    display: none;
                }
            '''
            pic = await download_to_cache(web_render_local + 'element_screenshot', method='POST', headers={
                'Content-Type': 'application/json',
            }, post_data=json.dumps({'url': f'https://static-tweet.vercel.app/{tweet_id}', 'css': css, 'mw': False, 'element': 'article'}), request_private_ip=True)
            await msg.finish([Image(pic), f"https://twitter.com/{res_json['pageProps']['tweet']['user']['screen_name']}/status/{tweet_id}"])

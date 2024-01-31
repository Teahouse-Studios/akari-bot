import re
import ujson as json

from config import CFG
from core.builtins import Bot
from core.builtins.message import Image, Url
from core.component import module
from core.dirty_check import check_bool, rickroll
from core.logger import Logger
from core.utils.http import download_to_cache, get_url

web_render = CFG.get_url('web_render')
web_render_local = CFG.get_url('web_render_local')


t = module('tweet', 
           developers=['Dianliang233'], 
           desc='{tweet.help.desc}', 
           exclude_from=['QQ', 'QQ|Group', 'Kook'],
           alias=['x']
          )


@t.handle('<tweet> {{tweet.help}}')
async def _(msg: Bot.MessageSession, tweet: str, use_local=True):
    if tweet.isdigit():
        tweet_id = tweet
    else:
        match = re.search(r"status/(\d+)", tweet)
        if match:
            tweet_id = match.group(1)
        else:
            await msg.finish(msg.locale.t('tweet.message.invalid'))

    if not web_render_local:
        if not web_render:
            Logger.warn('[Webrender] Webrender is not configured.')
            await msg.finish(msg.locale.t("error.config.webrender.invalid"))
        use_local = False

    res = await get_url(f'https://react-tweet.vercel.app/api/tweet/{tweet_id}', 200)
    res_json = json.loads(res)
    if not res_json['data']:
        await msg.finish(msg.locale.t('tweet.message.not_found'))
    elif res_json['data']['__typename'] == "TweetTombstone":
        await msg.finish(f"{msg.locale.t('tweet.message.tombstone')}{res_json['data']['tombstone']['text']['text'].replace(' Learn more', '')}")
    else:
        if await check_bool(res_json['data']['text'], res_json['data']['user']['name'],
                            res_json['data']['user']['screen_name']):
            await msg.finish(rickroll(msg))

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
            
        pic = await download_to_cache((web_render_local if use_local else web_render) + 'element_screenshot', method='POST', headers={
            'Content-Type': 'application/json',
        }, post_data=json.dumps(
            {'url': f'https://react-tweet-next.vercel.app/light/{tweet_id}', 'css': css, 'mw': False,
             'element': 'article'}), request_private_ip=True)
        await msg.finish(
            [Image(pic), Url(f"https://twitter.com/{res_json['data']['user']['screen_name']}/status/{tweet_id}")])

from core.builtins import Image, Bot
from core.component import module
import ujson as json

httpcat = module('httpcat', alias={'htpc': 'httpcat'}, desc='可爱的http猫猫', developers='haoye_qwq')


def init():
    with open("./modules/httpcat/url.json", 'w') as write_f:
        json.dump({'url': 'https://http.cat/'}, write_f)


@httpcat.handle('set <url> {设置猫猫API,格式为：https://example.domain/.../，默认为http.cat}', required_admin=True)
async def set_url(send: Bot.MessageSession):
    url = send.parsed_msg['<url>']
    with open("./modules/httpcat/url.json", 'w') as write_f:
        json.dump({'url': url}, write_f)
    await send.sendMessage(f"已设置API为{url}")


@httpcat.handle('reset {重置自定义API}', required_admin=True)
async def reset(send: Bot.MessageSession):
    init()
    await send.sendMessage('已重置到http.cat')


@httpcat.handle('<code> {获取http猫猫图片}')
async def http_cat(send: Bot.MessageSession):
    status_code = send.parsed_msg['<code>']
    with open('./modules/httpcat/url.json', 'r', encoding='utf8') as read_f:
        data = read_f.read()
        json_dict = json.loads(data)
    api_url = json_dict.get('url')
    await send.sendMessage(Image(f"{api_url}{status_code}.jpg"))


@httpcat.handle('help {获取帮助}')
async def help_httpcat(send: Bot.MessageSession):
    await send.sendMessage(
        '你可以获取：\n信息响应 (100–199)\n成功响应 (200–299)\n重定向消息 (300–399)\n客户端错误响应 (400–499)\n服务端错误响应 ('
        '500–599)\n具体请查看https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Status')

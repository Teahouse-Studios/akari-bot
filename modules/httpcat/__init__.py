from core.builtins import Image, Bot
from core.component import on_command

httpcat = on_command('httpcat', alias={'htpc':'httpcat'},desc='可爱的http猫猫')

@httpcat.handle('<code> {获取http猫猫图片}')
async def http_cat(send:Bot.MessageSession):
    status_code = send.parsed_msg['<code>']
    await send.sendMessage(Image(f"https://http.cat/{status_code}.jpg"))

@httpcat.handle('help {获取帮助}')
async def help_httpcat(send:Bot.MessageSession):
    await send.sendMessage('你可以获取：\n信息响应 (100–199)\n成功响应 (200–299)\n重定向消息 (300–399)\n客户端错误响应 (400–499)\n服务端错误响应 (500–599)')

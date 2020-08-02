from graia.broadcast import Broadcast
from graia.application import GraiaMiraiApplication, Session
from graia.application.message.chain import MessageChain
import asyncio

from graia.application.message.elements.internal import Plain
from graia.application.friend import Friend
from graia.application.group import Group

from command import command
from mcv import mcv
from wikim import wikim
from bug import bugtracker
from user import Username
import re
from userp import Userp
from pathexist import pathexist,pathexist2
import urllib
from server import ser
from wikil import im
from rc import rc
from ab import ab
from help import help
from newbie import new
from mcbv import mcbv
from mcdv import mcdv
from checkuser import checkuser
import mcvrss

loop = asyncio.get_event_loop()

bcc = Broadcast(loop=loop)
app = GraiaMiraiApplication(
    broadcast=bcc,
    connect_info=Session(
        host="http://localhost:11919", # 填入 httpapi 服务运行的地址
        authKey='1145141919810', # 填入 authKey
        account=2052142661, # 你的机器人的 qq 号
        websocket=True # Graia 已经可以根据所配置的消息接收的方式来保证消息接收部分的正常运作.
    )
)

@bcc.receiver("GroupMessage")
async def msg(app: GraiaMiraiApplication, group: Group, message: MessageChain):
    try:
        print (await command(message.asDisplay(),str(member.id),str(group.id)))
        c = await command(message.asDisplay(),str(member.id),str(group.id))
        try:
            d = c.split(' ')
            d = d[0]
        except:
            d = c
        print(d)
        if d == 'echo':
            echo = re.sub(r'^echo ','',c)
            await app.sendGroupMessage(group, MessageChain.create([Plain(echo)]))
        elif d == 'paa':
            await app.sendGroupMessage(group, MessageChain.create([At(member.id),Plain('爬')]))
        elif d == 'help':
            await app.sendGroupMessage(group, MessageChain.create([Plain((await help()))]))
        elif d == 'mcv':
            await app.sendGroupMessage(group, MessageChain.create([Plain((await mcv()))]))
        elif d == 'mcbv':
            await app.sendGroupMessage(group, MessageChain.create([Plain((await mcbv()))]))
        elif d == 'mcdv':
            await app.sendGroupMessage(group, MessageChain.create([Plain((await mcdv()))]))
        elif d.find('新人')!= -1 or d.find('new')!=-1:
            await app.sendGroupMessage(group, MessageChain.create([Plain((await new()))]))
        elif d.find('xrrrlei')!= -1:
            await app.sendGroupMessage(group, MessageChain.create([Plain((await new()))]))
        elif d.find("wiki") != -1 or d.find("Wiki") != -1:
            await app.sendGroupMessage(group, MessageChain.create([Plain('⏳')]))
            await app.sendGroupMessage(group, MessageChain.create([Plain((await wikim(c)))]))
        elif c.find("bug") != -1 or c.find("MC-") != -1 or c.find("BDS-") != -1 or c.find("MCPE-") != -1 or c.find("MCAPI-") != -1 or c.find("MCCE-") != -1 or c.find("MCD-") != -1 or c.find("MCL-") != -1 or c.find("REALMS-") != -1 or c.find("MCE-") != -1 or c.find("WEB-") != -1:
            await app.sendGroupMessage(group, MessageChain.create([Plain('⏳')]))
            await app.sendGroupMessage(group, MessageChain.create([Plain((await bugtracker(c)))]))
        elif d == 'server' or d == 'Server':
            await app.sendGroupMessage(group,MessageChain.create([plain((await ser(c)))]))
        elif d.find("user") != -1 or d.find("User") != -1:
            if c.find("-p") != -1:
                f = re.sub(' -p', '', c)
                print(f)
                try:
                    z = re.sub(r'^User','user',f)
                    try:
                        g = re.match(r'^user ~(.*) (.*)',z)
                        h = g.group(1)
                        h2 = g.group(2)
                        h2 = re.sub('_',' ',h2)
                    except Exception:
                        try:
                            g = re.match(r'^user-(.*?) (.*)',z)
                            h = 'minecraft-'+g.group(1)
                            h2 = g.group(2)
                            h2 = re.sub('_', ' ', h2)
                        except Exception:
                            try:
                                g = re.match(r'^user (.*?):(.*)', z)
                                h = 'minecraft-' + g.group(1)
                                h2 = g.group(2)
                                h2 = re.sub('_', ' ', h2)
                            except Exception:
                                try:
                                    g = re.match(r'user (.*)',z)
                                    h = 'minecraft'
                                    h2 = g.group(1)
                                    h2 = re.sub('_', ' ', h2)
                                except Exception as e:
                                    print(str(e))
                    if checkuser(h,h2):
                        if pathexist(h):
                            await app.sendGroupMessage(group,MessageChain.create([plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")]))
                        else:
                            await app.sendGroupMessage(group,MessageChain.create([plain('检测到此次为第一次访问该Wiki，下载资源可能会耗费一定的时间，请耐心等待。')]))
                            await app.sendGroupMessage(group,MessageChain.create([plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")]))
                    else:
                        await app.sendGroupMessage(group,MessageChain.create([plain('没有找到此用户。')]))
                except Exception as e:
                    print(str(e))

            else:
                await app.sendGroupMessage(group,MessageChain.create([plain((await Username(c)))]))
        elif d == 'rc':
            await app.sendGroupMessage(group,MessageChain.create([plain((await rc()))]))
        elif d == 'ab':
            await app.sendGroupMessage(group,MessageChain.create([plain((await ab()))]))
        if c == 'rss add mcv':
            await app.sendGroupMessage(group,MessageChain.create([plain((mcvrss.mcvrssa(str(group.id))))]))
        if c == 'rss remove mcv':
            await app.sendGroupMessage(group,MessageChain.create([plain((mcvrss.mcvrssr(str(group.id))))]))
        else:
            pass
    except Exception:
        pass
@bcc.receiver("FriendMessage")
async def msg(app: GraiaMiraiApplication, friend: Friend, message: MessageChain):
    try:
        print (await command(message.asDisplay(),'0'))
        c = await command(message.asDisplay(),'0')
        try:
            d = c.split(' ')
            d = d[0]
        except:
            d = c
        print(d)
        if d == 'echo':
            echo = re.sub(r'^echo ','',c)
            await app.sendFriendMessage(friend,MessageChain.create([plain(echo)]))
        if d == 'help':
            await app.sendFriendMessage(friend,MessageChain.create([plain((await help()))]))
        if d == 'mcv':
            await app.sendFriendMessage(friend,MessageChain.create([plain((await mcv()))]))
        elif d == 'mcbv':
            await app.sendFriendMessage(friend,MessageChain.create([plain((await mcbv()))]))
        elif d == 'mcdv':
            await app.sendFriendMessage(friend,MessageChain.create([plain((await mcdv()))]))
        elif c.find("wiki") !=-1 or c.find("Wiki") !=-1:
            await app.sendFriendMessage(friend,MessageChain.create([plain((await wikim(c)))]))
        elif d.find('新人')!= -1 or d.find('new')!=-1:
            await app.sendFriendMessage(friend,MessageChain.create([plain((await new()))]))
        elif c.find("bug") != -1 or c.find("MC-") != -1 or c.find("BDS-") != -1 or c.find("MCPE-") != -1 or c.find("MCAPI-") != -1 or c.find("MCCE-") != -1 or c.find("MCD-") != -1 or c.find("MCL-") != -1 or c.find("REALMS-") != -1 or c.find("MCE-") != -1 or c.find("WEB-") != -1:
            await app.sendFriendMessage(friend,MessageChain.create([plain((await bugtracker(c)))]))
        elif d == 'server' or d == 'Server':
            await app.sendFriendMessage(friend,MessageChain.create([plain((await ser(c)))]))
        elif d.find("user") != -1 or d.find("User") != -1:
            if c.find("-p") != -1:
                f = re.sub(' -p', '', c)
                print(f)
                try:
                    z = re.sub(r'^User','user',f)
                    try:
                        g = re.match(r'^user ~(.*) (.*)',z)
                        h = g.group(1)
                        h2 = g.group(2)
                        h2 = re.sub('_',' ',h2)
                    except Exception:
                        try:
                            g = re.match(r'^user-(.*?) (.*)',z)
                            h = 'minecraft-'+g.group(1)
                            h2 = g.group(2)
                            h2 = re.sub('_', ' ', h2)
                        except Exception:
                            try:
                                g = re.match(r'^user (.*?):(.*)', z)
                                h = 'minecraft-' + g.group(1)
                                h2 = g.group(2)
                                h2 = re.sub('_', ' ', h2)
                            except Exception:
                                try:
                                    g = re.match(r'user (.*)',z)
                                    h = 'minecraft'
                                    h2 = g.group(1)
                                    h2 = re.sub('_', ' ', h2)
                                except Exception as e:
                                    print(str(e))
                    if checkuser(h,h2):
                        if pathexist(h):
                            await app.sendFriendMessage(friend,MessageChain.create([plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")]))
                        else:
                            await app.sendFriendMessage(friend,MessageChain.create([plain('检测到此次为第一次访问该Wiki，下载资源可能会耗费一定的时间，请耐心等待。')]))
                            await app.sendFriendMessage(friend,MessageChain.create([plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")]))
                    else:
                        await app.sendFriendMessage(friend,MessageChain.create([plain('没有找到此用户。')]))
                except Exception as e:
                    print(str(e))

            else:
                await app.sendFriendMessage(friend,MessageChain.create([plain((await Username(c)))]))
        elif d == 'rc':
            await app.sendFriendMessage(friend,MessageChain.create([plain((await rc()))]))
        elif d == 'ab':
            await app.sendFriendMessage(friend,MessageChain.create([plain((await ab()))]))
    except Exception:
        pass
app.launch_blocking()

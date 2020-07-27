from mirai import Mirai, Group, MessageChain, Member, Plain, At, Source, Image, Friend
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
qq = 2052142661 # 字段 qq 的值
authKey = '1145141919810' # 字段 authKey 的值
mirai_api_http_locate = 'localhost:11919/ws' # httpapi所在主机的地址端口,如果 setting.yml 文件里字段 "enableWebsocket" 的值为 "true" 则需要将 "/" 换成 "/ws", 否则将接收不到消息.

app = Mirai(f"mirai://{mirai_api_http_locate}?authKey={authKey}&qq={qq}",websocket=True)
@app.receiver("GroupMessage")
async def msg(app: Mirai, group: Group,member: Member, message: MessageChain):
    try:
        print (await command(message.toString(),str(member.id),str(group.id)))
        c = await command(message.toString(),str(member.id),str(group.id))
        try:
            d = c.split(' ')
            d = d[0]
        except:
            d = c
        print(d)
        if d == 'echo':
            echo = re.sub(r'^echo ','',c)
            await app.sendGroupMessage(group, [Plain(echo)])
        elif d == 'paa':
            await app.sendGroupMessage(group, [At(member.id),Plain('爬')])
        elif d == 'help':
            await app.sendGroupMessage(group, [Plain((await help()))])
        elif d == 'mcv':
            await app.sendGroupMessage(group, [Plain((await mcv()))])
        elif d == 'mcbv':
            await app.sendGroupMessage(group, [Plain((await mcbv()))])
        elif d == 'mcdv':
            await app.sendGroupMessage(group, [Plain((await mcdv()))])
        elif d.find('新人')!= -1 or d.find('new')!=-1:
            await app.sendGroupMessage(group, [Plain((await new()))])
        elif d.find('xrrrlei')!= -1:
            await app.sendGroupMessage(group, [Plain((await new()))])
        elif d.find("wiki") != -1 or d.find("Wiki") != -1:
            await app.sendGroupMessage(group, [Plain('⏳')])
            await app.sendGroupMessage(group, [Plain((await wikim(c)))])
        elif c.find("bug") != -1 or c.find("MC-") != -1 or c.find("BDS-") != -1 or c.find("MCPE-") != -1 or c.find("MCAPI-") != -1 or c.find("MCCE-") != -1 or c.find("MCD-") != -1 or c.find("MCL-") != -1 or c.find("REALMS-") != -1 or c.find("MCE-") != -1 or c.find("WEB-") != -1:
            await app.sendGroupMessage(group, [Plain('⏳')])
            await app.sendGroupMessage(group, [Plain((await bugtracker(c)))])
        elif d == 'server' or d == 'Server':
            await app.sendGroupMessage(group, [Plain((await ser(c)))])
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
                            await app.sendGroupMessage(group, [Plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")])
                        else:
                            await app.sendGroupMessage(group, [Plain('检测到此次为第一次访问该Wiki，下载资源可能会耗费一定的时间，请耐心等待。')])
                            await app.sendGroupMessage(group, [Plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")])
                    else:
                        await app.sendGroupMessage(group, [Plain('没有找到此用户。')])
                except Exception as e:
                    print(str(e))

            else:
                await app.sendGroupMessage(group, [Plain((await Username(c)))])
        elif d == 'rc':
            await app.sendGroupMessage(group, [Plain((await rc()))])
        elif d == 'ab':
            await app.sendGroupMessage(group, [Plain((await ab()))])
        else:
            pass
    except Exception:
        pass
@app.receiver("FriendMessage")
async def msg(app: Mirai, friend: Friend, message: MessageChain):
    try:
        print (await command(message.toString(),'0'))
        c = await command(message.toString(),'0')
        try:
            d = c.split(' ')
            d = d[0]
        except:
            d = c
        print(d)
        if d == 'echo':
            echo = re.sub(r'^echo ','',c)
            await app.sendFriendMessage(friend, [Plain(echo)])
        if d == 'help':
            await app.sendFriendMessage(friend, [Plain((await help()))])
        if d == 'mcv':
            await app.sendFriendMessage(friend, [Plain((await mcv()))])
        elif d == 'mcbv':
            await app.sendFriendMessage(friend, [Plain((await mcbv()))])
        elif d == 'mcdv':
            await app.sendFriendMessage(friend, [Plain((await mcdv()))])
        elif c.find("wiki") !=-1 or c.find("Wiki") !=-1:
            await app.sendFriendMessage(friend, [Plain((await wikim(c)))])
        elif d.find('新人')!= -1 or d.find('new')!=-1:
            await app.sendFriendMessage(friend, [Plain((await new()))])
        elif c.find("bug") != -1 or c.find("MC-") != -1 or c.find("BDS-") != -1 or c.find("MCPE-") != -1 or c.find("MCAPI-") != -1 or c.find("MCCE-") != -1 or c.find("MCD-") != -1 or c.find("MCL-") != -1 or c.find("REALMS-") != -1 or c.find("MCE-") != -1 or c.find("WEB-") != -1:
            await app.sendFriendMessage(friend, [Plain((await bugtracker(c)))])
        elif d == 'server' or d == 'Server':
            await app.sendFriendMessage(friend, [Plain((await ser(c)))])
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
                            await app.sendFriendMessage(friend, [Plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")])
                        else:
                            await app.sendFriendMessage(friend, [Plain('检测到此次为第一次访问该Wiki，下载资源可能会耗费一定的时间，请耐心等待。')])
                            await app.sendFriendMessage(friend, [Plain(Userp(h,h2)),Image.fromFileSystem("/home/wdljt/oasisakari/bot/assests/usercard/"+h2+".png")])
                    else:
                        await app.sendFriendMessage(friend, [Plain('没有找到此用户。')])
                except Exception as e:
                    print(str(e))

            else:
                await app.sendFriendMessage(friend, [Plain((await Username(c)))])
        elif d == 'rc':
            await app.sendFriendMessage(friend, [Plain((await rc()))])
        elif d == 'ab':
            await app.sendFriendMessage(friend, [Plain((await ab()))])
    except Exception:
        pass
@app.subroutine
async def ver(app: Mirai):
    await app.sendGroupMessage('657876815',[Plain('已开启检测游戏版本。')])
    from mcversion import mcversion
    import time
    url = 'http://launchermeta.mojang.com/mc/game/version_manifest.json'
    verlist = mcversion()
    while True:
        version_manifest = requests.get(url)
        file = json.loads(version_manifest.text)
        release = file['latest']['release']
        snapshot = file['latest']['snapshot']
        if release in verlist:
            pass
        else:
            await app.sendGroupMessage('657876815',[Plain('启动器已更新'+file['latest']['release']+'正式版。')])
            addversion = open('mcversion.txt','a')
            addversion.write('\n'+release)
            addversion.close()
        if snapshot in verlist:
            pass
        else:
            await app.sendGroupMessage('657876815',[Plain('启动器已更新'+file['latest']['snapshot']+'快照。')])
            addversion = open('mcversion.txt','a')
            addversion.write('\n'+snapshot)
            addversion.close()
        time.sleep(10)
if __name__ == "__main__":
    app.run()

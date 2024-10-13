from hfs import Account
from httpcore import NetworkError

from core.builtins import Bot, Plain
from core.component import module

import asyncio

async def hfs_(name,id):
    student = Account()
    email, password = student.register(name, id, password='password')
    student.login(email,password)
    exam = student.get_exam(0)
    return exam.data

hfs_m = module('haofs', desc='基于 ghplvh/haofs 项目开发，用于查询好分数排名等')
@hfs_m.command('<姓名> <考号> {查询排名}', required_superuser=True)
async def _(msg:Bot.MessageSession):
    try:
        name = msg.parsed_msg['<姓名>']
        id = msg.parsed_msg['<考号>']
        haofs = await asyncio.to_thread(await hfs_(name,id))
        await msg.sendMessage([Plain(f"{name}({id}) 的 {haofs.get('name')} 成绩详情："),
                               Plain(f"分数：{haofs.get('score')}/{haofs.get('manfen')},"),
                               Plain(f"排名：班级 {haofs.get('classRank')}({haofs.get('classRankPart')}) | 级部 {haofs.get('gradeRank')}({haofs.get('gradeRankPart')})")])
    except Exception:
        await msg.sendMessage('发生错误')

@hfs_m.command('password <账号> <密码> {使用账密查询好分数成绩（必须学生端账密，私聊使用）}')
async def __(msg:Bot.MessageSession):
    if 'Group' not in msg.target.target_from:
        try:
            name = msg.parsed_msg['<账号>']
            password = msg.parsed_msg['<密码>']
            id = ''
            student = Account()
            student.login(name, password)
            haofs = student.get_exam(0).data
            await msg.sendMessage([Plain(f"{name}({id}) 的 {haofs.get('name')} 成绩详情："),
                                   Plain(f"分数：{haofs.get('score')}/{haofs.get('manfen')},"),
                                   Plain(
                                       f"排名：班级 {haofs.get('classRank')}({haofs.get('classRankPart')}) | 级部 {haofs.get('gradeRank')}({haofs.get('gradeRankPart')})")])
        except TypeError:
            await msg.send_message('账密错误')

    else:
        await msg.send_message('检测到在群聊中，终止程序')

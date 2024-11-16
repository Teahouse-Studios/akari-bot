from core.extra.hfs import Account, Paper, Exam
from core.database import BotDBUtil
from httpcore import NetworkError

from core.builtins import Bot, Plain, Image
from core.component import module

import asyncio

async def hfs_(name,id):
    student = Account()
    email, password = student.register(name, id, password='password')
    student.login(email,password)
    exam = student.get_exam(0)
    return exam.data

haofs = BotDBUtil().HaofsAccount()

hfs_m = module('haofs', desc='基于 pypi/haofs 项目开发，用于查询好分数排名等')
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
        raise NetworkError

@hfs_m.command('login <账号> {绑定好分数账密（必须学生端，私聊使用）}')
async def __(msg:Bot.MessageSession):
    if 'Group' not in msg.target.target_from:
        sender = msg.target.sender_id
        is_hfs_account = True
        email = msg.parsed_msg['<账号>']
        await msg.send_message('请发送密码',quote=False)
        password = (await msg.wait_next_message(timeout=None)).as_display(text_only=True)
        try:
            _student = Account()
            _student.login(email, password)
            del _student
        except Exception:
            is_hfs_account = False
        if not is_hfs_account:
            await msg.finish(
                [
                    Plain('发生错误，可能有以下几种情况：'),
                    Plain('1.账号或密码错误;'),
                    Plain('2.非学生端账号')
                ]
            )
        elif haofs.isexist(sender):
            if await msg.waitConfirm('您已经绑定过了，确认要覆盖吗？(y/n)', quote=False):
                haofs.sign_up(sender, email, password)
                await msg.finish('已完成')
            else:
                await msg.finish('已取消')
        else:
            haofs.sign_up(sender, email, password)
            await msg.finish('已完成')
    else:
        await msg.finish('检测到在群聊中，终止程序')

@hfs_m.command('query {查询好分数成绩}')
async def ___(msg:Bot.MessageSession):
    sender = msg.target.sender_id
    if haofs.isexist(sender):
        email,password = haofs.login(sender)
        stud = Account()
        stud.login(email, password)
        exam = stud.get_exam(0).data
        await msg.send_message(
            [
                Plain(f"{stud.student.get('studentName')}({stud.student.get('xuehao')}) 的 {exam.get('name')} 成绩详情："),
                Plain(f"分数：{exam.get('score')}/{exam.get('manfen')},"),
                Plain(f"排名：班级 {exam.get('classRank')}({exam.get('classRankPart')}) | 级部 {exam.get('gradeRank')}({exam.get('gradeRankPart')})")
            ],
        quote=False)
    else:
        await msg.finish('未绑定，请先私聊使用\"~haofs login <账号>\"登录')

@hfs_m.command('papers {查看答题卡}')
async def ____(msg:Bot.MessageSession):
    sender = msg.target.sender_id
    if haofs.isexist(sender):
        email,password = haofs.login(sender)
        stud = Account()
        stud.login(email, password)
        exm = stud.get_exam(0).papers
        papers = []
        for obj in exm:
            papers.append(Plain(obj))
            papers.extend([Image(i) for i in exm.get(obj).pictures])
        papers.append(Plain('[120秒后撤回，需保存请截图]'))
        s = await msg.send_message(papers)
        await msg.sleep(120)
        await s.delete()

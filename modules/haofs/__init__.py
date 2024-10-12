from hfs import Account
from core.builtins import Bot, Plain
from core.component import module
from concurrent.futures import ThreadPoolExecutor

async def hfs_(name,id):
    student = Account()
    email, password = student.register(name, id, password='password')
    student.login(email,password)
    exam = student.get_exam(0)
    return exam.data

hfs_m = module('haofs', desc='基于 ghplvh/haofs 项目开发，用于查询好分数排名等')
@hfs_m.command('<姓名> <考号> {查询排名}')
async def _(msg:Bot.MessageSession):
    async def send():
        try:
            name = msg.parsed_msg['<姓名>']
            id = msg.parsed_msg['<考号>']
            haofs = await hfs_(name, id)
            await msg.sendMessage([Plain(f"{name}({id}) 的 {haofs.get('name')} 成绩详情："),
                                   Plain(f"分数：{haofs.get('score')}/{haofs.get('manfen')},"),
                                   Plain(
                                       f"排名：班级 {haofs.get('classRank')}({haofs.get('classRankPart')}) | 级部 {haofs.get('gradeRank')}({haofs.get('gradeRankPart')})")])
        except Exception:
            await msg.sendMessage('发生错误')
    async with ThreadPoolExecutor() as t:
        await t.submit(send())





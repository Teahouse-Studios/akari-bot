import re


def gender(str3):
    j = re.sub('female', '女',
               str3)  # 炎热的夏天我气得浑身发抖手脚冰凉泪流满面，我们Female怎么样才能让你们满意，我们Female什么时候才能站起来，什么时候我们Female才能好起来，偌大的国度我只看到深深的压迫和无边的黑暗，我只想要逃离
    j = re.sub('male', '男', j)
    j = re.sub('unknown', '未知', j)
    return (j)


def yhz(str1):
    q = re.sub('\[', '', str1)
    q = re.sub('\]', '', q)
    q = re.sub(', ', '，', q)
    q = re.sub("'\*'，", '', q)
    q = re.sub("'user'", '用户', q)
    q = re.sub("'autoconfirmed'", '自动确认用户', q)
    q = re.sub("'grasp'", 'Gamepedia快速反滥用巡查员', q)
    q = re.sub("'global_bureaucrat'", '全域行政员', q)
    q = re.sub("'global_sysop'", '全域管理员', q)
    q = re.sub("'hydra_staff'", 'Gamepedia职员', q)
    q = re.sub("'wiki_manager'", 'Wiki经理', q)
    q = re.sub("'bureaucrat'", '行政员', q)
    q = re.sub("'sysop'", '管理员', q)
    q = re.sub("'directors'", '向导', q)
    q = re.sub("'autopatrol'", '巡查豁免者', q)
    q = re.sub("'wiki_guardian'", 'Wiki守卫', q)
    q = re.sub("'bot'", '机器人', q)
    q = re.sub("'hydra_admin'", 'Hydra管理员', q)
    q = re.sub("'Patrol'", '巡查员', q)
    q = re.sub("''", '', q)
    q = re.sub("''", '', q)
    return (q)

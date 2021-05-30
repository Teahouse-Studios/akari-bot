import re


def gender(str3):
    j = re.sub('female', '女',
               str3)  # 炎热的夏天我气得浑身发抖手脚冰凉泪流满面，我们Female怎么样才能让你们满意，我们Female什么时候才能站起来，什么时候我们Female才能好起来，偌大的国度我只看到深深的压迫和无边的黑暗，我只想要逃离
    j = re.sub('male', '男', j)
    j = re.sub('unknown', '未知', j)
    return j
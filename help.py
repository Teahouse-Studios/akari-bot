path = '~'
async def help():
    return(f'''{path}ab - 查看Minecraft Wiki过滤器日志。
{path}bug -h
{path}mcv - 获取当前Minecraft Java版最新版本。
{path}mcbv - 获取当前Minecraft基岩版最新版本。
{path}mcdv - 获取当前Minecraft Dungeons最新版本。
{path}rc - 查看Minecraft Wiki最近更改。
{path}server -h
{path}user -h
{path}wiki -h
! - 用于快捷查bug，如!mc-4
[[]] - 用于快捷查wiki，如[[海晶石]]
{{{{}}}} - 用于快捷查wiki模板，如{{{{v}}}}''')
async def wikihelp():
    return(f'''{path}wiki ~<site> <pagename> - 从指定Gamepedia站点中输出条目链接。
{path}wiki <lang>:<pagename>, {path}wiki-<lang> <pagename> - 从指定语言中的Minecraft Wiki中输出条目链接。
{path}wiki <pagename> - 从Minecraft Wiki（英文）中输出条目链接。''')
async def userhelp():
    return(f'''{path}user ~<site> <pagename> - 从指定Gamepedia站点中输出用户信息。
{path}user <lang>:<pagename>, {path}user-<lang> <pagename> - 从指定语言中的Minecraft Wiki中输出用户信息。
{path}user <pagename> - 从Minecraft Wiki（英文）中输出用户信息。
[-r] - 输出详细信息。
[-p] - 输出一张用户信息的图片（不包含用户组）。''')
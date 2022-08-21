# 简介

本文将会教你如何搭建自己的小可机器人。

# 准备

1. 一台可运行 Python 的服务器或主机（电脑、树莓派、安装了 Termux 的手机、etc...）。
2. 主机已安装并可运行 [Python 3 环境](https://www.python.org/) ，版本大于 3.8 皆可部署。
3. 对应你需要运行的平台所需要的必要内容（环境、token等）。

# 基础部分部署

## 安装基础依赖

1. 从 [Release 页面](https://github.com/Teahouse-Studios/bot/releases/latest) 的 Assets 部分中下载 Source code（源代码）。
2. 解压源代码，然后打开终端，输入 `pip install -r requirements.txt` 来安装依赖。

## 配置

进入 `config` 文件夹，将 `config.cfg.example` 重命名为 `config.cfg`，然后开始配置你所需要的内容。

对于第一次的简单部署，我们只需要关注数据库字段即可，其余字段可留空：

`db_path = mysql+pymysql://`

机器人需要一个数据库以用于存储用户数据。

此字段需要填写一个可被 `sqlalchemy` 支持的数据库链接，以下为推荐方案，请任选一个：

### MySQL

若使用 `MySQL` 作为主要使用数据库：

**格式**

`mysql+pymysql://<数据库用户名>:<数据库用户密码>@<数据库地址>`

**实际示例**

`mysql+pymysql://bot:123456@example.com/bot_prod`

### SQLite

如果你不希望为了部署一个机器人而去研究如何安装数据库（或购买某服务商的数据库服务）的话
，使用 SQLite 就是最佳选择。缺点是可能会遇到锁表问题（极小概率发生），以及将来运维失误（误删除 db 且没有备份）导致原先用户数据损毁的情况。

如果你选择 SQLite，只需要将字段内容填写为以下格式即可。无需再关注数据库搭建等问题：

**格式**

`db_path = sqlite:///<相对路径>/<数据库文件名>.db`

**实际示例**

`db_path = sqlite:///database/save.db`

此示例将会在 `database` 文件夹内创建 `save.db` 来存储用户数据。

## 运行测试控制台

一旦你配置好了数据库后，你就可以直接去启动测试控制台（`console.py`）了。

测试控制台包括一个基础的运行环境，你可以在测试控制台内使用命令进行基础的机器人交互。

测试控制台仅支持回复文本消息和图片，其它消息元素将被忽略或转换为文本或图片来显示。

1. 于 `console.py` 所在目录，按下 `Shift` + `右键` 来打开右键菜单。
2. 选择 `在此处打开 Powershell 窗口` 或 `在此处打开命令窗口`
3. 于终端内输入 `python console.py` 来启动测试控制台。

## 配置平台机器人

接下来，我们需要开始配置你想让机器人运行的平台。

你只需要填写你需要的平台的字段，其余的留空即可。留空后对应平台的机器人将不会运行。

### QQ

我们在这里使用了 [aiocqhttp](https://github.com/nonebot/aiocqhttp) 来对接 [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) 客户端。

`qq_host = 127.0.0.1:11451` - 将会在填写的 IP 地址和端口中开启一个 websocket 服务器，用于 go-cqhttp 反向连接。

`qq_account = 2052142661` - 填写机器人的 QQ 号。

填写好后，请配置 `go-cqhttp` 的 `config.yml` 文件中的对应的连接方式。

```
...
# 连接服务列表
servers:
  # 添加方式，同一连接方式可添加多个，具体配置说明请查看文档
  #- http: # http 通信
  #- ws:   # 正向 Websocket
  #- ws-reverse: # 反向 Websocket
  #- pprof: #性能分析服务器
  - ws-reverse:
      universal: ws://127.0.0.1:11451/ws/ # 此处填写先前的 IP 地址和端口，注意不要删去后面的 /ws/
      reconnect-interval: 3000
      middlewares:
        <<: *default # 引用默认中间件
...
```

### Discord

我们在这里使用了 [Pycord](https://github.com/Pycord-Development/pycord) 来调用 Discord API。

为了达到目的，你需要于 [Discord 开发者平台](https://discord.com/developers) 创建一个机器人并获取 Token。

`dc_token =` - 填写你获取到的机器人 Token。

### Telegram

我们在这里使用了 [AIOGram](https://github.com/aiogram/aiogram) 来异步调用 Telegram API。

为了达到目的，你需要在 Telegram 搜索 `@BotFather` 来创建机器人。

`tg_token =` - 填写你获取到的机器人 Token。

## 运行平台机器人

### Windows

我们不推荐双击运行 `start.bat` 来启动程序。

建议在启动机器人之前，先打开终端（cmd 或 Powershell）再运行 `start.bat`。

1. 于 `start.bat` 所在目录，按下 `Shift` + `右键` 来打开右键菜单。
2. 选择 `在此处打开 Powershell 窗口` 或 `在此处打开命令窗口`
3. 于终端内输入 `.\start.bat` （Powershell） 或 `start.bat` （cmd）来启动机器人。

### Linux

1. 于终端内，设置 `start` 脚本的执行权限：`chmod +x start`
2. 启动脚本：`./start`

## 配置其他功能

由于小可有着许多的功能，部分功能需要进一步的配置才能使用。

部分字段可能并未预设于 `config.yml.example` 中，手动添加即可。

### 屏蔽词

小可内置了 [阿里云内容安全服务](https://www.aliyun.com/product/lvwang) 对接，可用于 QQ 平台下部分模块检查发送文本是否安全，以达到机器人账户安全的目的。

如有需求，请前往阿里云进行开通并获取 accessKeyId 及 accessKeySecret。未填写字段将不会使用屏蔽词服务。

`Check_accessKeyId =` - 填写获取的 `accessKeyId`

`Check_accessKeySecret =` - 填写获取的 `accessKeySecret`

### Webrender

此为小可的外置服务。主要用于处理 html 渲染图片及部分功能的访问代理。

#### 部署

1. 此服务使用 JavaScript 编写，由 `Puppeteer` 驱动，为此，你需要安装好 [Node.js](https://nodejs.org/)
   环境，以及安装好 [Chrome](https://www.google.cn/intl/zh-CN/chrome/) 。
2. 下载 [源代码文件](https://github.com/Teahouse-Studios/oa-web-render) ，并在终端内使用 `npm install` 安装依赖。
3. 于 `package.json` 同级目录中，创建 `.env` 文件，并于内填写以下字段：

```
CHROMIUM_PATH="C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" # 填写 chrome.exe 的绝对路径
FC_SERVER_PORT=15551 # 填写服务运行的端口
```

4. 于终端内，使用 `node ./src/index.js` 来开启服务。服务无任何内容输出。

你亦可使用云服务产商的 Serverless 服务来部署本服务。

#### 字段填写

`web_render =` - Webrender 的地址（IP 或域名）及端口

`web_render_local =` - 本地 Webrender 的地址（可与上一字段同一参数）

**示例**

`web_render = 127.0.0.1:15551`

### 模块

#### Arcaea

Arcaea 模块使用了 Lowiro 官方的 ArcaeaLimitedAPI 和 BotArcAPI 进行开发。

ArcaeaLimitedAPI 需要向 Lowiro 官方发送邮件申请以获得 Token。

在没有 ArcaeaLimitedAPI Token 的情况下，也亦可仅使用 BotArcAPI 来支持模块部分功能运作。

`arcapi_official_url =` - 填写你于邮件中获得的 ArcaeaLimitedAPI 地址

`arcapi_official_token =` - 填写你于邮件中获得的 ArcaeaLimitedAPI Token

`botarcapi_url =` - 填写 BotArcAPI 公用实例地址

`botarcapi_agent =` - 填写 BotArcAPI 公用实例申请到的 UA 名

填写完后，你还需要从下载 [Arcaea](https://arcaea.lowiro.com/) 的 Apk 文件，将其放置于 `assets` 文件夹并重命名为 `arc.apk`，并在 Bot
启动后使用 `~arcaea initialize` 来初始化资源文件。

#### maimai

maimai 模块基于 [mai-bot](https://github.com/Diving-Fish/mai-bot) 修改而来。此模块需要额外的资源文件才可正常工作。

1. 下载 [资源文件](https://www.diving-fish.com/maibot/static.zip) ，并于 `assets` 目录下创建一个 `maimai` 文件夹。
2. 解压资源文件，形成以下目录结构：

```angular2html
assets
└─maimai
    └─static
        │  adobe_simhei.otf
        │  aliases.csv
        │  msyh.ttc
        │  
        └─mai
            │...
```

#### secret

此模块下的内容主要用于监测 Minecraft Wiki 注册日志和滥用日志，如无需要可直接删除此模块的文件夹。

### 其他功能

`qq_msg_logging_to_db = True` - 将 QQ 平台内的命令触发消息记录至 `database/msg.db` 中，有助于判断是否存在违规使用机器人的情况。

`base_superuser =` - 设置机器人主超级用户。可用格式为 `QQ|<QQ号>`、`Discord|<ClientID>`、`Telegram|<ClientID>`，可在机器人开启后使用 `~whoami`
命令来查看自身的 ID，机器人启动后将自动标记对象为超级用户。

`slower_schedule = False` - 部分计划任务模块使用更长的时间间隔执行，可能有助于网络较差环境的优化。

`enable_tos = False` - 是否启用内置的违反服务条款的检查。

`qq_enable_dirty_check = True` - 是否启用 QQ 平台的屏蔽词检查。

`qq_enable_urlmanager = True` - 是否启用 QQ 平台的 URL 管理（替换外部链接，提示非官方页面）。

#### 自定义确认词及命令前缀

你可以通过编辑 `core/elements/others/__init__.py` 里面的 `confirm_command` 变量来添加（或删除）机器人在部分场景下询问用户是否继续的词语，通过编辑 `command_prefix`
变量来增加（或删除）可使用的命令前缀。

`command_prefix` 首位将被用作帮助文档中默认展示的前缀。

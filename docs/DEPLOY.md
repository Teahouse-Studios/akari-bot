# 目录

-   [简介](#简介)
-   [正常部署](#正常部署)
    -   [准备](#准备)
    -   [下载源代码](#下载源代码)
    -   [安装依赖](#安装依赖)
    -   [配置](#配置)
    -   [运行机器人](#运行机器人)
-   [获取帮助](#获取帮助)
-   [开发](#开发)
-   [疑难解答](#疑难解答)

# 简介

本文将会教你如何搭建自己的小可机器人。

# 正常部署

若想使用 Docker 部署，请转到[使用 Docker 部署](./docs/DEPLOY_Docker.md)。

## 准备

1. 一台可运行 Python 的服务器或主机（电脑、树莓派、安装了 Termux 的手机、etc...）。

2. 主机已安装并可运行 [Python 3 环境](https://www.python.org/) ，版本大于 3.9 皆可部署。

3. 对应你需要运行的平台所需要的必要内容（环境、token 等）。

## 下载源代码

**方式一：使用 [Git](https://git-scm.com/) 克隆**

1. 请在要放置小可的文件夹中右键打开终端，并输入以下指令：

    ```sh
    git clone https://github.com/Teahouse-studios/akari-bot.git
    ```

    直连 GitHub 的克隆速度较慢，在特殊情况下，你可以使用镜像站进行克隆：

    ```sh
    git clone https://gitclone.com/github.com/Teahouse-studios/akari-bot.git
    ```

    ```sh
    git clone https://gh-proxy.com/github.com/Teahouse-studios/akari-bot.git
    ```

    镜像站会在每天晚上进行仓库更新，所以若想在镜像站更新之前获取最新版本的代码，请使用原 GitHub 地址。

2. 在文件夹内打开终端。

    ```sh
    cd akari-bot
    ```

**方式二：直接下载代码**

1. 你可以下载 [master 分支的最新代码](https://github.com/Teahouse-Studios/akari-bot/archive/refs/heads/master.zip)。

    > 由于无法保证 Release 版本的稳定性，我们不再提供 Release 版本的下载。

    > 不建议直接下载代码部署，因为这样你将无法使用 git 或是使用机器人内置的命令更新代码。

2. 解压源代码，并在文件夹中打开终端。

## 安装依赖

**方式一：使用 [Poetry](https://python-poetry.org/)**

如果你已经安装了 Poetry，你可以跳过以下安装步骤。

1. 打开 Powershell，并执行以下指令来安装 Poetry：

    **Windows**

    ```powershell
    (Invoke-WebRequest -Uri "https://install.python-poetry.org" -UseBasicParsing).Content | py -
    ```

    **Linux**

    ```sh
    curl -sSL "https://install.python-poetry.org" | python3 -
    ```

    > 若你使用了 Microsoft Store 或 pyenv-windows 安装 Python，请将 `py` 替换为 `python`。

    > 安装 Poetry 前请**务必**检查系统环境变量中是否存在多个 Python Executable Path（Python 可执行路径）并及时清除，否则安装 Poetry 后可能会出现 Python 环境混乱导致无法正常加载依赖的情况。

2. 安装完成后，请将以下目录添加到 PATH 环境变量，方便调用：

    **Windows**

    ```
    %APPDATA%\Python\Scripts
    ```

    **Linux**

    ```
    $HOME/.local/bin
    ```

    请善用搜索引擎寻找更改 PATH 的方法。

    在添加到 PATH 之后，你通常需要重启终端，甚至整个电脑才能使其生效。

    你可以通过 `poetry --version` 确认安装是否有效。

3. 在安装完 Poetry 后，请执行以下指令：

    ```sh
    poetry install
    ```

**方式二：使用 pip**

如果你不想使用 Poetry，你可以使用 pip 来安装依赖：

```sh
pip install -r requirements.txt
```

> 在安装依赖时若出现报错，请转到[疑难解答](#疑难解答)

## 配置

进入 `config` 文件夹，将 `config.toml.example` 重命名为 `config.toml`，然后开始配置你所需要的内容。

> 由于目前配置文件后缀改为 `toml`，与 `cfg` 不同的是，请在填写好必要的字段后，请删除所有配置文件中留空的字段，否则程序无法正常运行。若你拥有旧版 `cfg` 文件，机器人会自动帮你转换为 `toml` 格式。

### 配置数据库

机器人需要一个数据库以用于存储用户数据，对于第一次的简单部署，我们只需要关注数据库字段即可，其余字段可留空。

此字段需要填写一个可被 `sqlalchemy` 支持的数据库链接，以下为推荐方案，请任选一个：

#### MySQL

若使用 `MySQL` 作为主要使用数据库：

**格式**：`db_path = "mysql+pymysql://<数据库用户名>:<数据库用户密码>@<数据库地址>"`

**实际示例**：`db_path = "mysql+pymysql://bot:123456@example.com/bot_prod"`

#### SQLite

如果你不希望为了部署一个机器人而去研究如何安装数据库（或购买某服务商的数据库服务）的话，使用 SQLite 就是最佳选择。缺点是可能会遇到锁表问题（极小概率发生），以及将来运维失误（误删除 db 且没有备份）导致原先用户数据损毁的情况。

如果你选择 SQLite，只需要将字段内容填写为以下格式即可。无需再关注数据库搭建等问题：

**格式**：`db_path = "sqlite:///<相对路径>/<数据库文件名>.db"`

**实际示例**：`db_path = "sqlite:///database/save.db"`

此示例将会在 `database` 文件夹内创建 `save.db` 来存储用户数据。

### 配置平台机器人

#### QQ

我们在这里使用了 [aiocqhttp](https://github.com/nonebot/aiocqhttp) 来对接 [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) 客户端。

> 根据 go-cqhttp 官方仓库的消息：[QQ Bot 的未来以及迁移建议](https://github.com/Mrs4s/go-cqhttp/issues/2471)，开发者已无力继续维护此项目。

一个新注册的 QQ 账号仅需完成基础配置部分即可，为了避免在机器人使用后期时遇到 Code45 等问题，我们建议按照进阶配置来配置签名服务器。

##### 基础配置

如果你想使用 Docker 部署 go-cqhttp，请转到[使用 Docker](https://docs.go-cqhttp.org/guide/docker.html)。

1. 从 go-cqhttp 的官方仓库上下载最新的 [Release](https://github.com/Mrs4s/go-cqhttp/releases/latest)。

    | 系统类型       | 可执行文件                    | 压缩文件                        |
    | -------------- | ----------------------------- | ------------------------------- |
    | Intel 版 Macos | Not available                 | `go-cqhttp_darwin_amd64.tar.gz` |
    | M1 版 Macos    | Not available                 | `go-cqhttp_darwin_arm64.tar.gz` |
    | 32 位 Linux    | Not available                 | `go-cqhttp_linux_386.tar.gz`    |
    | 64 位 Linux    | Not available                 | `go-cqhttp_linux_amd64.tar.gz`  |
    | arm64 Linux    | Not available                 | `go-cqhttp_linux_arm64.tar.gz`  |
    | armv7 Linux    | Not available                 | `go-cqhttp_linux_armv7.tar.gz`  |
    | 32 位 Windows  | `go-cqhttp_windows_386.exe`   | `go-cqhttp_windows_386.zip`     |
    | 64 位 Windows  | `go-cqhttp_windows_amd64.exe` | `go-cqhttp_windows_amd64.zip`   |
    | arm64 Windows  | `go-cqhttp_windows_arm64.exe` | `go-cqhttp_windows_arm64.zip`   |
    | armv7 Windows  | `go-cqhttp_windows_armv7.exe` | `go-cqhttp_windows_armv7.zip`   |

2. 解压下载好的文件到一个已经预先准备好的文件夹中：

    **Windows** - 请使用自己熟悉的解压软件自行解压。

    **Linux** - 请在命令行中输入 `tar -xzvf [文件名]`。

3. 运行 go-cqhttp。

4. 此时将提示：

    ```
    [WARNING]: 尝试加载配置文件 config.yml 失败: 文件不存在
    [INFO]: 默认配置文件已生成,请编辑 config.yml 后重启程序.
    ```

    程序将会自动在存放 go-cqhttp 文件夹的目录下生成一个默认配置文件 `config.yml`。

    接下来，请配置 go-cqhttp 的 `config.yml` 文件中的对应的连接方式。

    ```yml
    ...
    # 连接服务列表
    servers:
      # 添加方式，同一连接方式可添加多个，具体配置说明请查看文档
      #- http: # http 通信
      #- ws:   # 正向 Websocket
      #- ws-reverse: # 反向 Websocket
      #- pprof: # 性能分析服务器
      - ws-reverse:
          universal: ws://127.0.0.1:11451/ws/ # 此处填写先前的 IP 地址和端口，注意不要删去后面的 /ws/
          reconnect-interval: 3000
          middlewares:
            <<: *default # 引用默认中间件
      ...
    ...
    ```

    请在小可机器人的配置文件 `config.toml` 填写以下字段：

    `qq_host = "127.0.0.1:11451"` - 将会在填写的 IP 地址和端口中开启一个 Websocket 服务器，用于 go-cqhttp 反向连接。

    `qq_account = 2314163511` - 填写机器人的 QQ 号。

    > 若在配置中遇到问题，请参阅 [go-cqhttp 官方文档](https://docs.go-cqhttp.org/)。

##### 进阶配置（配置签名服务器）

由于 QQ 风控机制的加强，go-cqhttp 若出现 Code45 报错情况时，请参照以下步骤配置签名服务器：

5. 安装 JRE 17（Java Runtime Environment 17），请善用搜索引擎查找安装方法。

6. 在 ~~[unidbg-fetch-qsign](https://github.com/fuqiuluo/unidbg-fetch-qsign)~~（原作者已删库，请自行在 GitHub 上搜索有关 `qsign` 的仓库）的 Release 界面中下载最新版本的 unidbg-fetch-qsign 并解压到一个提前准备好的文件夹中。

7. 删除与 go-cqhttp 同一目录下的 `data` 文件夹和 `device.json` 文件。

8. 在存放 unidbg-fetch-qsign 的文件夹中，运行以下命令：

    ```sh
    bin\unidbg-fetch-qsign --basePath=txlib\<你要使用的版本>
    ```

    请替换 `<你要使用的版本>` 字段为在存放 unidbg-fetch-qsign 的文件夹 `txlib` 文件夹存在的版本。

    例：`--basePath=txlib\8.9.73`

    > 在选择版本时，应当遵从以下原则：
    > 升级版本应当**一个一个版本**升，以后冻结了可能就没机会回退版本了。发生 Code45 应当先尝试删除 go-cqhttp 的 `device.json` 文件和 `data\cache` 文件夹并重新登录，而不是第一时间升级版本。

9. 按照先前步骤配置 go-cqhttp 的 `config.yml` 文件。

10. 接下来，请配置 go-cqhttp 的 `config.yml` 文件中的签名服务器：

    ```yml
    account: # 账号相关
      # 数据包的签名服务器列表，第一个作为主签名服务器，后续作为备用
      sign-servers:
        - url: 'http://127.0.0.1:8080'  # 主签名服务器地址， 必填
          key: '114514'  # 签名服务器所需要的apikey, 如果签名服务器的版本在1.1.0及以下则此项无效
          authorization: '-'   # authorization 内容, 依服务端设置，如 'Bearer xxxx'
        ...
      ...
    ...
    ```

11. 运行 go-cqhttp 以生成设备文件。

12. 下载对应版本的[安卓手机协议](https://github.com/MrXiaoM/qsign/blob/mirai/txlib/)并将其重命名为 `1.json` 。将该文件储存在与 go-cqhttp 同一目录下的 `data\versions` 文件夹中。

13. 在与 go-cqhttp 同一目录下的 `device.json` 文件夹中，并修改以下字段：

    ```json
    "protocol": 1,
    ```

14. 重启 go-cqhttp 完成最终配置。

#### Discord

我们在这里使用了 [Pycord](https://github.com/Pycord-Development/pycord) 来调用 Discord API。

为了达到目的，你需要于 [Discord 开发者平台](https://discord.com/developers)创建一个机器人并获取 Token。

`dc_token =` - 填写你获取到的机器人 Token。

#### Telegram

我们在这里使用了 [AIOGram](https://github.com/aiogram/aiogram) 来异步调用 Telegram API。

为了达到目的，你需要在 Telegram 搜索 `@BotFather` 来创建机器人。

`tg_token =` - 填写你获取到的机器人 Token。

#### Kook

你需要在 [Kook 开发者平台](https://developer.kookapp.cn/)创建一个机器人并获取 Token。

`kook_token =` - 填写你获取到的机器人 Token。

#### Matrix

你需要自行完成账号注册与登录。

`matrix_homeserver =` - 填写你使用的 Matrix server URL（只包括协议与主机，最后无需添加`/`）。

`matrix_user =` - 填写机器人的[完全限定用户 ID](https://spec.matrix.org/v1.9/appendices/#user-identifiers)（包括`@`与`:`）。

`matrix_device_id =` - 填写机器人的设备 ID（即 Element 的会话 ID）

`matrix_device_name =` - 填写机器人的设备名称（可随便乱写，给人看的）

`matrix_token =` - 填写机器人任意设备的 Access Token。

> 不推荐使用其他客户端获取 Access Token，这样容易导致 olm 会话非常混乱。
> 如果（不怕死）使用客户端获取 Access Token，不要使用客户端的退出登录功能，推荐通过浏览器隐私模式登陆并获取 Token。

使用以下命令进行密码登录：

```sh
curl -XPOST -d '{"type":"m.login.password", "user":"<user>", "password":"<password>"}' "https://<homeserver>/_matrix/client/r0/login"
```

##### E2E 加密

目前，由于 libolm 在一些情况下需要手动配置，机器人默认没有启用端对端加密（E2EE）支持。

若要启用 E2EE 支持，请执行以下命令：

```sh
poetry run -- pip3 install matrix-nio[e2e] ; Poetry
pip3 install matrix-nio[e2e] ; PIP
```

`matrix_megolm_backup_passphrase =` - （可选）填写机器人的 megolm 备份密码短语，建议使用随机的长密码，不填写则不会导出 megolm 备份。

如果需要导入 megolm 备份，请将备份文件放置在 `matrix_store/megolm_backup/restore.txt` 下，并将密码短语写入 `matrix_store/megolm_backup/restore-passphrase.txt`。

### 配置其他功能

由于小可有较多功能，部分功能需要进一步的配置才能使用。

部分字段可能并未预设于 `config.toml.example` 中，手动添加即可。

#### 屏蔽词

小可内置了[阿里云内容安全服务](https://www.aliyun.com/product/lvwang)对接，可用于 QQ 和 Kook 平台下部分模块检查发送文本是否安全，以达到机器人账户安全的目的。

如有需求，请前往阿里云进行开通并获取 AccessKeyID 及 AccessKeySecret。未填写字段将不会使用屏蔽词服务。

另请注意，由于阿里云政策限制，内容安全服务**不面向个人开发者**，若账号未完成阿里云企业认证，即使生成 AccessKey 也不会调用相关接口。

`check_accessKeyId =` - 填写获取的 AccessKeyID。

`check_accessKeySecret =` - 填写获取的 AccessKeySecret。

#### QQ 频道消息处理（Beta）

通过上文的 [aiocqhttp](https://github.com/nonebot/aiocqhttp) 对接 [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) 方式，可以按需选择是否启用 QQ 频道消息处理功能。

根据 go-cqhttp 的文档，iPad / Android Pad / Android Phone 协议支持处理 QQ 频道消息，可以在其生成的 `device.json` 中寻找 `"protocol":6,` 字段，将本处的数值修改为 1（Android Phone）、5（iPad）或 6（Android Pad）任意一个均可调用本功能。

> 注意：QQ 频道消息的处理仍然处于测试阶段，由于 go-cqhttp 对频道消息支持的不完善，频道内消息无法撤回，且频道列表不会自动刷新（加入新频道需要手动重启一次 gocqhttp）。

> 关于 go-cqhttp 选用以上方式登录时出现的的 Code45 或其他登录问题，请根据 go-cqhttp 官方 [Issue](https://github.com/Mrs4s/go-cqhttp) 对照解决，或选用除以上协议外的其他协议。

#### Webrender

此为小可的外置服务。主要用于处理 html 渲染图片及部分功能的访问代理。

##### 部署

1. 此服务使用 JavaScript 编写，由 `Puppeteer` 驱动，为此，你需要安装好 [Node.js](https://nodejs.org/) 环境，以及安装好 [Chrome](https://www.google.cn/intl/zh-CN/chrome/)。

2. 下载[源代码文件](https://github.com/Teahouse-Studios/oa-web-render)，并在终端内使用 `npm install` 安装依赖。

3. 于 `package.json` 同级目录中，创建 `.env` 文件，并于内填写以下字段：

    ```conf
    CHROMIUM_PATH = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" # 填写 chrome.exe 的绝对路径
    FC_SERVER_PORT = 15551 # 填写服务运行的端口
    ```

    > 在填写好配置文件之后，请删除所有配置文件中的注释，否则程序无法正确读取配置。

4. 于终端内，使用 `node ./src/index.js` 来开启服务。服务无任何内容输出。

你亦可使用云服务产商的 Serverless 服务来部署本服务。

##### 字段填写

`web_render =` - Webrender 的地址（IP 或域名）及端口。

`web_render_local =` - 本地 Webrender 的地址。（可与上一字段同一参数）

**示例**

`web_render = "http://127.0.0.1:15551"`

#### 模块

##### coin

`coin` 模块需要一些额外的参数才能正常工作。

`coin_limit = 10000` - 一次可投掷的硬币最大个数。

`coin_faceup_rate = 4994` - 硬币正面朝上的概率，按一万分之几计算。

`coin_facedown_rate = 4994` - 硬币反面朝上的概率，按一万分之几计算。

##### dice

`dice` 模块需要一些额外的参数才能正常工作。

`dice_limit = 10000` - 一次可投掷的骰子最大个数。

`dice_roll_limit = 100` - 投掷骰子的最大次数。

`dice_mod_max = 10000` - 投掷骰子的最大调节值。

`dice_mod_min = -10000` - 投掷骰子的最小调节值。

`dice_output_cnt = 50` - 输出时的最大数据量，超过则无法正常显示。

`dice_detail_cnt= 5` - 多次投掷骰子的总数，超过则不再显示详细信息。

`dice_count_limit = 10` - 骰子表达式最多的项数。

##### maimai

`maimai` 模块基于 [mai-bot](https://github.com/Diving-Fish/mai-bot) 修改而来。此模块需要额外的资源文件才可正常工作。

1. 下载[资源文件](https://www.diving-fish.com/maibot/static.zip)，并于 `assets` 目录下创建一个 `maimai` 文件夹。

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

##### secret

此模块下的内容主要用于监测 Minecraft Wiki 注册日志和滥用日志，如无需要可直接删除此模块的文件夹。

##### wolframalpha

`wolframalpha` 模块需要一些额外的参数才能正常工作。

为了达到目的，你需要前往 [Wolfram|Alpha 开发者平台](https://developer.wolframalpha.com/) 注册一个账号并申请一个 Simple API，然后填写以下字段：

`wolfram_alpha_appid =` - Wolfram|Alpha 的 APPID。

#### 其他功能

`base_superuser =` - 设置机器人主超级用户。可用格式为 `QQ|<QQ号>`、`Discord|Client|<ClientID>`、`Telegram|Client|<ClientID>`、`Kook|User|<UserID>`，可在机器人开启后使用 `~whoami` 命令来查看自身的 ID，机器人启动后将自动标记对象为超级用户。

`qq_disable_temp_session = true` - 是否禁用 QQ 平台的临时会话功能。

`qq_enable_listening_self_message = false` - 是否启用 QQ 平台的自我消息处理（可能有助于多设备下使用，但也可能会导致误触发导致消息陷入死循环状态）。

`enable_dirty_check = true` - 是否启用屏蔽词检查。

`enable_urlmanager = true` - 是否启用 URL 管理（替换外部链接，提示非官方页面）。若停用此功能将同时停用 `wiki_audit` 命令。

`slower_schedule = false` - 部分计划任务模块使用更长的时间间隔执行，可能有助于网络较差环境的优化。

`enable_tos = false` - 是否启用内置的违反服务条款的检查。

`enable_analytics = true` - 是否启用内置的 `analytics` 命令，用于统计命令使用次数。

`enable_eval = true` - 是否启用内置的 `eval` 命令。

`allow_request_private_ip = true` - 是否允许机器人请求私有 IP 地址。

#### 自定义确认词及命令前缀

你可以通过编辑配置文件中的 `confirm_command` 来添加（或删除）机器人在部分场景下询问用户是否继续的确认词，编辑 `command_prefix` 来增加（或删除）可使用的默认命令前缀。

`command_prefix` 首位将被用作帮助文档中默认展示的前缀。

## 运行机器人

小可机器人主要由平台机器人构成，为了让开发者更好地测试模块，我们还提供了控制台，接下来我们将逐步讲解如何运行机器人。

### 运行平台机器人

**Windows**

我们不推荐双击运行 `start.bat` 来启动程序。

建议在启动机器人之前，先打开终端（cmd 或 Powershell）再运行 `start.bat`。

1. 于 `start.bat` 所在目录，按下 `Shift` + `右键` 来打开右键菜单。
2. 选择 `在此处打开 Powershell 窗口` 或 `在此处打开命令窗口`。
3. 于终端内输入 `.\start.bat` （Powershell） 或 `start.bat` （cmd）来启动机器人。

**Linux**

1. 于终端内，设置 `start` 脚本的执行权限：`chmod +x start`
2. 启动脚本：`./start`

### 运行控制台

控制台包括一个基础的运行环境，你可以在控制台内使用命令进行基础的机器人交互。

控制台仅支持回复文本消息和图片，其它消息元素将被忽略或转换为文本或图片来显示。

你可能需要使用 `poetry shell` 切换 poetry 的虚拟环境来调用先前安装的依赖。

1. 于 `console.py` 所在目录，打开终端。
2. 在终端内输入 `python console.py` 来启动控制台。

# 获取帮助

到此，恭喜你成功部署了属于你的小可机器人！

如果你在部署的过程中还有其他疑问，你可以向我们发送 Issue 来请求帮助。

> 请注意，你应该具备基本的提问技巧。
> 有关如何提问，请阅读[《提问的智慧》](https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way/blob/main/README-zh_CN.md)。

# 开发

如果你想为小可开发模块，建议在开发之前执行 `pre-commit install` 来安装 `pre-commit` Git 钩子，它可以在提交 Commit 前执行一些操作。如：同步 poetry.lock 至 requirements.txt、自动 PEP8 格式化等。

# 疑难解答

以下的疑难解答部分可以解决小部分在自搭建时遇到的问题。

在排错之前，请确保你已经详细地阅读了文档内所有的注释说明。

疑难解答将会分为不同方面，如果你有更好的疑难解答欢迎提交 PR。

## 安装依赖

### 在安装依赖时遇到跟 `hnswlib` 有关的问题导致无法正常安装依赖

该情况可能只会发生在 Windows 系统下。

你可能没有安装好 Microsoft C++ 生成工具。

1. 下载 [Microsoft C++ 生成工具](https://visualstudio.microsoft.com/zh-hans/visual-cpp-build-tools/)。

2. 在下载文件夹中打开安装程序，等待片刻会出现一个名为“Visual Studio Installer”的窗口。

3. 在“工作负荷”板块中，选择“使用 C++ 的桌面开发”，然后点击右下角的“安装”。

4. 等待安装完成后即可关闭窗口。

5. 尝试重新安装依赖。

### 在使用 pip 安装依赖时遇到依赖冲突

尝试在安装依赖时加上 `--no-deps` 参数。

例：`pip install --no-deps -r requirements.txt`。

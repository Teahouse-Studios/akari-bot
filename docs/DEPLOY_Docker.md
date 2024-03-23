# 目录

-   [简介](#简介)
-   [正常部署](#正常部署)
    -   [准备](#准备)
    -   [拉取镜像](#拉取镜像)
    -   [配置](#配置)
    -   [运行机器人](#运行机器人)
-   [获取帮助](#获取帮助)
-   [开发](#开发)
-   [疑难解答](#疑难解答)

# 简介

本文将会教你如何使用 Docker 搭建自己的小可机器人。

# 使用 Docker 镜像部署

若不想使用 Docker 部署，请转到[正常部署](./docs/DEPLOY.md)。

## 准备

1. 一台已经安装好 [Docker](https://www.docker.com/) 的设备。

2. 对应你需要运行的平台所需要的必要内容（环境、token 等）。

请善用搜索引擎来获取详细安装教程。

## 拉取镜像

输入下面的指令拉取镜像。

> [!IMPORTANT]
> 目前小可的 Docker 镜像支持的架构仅为 arm64 和 amd64。

```sh
docker pull silianz/akari-bot:dev-docker
```

## 配置

从小可的 GitHub 仓库中下载 `config` 文件夹，并放到事先准备好的目录下。

进入 `config` 文件夹，将 `config.toml.example` 重命名为 `config.toml`，然后开始配置你所需要的内容。

> [!IMPORTANT]
> 由于目前配置文件后缀改为 `toml`，与 `cfg` 不同的是，请在填写好必要的字段后，请删除所有配置文件中留空的字段，否则程序无法正常运行。若你拥有旧版 `cfg` 文件，机器人会自动帮你转换为 `toml` 格式。

### 配置数据库

机器人需要一个数据库以用于存储用户数据，对于第一次的简单部署，我们只需要关注数据库字段即可，其余字段可留空。

此字段需要填写一个可被 `sqlalchemy` 支持的数据库链接，以下为推荐方案，请任选一个：

#### MySQL

若使用 `MySQL` 作为主要使用数据库：

**格式**：`db_path = "mysql+pymysql://<数据库用户名>:<数据库用户密码>@<数据库地址>"`

**实际示例**：`db_path = "mysql+pymysql://bot:123456@example.com/bot_prod"`

#### SQLite

> [!NOTE]
> 如果你不希望为了部署一个机器人而去研究如何安装数据库（或购买某服务商的数据库服务）的话，使用 SQLite 就是最佳选择。缺点是可能会遇到锁表问题（极小概率发生），以及将来运维失误（误删除 db 且没有备份）导致原先用户数据损毁的情况。

如果你选择 SQLite，只需要将字段内容填写为以下格式即可。无需再关注数据库搭建等问题：

**格式**：`db_path = "sqlite:///<相对路径>/<数据库文件名>.db"`

**实际示例**：`db_path = "sqlite:///database/save.db"`

此示例将会在 `database` 文件夹内创建 `save.db` 来存储用户数据。

### 配置平台机器人

#### QQ（OpenShamrock）

我们在这里使用了 [aiocqhttp](https://github.com/nonebot/aiocqhttp) 来对接 [OpenShamrock](https://github.com/whitechi73/OpenShamrock) 客户端。

使用该方案需要一定的安卓（Android）的使用基础，如果看不懂下面的文档的，请转到 [QQ（go-cqhttp）](#qqgo-cqhttp) 并使用 go-cqhttp 来配置 QQ 平台。

1. 尝试根据 [OpenShamrock 官方文档](https://whitechi73.github.io/OpenShamrock/guide/getting-started.html) 完成 OpenShamrock 的初步安装。

2. 安装完后，请在小可机器人的配置文件 `config.toml` 填写以下字段：

    `qq_host = "127.0.0.1:11451"` - 将会在填写的 IP 地址和端口中开启一个 Websocket 服务器，用于 go-cqhttp 反向连接。

    `qq_account = 2314163511` - 填写机器人的 QQ 号。

    `use_shamrock = true` - 告诉机器人正在使用 OpenShamrock，以确保正常运行。

    接下来，请配置 OpenShamrock 的以下选项[^1]：

    [^1]: 在 OpenShamrock 中，双击要更改的配置项进行配置。

    **接口信息：**

    - 被动 WebSocket 地址：`ws://127.0.0.1:11451/ws/` - 此处填写先前的 IP 地址和端口，注意不要删去后面的 /ws/。

    **功能设置：**

    - 消息格式为 CQ 码：开启
    - 被动 WebSocket：开启

3. 强制杀死 QQ 进程[^2]并重新启动 QQ 来应用 OpenShamrock 配置文件。

[^2]: 你可以通过设置 - 应用管理 - QQ 来结束 QQ 的进程。

> [!NOTE]
> 若在安装和配置中遇到问题，请参阅 [OpenShamrock 官方文档](https://whitechi73.github.io/OpenShamrock/)。

#### QQ（go-cqhttp）

我们在这里使用了 [aiocqhttp](https://github.com/nonebot/aiocqhttp) 来对接 [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) 客户端。

> [!NOTE]
> 根据 go-cqhttp 官方仓库的消息：[QQ Bot 的未来以及迁移建议](https://github.com/Mrs4s/go-cqhttp/issues/2471)，开发者已无力继续维护此项目。

一个新注册的 QQ 账号仅需完成基础配置部分即可，为了避免在机器人使用后期时遇到 Code45[^3] 等问题，我们建议按照进阶配置来配置签名服务器。

[^3]: Code45 是 Mirai（一个高效率 QQ 机器人框架，也是 go-cqhttp 正在使用的框架）在登陆遇到的一种常见登陆失败报错。
具体表现为：`[WARNING]: 登录失败: 登录失败，建议升级最新版本后重试，或通过问题反馈与我们联系。 Code: 45`。

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

2. 解压下载好的文件到一个已经预先准备好的文件夹中。

3. 运行 go-cqhttp。

4. 此时将提示：

    ```
    [WARNING]: 尝试加载配置文件 config.yml 失败: 文件不存在。
    [INFO]: 默认配置文件已生成，请编辑 config.yml 后重启程序。
    ```

    程序将会自动在存放 go-cqhttp 文件夹的目录下生成一个默认配置文件 `config.yml`。

    请填写好配置文件中的 QQ 账号和密码。

5. 请在小可机器人的配置文件 `config.toml` 填写以下字段：

    `qq_host = "127.0.0.1:11451"` - 将会在填写的 IP 地址和端口中开启一个 Websocket 服务器，用于 go-cqhttp 反向连接。

    `qq_account = 2314163511` - 填写机器人的 QQ 号。

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

> [!NOTE]
> 若在配置中遇到问题，请参阅 [go-cqhttp 官方文档](https://docs.go-cqhttp.org/)。

##### 进阶配置（配置签名服务器）

由于 QQ 风控机制的加强，go-cqhttp 若出现 Code45 报错情况时，请参照以下步骤配置签名服务器：

6. 安装 JRE 17（Java Runtime Environment 17），请善用搜索引擎查找安装方法。

7. 在 ~~[unidbg-fetch-qsign](https://github.com/fuqiuluo/unidbg-fetch-qsign)~~（原作者已删库，请自行在 GitHub 上搜索有关 `qsign` 的仓库）的 Release 界面中下载最新版本的 unidbg-fetch-qsign 并解压到一个提前准备好的文件夹中。

8. 删除与 go-cqhttp 同级目录下的 `data` 文件夹和 `device.json` 文件。

9. 在存放 unidbg-fetch-qsign 的文件夹中，运行以下命令：

    ```sh
    bin/unidbg-fetch-qsign --basePath=txlib/<你要使用的版本>
    ```

    请替换 `<你要使用的版本>` 字段为在存放 unidbg-fetch-qsign 的文件夹 `txlib` 文件夹存在的版本。

    例：`--basePath=txlib/8.9.73`

> [!IMPORTANT]
> 在选择版本时，应当遵从以下原则：
> 升级版本应当**一个一个版本**升，以后冻结了可能就没机会回退版本了。发生 Code45[^3] 应当先尝试删除 go-cqhttp 的 `device.json` 文件和 `data\cache` 文件夹并重新登录，而不是第一时间升级版本。

10. 接下来，请配置 go-cqhttp 的 `config.yml` 文件中的签名服务器：

    ```yml
    account: # 账号相关
      # 数据包的签名服务器列表，第一个作为主签名服务器，后续作为备用
      sign-servers:
        - url: 'http://127.0.0.1:8080'  # 主签名服务器地址， 必填
          key: '114514'  # 签名服务器所需要的 apikey, 如果签名服务器的版本在1.1.0及以下则此项无效
          authorization: '-'   # authorization 内容, 依服务端设置，如 'Bearer xxxx'
        ...
      ...
    ...
    ```

11. 运行 go-cqhttp 以生成设备文件。

12. 下载对应版本的[安卓手机协议](https://github.com/MrXiaoM/qsign/blob/mirai/txlib/)并将其重命名为 `1.json` 。将该文件储存在与 go-cqhttp 同一目录下的 `data\versions` 文件夹中。

13. 在与 go-cqhttp 同一目录下的 `device.json` 文件夹中，并修改以下字段：

    ```json
    {
        "protocol": 1
    }
    ```

14. 重启 go-cqhttp 来应用最终配置。

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

`matrix_homeserver =` - 填写你使用的 Matrix server URL（只包括协议与主机，最后无需添加 `/`）。

`matrix_user =` - 填写机器人的[完全限定用户 ID](https://spec.matrix.org/v1.9/appendices/#user-identifiers)（包括 `@` 与 `:`）。

`matrix_device_id =` - 填写机器人的设备 ID（即 Element 的会话 ID）

`matrix_device_name =` - 填写机器人的设备名称（可随便乱写，给人看的）

`matrix_token =` - 填写机器人任意设备的 Access Token。

> [!IMPORTANT]
> 不推荐使用其他客户端获取 Access Token，这样容易导致 olm 会话非常混乱。
>
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

> [!WARNING]
> QQ 频道消息的处理仍然处于测试阶段，由于 go-cqhttp 对频道消息支持的不完善，频道内消息无法撤回，且频道列表不会自动刷新（加入新频道需要手动重启一次 gocqhttp）。

> [!NOTE]
> 关于 go-cqhttp 选用以上方式登录时出现的的 Code45[^3] 或其他登录问题，请根据 go-cqhttp 官方 [Issue](https://github.com/Mrs4s/go-cqhttp) 对照解决，或选用除以上协议外的其他协议。

#### Webrender

此为小可的外置服务。主要用于处理 HTML 渲染图片及部分功能的访问代理。

##### 部署

1. 此服务使用 JavaScript 编写，由 `Puppeteer` 驱动，为此，你需要安装好 [Node.js](https://nodejs.org/) 环境，以及安装好 [Chrome](https://www.google.cn/intl/zh-CN/chrome/)。

2. 下载[源代码文件](https://github.com/Teahouse-Studios/oa-web-render)，并在终端内使用 `npm install` 安装依赖。

3. 于 `package.json` 同级目录中，创建 `.env` 文件，并于内填写以下字段：

    ```conf
    CHROMIUM_PATH = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" # 填写 chrome.exe 的绝对路径
    FC_SERVER_PORT = 15551 # 填写服务运行的端口
    ```

> [!IMPORTANT]
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

`dice_output_count = 50` - 输出时的最大数据量，超过则无法正常显示。

`dice_detail_count= 5` - 多次投掷骰子的总数，超过则不再显示详细信息。

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

配置完成后，使用 `docker run` 开启小可：

```sh
docker run \
> -d \
> -v /path/to/akari-bot/config/config.toml:/akari-bot/config/config.toml \ # 请将路径修改成对应的位置。
> -p 11451:11451  \ # WebSocket 服务器的端口，请根据你的配置文件更改。
> -p 3306:3306  \ # 用于对接 mysql 数据库。（可选）
> --name=akari-bot  \ # 指定容器名称。
> bakabaka9/akari-bot
```

如果终端中返回了 `long_tag` 类型的容器 `ID`, 证明容器已创建完毕，这时我们可以执行 `docker logs akari-bot` 查看小可的日志。

如果没有任何报错，恭喜你！你的小可机器人已经搭建成功！

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

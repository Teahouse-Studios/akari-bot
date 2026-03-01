# 贡献指南
首先，感谢你对小可（及其衍生项目）的关注。

我们欢迎任何形式的贡献。关于不同的参与方式及处理流程的详细说明，请参阅下方[目录](#目录)。

在开始贡献之前，请务必阅读相关章节。这将大幅减轻维护者的负担，并为所有参与者带来更顺畅的协作体验。

> [!NOTE]
> 如果你喜欢本项目，但暂时不打算贡献代码，也完全没关系。你仍然可以通过以下方式支持我们：
> - 为本项目点 Star
> - 在你的项目 README 中引用本项目
> - 将机器人加入你的群聊 / 服务器
> - 向他人分享或推荐本项目 / 机器人

## 目录

- [提出问题](#提出问题)
- [做出贡献](#做出贡献)
  - [报告错误](#报告错误)
  - [提出建议](#提出建议)
  - [本地化](#本地化)
- [提交代码更改](#提交代码更改)
  - [快速开始](#快速开始)
  - [开发环境](#开发环境)
  - [分支命名](#分支命名)
  - [提交规范](#提交规范)
  - [PR 描述](#pr-描述)
  - [代码风格](#代码风格)
- [文字排版](#文字排版)

## 提出问题
> [!NOTE]
> 建议先阅读[《提问的智慧》](https://github.com/ryanhanwu/How-To-Ask-Questions-The-Smart-Way/blob/main/README-zh_CN.md)，以避免带来不必要的麻烦。
> 
> 提示：本指南不提供此项目的实际支持服务！
> 
> （本提示由指南建议声明）

在开始之前，请先搜索是否已有相关 [Issue](https://github.com/Teahouse-Studios/akari-bot/issues)。一些显而易见的问题，建议优先通过搜索引擎自行查找答案。

如果你仍有疑问需要联系开发者，我们支持以下方法：

- 在 Issue 中[创建新问题](https://github.com/Teahouse-Studios/akari-bot/issues/new)
- 加入 QQ 平台的[小可公共实例测试群（738829671）](https://qm.qq.com/q/Rmuo5ORYgq)或[茶馆工作室聊天群（979982065）](https://qm.qq.com/q/sjwFNX1NVC)

不管使用什么方法，请**尽可能详细地描述**你遇到的问题。

## 做出贡献

### 报告错误
> [!WARNING]
> **绝对不要**在 Issue 或其他任何公开渠道报告或复现包含敏感信息的安全问题或漏洞。
> 
> 涉及敏感内容的问题必须通过电子邮件（地址详见 [`pyproject.toml`](/pyproject.toml)）或私聊联系开发者。
>
> 违反本条规则的内容将被删除；若执意违反，后果自负。

提交错误报告前，请先确认是否已有相关 [Issue](https://github.com/Teahouse-Studios/akari-bot/issues)。

如果没有类似问题，请使用[错误报告模板](https://github.com/Teahouse-Studios/akari-bot/issues/new?template=report_bug.yaml)创建新的 Issue，并提供以下信息：
- 错误的简要描述
- 复现步骤
- 预期结果和实际结果
- 错误信息（若有）

一个优秀的错误报告不应让他人反复追问细节。请尽可能提供完整信息。

### 提出建议
提交建议前，请先确认是否已有相关 [Issue](https://github.com/Teahouse-Studios/akari-bot/issues)。

如果没有类似的内容，请使用[功能建议模板](https://github.com/Teahouse-Studios/akari-bot/issues/new?template=feature_request.yaml)创建新的 Issue，并提供：
- 建议的简要描述
- 可能的实现方案
- 建议对项目有益的理由（推荐）

如果你已经完成了对应功能的开发，仍建议先提交 Issue 进行讨论，再创建 PR，以便充分沟通。

### 本地化
本项目的多语言内容由 Crowdin 托管，并由机器人定期同步本地化文件。

你可以前往[这里](https://crowdin.com/project/akari-bot)参与翻译改进。

为避免不必要的 Issue 堆积，除简体中文外，不建议在 Issue 中提交翻译相关问题。

如果你没有 Crowdin 账号，可以联系开发者代为提交翻译内容。

## 提交代码更改
如果你希望提交更“硬核”的贡献……

本项目在规范层面并没有太多限制（毕竟我们自己也不一定总是严格遵守各种条条框框）。但请至少遵守基本规范，避免“帮倒忙”。

### 快速开始
1. Fork 本项目储存库
2. Clone 你的 Fork 至本地
3. 创建新的分支
4. 做出你的更改
5. 向本项目提交 PR

tl;dr：[《🐧你为啥直接 commit 到我的 master 分支啊》](https://bilibili.com/video/BV1pwC6BxEeb)

### 开发环境
本项目基于 Python 开发。
Python 环境是必要的，注意最低版本要求（见 [README](/README.md)）。

推荐搭配 IDE 使用，例如 [PyCharm](https://www.jetbrains.com/pycharm) 或 [VSCode](https://code.visualstudio.com)。

本项目使用 [uv](https://docs.astral.sh/uv) 管理依赖。在安装后使用以下命令安装依赖：
```
uv sync
```
如果你需要安装新依赖，请使用以下命令：
```
uv add <包名>
```
请将新增依赖移动至 `pyproject.toml` 中对应注释分组下，并按字母顺序排列。

最后，别忘了使用以下命令锁定依赖：
```
uv lock
```

本项目已配置 Pre-commit Hook，使用以下命令安装：
```
pre-commit install
```
提交代码时将自动执行代码格式化、静态分析、依赖导出等操作。

### 分支命名
本项目中所有关于新功能或改动的分支使用 `dev/` 前缀，修复错误的分支使用 `fix/` 前缀。
（虽然实际上大多还是会直接 push 到 `main`。）

分支的命名必须使用英文。建议采用简短的描述或直接使用 Issue 编号。

### 提交规范
Commit message 必须使用中文或英文描述，除此之外没有硬性要求。

能够遵循 Conventional Commits 规范则更佳。

### PR 描述
PR 标题必须使用英文，正文可使用中文或英文简要描述更改内容。

建议在描述中[关联 Issue](#提出建议)，输入 `#<编号>` 即可关联。

一个 PR 必须通过 CI 测试，并得到至少 1 名开发者的 LGTM（看起来不错）后方可合并。

重大更改*原则上*不应该直接 push 到 `main`，须提交 PR 进行审查。

### 代码风格
本项目使用 [Ruff](https://docs.astral.sh/ruff) 作为代码格式化和静态分析工具。在提交代码之前，请运行以下命令以确保代码符合规范：
```
ruff format .
ruff check .
```
如果你使用 VSCode，可以安装 Ruff 插件。

## 文字排版
> “有研究显示，打字的时候不喜欢在中文和英文之间加空格的人，感情路都走得很辛苦，有七成的比例会在 34 岁的时候跟自己不爱的人结婚，而其余三成的人最后只能把遗产留给自己的猫。毕竟爱情跟书写都需要适时地留白。
>
> 与大家共勉之。”
>
> ——[vinta/paranoid-auto-spacing](https://github.com/vinta/pangu.js)

本项目的所有中文文字排版（包括本文）参考[中文文案排版指北](https://github.com/sparanoid/chinese-copywriting-guidelines/blob/master/README.zh-Hans.md)。

包括但不限于：
- 中英文之间需要增加空格
- 使用全角中文标点
- 专有名词使用正确的大小写

但以下情况为例外：
- 简体中文使用弯引号
- 链接之间不额外增加空格

此外，还有一些额外补充规范：
- 称呼用户须使用“你”，而不是“您”
- 机器人自称时避免使用“我”，统一使用“机器人”
- 尽可能避免使用第一人称进行描述
- 机器人的第三人称统一为“它”

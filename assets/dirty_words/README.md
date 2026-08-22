本目录用于存放本地文本过滤词库。

## 使用方法

1. 将需要过滤的所有文本整理为一个或多个 `.txt` 文件。
2. 每个文件代表一个独立的过滤词分类。
3. 每行填写一个过滤词。
4. 机器人启动后会读取本目录下的所有 `.txt` 文件，并加载其中的过滤词。

### 示例

目录结构：

```text
dirty_words/
├── profanity.txt
├── politics.txt
└── spam.txt
```

词库文件：

```text
示例词A
示例词B
示例词C
```

## 命中后的显示格式

当文本命中过滤词时，将不会显示原始内容，而是显示如下标签：

```text
[REDACTED:custom_<文件名称>]
```

例如：

* 命中 `profanity.txt` 中的词条：

```text
[REDACTED:custom_profanity]
```

* 命中 `politics.txt` 中的词条：

```text
[REDACTED:custom_politics]
```

> “当你在凝视深渊的时候，深渊也正在凝视着你。”——弗里德里希·尼采
>
> 官方无法提供任何默认过滤词库，因为过滤词库本身也是一种敏感信息。请根据自身需求自行构建与维护词库。

----

This directory stores local text filtering word lists.

## Usage

1. Organize all text to be filtered into one or more `.txt` files.
2. Each file represents an independent filter category.
3. Enter one filter keyword per line.
4. Once started, the bot will read all `.txt` files in this directory and load the filter keywords inside.

### Example

Directory structure: 

```text
dirty_words/
├── profanity.txt
├── politics.txt
└── spam.txt
```

Word list files:

```text
ExampleWordA
ExampleWordB
ExampleWordC
```

## Match Display Format

When text triggers a filter keyword, the original content will not be displayed. Instead, it will be replaced with the following tag:

```text
[REDACTED:custom_<Filename>]
```

Examples:

* Triggering a word in `profanity.txt`:

```text
[REDACTED:custom_profanity]
```

* Triggering a word in `politics.txt`:

```text
[REDACTED:custom_politics]
```

> "When you gaze long into an abyss, the abyss also gazes into you." — Friedrich Nietzsche
>
> The official team cannot provide any default filter word lists, as the filter lists themselves are considered sensitive information. Please build and maintain your own word lists according to your needs.

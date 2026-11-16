在本目录下放置 `.txt` 词库文件，每个文件为一个过滤分类，每行一个过滤词。机器人启动时会加载本目录下的所有 `.txt` 文件。

```text
filter_words/
├── politics.txt
├── profanity.txt
...
```

命中的文本会被替换为 `[吃掉了:local_<文件名>]`，例如命中 `politics.txt` 中的词条时显示 `[吃掉了:local_politics]`。

> “当你在凝视深渊的时候，深渊也正在凝视着你。”——弗里德里希·尼采
>
> 我们无法提供任何默认过滤词库，因为词库本身也是一种敏感信息。请根据自身需求自行构建与维护词库。

---

Place `.txt` word list files in this directory. Each file is a separate filter category with one keyword per line. The bot loads all `.txt` files in this directory on startup.

```text
filter_words/
├── politics.txt
├── profanity.txt
...
```

Matching text is replaced with `[REDACTED:local_<filename>]`. For example, a word from `politics.txt` is shown as `[REDACTED:local_politics]`.

> "When you gaze long into an abyss, the abyss also gazes into you." — Friedrich Nietzsche
>
> We cannot provide any default filter word lists, as the filter lists themselves are considered sensitive information. Please build and maintain your own word lists according to your needs.

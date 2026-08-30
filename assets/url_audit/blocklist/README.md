# URL 全局阻止列表

URL 全局阻止列表用于阻止机器人发出指定的 HTTP(S) 链接。命中阻止列表的 URL 元素、普通文本以及 Embed 文本中的 HTTP(S) URL 会被替换为本地化的拦截提示，不会输出原始 URL；Embed 的跳转 URL 命中时会被移除。

阻止列表优先级高于代码中的可信标记、URL 全局允许列表和 URLManager。即使链接被标记为可信或同时命中允许列表，仍会被阻止列表拦截。

## 配置文件

- `global.txt`：随主仓同步的规则，由项目维护者修改并提交。
- `user.txt`：部署者的本地规则，可手动创建，也可通过命令维护。该文件已被 Git 忽略。

每行填写一条规则。空行以及以 `#` 开头的行会被忽略。

精确规则直接填写完整 URL：

```text
https://unsafe.example.com/
https://example.com/malware/file.zip
```

正则规则需要添加 `regex:` 前缀：

```text
regex:https://unsafe-[a-z]+\.example\.com/.*
regex:https://example\.com/malware/[^/?#]+\.zip
```

规则匹配规范化后的完整 URL。正则表达式使用 `fullmatch`，因此必须覆盖协议、主机名、路径及所需的查询参数或片段。

## 命令配置

`url-audit` 是仅限超级用户使用的基础命令。阻止列表命令只修改 `user.txt`。

```text
~url-audit blocklist add https://unsafe.example.com/
~url-audit blocklist add-regex https://unsafe-[a-z]+\.example\.com/.*
~url-audit blocklist remove https://unsafe.example.com/
~url-audit blocklist remove-regex https://unsafe-[a-z]+\.example\.com/.*
~url-audit blocklist query https://unsafe-cdn.example.com/file
~url-audit blocklist list
```

`add-regex` 和 `remove-regex` 接收正则表达式本身，不需要添加 `regex:` 前缀。命令不能删除 `global.txt` 中的主仓规则。

## Wiki 集成

Wiki 不再维护独立的审计列表。命中本全局阻止列表的 Wiki API 会在站点绑定、页面查询或搜索发出内容请求前被拒绝；即使同一 URL 同时命中允许列表，也仍以阻止列表为准。

```text
~url-audit blocklist add https://unsafe.example.org/w/api.php
~url-audit blocklist add-regex https://unsafe-[a-z]+\.example\.org/(?:w/)?api\.php
~wiki-audit block https://unsafe.example.org/wiki/Example_Page
~wiki-audit unblock https://unsafe.example.org/w/api.php
```

`wiki-audit block` 会先从 Wiki 页面、站点或 API 地址探测规范 API URL，再写入用户阻止列表。`unblock` 优先使用已有 Wiki 缓存还原 API URL；缓存无法识别时，应直接提供 API URL。

## 安全限制

阻止列表与允许列表共用受约束的正则实现，但各自独立计算规则上限：

- 单条规则最长 500 个字符，待匹配 URL 最长 4096 个字符。
- 每份名单最多加载 256 条规则，其中正则规则最多 64 条。
- 每个配置文件最大为 64 KiB。
- 禁止递归、子程序调用、调用点、回溯控制动词及反向引用等高风险结构。
- 能匹配安全探测 URL 的过宽表达式会被拒绝，例如 `.*`。
- 单条正则匹配限时 5 毫秒，一批正则匹配总计限时 20 毫秒；阻止列表匹配超时或预算耗尽时按命中处理，拒绝发送链接。

建议转义域名中的 `.`，限定重复次数或字符范围，并避免嵌套、重叠或含糊的重复结构。

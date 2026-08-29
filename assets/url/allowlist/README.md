# URL 全局允许列表

URL 全局允许列表用于放行无法在模块代码中直接标记为可信的 HTTP(S) 链接。链接命中允许列表后，不会被 URLManager 作为未认证链接处理。

模块显式标记为不可信的链接仍会按不可信链接处理；全局 URL 阻止列表的优先级更高，同时命中两份列表时仍会拦截。

## 配置文件

目录中使用以下两个文件：

- `global.txt`：随主仓同步的规则，由项目维护者修改并提交。
- `user.txt`：部署者的本地规则，可手动创建，也可通过命令维护。该文件已被 Git 忽略。

两个文件使用相同格式：每行一条规则，空行以及以 `#` 开头的行会被忽略。

### 精确 URL

直接写入完整的 HTTP(S) URL：

```text
https://example.com/
https://example.com/download/file.zip
```

精确规则匹配规范化后的完整 URL，不是域名、目录或前缀匹配。规范化会统一协议和主机名大小写、国际化域名及默认端口，并将空路径转换为 `/`；查询参数和片段仍属于匹配内容。

### 正则表达式

文件中的正则规则必须以 `regex:` 开头：

```text
regex:https://[a-z-]+\.example\.org/w/api\.php
regex:https://example\.com/download/[^/?#]+\.zip
```

正则表达式使用 `fullmatch` 匹配规范化后的完整 URL，因此表达式需要覆盖协议、主机名、路径以及所需的查询参数或片段。无需仅为完整匹配额外添加 `^` 和 `$`。

## 命令配置

`url` 是仅限超级用户使用的基础模块。允许列表命令只修改 `user.txt`，不会修改 `global.txt`。

```text
~url allowlist add https://example.com/
~url allowlist add-regex https://[a-z-]+\.example\.org/w/api\.php
~url allowlist remove https://example.com/
~url allowlist remove-regex https://[a-z-]+\.example\.org/w/api\.php
~url allowlist query https://zh-cn.example.org/w/api.php
~url allowlist list
```

`add-regex` 和 `remove-regex` 接收正则表达式本身，不需要添加 `regex:` 前缀。`query` 会显示命中的规则及其来源。命令不能删除 `global.txt` 中的主仓规则。

对于 Wiki，可以向 `wiki-audit` 提供任意 Wiki 页面、站点首页或 API 地址。命令会先探测对应的规范 API URL，再将 API URL 写入 `user.txt`：

```text
~wiki-audit trust https://wiki.example.org/wiki/Example_Page
~wiki-audit query https://wiki.example.org/wiki/Example_Page
~wiki-audit distrust https://wiki.example.org/w/api.php
~wiki-audit block https://wiki.example.org/wiki/Example_Page
~wiki-audit unblock https://wiki.example.org/w/api.php
```

`trust`、`block` 与 `query` 会实时探测 API URL。`distrust` 和 `unblock` 优先使用已有 Wiki 缓存还原 API URL，以便站点已关闭时仍可删除规则；无法从缓存识别时，应直接提供 API URL。`query` 只查询规范 API URL 的全局 allowlist 状态。

`wiki-audit` 不会将用户提供的页面 URL 写入名单，也不会绕过全局 URL 阻止列表。

## 正则表达式安全限制

用户提供的正则表达式会受到以下限制：

- 单条规则最长 500 个字符，待匹配 URL 最长 4096 个字符。
- 全局规则与用户规则合计最多加载 256 条，其中正则规则最多 64 条。
- 每个配置文件最大为 64 KiB。
- 禁止递归、子程序调用、调用点、回溯控制动词及数字或命名反向引用等高风险结构。
- 能匹配安全探测 URL 的过宽表达式会被拒绝，例如 `.*`。
- 单条正则匹配限时 5 毫秒，一批正则匹配总计限时 20 毫秒；超时规则会被忽略。

建议转义域名中的 `.`，限定重复次数或字符范围，并避免嵌套、重叠或含糊的重复结构。

```text
~url allowlist add https://wiki.example.org/w/api.php
~url allowlist add-regex https://[a-z-]+\.example\.org/(?:w/)?api\.php
```

正则规则按完整 API URL 匹配，适合一次放行同一 Wiki 的不同语言站点，或兼容各站点不同的 API 路径规范。全局阻止列表优先级更高；同一 API 同时命中允许列表与阻止列表时，Wiki 会在请求内容前拒绝访问。

从旧版本升级时，原 `wiki-audit` 数据库规则会自动迁移到对应列表的 `user.txt`；旧 `assets/url/whitelist/user.txt` 也会自动合并到本目录。

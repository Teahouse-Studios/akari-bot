# URL 全局名单

本目录存放机器人发出 HTTP(S) 链接时使用的全局名单：

- `allowlist/`：允许列表，放行无法在模块代码中标记为可信的链接，命中后不再被 URLManager 视为未认证链接。模块显式标记为不可信的链接不受影响。
- `blocklist/`：阻止列表，命中的链接在消息文本、URL 元素和 Embed 中会被替换为拦截提示，Embed 跳转 URL 会被移除。

阻止列表优先级最高：即使链接被代码标记为可信或同时命中允许列表，仍会被拦截。

## 规则文件

每个名单目录包含两个文件：

- `global.txt`：随主仓同步的规则，由项目维护者修改。
- `user.txt`：部署者的本地规则，可手动创建或通过命令维护，已被 Git 忽略。

每行一条规则，空行及以 `#` 开头的行会被忽略。

```text
# 精确匹配完整 URL
https://example.com/download/file.zip

# 正则规则以 regex: 开头
regex:https://[a-z-]+\.example\.org/w/api\.php
```

规则匹配规范化后的完整 URL（协议与主机名大小写、国际化域名、默认端口及空路径会被统一），不是域名或前缀匹配。正则使用 `fullmatch`，需覆盖协议、主机名、路径及所需的查询参数。

## 命令

`url-audit` 仅限超级用户使用，只修改 `user.txt`，不能删除 `global.txt` 中的规则。将 `allowlist` 换为 `blocklist` 即可操作阻止列表。

```text
~url-audit allowlist add https://example.com/
~url-audit allowlist add-regex https://[a-z-]+\.example\.org/w/api\.php
~url-audit allowlist remove https://example.com/
~url-audit allowlist remove-regex https://[a-z-]+\.example\.org/w/api\.php
~url-audit allowlist query https://zh-cn.example.org/w/api.php
~url-audit allowlist list
```

`add-regex` / `remove-regex` 直接接收正则表达式，无需 `regex:` 前缀。

### Wiki

`wiki-audit` 接受任意 Wiki 页面、首页或 API 地址，探测出规范 API URL 后写入对应名单的 `user.txt`。命中阻止列表的 Wiki 会在请求内容前被拒绝。

```text
~wiki-audit trust https://wiki.example.org/wiki/Example_Page
~wiki-audit distrust https://wiki.example.org/w/api.php
~wiki-audit block https://wiki.example.org/wiki/Example_Page
~wiki-audit unblock https://wiki.example.org/w/api.php
~wiki-audit query https://wiki.example.org/wiki/Example_Page
```

`distrust` 和 `unblock` 优先从 Wiki 缓存还原 API URL，以便站点关闭后仍可删除规则；缓存无法识别时请直接提供 API URL。

## 正则限制

- 单条规则最长 500 字符；每份名单最多 256 条规则，其中正则最多 64 条；单个文件最大 64 KiB。
- 禁止递归、反向引用、回溯控制等高风险结构，能匹配探测 URL 的过宽表达式（如 `.*`）会被拒绝。
- 正则匹配有时间限制。允许列表超时视为未命中，阻止列表超时视为命中。

建议转义域名中的 `.`，限定重复次数与字符范围，避免嵌套或重叠的重复结构。

---

# Global URL Lists

This directory holds the global lists applied when the bot sends HTTP(S) links:

- `allowlist/`: Allows links that cannot be marked as trusted in module code. Matching links are no longer treated as unverified by URLManager. Links explicitly marked as untrusted by a module are unaffected.
- `blocklist/`: Matching links are replaced with a block notice in message text, URL elements, and embeds; embed target URLs are removed.

The blocklist has the highest priority: a link is blocked even if code marks it as trusted or it also matches the allowlist.

## Rule Files

Each list directory contains two files:

- `global.txt`: Rules synced with the main repository, maintained by the project maintainers.
- `user.txt`: Local rules for the deployer. Create it manually or manage it with commands. It is ignored by Git.

One rule per line. Empty lines and lines starting with `#` are ignored.

```text
# Exact match on the full URL
https://example.com/download/file.zip

# Regex rules start with regex:
regex:https://[a-z-]+\.example\.org/w/api\.php
```

Rules match the full normalized URL (scheme and host case, internationalized domains, default ports, and empty paths are normalized); they are not domain or prefix matches. Regex rules use `fullmatch` and must cover the scheme, host, path, and any required query parameters.

## Commands

`url-audit` is superuser-only. It only modifies `user.txt` and cannot remove rules from `global.txt`. Replace `allowlist` with `blocklist` to manage the blocklist.

```text
~url-audit allowlist add https://example.com/
~url-audit allowlist add-regex https://[a-z-]+\.example\.org/w/api\.php
~url-audit allowlist remove https://example.com/
~url-audit allowlist remove-regex https://[a-z-]+\.example\.org/w/api\.php
~url-audit allowlist query https://zh-cn.example.org/w/api.php
~url-audit allowlist list
```

`add-regex` / `remove-regex` take the regular expression directly, without the `regex:` prefix.

### Wiki

`wiki-audit` accepts any wiki page, main page, or API URL, detects the canonical API URL, and writes it to the corresponding `user.txt`. Wikis that match the blocklist are rejected before any content is requested.

```text
~wiki-audit trust https://wiki.example.org/wiki/Example_Page
~wiki-audit distrust https://wiki.example.org/w/api.php
~wiki-audit block https://wiki.example.org/wiki/Example_Page
~wiki-audit unblock https://wiki.example.org/w/api.php
~wiki-audit query https://wiki.example.org/wiki/Example_Page
```

`distrust` and `unblock` first try to resolve the API URL from the wiki cache, so rules can still be removed after a site goes offline. If the cache does not recognize the URL, provide the API URL directly.

## Regex Limits

- Each rule is at most 500 characters; each list loads at most 256 rules, of which at most 64 are regex; each file is at most 64 KiB.
- High-risk constructs such as recursion, backreferences, and backtracking control verbs are rejected, as are overly broad patterns that match probe URLs (e.g. `.*`).
- Regex matching is time-limited. A timeout counts as no match for the allowlist and as a match for the blocklist.

Escape `.` in domain names, bound repetitions and character ranges, and avoid nested or overlapping repetitions.

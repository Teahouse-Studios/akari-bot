# data 目录

本目录存放**运行时与部署者产生**的可写内容。与之相对，`assets` 目录只存放随仓库分发的只读内容。

## 约定

- 随仓库分发、运行时只读的文件放 `assets/`。
- 程序写入的文件，以及由部署者提供且已被 Git 忽略的文件，放 `data/`。
- 模块自身的可写数据放在模块目录下的 `data/`（例如 `modules/phigros/data/`）；模块内随仓库分发的只读内容仍在模块的 `assets/`。
- 少数只读但属于「数据文件」的内容保留 `data` 子目录名，置于 `assets` 之下（例如 `modules/mkey/assets/data/`）。

## 目录结构

| 路径 | 用途 |
| --- | --- |
| `data/i18n_cache/` | 国际化快照缓存，位置由 `AKARI_BOT_I18N_CACHE_DIR` 指定 |
| `data/private/<client>/` | 客户端私有数据：版本标记、模块加载缓存、Matrix 同步数据、Web 密码、用户存档等 |
| `data/union_merge_logs/` | 账号合并前的数据快照 |
| `data/url_audit/{allowlist,blocklist}/user.txt` | 部署者维护的 URL 规则（`global.txt` 仍在 `assets/url_audit/`） |
| `data/bad_words/` | 本地文本过滤词库，每个 `.txt` 为一个分类 |
| `data/retired/` | 客户端下线公告文案 |
| `data/config_store_bak/` | 配置生成脚本的临时备份 |

> 除各目录内的说明文档外，本目录中的内容均已被 Git 忽略，不随仓库分发。

---

## `data` directory

This directory holds **writable** content produced at runtime or provided by the operator.

- Files shipped with the repository that are read-only live in `assets/`.
- Files written by the program, or provided by the operator and ignored by Git, live in `data/`.
- A module's own writable data lives in its `data/` directory (e.g. `modules/phigros/data/`), while its shipped read-only content stays in its `assets/`.
- A few read-only directories keep the `data` name nested under `assets` (e.g. `modules/mkey/assets/data/`).

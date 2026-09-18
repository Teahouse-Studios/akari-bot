"""
assets / data 布局迁移脚本。

旧版把可写内容与只读资源一并放在 ``assets`` 下。新版按「只读留 assets、可写进 data」
拆分：运行时产物、部署者提供的内容以及模块的下载资源改放 ``data`` 目录。

升级既有部署时，从仓库根目录执行一次：

    python core/scripts/migrate_assets_to_data.py [--dry-run]

脚本只做移动，不覆盖目标位置已存在的文件，因而可以重复执行；已经迁移过的条目会被跳过。
"""

import shutil
import sys
from pathlib import Path

# (旧路径, 新路径)
MOVES = [
    ("assets/i18n_cache", "data/i18n_cache"),
    ("assets/private", "data/private"),
    ("assets/union_merge_logs", "data/union_merge_logs"),
    ("assets/bad_words", "data/bad_words"),
    ("assets/retired", "data/retired"),
    ("assets/config_store_bak", "data/config_store_bak"),
    ("assets/url_audit/allowlist/user.txt", "data/url_audit/allowlist/user.txt"),
    ("assets/url_audit/blocklist/user.txt", "data/url_audit/blocklist/user.txt"),
    ("modules/ai/assets/instructions.txt", "modules/ai/data/instructions.txt"),
    ("modules/ai/assets/llm_api_list.yaml", "modules/ai/data/llm_api_list.yaml"),
    ("modules/ai/assets/llm_api_list.yml", "modules/ai/data/llm_api_list.yml"),
    ("modules/mkey/data", "modules/mkey/assets/data"),
    ("modules/threedsdb/data", "modules/threedsdb/assets/data"),
]


def migrate(root: Path, dry_run: bool = False) -> int:
    """按 :data:`MOVES` 逐条迁移，返回实际处理（或 dry run 下预计处理）的条目数。

    :param root: 仓库根目录。
    :param dry_run: 为 True 时只打印计划，不做实际改动。
    """
    moved = 0
    for source, target in MOVES:
        src = root / source
        dst = root / target
        if not src.exists():
            print(f"skip (not found): {source}")
            continue
        if dst.exists():
            print(f"skip (target exists): {source} -> {target}")
            continue
        print(f"{'would move' if dry_run else 'move'}: {source} -> {target}")
        moved += 1
        if dry_run:
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
    return moved


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv[1:]
    count = migrate(Path("."), dry_run=dry_run)
    print(f"{'Would move' if dry_run else 'Moved'} {count} entr{'y' if count == 1 else 'ies'}.")

"""Phigros 资源自动更新测试。"""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import AsyncMock, Mock, patch

import orjson

from core.tester import Tester, func_case
from modules.phigros.libraries import assets

SONG_INFO = {
    "song.id": {
        "name": "Song",
        "artist": "Artist",
        "illustrator": "Illustrator",
        "charter": {},
        "diff": {"EZ": 1.0},
    }
}
INFO_TSV = "song.id\tSong\tArtist\tIllustrator\n"
DIFF_TSV = "song.id\t1.0\n"


def _patch_asset_paths(root: Path):
    asset_dir = root / "assets"
    return patch.multiple(
        assets,
        pgr_assets_path=asset_dir,
        song_info_path=asset_dir / "song_info.json",
        illustration_dir=asset_dir / "illustration",
        version_path=asset_dir / "resource_version.txt",
        random_cache_path=Mock(return_value=root / "resource-temp"),
    )


async def _test_remote_update_writes_version_and_song_info():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        responses = {
            assets.VERSION_URL: "2.0\n",
            assets.INFO_TSV_URL: INFO_TSV,
            assets.DIFF_TSV_URL: DIFF_TSV,
        }

        async def get_url(url, status_code=200):
            return responses[url]

        with _patch_asset_paths(root), patch.object(assets, "get_url", new=get_url):
            assets.version_path.parent.mkdir(parents=True)
            assets.version_path.write_text("1.0", encoding="utf-8")
            result = await assets.update_assets(update_illustration=False)

            return (
                result
                and assets.version_path.read_text(encoding="utf-8") == "2.0"
                and assets.load_song_info() == SONG_INFO
            )


async def _test_same_version_skips_update():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)
        with _patch_asset_paths(root), patch.object(assets, "get_url", new=AsyncMock(return_value="1.0")):
            assets.version_path.parent.mkdir(parents=True)
            assets.version_path.write_text("1.0", encoding="utf-8")
            assets.song_info_path.write_bytes(orjson.dumps(SONG_INFO))
            updater = AsyncMock()
            with patch.object(assets, "_update_assets_locked", new=updater):
                result = await assets.check_and_update_assets(update_illustration=False)

            return result is None and not updater.await_args_list


async def _test_failed_update_preserves_version():
    with TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        async def get_url(url, status_code=200):
            if url == assets.VERSION_URL:
                return "2.0"
            raise RuntimeError("resource unavailable")

        with _patch_asset_paths(root), patch.object(assets, "get_url", new=get_url):
            assets.version_path.parent.mkdir(parents=True)
            assets.version_path.write_text("1.0", encoding="utf-8")
            result = await assets.update_assets(update_illustration=False)

            return not result and assets.version_path.read_text(encoding="utf-8") == "1.0"


async def _test_concurrent_checks_are_serialized():
    with TemporaryDirectory() as temp_dir:
        active = 0
        max_active = 0

        async def update(*args):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0)
            active -= 1
            return True

        with (
            _patch_asset_paths(Path(temp_dir)),
            patch.object(assets, "_remote_version", new=AsyncMock(return_value="2.0")),
            patch.object(assets, "_update_assets_locked", new=update),
        ):
            results = await asyncio.gather(
                assets.check_and_update_assets(update_illustration=False),
                assets.check_and_update_assets(update_illustration=False),
            )

        return results == [True, True] and max_active == 1


@func_case
async def test_phigros_assets(tester: Tester):
    """phigros：资源版本检查与更新。"""
    await tester.test(_test_remote_update_writes_version_and_song_info, "远端版本更新并写入资源")
    await tester.test(_test_same_version_skips_update, "版本一致时跳过更新")
    await tester.test(_test_failed_update_preserves_version, "更新失败保留本地版本")
    await tester.test(_test_concurrent_checks_are_serialized, "并发检查串行执行")
    return tester

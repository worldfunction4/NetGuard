"""OSS 同步回归：files 列表不能扩成整目录扫描；没有凭据返回 False"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from backup.cloud import sync_backup_to_cloud


class TestCloudSyncFiles:
    def test_files_list_uploads_only_those_files(self, tmp_path):
        """修复前忽略 files，对 local_path 做 rglob / upload_dir"""
        chosen_a = tmp_path / "SW-01" / "a_before.txt"
        chosen_b = tmp_path / "SW-01" / "a_after.txt"
        decoy = tmp_path / "SW-01" / "historical.txt"
        for path in (chosen_a, chosen_b, decoy):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("snapshot", encoding="utf-8")

        client = MagicMock()
        client.upload.return_value = True
        client.upload_dir.side_effect = AssertionError("不应扫描整个备份目录")

        with patch("backup.cloud.make_oss_client_from_env", return_value=client):
            ok = sync_backup_to_cloud(
                local_path=str(tmp_path),
                files=[str(chosen_a), str(chosen_b)],
            )

        assert ok is True
        uploaded = {Path(call.args[0]).resolve() for call in client.upload.call_args_list}
        assert uploaded == {chosen_a.resolve(), chosen_b.resolve()}
        client.upload_dir.assert_not_called()

    def test_no_credentials_returns_false(self, tmp_path):
        target = tmp_path / "only.txt"
        target.write_text("x", encoding="utf-8")
        with patch.dict(os.environ, {
            "OSS_ACCESS_KEY": "",
            "OSS_SECRET_KEY": "",
            "OSS_BUCKET": "",
        }):
            ok = sync_backup_to_cloud(local_path=str(tmp_path), files=[str(target)])
        assert ok is False

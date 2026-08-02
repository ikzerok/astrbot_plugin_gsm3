"""core.api 模块单元测试"""

import pytest

from core.api import GSM3Client, fmt_time


class TestFmtTime:
    def test_iso_utc_to_bjt(self):
        """UTC 时间应正确转换为北京时间（+8）"""
        assert fmt_time("2026-08-02T13:07:19.904Z") == "08-02 21:07"

    def test_empty(self):
        assert fmt_time("") == "未知"
        assert fmt_time(None) == "未知"  # type: ignore[arg-type]

    def test_invalid(self):
        assert fmt_time("not-a-time") == "未知"


class TestFindInstances:
    @pytest.mark.asyncio
    async def test_exact_id(self, monkeypatch):
        instances = [
            {"id": "abc-123", "name": "泰拉瑞亚", "status": "stopped"},
            {"id": "def-456", "name": "龙之冒险", "status": "running"},
        ]
        client = GSM3Client("http://127.0.0.1:3001", "test-key")

        async def fake_list():
            return instances, None

        monkeypatch.setattr(client, "list_instances", fake_list)
        found, err = await client.find_instances("abc-123")
        assert err is None
        assert found == [instances[0]]

    @pytest.mark.asyncio
    async def test_fuzzy_name(self, monkeypatch):
        instances = [
            {"id": "abc-123", "name": "泰拉瑞亚", "status": "stopped"},
            {"id": "def-456", "name": "泰拉瑞亚_tmodloader", "status": "stopped"},
        ]
        client = GSM3Client("http://127.0.0.1:3001", "test-key")

        async def fake_list():
            return instances, None

        monkeypatch.setattr(client, "list_instances", fake_list)
        found, err = await client.find_instances("泰拉瑞亚")
        assert err is None
        assert len(found) == 2

    @pytest.mark.asyncio
    async def test_not_found(self, monkeypatch):
        client = GSM3Client("http://127.0.0.1:3001", "test-key")

        async def fake_list():
            return [], None

        monkeypatch.setattr(client, "list_instances", fake_list)
        found, err = await client.find_instances("不存在的服")
        assert found == []
        assert err is None

    @pytest.mark.asyncio
    async def test_empty_keyword(self):
        client = GSM3Client("http://127.0.0.1:3001", "test-key")
        found, err = await client.find_instances("")
        assert found is None
        assert err == "请提供实例名称或 ID"

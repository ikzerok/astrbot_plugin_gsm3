"""GSM3 API 客户端：封装 GSManager3 external API 的所有请求。"""

from datetime import datetime, timedelta, timezone

import httpx

BJT = timezone(timedelta(hours=8))  # 北京时间

ACTION_MAP = {
    "start": ("启动", "POST", "/api/external/instances/{id}/start"),
    "stop": ("停止", "POST", "/api/external/instances/{id}/stop"),
    "restart": ("重启", "POST", "/api/external/instances/{id}/restart"),
}

STATUS_ICON = {
    "running": "🟢 运行中",
    "starting": "🟡 启动中",
    "stopping": "🟠 停止中",
    "stopped": "⚫ 已停止",
}


def fmt_time(iso_str: str) -> str:
    """ISO 时间转北京时间，失败返回 '未知'"""
    if not iso_str:
        return "未知"
    try:
        t = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(BJT)
        return t.strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return "未知"


class GSM3Client:
    """GSManager3 external API 客户端"""

    def __init__(self, base_url: str, api_key: str, timeout: int = 10):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    async def request(self, method: str, path: str, **kwargs) -> dict:
        """统一请求封装，带 Bearer 认证。任何异常都返回错误字典，不让插件崩溃。"""
        if not self.api_key:
            return {"success": False, "message": "未配置 API Key，请在插件配置中填写"}
        headers = {"Authorization": f"Bearer {self.api_key}"}
        url = f"{self.base_url}{path}"
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.request(method, url, headers=headers, **kwargs)
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            return {
                "success": False,
                "message": f"HTTP {e.response.status_code}: {e.response.text[:200]}",
            }
        except httpx.HTTPError as e:
            return {"success": False, "message": f"请求失败: {type(e).__name__}: {e}"}
        except Exception as e:
            return {"success": False, "message": f"未知错误: {type(e).__name__}: {e}"}

    async def list_instances(self) -> tuple[list | None, str | None]:
        """拉取全部实例。成功返回 (实例列表, None)，失败返回 (None, 错误信息)。"""
        data = await self.request("GET", "/api/external/instances")
        if not data.get("success"):
            return None, data.get("message", "API 请求失败")
        instances = data.get("data") or []
        return instances, None

    async def find_instances(self, keyword: str) -> tuple[list | None, str | None]:
        """按关键字查找实例：先精确匹配 ID，再按名称模糊匹配。"""
        if not keyword:
            return None, "请提供实例名称或 ID"
        instances, err = await self.list_instances()
        if err:
            return None, err
        exact = [i for i in instances if i.get("id") == keyword]
        if exact:
            return exact, None
        fuzzy = [i for i in instances if keyword.lower() in i.get("name", "").lower()]
        return fuzzy, None

    async def control(
        self, instance_id: str, action: str, use_action_endpoint: bool = False
    ) -> dict:
        """执行 start/stop/restart。返回 API 原始响应。"""
        label, method, path_tmpl = ACTION_MAP[action]
        if use_action_endpoint:
            path = f"/api/external/instances/{instance_id}/action"
            payload = {"json": {"action": action}}
        else:
            path = path_tmpl.format(id=instance_id)
            payload = {}
        data = await self.request(method, path, **payload)
        if data.get("success"):
            return {"success": True, "message": data.get("message") or f"{label}成功"}
        return {"success": False, "message": data.get("message", data.get("error", "未知错误"))}

    def fmt_instance(self, inst: dict) -> str:
        """格式化单个实例为可读文本"""
        status = STATUS_ICON.get(inst.get("status"), inst.get("status", "未知"))
        lines = [
            f"📦 {inst.get('name', '未知')}",
            f"  状态: {status}",
            f"  类型: {inst.get('instanceType', '未知')}",
        ]
        if inst.get("lastStarted"):
            lines.append(f"  上次启动: {fmt_time(inst['lastStarted'])}")
        if inst.get("lastStopped"):
            lines.append(f"  上次停止: {fmt_time(inst['lastStopped'])}")
        if inst.get("workingDirectory"):
            lines.append(f"  目录: {inst.get('workingDirectory')}")
        return "\n".join(lines)

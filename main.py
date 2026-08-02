from datetime import datetime, timedelta, timezone

import httpx
from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star
from astrbot.core.star.filter.command import GreedyStr

BJT = timezone(timedelta(hours=8))  # 北京时间

STATUS_ICON = {
    "running": "🟢 运行中",
    "starting": "🟡 启动中",
    "stopping": "🟠 停止中",
    "stopped": "⚫ 已停止",
}

ACTION_MAP = {
    "start": ("启动", "POST", "/api/external/instances/{id}/start"),
    "stop": ("停止", "POST", "/api/external/instances/{id}/stop"),
    "restart": ("重启", "POST", "/api/external/instances/{id}/restart"),
}


def _fmt_time(iso_str: str) -> str:
    """ISO 时间转北京时间，失败返回 '未知'"""
    if not iso_str:
        return "未知"
    try:
        t = datetime.fromisoformat(iso_str.replace("Z", "+00:00")).astimezone(BJT)
        return t.strftime("%m-%d %H:%M")
    except (ValueError, TypeError):
        return "未知"


class Gsm3Plugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.base_url = (config.get("base_url") or "http://127.0.0.1:3001").rstrip("/")
        self.api_key = config.get("api_key") or ""
        self.timeout = config.get("timeout") or 10

    # ─────────────── API 基础 ───────────────

    async def _request(self, method: str, path: str, **kwargs) -> dict:
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

    async def _list_instances(self) -> tuple[list | None, str | None]:
        """拉取全部实例。成功返回 (实例列表, None)，失败返回 (None, 错误信息)。"""
        data = await self._request("GET", "/api/external/instances")
        if not data.get("success"):
            return None, data.get("message", "API 请求失败")
        return data.get("data", []), None

    async def _find_instances(self, keyword: str) -> tuple[list | None, str | None]:
        """按关键字查找实例：先精确匹配 ID，再按名称模糊匹配。"""
        if not keyword:
            return None, "请提供实例名称或 ID"
        instances, err = await self._list_instances()
        if err:
            return None, err
        exact = [i for i in instances if i.get("id") == keyword]
        if exact:
            return exact, None
        fuzzy = [i for i in instances if keyword.lower() in i.get("name", "").lower()]
        return fuzzy, None

    def _fmt_instance(self, inst: dict) -> str:
        """格式化单个实例为可读文本"""
        status = STATUS_ICON.get(inst.get("status"), inst.get("status", "未知"))
        lines = [
            f"📦 {inst.get('name', '未知')}",
            f"  状态: {status}",
            f"  类型: {inst.get('instanceType', '未知')}",
        ]
        if inst.get("lastStarted"):
            lines.append(f"  上次启动: {_fmt_time(inst['lastStarted'])}")
        if inst.get("lastStopped"):
            lines.append(f"  上次停止: {_fmt_time(inst['lastStopped'])}")
        if inst.get("workingDirectory"):
            lines.append(f"  目录: {inst.get('workingDirectory')}")
        return "\n".join(lines)

    # ─────────────── 指令组 ───────────────

    @filter.command_group("gsm")
    def gsm(self):
        """GSM3 游戏服务器管理"""
        pass

    # /gsm list —— 列出所有实例及状态
    @gsm.command("list")
    async def gsm_list(self, event: AstrMessageEvent):
        instances, err = await self._list_instances()
        if err:
            yield event.plain_result(f"❌ {err}")
            return
        if not instances:
            yield event.plain_result("当前没有实例。")
            return
        lines = [f"共 {len(instances)} 个实例："]
        for inst in instances:
            status = STATUS_ICON.get(inst.get("status"), inst.get("status", "未知"))
            lines.append(f"• {inst.get('name', '未知')} — {status}")
        lines.append("")
        lines.append("使用 /gsm status <名称> 查看详情，/gsm start|stop|restart <名称> 控制实例。")
        yield event.plain_result("\n".join(lines))

    # /gsm status [名称/ID] —— 查看实例状态（不填则列出全部）
    @gsm.command("status")
    async def gsm_status(self, event: AstrMessageEvent, name: str = ""):
        if not name:
            # 复用 list 逻辑
            for result in self.gsm_list(event):
                yield result
            return
        found, err = await self._find_instances(name)
        if err:
            yield event.plain_result(f"❌ {err}")
            return
        if not found:
            yield event.plain_result(f"❌ 没有找到匹配「{name}」的实例")
            return
        if len(found) > 1:
            names = "、".join(i.get("name", "?") for i in found)
            yield event.plain_result(f"匹配到多个实例（{names}），请用更精确的名称或实例 ID。")
            return
        yield event.plain_result(self._fmt_instance(found[0]))

    # /gsm start <名称/ID> —— 启动实例
    @gsm.command("start")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def gsm_start(self, event: AstrMessageEvent, name: GreedyStr):
        async for result in self._control(event, name, "start"):
            yield result

    # /gsm stop <名称/ID> —— 停止实例
    @gsm.command("stop")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def gsm_stop(self, event: AstrMessageEvent, name: GreedyStr):
        async for result in self._control(event, name, "stop"):
            yield result

    # /gsm restart <名称/ID> —— 重启实例
    @gsm.command("restart")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def gsm_restart(self, event: AstrMessageEvent, name: GreedyStr):
        async for result in self._control(event, name, "restart"):
            yield result

    # /gsm action <名称/ID> <start|stop|restart> —— 底层 action 接口
    @gsm.command("action")
    @filter.permission_type(filter.PermissionType.ADMIN)
    async def gsm_action(self, event: AstrMessageEvent, args: GreedyStr):
        parts = args.strip().split()
        if len(parts) < 2:
            yield event.plain_result("用法: /gsm action <实例名称或ID> <start|stop|restart>")
            return
        action = parts[-1].lower()
        name = " ".join(parts[:-1])
        if action not in ACTION_MAP:
            yield event.plain_result(f"❌ 动作必须是 start、stop 或 restart，收到: {action}")
            return
        async for result in self._control(event, name, action, use_action_endpoint=True):
            yield result

    # ─────────────── 内部控制逻辑 ───────────────

    async def _control(
        self,
        event: AstrMessageEvent,
        name: str,
        action: str,
        use_action_endpoint: bool = False,
    ):
        """执行 start/stop/restart 的公共逻辑"""
        label, method, path_tmpl = ACTION_MAP[action]

        # 找到实例（支持 ID 精确或名称模糊）
        found, err = await self._find_instances(name)
        if err:
            yield event.plain_result(f"❌ {err}")
            return
        if not found:
            yield event.plain_result(f"❌ 没有找到匹配「{name}」的实例")
            return
        if len(found) > 1:
            names = "、".join(i.get("name", "?") for i in found)
            yield event.plain_result(f"匹配到多个实例（{names}），请用更精确的名称或实例 ID。")
            return

        inst = found[0]
        inst_id = inst["id"]

        # 已经在目标状态时直接提示（start 已在运行 / stop 已停止）
        if action == "start" and inst.get("status") == "running":
            yield event.plain_result(f"ℹ️ 「{inst.get('name')}」已经在运行了。")
            return
        if action == "stop" and inst.get("status") == "stopped":
            yield event.plain_result(f"ℹ️ 「{inst.get('name')}」已经停止了。")
            return

        if use_action_endpoint:
            path = f"/api/external/instances/{inst_id}/action"
            payload = {"json": {"action": action}}
        else:
            path = path_tmpl.format(id=inst_id)
            payload = {}

        data = await self._request(method, path, **payload)
        if data.get("success"):
            msg = data.get("message") or f"{label}成功"
            yield event.plain_result(f"✅ {msg}")
        else:
            yield event.plain_result(
                f"❌ {label}失败: {data.get('message', data.get('error', '未知错误'))}"
            )

    # ─────────────── 生命周期 ───────────────

    async def terminate(self):
        """插件卸载/停用时的清理"""
        logger.info("[gsm3] 插件已卸载")

"""
GSM3 服务器管理 - AstrBot 插件

管理 GSManager3 游戏服务器面板上的实例：查看状态、启动、停止、重启。
"""

from astrbot.api import AstrBotConfig, logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.star import Context, Star, register
from astrbot.core.star.filter.command import GreedyStr

from .core import ACTION_MAP, STATUS_ICON, GSM3Client

PLUGIN_NAME = "gsm3_manager"
PLUGIN_VERSION = "1.3.4"


@register(
    PLUGIN_NAME,
    "ikzerok",
    "管理 GSM3 (GSManager3) 上的游戏服务器实例 - 查看状态、启动、停止、重启",
    PLUGIN_VERSION,
    "https://github.com/ikzerok/astrbot_plugin_gsm3",
)
class Gsm3Plugin(Star):
    """GSM3 游戏服务器管理插件"""

    def __init__(self, context: Context, config: AstrBotConfig = None):
        super().__init__(context)
        self.config = config
        self.client = GSM3Client(
            base_url=config.get("base_url") or "http://127.0.0.1:3001",
            api_key=config.get("api_key") or "",
            timeout=config.get("timeout") or 10,
        )
        logger.info(f"GSM3 插件初始化完成: {self.client.base_url}")

    # ─────────────── 指令组 ───────────────

    @filter.command_group("gsm")
    def gsm(self):
        """GSM3 游戏服务器管理"""
        pass

    # /gsm help —— 显示帮助信息
    @gsm.command("help")
    async def gsm_help(self, event: AstrMessageEvent):
        lines = [
            "🎮 GSM3 服务器管理",
            "",
            "/gsm help — 显示本帮助",
            "/gsm list — 列出所有实例及状态",
            '/gsm status <"名称/ID"> — 查看实例详情（不填则列出全部）',
            '/gsm start <"名称/ID"> — 启动实例',
            '/gsm stop <"名称/ID"> — 停止实例',
            '/gsm restart <"名称/ID"> — 重启实例',
            '/gsm action <"名称/ID"> <start|stop|restart> — 底层操作接口',
            "",
            '实例名支持模糊匹配，例如 /gsm stop "泰拉瑞亚"；名称含空格时请务必用双引号包裹。',
        ]
        yield event.plain_result("\n".join(lines))

    # /gsm list —— 列出所有实例及状态
    @gsm.command("list")
    async def gsm_list(self, event: AstrMessageEvent):
        instances, err = await self.client.list_instances()
        if err:
            yield event.plain_result(f"❌ {err}")
            return
        if not instances:
            yield event.plain_result("当前没有实例。")
            return
        lines = [f"共 {len(instances)} 个实例："]
        for inst in instances:
            status = STATUS_ICON.get(inst.get("status"), inst.get("status", "未知"))
            lines.append(f'• "{inst.get("name", "未知")}" — {status}')
        lines.append("")
        lines.append(
            '使用 /gsm status <"名称"> 查看详情，/gsm start|stop|restart <"名称"> 控制实例。'
        )
        yield event.plain_result("\n".join(lines))

    # /gsm status [名称/ID] —— 查看实例状态（不填则列出全部）
    @gsm.command("status")
    async def gsm_status(self, event: AstrMessageEvent, name: str = ""):
        if not name:
            async for result in self.gsm_list(event):
                yield result
            return
        found, err = await self.client.find_instances(name)
        if err:
            yield event.plain_result(f"❌ {err}")
            return
        if not found:
            yield event.plain_result(f'❌ 没有找到匹配 "{name}" 的实例')
            return
        if len(found) > 1:
            names = "、".join(f'"{i.get("name", "?")}"' for i in found)
            yield event.plain_result(f"匹配到多个实例（{names}），请用更精确的名称或实例 ID。")
            return
        yield event.plain_result(self.client.fmt_instance(found[0]))

    # /gsm start <名称/ID> —— 启动实例
    @gsm.command("start")
    async def gsm_start(self, event: AstrMessageEvent, name: GreedyStr):
        async for result in self._control(event, name, "start"):
            yield result

    # /gsm stop <名称/ID> —— 停止实例
    @gsm.command("stop")
    async def gsm_stop(self, event: AstrMessageEvent, name: GreedyStr):
        async for result in self._control(event, name, "stop"):
            yield result

    # /gsm restart <名称/ID> —— 重启实例
    @gsm.command("restart")
    async def gsm_restart(self, event: AstrMessageEvent, name: GreedyStr):
        async for result in self._control(event, name, "restart"):
            yield result

    # /gsm action <名称/ID> <start|stop|restart> —— 底层 action 接口
    @gsm.command("action")
    async def gsm_action(self, event: AstrMessageEvent, args: GreedyStr):
        parts = args.strip().split()
        if len(parts) < 2:
            yield event.plain_result('用法: /gsm action <"实例名称或ID"> <start|stop|restart>')
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
        self, event: AstrMessageEvent, name: str, action: str, use_action_endpoint: bool = False
    ):
        """执行 start/stop/restart 的公共逻辑"""
        label = ACTION_MAP[action][0]

        # 找到实例（支持 ID 精确或名称模糊）
        found, err = await self.client.find_instances(name)
        if err:
            yield event.plain_result(f"❌ {err}")
            return
        if not found:
            yield event.plain_result(f'❌ 没有找到匹配 "{name}" 的实例')
            return
        if len(found) > 1:
            names = "、".join(f'"{i.get("name", "?")}"' for i in found)
            yield event.plain_result(f"匹配到多个实例（{names}），请用更精确的名称或实例 ID。")
            return

        inst = found[0]
        inst_id = inst["id"]

        # 已经在目标状态时直接提示（start 已在运行 / stop 已停止）
        if action == "start" and inst.get("status") == "running":
            yield event.plain_result(f'ℹ️ "{inst.get("name")}" 已经在运行了。')
            return
        if action == "stop" and inst.get("status") == "stopped":
            yield event.plain_result(f'ℹ️ "{inst.get("name")}" 已经停止了。')
            return

        result = await self.client.control(inst_id, action, use_action_endpoint)
        if result.get("success"):
            yield event.plain_result(f"✅ {result['message']}")
        else:
            yield event.plain_result(f"❌ {label}失败: {result['message']}")

    # ─────────────── 生命周期 ───────────────

    async def terminate(self):
        """插件卸载/停用时的清理"""
        logger.info("[gsm3] 插件已卸载")

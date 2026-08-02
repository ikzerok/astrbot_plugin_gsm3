# astrbot_plugin_gsm3

![logo](logo.png)

AstrBot 插件：管理 [GSManager3](https://github.com/nichacker/GSManager3) 游戏服务器面板上的实例。支持查看实例列表/状态、启动、停止、重启。

## 功能

- `/gsm list` — 列出所有实例及运行状态
- `/gsm status [名称/ID]` — 查看实例详情（不填参数则列出全部）
- `/gsm start <名称/ID>` — 启动实例（仅管理员）
- `/gsm stop <名称/ID>` — 停止实例（仅管理员）
- `/gsm restart <名称/ID>` — 重启实例（仅管理员）
- `/gsm action <名称/ID> <start|stop|restart>` — 调用底层 action 接口（仅管理员）

实例支持**精确 ID** 或**名称模糊匹配**（如 `/gsm stop 泰拉瑞亚`），匹配到多个时会提示你使用更精确的名称。

## 安装

### 方式一：插件市场安装（发布后）

在 AstrBot 管理面板 → 插件 → 插件市场，搜索 `gsm3` 安装。

### 方式二：手动安装

```bash
git clone https://github.com/ikzerok/astrbot_plugin_gsm3 /AstrBot/data/plugins/astrbot_plugin_gsm3
docker exec astrbot pip install -r /AstrBot/data/plugins/astrbot_plugin_gsm3/requirements.txt
docker restart astrbot
```

## 配置

在 AstrBot 管理面板 → 插件 → gsm3 → 设置 中填写：

| 配置项 | 说明 | 默认值 |
| --- | --- | --- |
| `base_url` | GSManager3 外部 API 地址 | `http://127.0.0.1:3001` |
| `api_key` | `/api/external` 接口的 Bearer Token | 空 |
| `timeout` | 请求超时（秒） | `10` |

## API 对接说明

调用 GSManager3 的 external API，全部请求携带 `Authorization: Bearer <api_key>`：

| 接口 | 方法 | 用途 |
| --- | --- | --- |
| `/api/external/instances` | GET | 实例列表 |
| `/api/external/instances/:id` | GET | 实例详情 |
| `/api/external/instances/:id/status` | GET | 实例状态 |
| `/api/external/instances/:id/start` | POST | 启动 |
| `/api/external/instances/:id/stop` | POST | 停止 |
| `/api/external/instances/:id/restart` | POST | 重启 |
| `/api/external/instances/:id/action` | POST | 通用操作（body: `{"action":"start\|stop\|restart"}`） |

## 开发

```bash
# 格式化（提交前请运行）
ruff format .
# lint
ruff check .
```

## License

MIT

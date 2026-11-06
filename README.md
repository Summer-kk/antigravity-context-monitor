# Antigravity Context Monitor (当前上下文监控插件)

<p align="center">
  <img src="assets/logo.svg" alt="Context Monitor Logo" width="100" height="100" />
</p>

<p align="center">
  <b>Google Antigravity 2.0 原生可视化侧边栏仪表盘 · 实时监控上下文占用与生命周期演进</b>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Antigravity-2.0+-blue?style=flat-square" alt="Antigravity 2.0+">
  <img src="https://img.shields.io/badge/Dependencies-0%20(Pure%20Stdlib)-emerald?style=flat-square" alt="Zero Dependencies">
  <img src="https://img.shields.io/badge/Platform-Windows%20(10%2F11)-sky?style=flat-square" alt="Windows Platform">
  <img src="https://img.shields.io/badge/Python-3.8+%20(py)-purple?style=flat-square" alt="Python py launcher">
  <img src="https://img.shields.io/badge/License-MIT-amber?style=flat-square" alt="License">
</p>

<p align="center">
  <img src="assets/preview.png" alt="Antigravity Context Monitor Preview" width="480" />
</p>

---

## 🌟 为什么需要本插件？

在进行复杂的长程编码、大文件读取或多轮调试时，**上下文膨胀（Context Bloat）** 是导致 Agent 遗忘历史、响应降级甚至触发截断压缩的关键原因。

**Antigravity Context Monitor** 专为解决这一痛点而生：
- 零侵入对话上下文，不消耗对话 Token；
- 依托 Antigravity 原生 **UI Sidecar** 体系，在侧边栏提供独立的可视化 HUD 面板；
- 实时洞察当前会话的上下文体积、缓存命中率、步骤增量及自动压缩事件。

---

## ✨ 核心特性

- 🎯 **256k 真实上限基准**：基于 Antigravity 实际上下文限制（262,144 Tokens）精准计算占用比例与可用余量，严密贴合触发压缩的阈值线。
- 📈 **全生命周期全景走势图**：
  - 突破传统“仅展示最近40轮”的视野盲区，完整提取 Step 1 到最新步的全量波形；
  - **1:1 物理像素矢量渲染**：圆点始终圆润饱满，文字清晰规整，彻底消除缩放拉伸变形；
  - **十字准星吸附探针**：鼠标悬停在曲线上即可丝滑追踪任意历史轮次的上下文总量、单步新增与工具调用；
  - **📉 压缩事件智能标注**：系统触发上下文瘦身与压缩时自动标记下落幅度，一目了然。
- 🎚️ **左右滑动可视化切换**：
  - 双态滑动胶囊开关（`⚡ 自动跟随` ⇋ `📌 已锁定`）；
  - 智能防抖引擎优先按真实用户交互排序，告别后台文件写入引起的会话跳动。
- 📂 **按项目分类与会话分组**：
  - 会话列表置于走势图下方，自动按所属项目归类排布；
  - 支持顶部项目 Chip 快捷筛选与一键点击锁定切换；
  - 页面全局严格锁死在当前窗口内（`h-screen overflow-hidden`），零整页滚动条，仅列表内部平滑自适应滚动。
- ⚡ **零第三方依赖 (Zero Dependencies)**：
  - 后端仅依赖 Python 原生标准库（`http.server`、`sqlite3`、`json`），**无需 `pip install` 任何额外库**；
  - 前端纯原生 HTML5/Tailwind/SVG，极度轻巧敏捷。

---

## 🚀 一键安装方法 (Windows)

在 PowerShell 中执行以下一行命令，即可将插件克隆至 Antigravity 插件目录，开箱即用：

```powershell
git clone https://github.com/Summer-kk/antigravity-context-monitor.git "$HOME\.gemini\config\plugins\context-monitor"
```

> **提示**：克隆完成后，在 Antigravity 侧边栏即可直接点击开启。默认直接使用 Windows 官方 Python 启动器 `py`，零外部依赖，无需 `pip install` 任何库。

---

## 💡 使用方式

1. **直接点击原生侧边栏链接**：
   在任何对话中点击：
   `sidecar://context-monitor/context-hud/`
   即可立即在侧边辅助窗格打开专属 HUD 面板。

2. **与 Agent 自然交互**：
   在聊天窗口中直接向 Agent 发送：
   - *“查看当前上下文”*
   - *“监控当前 Token 消耗”*
   - *“检查上下文健康度”*
   
   Agent 将自动引导您打开原生侧边栏。

---

## 📁 项目结构

```text
context-monitor/
├── .gitignore               # 规范的 Git 忽略清单
├── LICENSE                  # MIT 开源许可证
├── README.md                # 项目文档
├── plugin.json              # 插件核心清单
├── assets/
│   └── logo.svg             # 插件矢量图标
├── rules/
│   └── AGENTS.md            # Agent 行为规范与侧窗入口指引
└── sidecars/
    └── context-hud/
        ├── sidecar.json     # Sidecar 启动与挂载配置
        ├── server.py        # 极简 HTTP 路由服务 (含进程热重载)
        ├── engine.py        # 上下文数据解析与防抖跟随引擎
        └── index.html       # 原生前端 HUD 面板
```

---

## 🤝 贡献与反馈

欢迎提交 Issue 或 Pull Request 共同改进！
如果您觉得这个插件对您有帮助，欢迎点亮右上角的 ⭐️ **Star**！

---

## 📄 开源许可

本项目遵循 [MIT License](LICENSE) 开源协议。

# Mouse Keeper

[English](README.md) · **简体中文** · [日本語](README.ja.md)

托盘常驻的鼠标保活小工具。让 Windows 认为你一直在操作电脑，从而让那些靠
"系统空闲时长"判断在线状态的程序 —— 大多数人是为了 Microsoft Teams ——
保持在线。

- 纯 `ctypes` 调用 Win32 API，不依赖 pyautogui / pynput 等自动化库
- 两种模式：**智能**（只在你真的离开时才动）/ **始终**（到点就动）
- 顺带阻止息屏与睡眠
- **锁屏时自动停手**并如实显示状态，解锁后自己继续
- **停顿看门狗**：机器从休眠 / Modern Standby 醒来后能自动恢复
- 一键开机自启
- **自绘的 Fluent 风格面板**：圆角、投影、悬停高亮、跟随系统深浅色、高 DPI 清晰
- **10 种界面语言**，按 Windows 显示语言自动检测
- **托盘图标跟随任务栏主题**，运行期间主题变化会自动切换

---

## 快速开始

**直接跑源码**

```bash
python -m venv .venv && .venv\Scripts\pip install -r requirements.txt && .venv\Scripts\pythonw main.py
```

**打包成 exe（推荐）**

```bash
powershell -ExecutionPolicy Bypass -File build.ps1
```

产物在 `dist\MouseKeeper\MouseKeeper.exe`，双击运行，图标出现在系统托盘。
**挪位置时请整个 `MouseKeeper` 文件夹一起挪。**

默认用 `--onedir`（文件夹）而不是 `--onefile`（单文件），是有意为之：onefile
会在每次运行时把自己解压到临时目录，这个行为本身就会踩杀软的启发式规则，是
PyInstaller 产物被误报成木马的主要原因之一。onedir 没有解压动作，误报率低得多，
启动也更快。确实需要单文件的话：

```bash
powershell -ExecutionPolicy Bypass -File build.ps1 -OneFile
```

**先自检一下**（强烈建议，验证这台机器上方案是否成立）：

```bash
.venv\Scripts\python main.py --check
```

预期看到 `+ Self-check passed`。若不通过，说明 `SendInput` 被系统或安全软件
拦下了，本工具在这台机器上无效。

自检输出**始终是英文**，与界面语言无关 —— 它是给排错的人看的诊断信息；而且
刻意只用 ASCII 字符，这样在中日文代码页下把输出重定向到管道也不会触发
`UnicodeEncodeError`。

---

## 两种模式

| | 智能（默认） | 始终 |
|---|---|---|
| 触发条件 | 系统空闲达到阈值（默认 60 秒） | 每隔 N 秒无条件触发（默认 45 秒） |
| 你在用电脑时 | **完全静默**，一次都不动 | 照常注入，偶尔和你抢鼠标 |
| 什么时候用 | 日常。没有特别理由就用这个 | 想要行为完全可预测，或智能模式表现异常时 |

智能模式有个自洽的地方：工具注入的事件同样会重置系统空闲计时器，所以你一旦
离开，就恰好每隔 `idle_threshold_sec` 注入一次；而你一碰鼠标，空闲计数就不断
归零，工具永远不会触发。

---

## 面板

右键点击托盘图标：

```
┌──────────────────────────────────────┐
│  ●  运行中                            │  ← 点一下开关
│     已运行 12 分 · 移动 8 次 · 空闲 23s │
├──────────────────────────────────────┤
│  模式               [智能]  始终      │
│  间隔 · 秒      30 45 [60] 90 120     │
│  自动停止 · 小时    关 2 4 [8] 12     │
│  ✓ 同时阻止息屏 / 睡眠                 │
├──────────────────────────────────────┤
│    开机自启                           │
│    记录日志                           │
│    语言 · 简体中文                     │
│    打开配置文件夹                      │
├──────────────────────────────────────┤
│    退出                               │
└──────────────────────────────────────┘
```

| 项 | 说明 |
|---|---|
| 状态卡 | 圆形徽标显示运行 / 暂停 / 锁屏，点一下开关；左键单击托盘图标同效 |
| 模式 | 智能 / 始终 |
| 间隔 | 30 / 45 / 60 / 90 / 120 / 180 秒 |
| 自动停止 | 关 / 2 / 4 / 8 / 12 小时，到点自动停并弹通知 |
| 同时阻止息屏 / 睡眠 | 对应 `SetThreadExecutionState` |
| 开机自启 | 写 `HKCU\...\Run`，不需要管理员权限 |
| 记录日志 | 写到 `%APPDATA%\MouseKeeper\mouse-keeper.log` |
| 语言 | 打开二级页面，列出全部 10 种语言 |
| 打开配置文件夹 | 打开 `%APPDATA%\MouseKeeper\` |
| 退出 | 保存配置并退出 |

改设置时**面板不会关闭**，方便连着调；只有开关和功能项才会收起面板。

托盘图标有三态：**绿色箭头**（运行中）、**灰色暂停**（已暂停）、**琥珀挂锁**（已锁屏）。

**全局热键 `Ctrl+Alt+F12`** 随时暂停 / 恢复 —— 要把屏幕交出去时很方便。
可以在配置文件里改，比如 `"ctrl+shift+f9"`。

---

## 语言

English、简体中文、繁體中文、日本語、한국어、Deutsch、Français、Español、
Português、Русский。

默认是 `auto`，通过 `GetUserDefaultLocaleName` 读取 Windows 显示语言，匹配不上
就回落到英语。中文的处理：`-TW` / `-HK` / `-MO` / `Hant` 标签解析为繁体，
其余为简体。

字体是跟着语言走的，而不是全局固定一个 —— YaHei 没有谚文，Segoe UI 没有汉字
假名，用同一个字体会在某些语种下出现豆腐块。

**日志文件始终是英文**，跟界面语言无关。日志是给排错用的，不该因为中途改了
设置就变成一半一种文字。

---

## 配置

`%APPDATA%\MouseKeeper\config.json`。手动改完需重启生效；面板里能点到的项都是
即时保存的。

| 键 | 默认值 | 说明 |
|---|---|---|
| `mode` | `"smart"` | `smart` / `force` |
| `idle_threshold_sec` | `60` | 智能模式：空闲多少秒后开始动（10–280） |
| `interval_sec` | `45` | 始终模式：固定间隔（5–280） |
| `move_pixels` | `1` | 每次移动几像素（之后原样移回） |
| `keep_display_on` | `true` | 是否同时阻止息屏 |
| `auto_stop_hours` | `8.0` | 运行这么多小时后自动停，`0` = 不限 |
| `language` | `"auto"` | `auto` 或语言代码，如 `ja`、`de`、`zh-Hans` |
| `hotkey` | `"ctrl+alt+f12"` | 全局暂停 / 恢复热键 |
| `start_active` | `true` | 启动后立即开始保活 |
| `log_enabled` | `false` | 是否写日志文件 |

280 秒这个上限是因为 Teams 大约 5 分钟（300 秒）无输入就判定离开，节奏必须
明显低于这个值才有意义。

---

## 原理

```
每 1 秒（独立线程，不用消息定时器）
  ├─ SetThreadExecutionState(ES_CONTINUOUS|ES_SYSTEM_REQUIRED[|ES_DISPLAY_REQUIRED])
  │     → 阻止息屏 / 睡眠
  ├─ OpenInputDesktop() 探测是否锁屏 → 锁屏就跳过本轮
  ├─ 智能模式：GetLastInputInfo() 判断空闲是否达到阈值
  │   始终模式：距上次注入是否够久
  └─ 满足条件 → SendInput(MOUSEEVENTF_MOVE, +1px) → 停 50ms → SendInput(-1px)
        → 系统"最后输入时间"被刷新，光标精确回到原位

每轮结束比对两个时钟（monotonic 与墙钟）。
若发现这一轮实际过去了 ≥10 秒，说明机器刚被冻过或睡过：
立刻重申电源请求并补一次注入。
```

三个关键点：

1. **必须用 `SendInput`，不能用 `SetCursorPos`。** 后者只挪光标，不产生输入
   事件，`GetLastInputInfo` 背后的时间戳根本不会更新，Teams 该变黄还是变黄。
   这是最常见的踩坑方式。
2. **PowerToys Awake 之类的工具解决不了这个问题。** 它们调用
   `SetThreadExecutionState`，能阻止睡眠但**不产生任何输入事件**，对"离开状态"
   完全无效。防睡眠和防离开是两件事，本工具两件都做。
3. **移动用相对坐标并成对抵消**，注入前后光标位置完全一致，不会干扰你正在做的事。

### 为什么托盘菜单是自己画的

Windows 的托盘菜单通常是原生 HMENU（`CreatePopupMenu` + `TrackPopupMenuEx`），
由系统绘制。系统只接受"选中 / 禁用 / 单选 / 分隔符"这类语义标志，
**没有任何自绘钩子** —— 圆角、留白、悬停高亮一个都做不了。`pystray` 走的正是
这条路，所以这个项目把托盘那一层整个自己实现了：

- `trayicon.py`：`Shell_NotifyIcon` + 一个隐藏消息窗口，自己接管左右键
- `menu.py`：一个 `overrideredirect` 的 tkinter 窗口，整个面板画在一张 Canvas 上，
  窗口圆角和投影交给 DWM（`DWMWA_WINDOW_CORNER_PREFERENCE`）

**面板里没有级联子菜单。** 模式 / 间隔 / 自动停止都用同一行内的分段控件。
级联菜单要求鼠标斜着穿过其他行才能进子菜单，路径长又容易滑出去，是
Fitts / Steering Law 的经典痛点；分段控件把三次点击压成一次。

**也没有任何进度动画。** 状态卡左侧就是一个纯色圆形徽标加白色字形，和托盘图标
同一套语言。会动的进度环每秒都要重画，是最容易出显示问题的东西，而它提供的
信息（还差几秒注入）并不值得这个代价。

面板刷新也走同样的思路：`Panel.refresh()` 先比对一份"当前该画成什么样"的签名，
内容没变就直接跳过。真正会变的只有明细那一行文字，一秒一次足够。

线程模型：**界面全在主线程。** tkinter 的 mainloop 跑在主线程，托盘消息由
`after` 循环里的 `pump()` 抽取；保活引擎在后台线程里只改数据、不碰界面，
需要刷新时置一个标志位，由主线程的定时器读走。

三个踩过的坑，都写在代码注释里了：

1. `SetProcessDpiAwarenessContext` 的参数是**指针宽度**的句柄。直接传 Python 的
   `-4` 会被 ctypes 当成 32 位 int，64 位下调用**静默失败** —— 不报错、返回值也
   正常，但进程实际是 DPI 不感知的，整个界面会被系统拉伸，在高 DPI 屏上糊成一片。
2. `pump()` 里的 `PeekMessage` **必须按自己的 hwnd 过滤**。传 `None` 会把整个
   线程队列（含所有 tkinter 窗口的消息）一并取走，而在 Tk 的 notifier 之外
   `DispatchMessage` 并不会让 Tk 生成对应的 Tk 事件，结果是鼠标事件被静默吞掉。
3. 光标从外面跨进窗口时，Tk 只发 `<Enter>` 不发 `<Motion>`。只绑 `<Motion>`
   的话，鼠标停在某一行上却不高亮，非得抖一下才亮。

Win10 上没有 `DWMWA_WINDOW_CORNER_PREFERENCE`，窗口会退化成直角，功能不受影响。

### 两套图标，各配一种任务栏主题

托盘图标以两套完整素材的形式存放在 `assets/tray/light/` 和 `assets/tray/dark/`
下（各含 `running` / `paused` / `locked` 三张）。这**不是**"浅色版是默认、深色版
是兜底"的关系——每一套都是专门为**某一种**任务栏底色设计的对比度，用错了套图
标会直接看不清，而不只是"看起来差点意思"：`light` 套的鼠标指针是接近黑色的，
给浅色任务栏用；`dark` 套的指针是接近白色的，给深色任务栏用。

Windows 把任务栏的主题和面板所跟随的应用主题分开暴露：`SystemUsesLightTheme`
和 `AppsUseLightTheme`，都在
`HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize` 下。设置里
"个性化 > 颜色 > 自定义"可以让"默认 Windows 模式"（任务栏）和"默认应用模式"
（窗口）各自独立设置，所以 `winui.py` 里把这两个值分开读取，托盘图标只看自己
那个信号，不搭面板的车。

### 为什么主循环不用消息定时器

`arkane-systems/mousejiggler#130` 是一个至今没关的报告：在 Modern Standby
（S0 低功耗空闲）的笔记本上，屏幕一关，`System.Windows.Forms.Timer` 依赖的
`WM_TIMER` 消息就不再投递，jiggler 会**永久停摆** —— 进程还在，但再也不动了。

本项目的主循环是独立线程 + `Event.wait()`，不吃这一套。同一份报告还提到
`SetThreadExecutionState()` 在这类机器上可能压根没注册进系统电源请求，所以
额外加了停顿看门狗：一旦发现某一轮实际耗时远超预期，就重新拉起电源请求并
立刻补一次注入。

用 `powercfg /a` 可以看自己的机器是不是 Modern Standby。

---

## 已知限制

- **锁屏时保活必然失效。** `Win+L` 锁屏或安全桌面出现后，输入桌面切给了
  Winlogon，`SendInput` 不可能生效。程序会探测到并自动停手、托盘如实显示
  "已锁屏"，解锁后自动继续 —— 但**锁屏期间在线状态一定会掉**，这是绕不过去的。
- **提权窗口挡路。** 前台是以管理员权限运行的程序时，低权限进程的 `SendInput`
  会被 UIPI 拦截（开了日志能看到）。这是 Windows 的设计，不是 bug。
- **远程桌面断开后**会话会被挂起，同样会被识别为"锁屏"状态而暂停。
- **杀软误报。** PyInstaller 打出来的东西被误判成木马是常见现象，跟本项目的行为
  无关。默认的 onedir 打包已经把概率降到最低，但公司电脑上的 EDR 判定逻辑跟家用
  杀软是两回事。真被拦了就直接跑源码（`pythonw main.py`）。
- 只支持 Windows，通篇是 Win32 API。

---

## 用之前请想清楚

Teams 的在线状态本意是反映真实可用性。在部分公司，用工具维持绿色属于违反
IT / HR 政策的行为；装了 Intune 或 EDR 的机器上，输入注入行为通常是可被审计的。
本工具没有任何规避公司监控的功能，以后也不会加。是否合适，你自己判断。

---

## 项目结构

```
mouse-keeper/
├── main.py                  入口 + --check 自检
├── mouse_keeper/
│   ├── winapi.py            SendInput / GetLastInputInfo / 电源状态 / 锁屏探测 / 热键
│   ├── winui.py             DPI 感知 / DWM 圆角 / 系统深浅色 / HICON
│   ├── trayicon.py          Shell_NotifyIcon 托盘图标 + 隐藏消息窗口
│   ├── menu.py              自绘 Fluent 风格面板
│   ├── i18n.py              10 种语言的界面文案 + 语言检测
│   ├── config.py            配置读写与校验
│   ├── engine.py            保活主循环（后台线程 + 停顿看门狗）
│   ├── autostart.py         开机自启（HKCU Run 项）
│   ├── icon.py              从 assets/tray 加载托盘图标素材并导出为 .ico
│   └── tray.py              把上面这些粘起来的 App
├── assets/tray/             托盘图标源图（light/ 与 dark/ 两套任务栏主题素材）
├── build.ps1                PyInstaller 打包脚本（-OneFile 可切单文件）
└── requirements.txt         只有 Pillow（加载/缩放图标用），界面是 tkinter，标准库
```

> `build.ps1` 存成 **UTF-8 带 BOM**。Windows PowerShell 5.1 在读取不带 BOM 的
> `.ps1` 时会按系统 ANSI 代码页解码，非 ASCII 文本会乱码，严重时会破坏引号配对
> 导致脚本直接语法错误。
>
> 代码注释与文档均为英文。

---

## 许可证

[MIT](LICENSE)。

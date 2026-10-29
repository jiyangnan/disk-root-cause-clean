---
name: disk-root-cause-clean
description: Use when disk almost full, 磁盘将满, System Data / 系统数据暴涨, cleanup 磁盘清理 requested and simple cache sweeps failed — root-cause hunting (runaway logs, sparse files/vhdx, dead-tool leftovers, on-device AI models, artifact forests, unbounded session history) via reconciliation method. Cross-platform macOS + Windows.
---

# Disk Root-Cause Clean（磁盘根因式深挖清理）

## Overview

核心原则：**对账式挖掘**——每个 GB 都要能解释出处。普通做法是定性清几类目录（缓存/下载/废纸篓），本方法通过"父目录大小必须等于子项之和"强制暴露隐藏根因。实战验证：460GB 盘 93%→72%，累计回收 91GB。

**平台无关**。方法论（对账/模式库/纪律）通用，命令与路径见平台参考：

- macOS → 读 `references/macos.md`
- Windows → 读 `references/windows.md`
- 平台检测：`uname` 返回 Darwin 用前者；`$env:OS -eq "Windows_NT"` 或 PowerShell 环境用后者

## 通用方法（7 步）

1. **基线与排除**：记录磁盘基线；排除快照/还原点（macOS TM 快照 / Windows 卷影副本）；检查回收站/废纸篓——glob 扫描会漏
2. **盲区扫描矩阵**：隐藏目录、系统保护区（需提权）、设备备份、VM/模拟器镜像、散落大文件（>800MB）
3. **对账（本方法核心）**：下钻任何目录，父目录 du 值 vs 子项之和，差值大 = 隐藏内容。`dir/*` 通配不含隐藏项，必须补扫点开头项（macOS `.[!.]*` / PowerShell `-Force`）
4. **森林扫描**：node_modules / .git / worktrees / *-artifacts 全盘统计（结构性浪费：模板复制的依赖、用完不删的工作区）
5. **根因模式库匹配**（见下表）
6. **分层执行**（见执行纪律）
7. **验证**：每层结束对比基线，报告"回收 N GB + 剩余可清清单"

## 根因模式库（平台无关）

| 模式 | 识别特征 | 处置原则 |
|---|---|---|
| 稀疏/虚拟磁盘文件 | 表观大小 >> 实际占用（Docker.raw、vhdx、qcow2） | 在宿主工具内部 prune，文件自动收缩；绝不动文件本身 |
| 失控日志 | 单文件异常大 + 进程持有句柄 | 截断清空（truncate/Clear-Content）而非删除；删除不释放被持有文件 |
| 工具尸体 | 已卸载应用的残留数据目录 | 确认卸载史后整删 |
| 端侧 AI 模型 | 浏览器 profile 内模型目录（可达 4GB） | 删，按需自动重下 |
| 更新器堆积 | 更新框架的安装包缓存（Sparkle/各 updater） | 删，纯下载残留 |
| vendored SDK | 项目内嵌完整 SDK（.flutter_sdk/.gradle 等） | 项目休眠即可删，用时重装 |
| 工作区森林 | worktrees / 执行产物按日期无限堆积 | **逐个验证后**按日期清旧 |
| Chromium 套壳二分 | Cache/Service Worker/GPUCache=可再生；IndexedDB/Local Storage=数据 | 按子目录类型清，绝不按整个 profile 清 |
| 会话史无界 | agent 会话目录（sessions/sqlite）无限增长 | 按存储粒度删旧，保最近周期 |
| 模板复制依赖 | N 个项目各复制同款依赖目录 | 完结项目删依赖，长期改共享存储 |

## 执行纪律（安全门，任何平台不豁免）

1. **分层**：零损失项（缓存/日志/更新器/未用工具链）先执行；涉个人数据（会话史/登录态/项目工件）列编号清单让用户逐项勾选
2. **删除前验证（最重要）**：worktree/检出/草稿类目录，删前逐个确认零未提交更改；有未提交的跳过并单报。未提交的工作被删 = 用户工作白做，是最严重事故
3. **时间边界保新**：会话/历史类按存储粒度（年/月）删旧，**最近一个完整周期无条件保留**；宁少勿多
4. **单目的命令**：一次只删一个目标；组合删除易被权限系统拦截且难审查
5. **权限拦截 → 拆分而非绕过**：组合命令被拦时拆成单一目的命令重试；仍被拦交用户
6. **应用必须关闭**再清其缓存；**用户明示排除项**的相关物（如"不动 SDK"→ 模拟器快照）也须单列请示
7. **提权最小化**：系统保护区扫描需提权时，只读扫描可提权，删除动作逐条列出交用户确认

## 两段式报告（360 式交互协议）

只在**两个时机**出报告，用户自己前后对照——不出更多中间报告：

1. **体检报告**：扫描+分层完成、尚未删除任何东西时。`python3 scripts/make_report.py scan findings.json > 体检报告.html`
   当前磁盘状态 KPI + 三层预计回收（安全/待确认/排除）+ 按层着色的发现 treemap + 大户排行 + 剩余潜力；末尾横幅引导用户下清理指令
2. **清理战报**：清理执行完毕并 df 验证后。`python3 scripts/make_report.py cleaned result.json > 清理战报.html`
   释放总量 KPI + 可用空间时间线 + 清理构成 treemap + 前后 dumbbell 对比 + 剩余潜力

- JSON 字段以 `examples/scan.json` 与 `examples/cleaned.json` 为准（真实数据样例，直接照抄结构）
- 报告写到用户可打开的目录（如 `~/disk-cleanup-report/`），并在 Browser 面板展示或告知路径
- 两份报告之间的执行过程只做简短文字汇报，不生成报告

## Common Mistakes

| 错误 | 后果 |
|---|---|
| 删被进程持有的大日志 | 空间不释放，要截断 |
| 运行中应用清缓存 | 行为异常/缓存立即重建 |
| 通配符扫描不补隐藏项 | 对不上账，漏掉真正大户 |
| 信文件表观大小（稀疏/vhdx） | 高估占用 10 倍级 |
| 无脑批量删工作区 | 未提交工作白做；先逐个验证 |
| 会话历史一刀切 | 丢最近工作上下文 |
| 包管理器卸载大包失败即放弃 | 手动删包目录+bin 链接/可执行链接 |
| 挂死进程硬等（0% CPU + 睡眠态） | 先杀进程再直接删目标目录 |

# Windows 平台参考（知识构建版，未经本机实测）

> ⚠️ 本文件基于 Windows 10/11 通用知识编写，命令在 PowerShell 7 中应可用；个别命令因系统版本/权限策略可能需微调。执行前先小范围验证。

配合 SKILL.md 通用方法使用。

## 基线与排除

```powershell
Get-PSDrive -PSProvider FileSystem | Format-Table Name,Used,Free    # 基线
vssadmin list shadows /for=C:    # 卷影副本/还原点（需管理员；系统还原可占数十 GB）
Clear-RecycleBin -DriveLetter C -WhatIf    # 回收站（确认后去 -WhatIf）
```

## 盲区扫描矩阵

| 区域 | 命令/路径 | 说明 |
|---|---|---|
| 隐藏系统文件 | `Get-ChildItem C:\ -Force -File \| Sort Length -Desc \| Select -First 20` | hiberfil.sys/pagefile/swapfile 在此暴露 |
| 系统组件 | `Dism /Online /Cleanup-Image /AnalyzeComponentStore` | WinSxS 可回收量评估 |
| 更新残留 | `C:\Windows\SoftwareDistribution\Download` | 更新包缓存 |
| 旧系统 | `C:\Windows.old` | 升级残留可达数十 GB |
| WSL/Docker 虚拟盘 | `Get-ChildItem -Path $env:LOCALAPPDATA -Recurse -Filter *.vhdx -ErrorAction SilentlyContinue` | ext4.vhdx/DockerDesktopWSL 只涨不缩 |
| 设备备份 | `%LOCALAPPDATA%\Apple\MobileSync`（iTunes 备份）、`%APPDATA%\Apple Computer` | iOS 备份 |
| 崩溃转储 | `C:\Windows\Minidump`、`%LOCALAPPDATA%\CrashDumps`、`C:\Windows\MEMORY.DMP` | 可达数 GB |
| 用户缓存 | `$env:LOCALAPPDATA\Temp`、`$env:LOCALAPPDATA\npm-cache`、`$env:LOCALAPPDATA\pip\cache`、`$env:USERPROFILE\.cache` | 工具缓存同 macOS 结构 |
| 散落大文件 | `Get-ChildItem -Path ~ -Recurse -File -ErrorAction SilentlyContinue \| Where Length -gt 800MB` | 失控日志/数据库 |

## 对账与森林

```powershell
# 目录对账（含隐藏项，-Force 关键）
Get-ChildItem -Path <dir> -Force -ErrorAction SilentlyContinue |
  ForEach-Object { [PSCustomObject]@{ Name=$_.Name; GB=[math]::Round((Get-ChildItem $_.FullName -Recurse -Force -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB,2) } } |
  Sort-Object GB -Descending | Select-Object -First 20

# node_modules 森林
Get-ChildItem -Path ~ -Recurse -Directory -Filter node_modules -Depth 6 -ErrorAction SilentlyContinue |
  ForEach-Object { [PSCustomObject]@{ GB=[math]::Round((Get-ChildItem $_.FullName -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum).Sum/1GB,2); Path=$_.FullName } } |
  Sort-Object GB -Descending | Select-Object -First 20
```

提示：NTFS 上 WizTree（读 MFT，秒级全盘）远快于递归 PowerShell，可用其 CLI 导出 CSV 再对账。

## Windows 特有根因

| 模式 | 位置 | 处置 |
|---|---|---|
| 休眠文件 | `C:\hiberfil.sys`（≈物理内存大） | `powercfg /h off`（弃用休眠）或 `powercfg /h /type reduced` |
| 页面文件 | `pagefile.sys`/`swapfile.sys` | 通常不动；确需缩：系统属性→高级→虚拟内存 |
| WinSxS 组件库 | `C:\Windows\WinSxS` | `Dism /Online /Cleanup-Image /StartComponentCleanup [/ResetBase]`（ResetBase 后无法卸载已装更新） |
| WSL2/Docker vhdx 膨胀 | `%LOCALAPPDATA%\Packages\*\LocalState\ext4.vhdx`、`%LOCALAPPDATA%\Docker\wsl\*\*.vhdx` | 容器内清理 → `wsl --shutdown` → `Optimize-VHD -Path <> -Mode Full`（Hyper-V）或 diskpart `compact vdisk`；这是 Windows 版 "Docker.raw" 问题 |
| Installer 缓存 | `C:\Windows\Installer` | **勿手动删**（毁卸载/修复）；用 PatchCleaner 只清 orphaned |
| 还原点/卷影 | vssadmin | `vssadmin delete shadows /for=C: /all /quiet`（删全部还原点，须用户确认） |
| Delivery Optimization | 设置→系统→存储 | 内建清理或 `Delete-DeliveryOptimizationCache` |
| OneDrive 本地副本 | `%USERPROFILE%\OneDrive` | 设置"按需文件"（Files On-Demand），等价 macOS iCloud 优化 |
| Storage Sense | 设置→系统→存储 | 开启自动清理临时文件（防复发） |

## 失控日志（与 macOS 差异）

Windows 被进程独占的文件通常**无法截断**（与 macOS truncate 不同）：
1. `handle.exe <file>`（Sysinternals）或资源监视器 CPU/磁盘关联找到持有进程
2. 能停服务则停（`Stop-Service`），截断/删除后重启服务
3. 循环增长的 IIS/应用日志：配置滚动上限治本

## 执行注意

- 删除系统区需管理员 PowerShell；**TrustedInstaller 拥有的目录勿动**
- `Remove-Item -Recurse -Force` 逐目标执行，长路径 (>260) 失败时用 `\\?\` 前缀
- 用户排除项同样适用（如"不动 WSL 发行版"→ 其 vhdx 快照单列请示）

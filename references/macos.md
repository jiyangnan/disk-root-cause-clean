# macOS 平台参考（实战验证版）

配合 SKILL.md 通用方法使用。以下路径与命令均在 macOS 14+ 实测（2026-10 两轮清理，回收 91GB）。

## 基线与排除

```bash
df -k /System/Volumes/Data                       # 数据卷基线（APFS）
tmutil listlocalsnapshots /                      # TM 本地快照（常为系统数据暴涨元凶）
du -sh ~/.Trash                                  # 废纸篓（通配扫描会漏）
```

## 盲区扫描矩阵

| 区域 | 命令 | 实战命中 |
|---|---|---|
| 隐藏目录 | `du -xsh ~/.[!.]* \| sort -rh` | 工具尸体 1.2G、会话史 10G、端侧模型 4G |
| sudo 系统区 | `sudo du -xsh /private/var/db/powerlog /private/var/log /Library/Caches /private/var/folders` | powerlog 遥测 DB 可达 ~10G（macOS 27 实测） |
| iOS 设备备份 | `du -sh ~/Library/"Application Support"/MobileSync` | 整机备份数 GB |
| VM/模拟器 | `find ~ -name "*.pvm" -o -name "*.qcow2" -o -name "*.utmvm"` | AVD 快照、UTM |
| 散落大文件 | `find ~ -type f -size +800M -not -path "*/Library/*"` | 失控日志/数据库 |
| ~/Library 顶层 | `du -xsh ~/Library/* \| sort -rh` | Finder 把它几乎全计入"系统数据" |

## 对账与森林

```bash
du -xsh <dir>/* <dir>/.[!.]* | sort -rh          # 含隐藏项对账
find ~ -maxdepth 6 -name node_modules -type d -prune -print0 | xargs -0 du -xsk | sort -rn   # 实测 120 个共 18.7G
find ~ -maxdepth 4 -name .git -type d -prune -print0 | xargs -0 du -xsk | sort -rn
du -sh <项目>/.worktrees                          # worktree 森林（实测 26 个 8.4G）
```

## macOS 根因路径速查

- Docker：`~/Library/Containers/com.docker.docker`（Docker.raw 稀疏，ls 表观 460G / du 实际 35G）
- Xcode：`~/Library/Developer/Xcode/iOS DeviceSupport`（每 iOS 版本×机型 ~6G，旧版可删插机重建）
- Chromium 套壳：Service Worker 是大户（飞书 7G→1.2G、各 Electron app）
- 微信：`~/Library/Caches/com.tencent.xinWeChat/.../org.sparkle-project.Sparkle`（更新安装包堆积）
- Chrome 端侧模型：`chrome-profile/OptGuideOnDeviceModel`（4G）
- uv/pnpm/npm/brew/rustup：`~/.cache/uv`、`~/Library/pnpm/store`、`~/.npm`、`brew cleanup`、`rustup toolchain uninstall <旧>`
- 失控日志：`lsof <file>` 找持有者 → `: > file` 截断（进程持 stdout 重定向实测）
- ⚠️ `~/Library/Caches/ms-playwright` 是 Agent 自身浏览/自动化工具（如 gstack browse、webapp-testing）的无头浏览器二进制，删掉会弄坏自己的工具——要清也只 `playwright install` 换版本，别当普通缓存删

## 执行注意

- 删 Electron 应用缓存前 `pgrep -x "<AppName>"` 确认未运行
- uv 类 CLI 挂死（0% CPU + STAT=S）= 持锁睡眠：pkill 后 rm 直删
- macOS 无 root 密码时系统区留给用户自查（给三条命令）

# 公开版与本地生成版

仓库地址：https://github.com/kometwei/Stellaris-Governance-Hub

## 创意工坊公开核心版

公开核心版只索引《群星》游戏本体与官方 DLC 中已经安装的内阁席位，不扫描当前玩家的第三方 Mod，也不覆盖 `council_view.gui`。事件式内阁指派界面仍然完整可用。

构建命令：

```powershell
py -3 tools/build_release_profiles.py public
```

默认输出：

```text
dist/stellaris_mod_enhancer_core/
```

公开核心版没有第三方硬依赖。发布到 Steam Workshop 时，不要把仓库的 `tools/`、测试脚本或个人播放集生成结果一起上传。

需要让 Paradox Launcher 识别这份公开构建时，使用：

```powershell
py -3 tools/build_release_profiles.py public --install
```

如果确认要更新自己已经拥有的 Workshop 项目，可显式传入其 ID，例如：

```powershell
py -3 tools/build_release_profiles.py public --install --workshop-id 3810245754
```

只有确认该项目属于当前 Steam 账号时才应使用 `--workshop-id`；省略该参数时，启动器会把它视为尚未绑定 Workshop 项目的本地构建。

公开构建会注册为 `星政中枢｜内阁·舰队·领袖·灵能`。上传前可把 [`WORKSHOP_DESCRIPTION.md`](./WORKSHOP_DESCRIPTION.md) 的内容复制到启动器描述框；启动器上传描述时可能覆盖工坊页面已有说明。

首版公开/生成构建不包含旧的个人化传统解锁目录；该模块需要单独改造成按播放集生成后再加入。现有开发版内容不会因此被删除。

## 播放集本地生成版

高级用户应先在 Paradox Launcher 中启用自己的完整播放集，然后关闭启动器并双击：

```text
build_local_mod.bat
```

生成器将读取 `dlc_load.json`，扫描当前实际启用的 Mod，并安装一个独立本地 Mod：

```text
[本地生成] 星政中枢
```

生成目录：

```text
Documents/Paradox Interactive/Stellaris/mod/stellaris_mod_enhancer_generated/
```

启动器描述文件：

```text
Documents/Paradox Interactive/Stellaris/mod/stellaris_mod_enhancer_generated.mod
```

生成版会写出 `DEPENDENCIES.md` 和 `generated_manifest.json`，仅记录实际贡献了内阁席位、触发条件或 UI 兼容文件的依赖名称与 Workshop ID。播放集、游戏版本或 UIOD 版本变化后，应重新运行生成器。

本地生成版是完整的独立版本，不能与创意工坊核心版同时启用。建议加载在所有内容 Mod 和 UI Mod 之后。

## 安全边界

- 生成器不会修改 Steam Workshop 下载目录。
- 只会重建带有 `.auto_qol_generated_output` 标记的专用输出目录。
- 没有启用 `MORE COUNCIL POSITION` 时，不会借用其触发条件。
- 只有当前播放集启用了 UI Overhaul Dynamic 时，才生成对应的 `council_view.gui` 兼容文件。

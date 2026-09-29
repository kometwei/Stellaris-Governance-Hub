# -*- coding: utf-8 -*-
"""
Central path configuration for Stellaris Mod Enhancer tools.
Automatically resolves project, game, workshop, and documents directories
without hardcoding user-specific paths or exposing privacy.
"""
import os
import sys
from pathlib import Path

# 1. Mod 根目录与子目录（动态自适应定位，无论克隆到何处）
TOOLS_DIR = Path(__file__).resolve().parent
MOD_ROOT = TOOLS_DIR.parent
EVENTS_DIR = MOD_ROOT / "events"
COMMON_DIR = MOD_ROOT / "common"
LOCALISATION_DIR = MOD_ROOT / "localisation" / "simp_chinese"
INTERFACE_DIR = MOD_ROOT / "interface"

# 2. 用户文档目录（自动使用当前系统用户，杜绝写死 Admin）
DOCS_DIR = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"

# 3. 动态寻找 Steam 根目录
def find_steam_dir() -> Path:
    # 环境变量优先
    env_steam = os.environ.get("STELLARIS_STEAM_DIR")
    if env_steam and Path(env_steam).exists():
        return Path(env_steam)
    
    # Windows 注册表自动读取
    if sys.platform == "win32":
        try:
            import winreg
            for root_key in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for subkey in (r"Software\Valve\Steam", r"Software\Wow6432Node\Valve\Steam"):
                    try:
                        with winreg.OpenKey(root_key, subkey) as k:
                            val, _ = winreg.QueryValueEx(k, "SteamPath")
                            if val and Path(val).exists():
                                return Path(val)
                    except OSError:
                        pass
        except Exception:
            pass

    # 常见盘符探测回退
    common_steam_locations = [
        Path(r"D:\Steam"),
        Path(r"C:\Program Files (x86)\Steam"),
        Path(r"C:\Steam"),
        Path(r"E:\Steam"),
    ]
    for loc in common_steam_locations:
        if loc.exists():
            return loc
    return Path(r"D:\Steam")

STEAM_DIR = find_steam_dir()

# 4. 动态寻找群星本体游戏根目录
def find_game_install_dir() -> Path:
    env_game = os.environ.get("STELLARIS_GAME_DIR")
    if env_game and Path(env_game).exists():
        return Path(env_game)
    
    candidates = [
        STEAM_DIR / "steamapps" / "common" / "Stellaris",
        Path(r"D:\Steam\steamapps\common\Stellaris"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\common\Stellaris"),
        Path(r"E:\Steam\steamapps\common\Stellaris"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

GAME_INSTALL_DIR = find_game_install_dir()

# 5. 动态寻找 Steam 创意工坊群星 Mod 目录 (AppID: 281990)
def find_workshop_dir() -> Path:
    env_ws = os.environ.get("STELLARIS_WORKSHOP_DIR")
    if env_ws and Path(env_ws).exists():
        return Path(env_ws)
    
    candidates = [
        STEAM_DIR / "steamapps" / "workshop" / "content" / "281990",
        Path(r"D:\Steam\steamapps\workshop\content\281990"),
        Path(r"C:\Program Files (x86)\Steam\steamapps\workshop\content\281990"),
        Path(r"E:\Steam\steamapps\workshop\content\281990"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return candidates[0]

WORKSHOP_MOD_DIR = find_workshop_dir()

#!/usr/bin/env python3
"""Build clean public and playset-specific Stellaris Mod Enhancer releases.

Profiles:
  public  - vanilla/official content only, no third-party GUI override.
  local   - a standalone local mod generated from the currently enabled playset.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import build_smart_council_system as council
from paths import MOD_ROOT


DOCS_DIR = Path.home() / "Documents" / "Paradox Interactive" / "Stellaris"
REPO_URL = "https://github.com/kometwei/Stellaris-Governance-Hub"
SUPPORTED_VERSION = "v4.5.*"
RELEASE_VERSION = "1.2.0"
PUBLIC_NAME = "星政中枢｜内阁·舰队·领袖·灵能"
LOCAL_NAME = "[本地生成] 星政中枢"
THUMBNAIL_NAME = "thumbnail.png"
OUTPUT_MARKER = ".auto_qol_generated_output"

CORE_FILES = (
    "common/defines/zzz_auto_qol_fleet_defines.txt",
    "common/edicts/auto_qol_edicts.txt",
    "common/on_actions/auto_qol_on_actions.txt",
    "common/scripted_effects/auto_qol_council_scripted_effects.txt",
    "common/scripted_effects/auto_qol_fleet_scripted_effects.txt",
    "common/scripted_effects/auto_qol_leader_pool_scripted_effects.txt",
    "common/static_modifiers/auto_qol_static_modifiers.txt",
    "events/auto_envoy_events.txt",
    "events/auto_qol_council_events.txt",
    "events/auto_qol_delay_events.txt",
    "events/auto_qol_fleet_events.txt",
    "events/auto_qol_menu_events.txt",
    "unchecked_defines/zzz_auto_qol_council_interface_defines.txt",
    "LICENSE",
    THUMBNAIL_NAME,
)

IMPLICIT_LOCALISATION_KEYS = {
    "auto_qol_menu",
    "auto_qol_menu_desc",
    "edict_auto_qol_menu",
    "edict_auto_qol_menu_desc",
    "edict_auto_qol_menu_effect_desc",
    "qol_custom_navy_cap_modifier",
    "qol_custom_navy_cap_modifier_desc",
    "qol_custom_cmd_limit_modifier",
    "qol_custom_cmd_limit_modifier_desc",
    "auto_qol_council_buff",
    "auto_qol_council_buff_desc",
    "auto_qol_pool_clamp_5",
    "auto_qol_pool_clamp_5_desc",
    "auto_qol_pool_clamp_10",
    "auto_qol_pool_clamp_10_desc",
    "auto_qol_pool_clamp_20",
    "auto_qol_pool_clamp_20_desc",
}

PUBLIC_LOC_OVERRIDES = {
    "auto_qol_menu_desc": (
        "打开星政中枢，管理内阁席位、舰队容量、领袖池、灵能科技与智能建交。"
    ),
    "edict_auto_qol_menu_desc": (
        "打开星政中枢，管理内阁席位、舰队容量、领袖池、灵能科技与智能建交。"
    ),
    "auto_qol_menu.1.desc": (
        "欢迎使用 §H星政中枢§!。\\n\\n"
        "§E【核心功能模块】§!\\n"
        "· §H特使智能建交§!：按需与常规 AI 建立通讯\\n"
        "· §H舰队容量计算器§!：调整指挥上限与海军容量\\n"
        "· §H政务内阁指派§!：通过独立界面管理额外席位\\n"
        "· §H招募池智能治理§!：限制候选领袖总量\\n"
        "· §H灵能三件套§!：完成灵能传统后一键完成三项科技\\n\\n"
        "§L请选择需要操作的功能模块：§!"
    ),
    "auto_qol_council_menu.1.desc": (
        "本模块提供内阁席位点名指派、在任名册与候选池治理。\\n\\n"
        "公开核心版仅收录游戏本体及官方内容；第三方席位可使用仓库中的"
        "本地生成器创建专属版本。"
    ),
    "auto_qol_pool_clamp_5": "领袖池轻度精简",
    "auto_qol_pool_clamp_5_desc": "降低待招募领袖池的额外容量。",
    "auto_qol_pool_clamp_10": "领袖池中度精简",
    "auto_qol_pool_clamp_10_desc": "进一步降低待招募领袖池的额外容量。",
    "auto_qol_pool_clamp_20": "领袖池高度精简",
    "auto_qol_pool_clamp_20_desc": "大幅降低待招募领袖池的额外容量。",
}

LOCAL_LOC_OVERRIDES = {
    **PUBLIC_LOC_OVERRIDES,
    "auto_qol_council_menu.1.desc": (
        "本模块提供内阁席位点名指派、在任名册与候选池治理。\\n\\n"
        "当前版本由本地生成器根据 Paradox Launcher 中实际启用的播放集构建；"
        "播放集变化后请重新运行生成器。"
    ),
}


def parse_descriptor(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8-sig", errors="ignore")

    def value(key: str) -> str:
        match = re.search(rf'(?m)^\s*{re.escape(key)}\s*=\s*"([^"]*)"', text)
        return match.group(1) if match else ""

    return {
        "name": value("name"),
        "path": value("path"),
        "remote_file_id": value("remote_file_id"),
        "descriptor": str(path),
    }


def get_active_mod_records() -> list[dict[str, str | Path]]:
    load_file = DOCS_DIR / "dlc_load.json"
    if not load_file.exists():
        raise FileNotFoundError(f"Playset file not found: {load_file}")
    load_data = json.loads(load_file.read_text(encoding="utf-8-sig"))
    records: list[dict[str, str | Path]] = []
    for relative in load_data.get("enabled_mods", []):
        descriptor_path = DOCS_DIR / relative
        if not descriptor_path.exists():
            continue
        record = parse_descriptor(descriptor_path)
        raw_path = record.get("path", "")
        if not raw_path:
            continue
        mod_path = Path(str(raw_path).replace("/", "\\"))
        if not mod_path.exists():
            continue
        record["mod_path"] = mod_path
        records.append(record)
    return records


def is_enhancer_record(record: dict[str, str | Path]) -> bool:
    name = str(record.get("name", "")).lower()
    if "stellaris mod enhancer" in name or "群星体验增强" in name:
        return True
    mod_path = Path(record["mod_path"]).resolve()
    known_paths = {
        MOD_ROOT.resolve(),
        (MOD_ROOT.parent / "Stellaris Mod Enhancer").resolve(),
    }
    return mod_path in known_paths


def reset_generated_dir(target: Path) -> None:
    resolved = target.resolve()
    allowed_roots = [
        (MOD_ROOT / "dist").resolve(),
        (DOCS_DIR / "mod").resolve(),
    ]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise ValueError(f"Refusing to rebuild outside approved output roots: {resolved}")
    if resolved.exists():
        marker = resolved / OUTPUT_MARKER
        if not marker.exists():
            raise ValueError(
                f"Refusing to replace an unmarked directory: {resolved}. "
                "Choose an empty/new output path."
            )
        shutil.rmtree(resolved)
    resolved.mkdir(parents=True, exist_ok=True)
    (resolved / OUTPUT_MARKER).write_text(
        "Generated by tools/build_release_profiles.py\n", encoding="utf-8"
    )


def copy_relative(relative: str, output_root: Path) -> None:
    source = MOD_ROOT / relative
    if not source.exists():
        raise FileNotFoundError(f"Required source file is missing: {source}")
    destination = output_root / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def remove_named_option(text: str, localisation_key: str) -> str:
    marker = f'name = "{localisation_key}"'
    cursor = 0
    while True:
        option_start = text.find("option = {", cursor)
        if option_start < 0:
            return text
        open_index = text.find("{", option_start)
        close_index = council.find_matching_brace(text, open_index)
        if close_index < 0:
            raise ValueError(f"Unbalanced option while removing {localisation_key}")
        block = text[option_start : close_index + 1]
        if marker in block:
            start = option_start
            while start > 0 and text[start - 1] in " \t":
                start -= 1
            if start > 0 and text[start - 1] == "\n":
                start -= 1
            end = close_index + 1
            while end < len(text) and text[end] in " \t":
                end += 1
            if end < len(text) and text[end] == "\n":
                end += 1
            return text[:start] + text[end:]
        cursor = close_index + 1


def write_descriptor(
    output_root: Path,
    name: str,
    dependencies: list[str],
    external_path: Path | None = None,
    remote_file_id: str | None = None,
) -> str:
    lines = [
        f'version="{RELEASE_VERSION}"',
        "tags={",
        '\t"Fixes"',
        '\t"Utilities"',
        '\t"Leaders"',
        '\t"Diplomacy"',
        '\t"Gameplay"',
        "}",
        f'name="{name.replace(chr(34), chr(39))}"',
        f'picture="{THUMBNAIL_NAME}"',
        f'supported_version="{SUPPORTED_VERSION}"',
    ]
    if dependencies:
        lines.append("dependencies={")
        for dependency in dependencies:
            lines.append(f'\t"{dependency.replace(chr(34), chr(39))}"')
        lines.append("}")
    if external_path is not None:
        lines.append(f'path="{external_path.as_posix()}"')
    if remote_file_id:
        lines.append(f'remote_file_id="{remote_file_id}"')
    return "\n".join(lines) + "\n"


def write_council_catalog(
    output_root: Path,
    active_mod_dirs: list[Path],
    use_active_more_council: bool,
    include_ui_compat: bool,
) -> dict[str, object]:
    loc_dict = council.get_loc_dict(active_mod_dirs)
    positions = council.scan_all_positions(active_mod_dirs, loc_dict)
    imported_triggers = 0
    if use_active_more_council:
        more_triggers = council.collect_more_council_triggers(active_mod_dirs)
        imported_triggers = len(more_triggers)
        positions = council.apply_more_council_triggers(positions, more_triggers)
    categories = council.organize_categories(positions)
    defined_symbols = council.collect_defined_symbols(active_mod_dirs)
    event_files = council.split_event_content_by_category(
        council.generate_events(categories, defined_symbols), categories
    )
    events_dir = output_root / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in event_files.items():
        clean = "\n".join(line.rstrip() for line in content.splitlines()) + "\n"
        (events_dir / filename).write_text(clean, encoding="utf-8")

    loc_dir = output_root / "localisation" / "simp_chinese"
    loc_dir.mkdir(parents=True, exist_ok=True)
    council_loc = "l_simp_chinese:\n" + council.generate_loc(categories) + "\n"
    (loc_dir / "auto_qol_council_assign_l_simp_chinese.yml").write_text(
        council_loc, encoding="utf-8-sig"
    )

    ui_source = None
    if include_ui_compat:
        ui_source, _ = council.generate_council_ui_compat(
            active_mod_dirs, output_root=output_root
        )

    included_positions = [
        position for category in categories for position in category["positions"]
    ]
    return {
        "scanned_positions": len(positions),
        "generated_positions": len(included_positions),
        "categories": {
            category["cat_tag"]: len(category["positions"])
            for category in categories
        },
        "more_council_triggers": imported_triggers,
        "ui_compat": bool(ui_source),
        "_ui_source_dir": (
            str(Path(ui_source).resolve().parents[1]) if ui_source else None
        ),
        "source_dirs": sorted(
            {
                str(position["source_dir"])
                for position in included_positions
                if position.get("source_dir")
            }
        ),
    }


def validate_build(output_root: Path) -> None:
    descriptor = output_root / "descriptor.mod"
    if not descriptor.exists():
        raise ValueError(f"Build is missing descriptor.mod: {output_root}")

    event_ids: dict[str, Path] = {}
    duplicate_ids = []
    for path in output_root.rglob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        clean = council.strip_comments(text)
        if clean.count("{") != clean.count("}"):
            raise ValueError(f"Unbalanced braces in generated file: {path}")
        if path.parent.name != "events":
            continue
        for event_id in re.findall(
            r'(?m)^\s*id\s*=\s*([A-Za-z0-9_.-]+)\s*$', clean
        ):
            if event_id in event_ids:
                duplicate_ids.append(
                    f"{event_id} ({event_ids[event_id].name}, {path.name})"
                )
            event_ids[event_id] = path
    if duplicate_ids:
        raise ValueError("Duplicate generated event IDs: " + ", ".join(duplicate_ids))

    for path in (output_root / "common" / "edicts").glob("*.txt"):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        if re.search(r"(?m)^\s*length\s*=\s*0\s*(?:#.*)?$", text):
            raise ValueError(
                f"Unsafe zero-length edict in generated build: {path}. "
                "Stellaris 4.5 divides by the edict duration while updating its UI."
            )

    localisation_keys = set()
    for path in output_root.rglob("*.yml"):
        text = path.read_text(encoding="utf-8-sig", errors="strict")
        localisation_keys.update(
            re.findall(r'(?m)^\s*([^#\s][^:]*):\d+\s+"', text)
        )
    missing = sorted(
        key for key in collect_localisation_references(output_root)
        if key.startswith(("auto_qol", "edict_auto_qol", "qol_custom"))
        and key not in localisation_keys
    )
    if missing:
        raise ValueError("Missing generated localisation: " + ", ".join(missing))


def collect_localisation_references(output_root: Path) -> set[str]:
    references = set(IMPLICIT_LOCALISATION_KEYS)
    pattern = re.compile(
        r'\b(?:name|title|desc|custom_tooltip)\s*=\s*"([A-Za-z0-9_.-]+)"'
    )
    for folder in ("common", "events"):
        root = output_root / folder
        if not root.exists():
            continue
        for path in root.rglob("*.txt"):
            text = path.read_text(encoding="utf-8-sig", errors="ignore")
            references.update(pattern.findall(text))
    return references


def write_filtered_main_localisation(
    output_root: Path, overrides: dict[str, str]
) -> None:
    source = MOD_ROOT / "localisation" / "simp_chinese" / "auto_qol_l_simp_chinese.yml"
    lines = source.read_text(encoding="utf-8-sig").splitlines()
    by_key: dict[str, str] = {}
    order: list[str] = []
    for line in lines:
        match = re.match(r'^\s*([^#\s][^:]*):\d+\s+"', line)
        if not match:
            continue
        key = match.group(1).strip()
        by_key[key] = line
        order.append(key)

    references = collect_localisation_references(output_root)
    selected: list[str] = []
    for key in order:
        if key not in references:
            continue
        if key in overrides:
            value = overrides[key].replace('"', "'")
            selected.append(f' {key}:0 "{value}"')
        else:
            selected.append(by_key[key])

    for key, value in overrides.items():
        if key in references and key not in by_key:
            selected.append(f' {key}:0 "{value.replace(chr(34), chr(39))}"')

    missing = sorted(
        key for key in references
        if key not in by_key
        and key not in overrides
        and not key.startswith("auto_qol_council_assign.")
        and not key.startswith("auto_qol_assign.")
        and key not in {
            "auto_qol_council_menu.manual_assign",
            "auto_qol_council_menu.manual_assign_tt",
        }
    )
    if missing:
        raise ValueError("Missing public localisation keys: " + ", ".join(missing))

    destination = (
        output_root / "localisation" / "simp_chinese" /
        "auto_qol_l_simp_chinese.yml"
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        "l_simp_chinese:\n" + "\n".join(selected) + "\n",
        encoding="utf-8-sig",
    )


def has_ui_overhaul(active_records: list[dict[str, str | Path]]) -> bool:
    return any(
        str(record.get("remote_file_id", "")) == council.UI_OVERHAUL_DYNAMIC_WORKSHOP_ID
        or Path(record["mod_path"]).name == council.UI_OVERHAUL_DYNAMIC_WORKSHOP_ID
        for record in active_records
    )


def build_public(
    output_root: Path, install: bool, workshop_id: str | None
) -> dict[str, object]:
    reset_generated_dir(output_root)
    for relative in CORE_FILES:
        copy_relative(relative, output_root)

    menu_path = output_root / "events" / "auto_qol_menu_events.txt"
    menu_text = menu_path.read_text(encoding="utf-8-sig")
    menu_path.write_text(
        remove_named_option(menu_text, "auto_qol_menu.tradition_menu"),
        encoding="utf-8",
    )

    report = write_council_catalog(
        output_root,
        active_mod_dirs=[],
        use_active_more_council=False,
        include_ui_compat=False,
    )
    write_filtered_main_localisation(output_root, PUBLIC_LOC_OVERRIDES)
    public_name = PUBLIC_NAME
    descriptor = write_descriptor(
        output_root,
        public_name,
        dependencies=[],
        remote_file_id=workshop_id,
    )
    (output_root / "descriptor.mod").write_text(descriptor, encoding="utf-8")
    (output_root / "README.md").write_text(
        f"# {PUBLIC_NAME}\n\n"
        "适用于 Stellaris 4.5 的游戏内综合管理工具。公开版仅收录游戏本体与"
        "官方 DLC 内容，无第三方 Mod 硬依赖。\n\n"
        f"源代码与播放集本地生成器：{REPO_URL}\n",
        encoding="utf-8",
    )
    report.pop("source_dirs", None)
    report.pop("_ui_source_dir", None)
    validate_build(output_root)
    if install:
        launcher_descriptor = DOCS_DIR / "mod" / "stellaris_mod_enhancer_public.mod"
        launcher_descriptor.write_text(
            write_descriptor(
                output_root,
                public_name,
                dependencies=[],
                external_path=output_root.resolve(),
                remote_file_id=workshop_id,
            ),
            encoding="utf-8",
        )
    return report


def build_local(output_root: Path, install: bool) -> dict[str, object]:
    records = [record for record in get_active_mod_records() if not is_enhancer_record(record)]
    active_dirs = [Path(record["mod_path"]) for record in records]

    reset_generated_dir(output_root)
    for relative in CORE_FILES:
        copy_relative(relative, output_root)

    menu_path = output_root / "events" / "auto_qol_menu_events.txt"
    menu_text = menu_path.read_text(encoding="utf-8-sig")
    menu_path.write_text(
        remove_named_option(menu_text, "auto_qol_menu.tradition_menu"),
        encoding="utf-8",
    )

    report = write_council_catalog(
        output_root,
        active_mod_dirs=active_dirs,
        use_active_more_council=True,
        include_ui_compat=has_ui_overhaul(records),
    )
    write_filtered_main_localisation(output_root, LOCAL_LOC_OVERRIDES)

    used_paths = {Path(path).resolve() for path in report.pop("source_dirs")}
    ui_source_dir = report.pop("_ui_source_dir", None)
    if ui_source_dir:
        used_paths.add(Path(str(ui_source_dir)).resolve())
    if report.get("more_council_triggers"):
        more_dir = council.find_more_council_dir(active_dirs)
        if more_dir:
            used_paths.add(Path(more_dir).resolve())

    dependency_records = [
        record for record in records
        if Path(record["mod_path"]).resolve() in used_paths
    ]
    dependencies = []
    seen_dependency_names = set()
    for record in dependency_records:
        name = str(
            record.get("name")
            or f'Workshop {record.get("remote_file_id", "unknown")}'
        )
        if name not in seen_dependency_names:
            dependencies.append(name)
            seen_dependency_names.add(name)
    descriptor = write_descriptor(
        output_root,
        LOCAL_NAME,
        dependencies=dependencies,
    )
    (output_root / "descriptor.mod").write_text(descriptor, encoding="utf-8")

    dependency_rows = []
    manifest_records = []
    for index, record in enumerate(dependency_records, start=1):
        name = str(record.get("name", "Unknown Mod"))
        workshop_id = str(record.get("remote_file_id", "local")) or "local"
        dependency_rows.append(f"{index}. {name} ({workshop_id})")
        manifest_records.append({"name": name, "workshop_id": workshop_id})
    (output_root / "DEPENDENCIES.md").write_text(
        "# Generated playset dependencies\n\n"
        "Regenerate this local mod whenever the enabled playset changes.\n\n"
        + "\n".join(dependency_rows)
        + "\n",
        encoding="utf-8",
    )
    (output_root / "generated_manifest.json").write_text(
        json.dumps(
            {
                "generator": REPO_URL,
                "dependencies": manifest_records,
                "council": report,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    if install:
        launcher_descriptor = DOCS_DIR / "mod" / "stellaris_mod_enhancer_generated.mod"
        launcher_descriptor.write_text(
            write_descriptor(
                output_root,
                LOCAL_NAME,
                dependencies=dependencies,
                external_path=output_root.resolve(),
            ),
            encoding="utf-8",
        )
    validate_build(output_root)
    return {**report, "dependencies": len(dependencies)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("profile", choices=("public", "local"))
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--install",
        action="store_true",
        help="Register the build in the Stellaris Documents/mod folder.",
    )
    parser.add_argument(
        "--workshop-id",
        help="Existing owned Steam Workshop item ID for a public update.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.workshop_id and args.profile != "public":
        raise SystemExit("--workshop-id is only valid for the public profile")
    if args.workshop_id and not args.workshop_id.isdigit():
        raise SystemExit("--workshop-id must contain digits only")

    if args.output:
        output_root = args.output.resolve()
    elif args.profile == "public":
        output_root = (MOD_ROOT / "dist" / "stellaris_mod_enhancer_core").resolve()
    else:
        output_root = (
            DOCS_DIR / "mod" / "stellaris_mod_enhancer_generated"
        ).resolve()

    if args.profile == "public":
        report = build_public(output_root, args.install, args.workshop_id)
    else:
        report = build_local(output_root, install=args.install)

    print(f"Built {args.profile} profile: {output_root}")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.install:
        if args.profile == "local":
            print("Launcher descriptor installed. Enable only the generated local edition.")
        else:
            print("Public build registered in the launcher for Workshop upload.")


if __name__ == "__main__":
    main()

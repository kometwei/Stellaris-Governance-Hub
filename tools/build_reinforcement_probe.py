"""Build a standalone, opt-in reinforcement diagnostic addon.

Run alongside the existing hub. Does not include any reassembly commands.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/fleet_reinforcement_probe"
NS = "qol_reinforcement_probe"


def write(relative, text, *, bom=False):
    # Scripted effects are parsed by the macro preprocessor before localisation.
    # Native 00_scripted_effects.txt uses two literal backslashes before '['.
    # Without them, dynamic log strings consume following script as a macro.
    if relative.startswith("common/scripted_effects/"):
        text = text.replace("[", r"\\[")
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")


def validate():
    texts = [path.read_text(encoding="utf-8-sig") for path in OUT.rglob("*.txt")]
    text = "\n".join(texts)
    for path in (OUT / "common/scripted_effects").glob("*.txt"):
        content = path.read_text(encoding="utf-8")
        assert not re.search(r"(?<!\\)\[", content), "Unescaped macro bracket in scripted effect"
    for content in texts:
        clean = re.sub(r'"[^"\n]*"|#[^\n]*', "", content)
        depth = 0
        for token in re.findall(r"[{}]", clean):
            depth += 1 if token == "{" else -1
            assert depth >= 0, "Unexpected closing brace"
        assert depth == 0, "Unclosed script block"
    definitions = re.findall(r"(?m)^ id = (qol_reinforcement_probe\.\d+)", text)
    assert len(definitions) == len(set(definitions)), "Duplicate event ID"
    calls = set(re.findall(r"id = (qol_reinforcement_probe\.\d+)", text))
    calls.update(re.findall(r"events = \{ (qol_reinforcement_probe\.\d+)", text))
    assert calls <= set(definitions), "Missing event definition"
    loc = next(OUT.rglob("*.yml")).read_bytes()
    assert loc.startswith(b"\xef\xbb\xbf") and not loc.startswith(b"\xef\xbb\xbf\xef\xbb\xbf")
    keys = set(re.findall(r"(?m)^\s*([^\s:#]+):0", loc.decode("utf-8-sig")))
    refs = set(re.findall(r'(?:name|title|desc)\s*=\s*"([^"]+)"', text))
    assert refs <= keys, f"Missing localisation: {refs - keys}"
    forbidden = ("clear_orders", "queue_actions", "delete_fleet", "destroy_fleet",
                 "set_location", "auto_follow_fleet", "create_ship", "set_owner")
    assert not any(re.search(r"\b" + key + r"\s*=", text) for key in forbidden)
    print("PASS: script blocks, event references, localisation, BOM, no fleet mutation commands")


def build():
    write("descriptor.mod", 'name="补员归队诊断（仅记录）"\nversion="0.1.2"\nsupported_version="4.5.*"\n')
    write("common/on_actions/qol_reinforcement_probe.txt", f"on_ship_built = {{ events = {{ {NS}.10 }} }}\n")
    write("common/edicts/qol_reinforcement_probe.txt", f"""
qol_reinforcement_probe = {{
 length = 1
 icon = "GFX_edict_type_policy"
 potential = {{ is_ai = no }}
 effect = {{ hidden_effect = {{ country_event = {{ id = {NS}.1 }} }} }}
 ai_weight = {{ weight = 0 }}
}}
""")
    write("common/scripted_effects/qol_reinforcement_probe.txt", f"""
# Fleet scope. Assign diagnostic-only IDs so duplicate names are distinguishable.
qol_probe_identify_fleet = {{
 if = {{
  limit = {{ NOT = {{ is_variable_set = qol_probe_fleet_id }} }}
  owner = {{ change_variable = {{ which = qol_probe_fleet_counter value = 1 }} }}
  set_variable = {{ which = qol_probe_fleet_id value = owner.qol_probe_fleet_counter }}
 }}
}}

# Ship scope. Never issues commands or assumes a reinforcement destination.
qol_probe_snapshot_ship = {{
 log = "QOL_PROBE SHIP serial=[This.qol_probe_ship_id] name=[This.GetName]"
 if = {{
  limit = {{ exists = fleet }}
  fleet = {{
   qol_probe_identify_fleet = yes
   log = "QOL_PROBE CURRENT_FLEET id=[This.qol_probe_fleet_id] name=[This.GetName]"
   if = {{ limit = {{ has_fleet_order = merge_fleet_order }} log = "QOL_PROBE MERGE_ORDER=yes" }}
   else = {{ log = "QOL_PROBE MERGE_ORDER=no" }}
   if = {{ limit = {{ is_in_combat = yes }} log = "QOL_PROBE COMBAT=yes" }}
   else = {{ log = "QOL_PROBE COMBAT=no" }}
   if = {{ limit = {{ exists = solar_system }} solar_system = {{ log = "QOL_PROBE SYSTEM name=[This.GetName]" }} }}
  }}
 }}
 else = {{ log = "QOL_PROBE CURRENT_FLEET=unavailable" }}
 if = {{
  limit = {{ exists = event_target:qol_probe_birth_fleet }}
  event_target:qol_probe_birth_fleet = {{ log = "QOL_PROBE BIRTH_FLEET id=[This.qol_probe_fleet_id] name=[This.GetName]" }}
  if = {{ limit = {{ exists = fleet fleet = {{ is_same_value = event_target:qol_probe_birth_fleet }} }} log = "QOL_PROBE SAME_AS_BIRTH=yes" }}
  else = {{ log = "QOL_PROBE SAME_AS_BIRTH=no" }}
 }}
 else = {{ log = "QOL_PROBE BIRTH_FLEET=unavailable" }}
}}

# Country scope: an explicit baseline, useful for matching fleet IDs in logs.
qol_probe_snapshot_country = {{
 log = "QOL_PROBE BASELINE_BEGIN country=[This.GetName]"
 every_owned_fleet = {{
  limit = {{ is_mobile = yes is_ship_class = shipclass_military }}
  qol_probe_identify_fleet = yes
  log = "QOL_PROBE BASELINE_FLEET id=[This.qol_probe_fleet_id] name=[This.GetName]"
  if = {{ limit = {{ exists = solar_system }} solar_system = {{ log = "QOL_PROBE SYSTEM name=[This.GetName]" }} }}
 }}
 log = "QOL_PROBE BASELINE_END"
}}
""")
    events = f"""namespace = {NS}
country_event = {{
 id = {NS}.1
 is_triggered_only = yes
 trigger = {{ is_ai = no }}
 title = "{NS}.title"
 desc = "{NS}.desc"
 picture = GFX_evt_fleet_neutral
 option = {{
  name = "{NS}.start"
  hidden_effect = {{
   set_timed_country_flag = {{ flag = qol_probe_enabled days = 180 }}
   log = "QOL_PROBE ENABLED for 180 days"
   qol_probe_snapshot_country = yes
  }}
 }}
 option = {{
  name = "{NS}.snapshot"
  hidden_effect = {{ qol_probe_snapshot_country = yes }}
 }}
 option = {{
  name = "{NS}.stop"
  hidden_effect = {{ remove_country_flag = qol_probe_enabled log = "QOL_PROBE DISABLED" }}
 }}
 option = {{ name = "{NS}.close" }}
}}

# The native callback documents ROOT=ship, FROM=planet. Do not guess that
# FROM, FROMFROM, or the newborn's own fleet is its reinforcement destination.
ship_event = {{
 id = {NS}.10
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ exists = owner owner = {{ is_ai = no has_country_flag = qol_probe_enabled }} }}
 immediate = {{
  owner = {{ change_variable = {{ which = qol_probe_ship_counter value = 1 }} }}
  set_variable = {{ which = qol_probe_ship_id value = owner.qol_probe_ship_counter }}
  if = {{ limit = {{ exists = fleet }} fleet = {{ qol_probe_identify_fleet = yes save_event_target_as = qol_probe_birth_fleet }} }}
  log = "QOL_PROBE BUILT_BEGIN"
  if = {{ limit = {{ exists = from }} log = "QOL_PROBE CALLBACK_FROM name=[From.GetName]" }}
  qol_probe_snapshot_ship = yes
  log = "QOL_PROBE BUILT_END"
"""
    for number, days in [(11, 1), (12, 5), (13, 20), (14, 60)]:
        events += f"  ship_event = {{ id = {NS}.{number} days = {days} }}\n"
    events += " }\n}\n"
    for number, days in [(11, 1), (12, 5), (13, 20), (14, 60)]:
        events += f"""
ship_event = {{
 id = {NS}.{number}
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ exists = owner owner = {{ is_ai = no has_country_flag = qol_probe_enabled }} }}
 immediate = {{
  log = "QOL_PROBE FOLLOWUP_BEGIN day=+{days}"
  qol_probe_snapshot_ship = yes
  log = "QOL_PROBE FOLLOWUP_END"
 }}
}}
"""
    # Explicit console-only capability test. The save field is a CANDIDATE,
    # not a documented scope. A missing-target / invalid-context engine error
    # is an expected negative result, not a reason to treat it as a real API.
    # Keep this out of on_ship_built so normal logging never relies on it.
    events += f"""
country_event = {{
 id = {NS}.100
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ is_ai = no }}
 immediate = {{
  set_variable = {{ which = qol_probe_scope_sources value = 0 }}
  set_variable = {{ which = qol_probe_scope_controls value = 0 }}
  set_variable = {{ which = qol_probe_scope_readable value = 0 }}
  log = "QOL_TARGET_TEST BEGIN"
  every_owned_fleet = {{
   limit = {{ has_fleet_order = merge_fleet_order }}
   qol_probe_identify_fleet = yes
   root = {{ change_variable = {{ which = qol_probe_scope_sources value = 1 }} }}
   log = "QOL_TARGET_TEST SOURCE id=[This.qol_probe_fleet_id] name=[This.GetName]"
   if = {{
    limit = {{ exists = owner }}
    root = {{ change_variable = {{ which = qol_probe_scope_controls value = 1 }} }}
    log = "QOL_TARGET_TEST OWNER_CONTROL=pass"
   }}
   if = {{
    limit = {{ exists = original_merge_fleet_target }}
    root = {{ change_variable = {{ which = qol_probe_scope_readable value = 1 }} }}
    log = "QOL_TARGET_TEST CANDIDATE_EXISTS=yes"
   }}
   else = {{ log = "QOL_TARGET_TEST CANDIDATE_EXISTS=no" }}
  }}
  log = "QOL_TARGET_TEST RESULT sources=[This.qol_probe_scope_sources] owner_controls=[This.qol_probe_scope_controls] candidate_readable=[This.qol_probe_scope_readable]"
  log = "QOL_TARGET_TEST END"
 }}
}}
"""
    write("events/qol_reinforcement_probe.txt", events)
    loc = {
        "edict_qol_reinforcement_probe": "补员归队诊断（仅记录）",
        "edict_qol_reinforcement_probe_desc": "打开诊断菜单。默认关闭，仅记录新舰船与舰队状态，不下达舰队命令。",
        f"{NS}.title": "补员归队诊断",
        f"{NS}.desc": "开启后记录新造舰船及其完工后第1、5、20、60天的舰队状态，180天后自动停止。\\n\\n请让两支不同名字的舰队补充同一种舰船，再让其中一支进入战斗。\\n\\n此工具只采集可读取的信息，不能保证读取原补员目标。记录写入 game.log，以 QOL_PROBE 开头。",
        f"{NS}.start": "开启或续期诊断（180天）",
        f"{NS}.snapshot": "记录一次当前舰队名单",
        f"{NS}.stop": "停止诊断",
        f"{NS}.close": "关闭菜单",
    }
    write("localisation/simp_chinese/qol_reinforcement_probe_l_simp_chinese.yml", "l_simp_chinese:\n" + "\n".join(f' {k}:0 "{v}"' for k, v in loc.items()) + "\n", bom=True)
    launcher = OUT.parent / "fleet_reinforcement_probe.mod"
    launcher.write_text((OUT / "descriptor.mod").read_text(encoding="utf-8") + f'path="{OUT.as_posix()}"\n', encoding="utf-8")
    validate()
    print(f"Built: {OUT}")
    print(f"Launcher descriptor: {launcher}")


if __name__ == "__main__":
    build()

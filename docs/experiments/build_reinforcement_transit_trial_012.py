"""Build an isolated, manual-only reinforcement return-timer experiment."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/fleet_reinforcement_transit_trial"
NS = "qol_transit_trial"


def write(relative, text, *, bom=False):
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8-sig" if bom else "utf-8")


def validate():
    texts = [p.read_text(encoding="utf-8-sig") for p in OUT.rglob("*.txt")]
    for text in texts:
        clean = re.sub(r'"[^"\n]*"|#[^\n]*', "", text)
        depth = 0
        for token in re.findall(r"[{}]", clean):
            depth += 1 if token == "{" else -1
            assert depth >= 0, "Unexpected closing brace"
        assert depth == 0, "Unclosed block"
    events = (OUT / "events/qol_transit_trial.txt").read_text(encoding="utf-8")
    ids = re.findall(r"(?m)^ id = (qol_transit_trial\.\d+)$", events)
    assert len(ids) == len(set(ids))
    calls = set(re.findall(r"id = (qol_transit_trial\.\d+)", events))
    assert calls <= set(ids)
    # The MIA callback only observes; it must never change arrival dates.
    callback = events.split("# MIA callback: observation only.", 1)[1]
    assert "set_mia_return_delay" not in callback
    assert "owner = { is_ai = no has_country_flag = qol_transit_trial_observe }" in callback
    assert events.count("set_mia_return_delay =") == 3
    for days in (1, 7, 30):
        block = events.split(f" id = {NS}.{200 + days}\n", 1)[1].split("\ncountry_event", 1)[0]
        assert f"trigger = {{ is_ai = no has_country_flag = qol_transit_authorized_{days} }}" in block
        assert "every_owned_fleet" in block
        assert "qol_transit_trial_candidate = yes" in block
        assert f"set_mia_return_delay = {days}" in block
        assert "hide_window = yes" in block
        assert f"has_country_flag = qol_transit_authorized_{days}" in block
        assert f"remove_country_flag = qol_transit_authorized_{days}" in block
        legacy = events.split(f" id = {NS}.{100 + days}\n",1)[1].split("\ncountry_event",1)[0]
        assert "hide_window = yes" in legacy and "always = no" in legacy
        assert "set_mia_return_delay" not in legacy
    result = events.split(f" id = {NS}.2\n",1)[1].split("\ncountry_event",1)[0]
    assert "has_country_flag = qol_transit_result_ready" in result
    assert "remove_country_flag = qol_transit_result_ready" in result
    trigger = (OUT / "common/scripted_triggers/qol_transit_trial.txt").read_text(encoding="utf-8")
    for guard in ("owner = { is_ai = no }", "is_controlled_by = owner",
                  "has_fleet_order = merge_fleet_order", "is_leased = no", "is_alliance_fleet = no"):
        assert guard in trigger
    forbidden = ("clear_orders", "queue_actions", "set_mia", "return_from_mia",
                 "create_ship", "delete_fleet", "destroy_fleet", "set_owner", "set_location")
    combined = "\n".join(texts)
    assert not re.search(r"\bset_country_flag\s*=\s*\{", combined), "Timed flags require set_timed_country_flag"
    assert "set_timed_country_flag = { flag = qol_transit_trial_observe days = 180 }" in events
    assert not any(re.search(r"\b" + key + r"\s*=", combined) for key in forbidden)
    loc = next(OUT.rglob("*.yml")).read_bytes()
    assert loc.startswith(b"\xef\xbb\xbf") and not loc.startswith(b"\xef\xbb\xbf" * 2)
    keys = set(re.findall(r"(?m)^\s*([^\s:#]+):0", loc.decode("utf-8-sig")))
    refs = set(re.findall(r'(?:name|title|desc)\s*=\s*"([^"]+)"', combined))
    assert refs <= keys, f"Missing localisation: {refs - keys}"
    assert not (OUT / "common/defines").exists(), "Trial must not change global defines"
    print("PASS: blocks, event links, localisation, player/control guards, manual timer writes, no global defines")


def build():
    write("descriptor.mod", 'name="玩家补员倒计时试验（手动）"\nversion="0.1.2"\nsupported_version="4.5.*"\n')
    write("common/on_actions/qol_transit_trial.txt", f"on_fleet_went_mia = {{ events = {{ {NS}.20 }} }}\n")
    write("common/edicts/qol_transit_trial.txt", f"""qol_transit_trial = {{
 length = 1
 icon = "GFX_edict_type_policy"
 potential = {{ is_ai = no }}
 effect = {{ hidden_effect = {{ country_event = {{ id = {NS}.1 }} }} }}
 ai_weight = {{ weight = 0 }}
}}
""")
    write("common/scripted_triggers/qol_transit_trial.txt", """# Merge orders are only a candidate filter, NOT proof of reinforcement MIA.
qol_transit_trial_candidate = {
 exists = owner
 owner = { is_ai = no }
 is_controlled_by = owner
 is_mobile = yes
 is_ship_class = shipclass_military
 is_leased = no
 is_alliance_fleet = no
 num_ships > 0
 has_fleet_order = merge_fleet_order
}
""")
    events = f"""namespace = {NS}
country_event = {{
 id = {NS}.1
 is_triggered_only = yes
 trigger = {{ is_ai = no }}
 title = "{NS}.title"
 desc = "{NS}.desc"
 picture = GFX_evt_fleet_neutral
 immediate = {{
  set_variable = {{ which = qol_transit_trial_candidates value = 0 }}
  set_variable = {{ which = qol_transit_trial_attempted value = 0 }}
  set_variable = {{ which = qol_transit_trial_days value = 0 }}
  every_owned_fleet = {{
   limit = {{ qol_transit_trial_candidate = yes }}
   root = {{ change_variable = {{ which = qol_transit_trial_candidates value = 1 }} }}
   log = "QOL_TRANSIT CANDIDATE name=[This.GetName]"
  }}
 }}
 option = {{
  name = "{NS}.observe"
  hidden_effect = {{
   set_timed_country_flag = {{ flag = qol_transit_trial_observe days = 180 }}
   log = "QOL_TRANSIT OBSERVATION_ENABLED days=180"
  }}
 }}
 option = {{
  name = "{NS}.stop"
  hidden_effect = {{ remove_country_flag = qol_transit_trial_observe }}
 }}
"""
    for days in (1, 7, 30):
        events += f""" option = {{
  name = "{NS}.days_{days}"
  trigger = {{ check_variable = {{ which = qol_transit_trial_candidates value > 0 }} }}
  hidden_effect = {{
   set_timed_country_flag = {{ flag = qol_transit_authorized_{days} days = 1 }}
   country_event = {{ id = {NS}.{200 + days} }}
  }}
 }}
"""
    events += f""" option = {{ name = "{NS}.close" default_hide_option = yes }}
}}
"""
    # Old visible results may have been queued by the malformed 0.1.0 table.
    # Tombstones cannot write arrival dates, even if loaded from an old save.
    for days in (1, 7, 30):
        events += f"""
country_event = {{
 id = {NS}.{100 + days}
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ always = no }}
}}
"""
    for days in (1, 7, 30):
        events += f"""
country_event = {{
 id = {NS}.{200 + days}
 is_triggered_only = yes
 hide_window = yes
 trigger = {{ is_ai = no has_country_flag = qol_transit_authorized_{days} }}
 immediate = {{
  remove_country_flag = qol_transit_authorized_{days}
  set_variable = {{ which = qol_transit_trial_attempted value = 0 }}
  set_variable = {{ which = qol_transit_trial_days value = {days} }}
  every_owned_fleet = {{
   limit = {{ qol_transit_trial_candidate = yes }}
   root = {{ change_variable = {{ which = qol_transit_trial_attempted value = 1 }} }}
   log = "QOL_TRANSIT TIMER_ATTEMPT days={days} name=[This.GetName]"
   set_mia_return_delay = {days}
  }}
  log = "QOL_TRANSIT ATTEMPT_END count=[This.qol_transit_trial_attempted]"
  set_timed_country_flag = {{ flag = qol_transit_result_ready days = 1 }}
  country_event = {{ id = {NS}.2 }}
 }}
}}
"""
    events += f"""
country_event = {{
 id = {NS}.2
 is_triggered_only = yes
 trigger = {{ is_ai = no has_country_flag = qol_transit_result_ready }}
 title = "{NS}.result_title"
 desc = "{NS}.result_desc"
 picture = GFX_evt_fleet_neutral
 immediate = {{ remove_country_flag = qol_transit_result_ready }}
 option = {{
  name = "{NS}.back"
  hidden_effect = {{ country_event = {{ id = {NS}.1 }} }}
 }}
 option = {{ name = "{NS}.close" default_hide_option = yes }}
}}
"""
    events += f"""
# MIA callback: observation only.
fleet_event = {{
 id = {NS}.20
 hide_window = yes
 is_triggered_only = yes
 trigger = {{
  exists = owner
  owner = {{ is_ai = no has_country_flag = qol_transit_trial_observe }}
 }}
 immediate = {{
  log = "QOL_TRANSIT MIA_CALLBACK name=[This.GetName]"
  if = {{
   limit = {{ qol_transit_trial_candidate = yes }}
   log = "QOL_TRANSIT MIA_CALLBACK merge_candidate=yes"
  }}
  else = {{ log = "QOL_TRANSIT MIA_CALLBACK merge_candidate=no" }}
 }}
}}
"""
    write("events/qol_transit_trial.txt", events)
    loc = {
        "edict_qol_transit_trial": "玩家补员倒计时试验（手动）",
        "edict_qol_transit_trial_desc": "手动试验失踪返回倒计时。尚未验证补员归队行为，请在测试存档中使用。",
        f"{NS}.title": "玩家补员倒计时试验",
        f"{NS}.desc": "当前候选：§H[Root.qol_transit_trial_candidates]§!支。没有候选时不显示设置按钮。\\n\\n选择档位后仅执行一次：把候选失踪舰队的剩余返回时间设为1、7或30天。不是减去这些天数，也不是持续自动加速。\\n\\n候选依据是合并命令，不等于已确认的补员MIA；普通手动合并也会被统计，按接口文档非MIA舰队不受影响。补员与其他失踪类型仍无法可靠区分。\\n\\n请使用测试副本。重设可能延后原本更快的返回日期；关闭工具不会恢复日期，读修改前存档撤销。",
        f"{NS}.observe": "开启180天失踪事件记录（不改时间）",
        f"{NS}.stop": "停止失踪事件记录",
        f"{NS}.close": "关闭",
        f"{NS}.back": "返回试验菜单",
        f"{NS}.result_title": "单次倒计时设置结果",
        f"{NS}.result_desc": "已尝试向 §H[Root.qol_transit_trial_attempted]§!支候选设置剩余§H[Root.qol_transit_trial_days]§!天。\\n\\n这是调用次数，不是成功数量。请核对提示日期、实际归队日期和原目标舰队收到的船只。未变化不能算成功；本轮也不能证明战斗中仍能保持补员关联。",
    }
    for days in (1, 7, 30):
        loc[f"{NS}.days_{days}"] = f"单次设置：剩余返回时间设为{days}天（试验）"
    write("localisation/simp_chinese/qol_transit_trial_l_simp_chinese.yml",
          "l_simp_chinese:\n" + "\n".join(f' {k}:0 "{v}"' for k, v in loc.items()) + "\n", bom=True)
    launcher = OUT.parent / "fleet_reinforcement_transit_trial.mod"
    launcher.write_text((OUT / "descriptor.mod").read_text(encoding="utf-8") + f'path="{OUT.as_posix()}"\n', encoding="utf-8")
    validate()
    print(f"Built: {OUT}")
    print(f"Launcher descriptor: {launcher}")


if __name__ == "__main__":
    build()

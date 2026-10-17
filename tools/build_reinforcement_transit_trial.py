"""Retire the unsuccessful timer experiment; retain inert legacy event IDs."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/fleet_reinforcement_transit_trial"
NS = "qol_transit_trial"


def write(relative, text, *, bom=False):
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8-sig" if bom else "utf-8")


def validate():
    combined = "\n".join(p.read_text(encoding="utf-8-sig") for p in OUT.rglob("*.txt"))
    for effect in ("set_mia_return_delay", "set_mia", "return_from_mia",
                   "every_owned_fleet", "set_timed_country_flag", "queue_actions"):
        assert not re.search(r"\b" + effect + r"\s*=", combined), effect
    assert "on_fleet_went_mia =" not in combined
    assert "potential = { always = no }" in combined
    for number in (2, 20, 101, 107, 130, 201, 207, 230):
        assert f"id = {NS}.{number}" in combined
    print("PASS: retired timer writes, observation callback and edict; legacy events inert")


def build():
    write("descriptor.mod", 'name="玩家补员倒计时试验（手动）"\nversion="0.1.3"\nsupported_version="4.5.*"')
    write("common/on_actions/qol_transit_trial.txt", "# Retired: no MIA callback.")
    write("common/scripted_triggers/qol_transit_trial.txt", "qol_transit_trial_candidate = { always = no }")
    write("common/edicts/qol_transit_trial.txt", """qol_transit_trial = {
 length = 1
 icon = "GFX_edict_type_policy"
 potential = { always = no }
 ai_weight = { weight = 0 }
}""")
    events = f'''namespace = {NS}
country_event = {{
 id = {NS}.1
 is_triggered_only = yes
 title = "{NS}.title"
 desc = "{NS}.desc"
 picture = GFX_evt_fleet_neutral
 option = {{ name = "{NS}.close" default_hide_option = yes }}
}}
'''
    for number in (2, 101, 107, 130, 201, 207, 230, 20):
        kind = "fleet_event" if number == 20 else "country_event"
        events += f'''{kind} = {{
 id = {NS}.{number}
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ always = no }}
}}
'''
    write("events/qol_transit_trial.txt", events)
    write("localisation/simp_chinese/qol_transit_trial_l_simp_chinese.yml", f'''l_simp_chinese:
 edict_qol_transit_trial:0 "玩家补员倒计时试验（已停用）"
 edict_qol_transit_trial_desc:0 "试验未证实能改变补员倒计时，入口已停用。"
 {NS}.title:0 "补员倒计时试验已停用"
 {NS}.desc:0 "本轮实测未见补员加速，日志还报告部分候选并非MIA。现有筛选不能确认补员运输状态，不能将调用次数当作成功。\\n\\n此插件已停止写入返回时间，也不再监听失踪事件。可在启动器禁用，无需为散舰整理保留它。停用不会回滚此前可能写入的日期。"
 {NS}.close:0 "关闭"
''', bom=True)
    launcher = OUT.parent / "fleet_reinforcement_transit_trial.mod"
    launcher.write_text((OUT / "descriptor.mod").read_text(encoding="utf-8") +
                        f'path="{OUT.as_posix()}"\n', encoding="utf-8")
    validate()
    print(f"Built retired compatibility addon: {OUT}")


if __name__ == "__main__":
    build()

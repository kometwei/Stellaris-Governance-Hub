# -*- coding: utf-8 -*-
"""
生成全自动安全内阁席位分级点名指派系统 (V4 完美自适应国策与游牧版)
1. 彻底解决“指派不上去”：核心席位（科研、防务、国务）自适应游牧（is_nomadic = yes）与常规帝国，杜绝政府不匹配报错
2. 彻底解决“席位与条件不对”：国策席位严格绑定 has_valid_civic 触发器，只向玩家呈现本国当前真实拥有的席位
3. 全面支持游牧/星铁席位：完美支持【星之发现者】(councilor_star_seekers)、【后勤水手长】(councilor_waystation_bosun) 等
4. 保持全局 default_hide_option = yes，原生支持右上角 X 键与 ESC 键关闭
"""

import os

POSITIONS_CATEGORIES = [
    # 类别 1: 星穹列车 / 崩铁游牧核心专属
    {
        "cat_id": 10,
        "cat_tag": "starrail",
        "cat_name": "【星穹列车 / 游牧核心席位】",
        "cat_desc": "专为星穹列车与游牧帝国定制的专属政务席位，突破原版6席限制直接派驻。",
        "positions": [
            {
                "id": 101, "key": "councilor_research_nomadic", "title": "科学专员 (游牧科研主管)",
                "class": "scientist", "desc": "提升全科研门类研发速度", "civic_trigger": None,
                "adaptive": False
            },
            {
                "id": 102, "key": "councilor_defense_nomadic", "title": "战术指挥官 (游牧星际防务)",
                "class": "commander", "desc": "降低舰队维护费，提升舰船航行极速", "civic_trigger": None,
                "adaptive": False
            },
            {
                "id": 103, "key": "councilor_state_nomadic", "title": "舰队大使 (游牧政务外交)",
                "class": "official", "desc": "提升特使工作效率与外交情报网络", "civic_trigger": None,
                "adaptive": False
            },
            {
                "id": 104, "key": "councilor_star_seekers", "title": "星之发现者 (深空探索先驱)",
                "class": "scientist", "desc": "提升调查速度与亚光速航速",
                "civic_trigger": "OR = { has_valid_civic = civic_star_seekers has_valid_civic = civic_corporate_star_seekers }",
                "adaptive": False
            },
            {
                "id": 105, "key": "councilor_waystation_bosun", "title": "后勤水手长 (星系资源调度)",
                "class": "official", "desc": "提升星系资源采集与基地建造储量",
                "civic_trigger": "has_valid_civic = civic_caravan_masters",
                "adaptive": False
            },
        ]
    },
    # 类别 2: 科学研究与深空开发
    {
        "cat_id": 20,
        "cat_tag": "research",
        "cat_name": "【科学研究与深空开发席位】",
        "cat_desc": "专注于科技研发、工程突破与星海探索的资深学者席位。",
        "positions": [
            {
                "id": 201, "key": "councilor_research", "nomadic_key": "councilor_research_nomadic",
                "title": "科研主管 (科学专员 / 首席科学家)", "class": "scientist",
                "desc": "全学科研究速度加成 (自动适配常规帝国与游牧帝国)",
                "civic_trigger": None, "adaptive": True
            },
            {
                "id": 202, "key": "councilor_star_seekers", "title": "星之发现者 (深空探索先驱)",
                "class": "scientist", "desc": "调查速度 +2% / 级，亚光速航速 +1% / 级",
                "civic_trigger": "OR = { has_valid_civic = civic_star_seekers has_valid_civic = civic_corporate_star_seekers }",
                "adaptive": False
            },
            {
                "id": 203, "key": "councilor_technocracy", "title": "技术官僚科学总监",
                "class": "scientist", "desc": "全学科科技研发突破速度大幅提升",
                "civic_trigger": "has_valid_civic = civic_technocracy", "adaptive": False
            },
            {
                "id": 204, "key": "councilor_crafters", "title": "巧夺天工工程大师",
                "class": "official", "desc": "工匠岗位消费品与工程学产出加成",
                "civic_trigger": "has_valid_civic = civic_crafters", "adaptive": False
            },
            {
                "id": 205, "key": "councilor_privatized_exploration", "title": "深空开拓先锋总督",
                "class": "commander", "desc": "增加探索考察速度与领土扩张效率",
                "civic_trigger": "OR = { has_valid_civic = civic_privatized_exploration has_valid_civic = civic_eager_explorers }",
                "adaptive": False
            },
        ]
    },
    # 类别 3: 经贸发展与工业财政
    {
        "cat_id": 30,
        "cat_tag": "economy",
        "cat_name": "【经贸发展与工业财政席位】",
        "cat_desc": "专注于财富积累、贸易流通、矿产开采与工业产能的领袖席位。",
        "positions": [
            {
                "id": 301, "key": "councilor_merchant_guilds", "title": "贸易主管 (商业公会大掌柜)",
                "class": "official", "desc": "商人产出与帝国商业贸易值加成",
                "civic_trigger": "OR = { has_valid_civic = civic_merchant_guilds has_valid_civic = civic_corporate_merchant_guilds }",
                "adaptive": False
            },
            {
                "id": 302, "key": "councilor_mining_guilds", "title": "采矿公会大主管",
                "class": "official", "desc": "全帝国矿物产出大幅提升",
                "civic_trigger": "has_valid_civic = civic_mining_guilds", "adaptive": False
            },
            {
                "id": 303, "key": "councilor_catalytic_processing", "title": "催化技术总工程师",
                "class": "official", "desc": "提升有机食物转化为合金的催化效率",
                "civic_trigger": "has_valid_civic = civic_catalytic_processing", "adaptive": False
            },
            {
                "id": 304, "key": "councilor_efficient_bureaucracy", "title": "高效官僚首辅",
                "class": "official", "desc": "大幅降低帝国规模带来的各项负面惩罚",
                "civic_trigger": "has_valid_civic = civic_efficient_bureaucracy", "adaptive": False
            },
        ]
    },
    # 类别 4: 星际舰队与军事防务
    {
        "cat_id": 40,
        "cat_tag": "military",
        "cat_name": "【星际舰队与军事防务席位】",
        "cat_desc": "专注于指挥庞大无敌舰队、加固星系要塞与征服银河的军政席位。",
        "positions": [
            {
                "id": 401, "key": "councilor_defense", "nomadic_key": "councilor_defense_nomadic",
                "title": "防务统帅 (战术指挥官 / 国防防务总长)", "class": "commander",
                "desc": "大幅降低全军舰队维护费与星港开销 (自动适配游牧与常规帝国)",
                "civic_trigger": None, "adaptive": True
            },
            {
                "id": 402, "key": "councilor_distinguished_admiralty", "title": "帝国大元帅海军统帅",
                "class": "commander", "desc": "提升全舰队火力、射速与海军上将等级上限",
                "civic_trigger": "has_valid_civic = civic_distinguished_admiralty", "adaptive": False
            },
            {
                "id": 403, "key": "councilor_citizen_service", "title": "公民勤务统帅总督",
                "class": "commander", "desc": "增加帝国总海军容量与水兵动员兵力",
                "civic_trigger": "has_valid_civic = civic_citizen_service", "adaptive": False
            },
            {
                "id": 404, "key": "councilor_nationalistic_zeal", "title": "国家狂热战阵宣传官",
                "class": "commander", "desc": "降低宿敌与宣战影响力消耗，提升征战士气",
                "civic_trigger": "has_valid_civic = civic_nationalistic_zeal", "adaptive": False
            },
        ]
    },
    # 类别 5: 治国理政与公会外交
    {
        "cat_id": 50,
        "cat_tag": "state",
        "cat_name": "【治国理政与公会外交席位】",
        "cat_desc": "专注于国家政治制度运转、星际外交博弈与精英统治的内阁席位。",
        "positions": [
            {
                "id": 501, "key": "councilor_state", "nomadic_key": "councilor_state_nomadic",
                "title": "政务外交总管 (舰队大使 / 国务大臣)", "class": "official",
                "desc": "提升帝国凝聚力产出与外交亲善关系 (自动适配游牧与常规帝国)",
                "civic_trigger": None, "adaptive": True
            },
            {
                "id": 502, "key": "councilor_diplomatic_corps", "title": "外交使团全权代表",
                "class": "official", "desc": "增加特使数量与银河星海理事会外交权重",
                "civic_trigger": "has_valid_civic = civic_diplomatic_corps", "adaptive": False
            },
            {
                "id": 503, "key": "councilor_shadow_council", "title": "暗影内阁幕后主使",
                "class": "official", "desc": "提升统治阶层政治控制力与隐秘行动成功率",
                "civic_trigger": "has_valid_civic = civic_shadow_council", "adaptive": False
            },
            {
                "id": 504, "key": "councilor_aristocratic_elite", "title": "贵族精英上议院议长",
                "class": "official", "desc": "增强总督执政效果与精英人口政治威望",
                "civic_trigger": "has_valid_civic = civic_aristocratic_elite", "adaptive": False
            },
        ]
    }
]

def build_events():
    lines = []
    lines.append("namespace = auto_qol_council_assign\n")
    
    # 1. 主分类大类菜单 (ID: auto_qol_council_assign.1)
    lines.append("""# ========================================================
# 内阁席位点名指派中枢大厅 (突破 6 席位限制)
# ========================================================
country_event = {
\tid = auto_qol_council_assign.1
\ttitle = "auto_qol_council_assign.1.name"
\tdesc = "auto_qol_council_assign.1.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes
""")
    for cat in POSITIONS_CATEGORIES:
        cid = cat["cat_id"]
        ctag = cat["cat_tag"]
        lines.append(f"""\toption = {{
\t\tname = "auto_qol_council_assign.cat_{ctag}"
\t\tcountry_event = {{ id = auto_qol_council_assign.{cid} }}
\t}}
""")
    # 查看名册、返回与离开
    lines.append("""\toption = {
\t\tname = "auto_qol_council_assign.view_roster"
\t\tcountry_event = { id = auto_qol_council_assign.90 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.back_to_council_menu"
\t\tcountry_event = { id = auto_qol_council_menu.1 }
\t}

\toption = {
\t\tname = "auto_qol.close_direct"
\t\tdefault_hide_option = yes
\t}
}
""")

    # 2. 各分类二级菜单 (每个大类严格独立，ID: auto_qol_council_assign.10/20/30/40/50)
    for cat in POSITIONS_CATEGORIES:
        cid = cat["cat_id"]
        lines.append(f"""# ========================================================
# 分类子菜单: {cat["cat_name"]}
# ========================================================
country_event = {{
\tid = auto_qol_council_assign.{cid}
\ttitle = "auto_qol_council_assign.{cid}.name"
\tdesc = "auto_qol_council_assign.{cid}.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes
""")
        for pos in cat["positions"]:
            pos_id = pos["id"]
            pos_key = pos["key"]
            trigger_block = ""
            if pos.get("civic_trigger"):
                trigger_block = f"\n\t\ttrigger = {{ {pos['civic_trigger']} }}"
            
            lines.append(f"""\toption = {{{trigger_block}
\t\tname = "auto_qol_council_assign.{pos_key}.btn"
\t\tcustom_tooltip = "auto_qol_council_assign.{pos_key}.tt"
\t\tcountry_event = {{ id = auto_qol_council_assign.{pos_id} }}
\t}}
""")
        lines.append(f"""\toption = {{
\t\tname = "auto_qol_council_assign.back_to_assign_menu"
\t\tcountry_event = {{ id = auto_qol_council_assign.1 }}
\t}}

\toption = {{
\t\tname = "auto_qol.close_direct"
\t\tdefault_hide_option = yes
\t}}
}}
""")

    # 3. 候选人点名挑选菜单 (每个席位独立对应一个数字ID，严格 6 选项安全隔离)
    for cat in POSITIONS_CATEGORIES:
        cid = cat["cat_id"]
        for pos in cat["positions"]:
            pos_id = pos["id"]
            pos_key = pos["key"]
            pos_title = pos["title"]
            target_class = pos["class"]
            is_adaptive = pos.get("adaptive", False)
            nomadic_key = pos.get("nomadic_key", None)
            class_filter = f"leader_class = {target_class}" if target_class else ""

            lines.append(f"""# 候选人挑选: {pos_title} ({pos_key}) [ID: auto_qol_council_assign.{pos_id}]
country_event = {{
\tid = auto_qol_council_assign.{pos_id}
\ttitle = "auto_qol_council_assign.{pos_key}.pick_name"
\tdesc = "auto_qol_council_assign.pick_desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes

\timmediate = {{
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\t{class_filter}
\t\t\t}}
\t\t\tsave_event_target_as = auto_qol_cand_1
\t\t}}
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\t{class_filter}
\t\t\t\tNOR = {{
\t\t\t\t\tis_same_value = event_target:auto_qol_cand_1
\t\t\t\t}}
\t\t\t}}
\t\t\tsave_event_target_as = auto_qol_cand_2
\t\t}}
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\t{class_filter}
\t\t\t\tNOR = {{
\t\t\t\t\tis_same_value = event_target:auto_qol_cand_1
\t\t\t\t\tis_same_value = event_target:auto_qol_cand_2
\t\t\t\t}}
\t\t\t}}
\t\t\tsave_event_target_as = auto_qol_cand_3
\t\t}}
\t\trandom_owned_leader = {{
\t\t\tlimit = {{
\t\t\t\tis_pool_leader = no
\t\t\t\tis_ruler = no
\t\t\t\t{class_filter}
\t\t\t\tNOR = {{
\t\t\t\t\tis_same_value = event_target:auto_qol_cand_1
\t\t\t\t\tis_same_value = event_target:auto_qol_cand_2
\t\t\t\t\tis_same_value = event_target:auto_qol_cand_3
\t\t\t\t}}
\t\t\t}}
\t\t\tsave_event_target_as = auto_qol_cand_4
\t\t}}
\t}}
""")
            # 候选人 1~4 任命按钮 (包含席位挂载、防重复解锁锁机制与领袖派驻)
            for c_idx in [1, 2, 3, 4]:
                if is_adaptive and nomadic_key:
                    assign_logic = f"""\t\tif = {{
\t\t\tlimit = {{ is_nomadic = yes }}
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tNOT = {{ has_councilor = {{ COUNCILOR = {nomadic_key} }} }}
\t\t\t\t}}
\t\t\t\tset_council_position_to_council = {nomadic_key}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ NOT = {{ has_country_flag = auto_qol_slot_{nomadic_key} }} }}
\t\t\t\t\tset_country_flag = auto_qol_slot_{nomadic_key}
\t\t\t\t\tunlock_council_slots = 1
\t\t\t\t}}
\t\t\t}}
\t\t\tevent_target:auto_qol_cand_{c_idx} = {{
\t\t\t\tset_council_position = {nomadic_key}
\t\t\t\tsave_event_target_as = auto_qol_last_assigned
\t\t\t}}
\t\t}}
\t\telse = {{
\t\t\tif = {{
\t\t\t\tlimit = {{
\t\t\t\t\tNOT = {{ has_councilor = {{ COUNCILOR = {pos_key} }} }}
\t\t\t\t}}
\t\t\t\tset_council_position_to_council = {pos_key}
\t\t\t\tif = {{
\t\t\t\t\tlimit = {{ NOT = {{ has_country_flag = auto_qol_slot_{pos_key} }} }}
\t\t\t\t\tset_country_flag = auto_qol_slot_{pos_key}
\t\t\t\t\tunlock_council_slots = 1
\t\t\t\t}}
\t\t\t}}
\t\t\tevent_target:auto_qol_cand_{c_idx} = {{
\t\t\t\tset_council_position = {pos_key}
\t\t\t\tsave_event_target_as = auto_qol_last_assigned
\t\t\t}}
\t\t}}"""
                else:
                    assign_logic = f"""\t\tif = {{
\t\t\tlimit = {{
\t\t\t\tNOT = {{ has_councilor = {{ COUNCILOR = {pos_key} }} }}
\t\t\t}}
\t\t\tset_council_position_to_council = {pos_key}
\t\t\tif = {{
\t\t\t\tlimit = {{ NOT = {{ has_country_flag = auto_qol_slot_{pos_key} }} }}
\t\t\t\tset_country_flag = auto_qol_slot_{pos_key}
\t\t\t\tunlock_council_slots = 1
\t\t\t}}
\t\t}}
\t\tevent_target:auto_qol_cand_{c_idx} = {{
\t\t\tset_council_position = {pos_key}
\t\t\tsave_event_target_as = auto_qol_last_assigned
\t\t}}"""

                lines.append(f"""\toption = {{
\t\ttrigger = {{ exists = event_target:auto_qol_cand_{c_idx} }}
\t\tname = "auto_qol_assign.cand_{c_idx}"
{assign_logic}
\t\tcountry_event = {{ id = auto_qol_council_assign.99 }}
\t}}
""")
            # 刷新与返回
            lines.append(f"""\t# 刷新换一批
\toption = {{
\t\tname = "auto_qol_assign.refresh"
\t\tcountry_event = {{ id = auto_qol_council_assign.{pos_id} }}
\t}}

\t# 返回分类子菜单
\toption = {{
\t\tname = "auto_qol_assign.back_to_cat"
\t\tcountry_event = {{ id = auto_qol_council_assign.{cid} }}
\t}}

\t# 离开并关闭界面 (支持右上角X与ESC)
\toption = {{
\t\tname = "auto_qol.close_direct"
\t\tdefault_hide_option = yes
\t}}
}}
""")

    # 4. 任命成功反馈弹窗 (ID: auto_qol_council_assign.99)
    lines.append("""# ========================================================
# 席位任命成功通告
# ========================================================
country_event = {
\tid = auto_qol_council_assign.99
\ttitle = "auto_qol_council_assign.99.name"
\tdesc = "auto_qol_council_assign.99.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes

\toption = {
\t\tname = "auto_qol_council_assign.success.continue"
\t\tcountry_event = { id = auto_qol_council_assign.1 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.success.view_roster"
\t\tcountry_event = { id = auto_qol_council_assign.90 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.success.close"
\t\tdefault_hide_option = yes
\t}
}
""")

    # 5. 在任内阁名册大厅 (ID: auto_qol_council_assign.90)
    lines.append("""# ========================================================
# 在任内阁总名册大厅
# ========================================================
country_event = {
\tid = auto_qol_council_assign.90
\ttitle = "auto_qol_council_assign.90.name"
\tdesc = "auto_qol_council_assign.90.desc"
\tpicture = GFX_evt_throne_room
\tis_triggered_only = yes

\timmediate = {
\t\trandom_owned_leader = {
\t\t\tlimit = { is_councilor = yes }
\t\t\tsave_event_target_as = auto_qol_in_office_1
\t\t}
\t\trandom_owned_leader = {
\t\t\tlimit = {
\t\t\t\tis_councilor = yes
\t\t\t\tNOR = { is_same_value = event_target:auto_qol_in_office_1 }
\t\t\t}
\t\t\tsave_event_target_as = auto_qol_in_office_2
\t\t}
\t\trandom_owned_leader = {
\t\t\tlimit = {
\t\t\t\tis_councilor = yes
\t\t\t\tNOR = {
\t\t\t\t\tis_same_value = event_target:auto_qol_in_office_1
\t\t\t\t\tis_same_value = event_target:auto_qol_in_office_2
\t\t\t\t}
\t\t\t}
\t\t\tsave_event_target_as = auto_qol_in_office_3
\t\t}
\t\trandom_owned_leader = {
\t\t\tlimit = {
\t\t\t\tis_councilor = yes
\t\t\t\tNOR = {
\t\t\t\t\tis_same_value = event_target:auto_qol_in_office_1
\t\t\t\t\tis_same_value = event_target:auto_qol_in_office_2
\t\t\t\t\tis_same_value = event_target:auto_qol_in_office_3
\t\t\t\t}
\t\t\t}
\t\t\tsave_event_target_as = auto_qol_in_office_4
\t\t}
\t}

\toption = {
\t\ttrigger = { exists = event_target:auto_qol_in_office_1 }
\t\tname = "auto_qol_assign.roster_1"
\t}
\toption = {
\t\ttrigger = { exists = event_target:auto_qol_in_office_2 }
\t\tname = "auto_qol_assign.roster_2"
\t}
\toption = {
\t\ttrigger = { exists = event_target:auto_qol_in_office_3 }
\t\tname = "auto_qol_assign.roster_3"
\t}
\toption = {
\t\ttrigger = { exists = event_target:auto_qol_in_office_4 }
\t\tname = "auto_qol_assign.roster_4"
\t}

\toption = {
\t\tname = "auto_qol_assign.roster_refresh"
\t\tcountry_event = { id = auto_qol_council_assign.90 }
\t}

\toption = {
\t\tname = "auto_qol_council_assign.back_to_assign_menu"
\t\tcountry_event = { id = auto_qol_council_assign.1 }
\t}

\toption = {
\t\tname = "auto_qol.close_direct"
\t\tdefault_hide_option = yes
\t}
}
""")

    return "".join(lines)

def build_loc():
    loc = []
    loc.append(' auto_qol_council_menu.manual_assign:0 "【政务内阁】核心席位手动点名指派中枢"')
    loc.append(' auto_qol_council_menu.manual_assign_tt:0 "§G点击进入内阁点名指派中枢§!\\n突破游戏原版 6 个席位的视觉限制，自由挑选心仪领袖手动任命到关键内阁席位，后台实打实激活其全局特质与加成。"')
    
    loc.append(' auto_qol_council_assign.1.name:0 "帝国政务内阁 · 席位点名指派中枢"')
    loc.append(' auto_qol_council_assign.1.desc:0 "§H欢迎使用内阁席位手动指派中枢§!\\n\\n原版内阁面板受 UI 界面限制最多仅展示 6 个席位。然而群星底层引擎支持§G无上限后台内阁§!！\\n在此你可以突破 6 席限制，选择指定席位并手动点名派遣名下心仪领袖上岗。\\n上岗后其实际特质与帝国增益将在后台完全叠加生效！\\n\\n§E请选择你要指派的内阁席位大类：§!"')
    loc.append(' auto_qol_council_assign.view_roster:0 "【在任名册】查阅当前后台已在任内阁领袖"')
    loc.append(' auto_qol_council_assign.back_to_council_menu:0 "返回助手内阁主控制台"')
    loc.append(' auto_qol_council_assign.back_to_assign_menu:0 "返回席位大类选择"')
    loc.append(' auto_qol_assign.back_to_cat:0 "返回当前分类"')
    loc.append(' auto_qol_assign.refresh:0 "【换一批候选领袖 (随机刷新)】"')
    loc.append(' auto_qol.close_direct:0 "离开并关闭界面 (X / ESC)"')

    loc.append(' auto_qol_assign.cand_1:0 "任命：[auto_qol_cand_1.GetName] ([auto_qol_cand_1.GetClass])"')
    loc.append(' auto_qol_assign.cand_2:0 "任命：[auto_qol_cand_2.GetName] ([auto_qol_cand_2.GetClass])"')
    loc.append(' auto_qol_assign.cand_3:0 "任命：[auto_qol_cand_3.GetName] ([auto_qol_cand_3.GetClass])"')
    loc.append(' auto_qol_assign.cand_4:0 "任命：[auto_qol_cand_4.GetName] ([auto_qol_cand_4.GetClass])"')

    loc.append(' auto_qol_council_assign.pick_desc:0 "以下为你名下的可用领袖候选人。\\n点击即可将该领袖直接任命并强行派驻至目标内阁席位！\\n若未看到心仪领袖，可点击下方【换一批候选领袖】进行刷新。"')
    loc.append(' auto_qol_assign.pick_desc:0 "以下为你名下的可用领袖候选人。\\n点击即可将该领袖直接任命并强行派驻至目标内阁席位！\\n若未看到心仪领袖，可点击下方【换一批候选领袖】进行刷新。"')

    loc.append(' auto_qol_council_assign.99.name:0 "内阁席位任命成功！"')
    loc.append(' auto_qol_council_assign.99.desc:0 "§G任命已顺利完成！§!\\n\\n领袖 §H[auto_qol_last_assigned.GetName]§! 已经正式履职！\\n其内阁特质、岗位增益与帝国全域修正已在后台完全激活生效。即便原版 UI 界面已排满，其内阁增益依然 100% 持续为您效力！"')
    loc.append(' auto_qol_council_assign.success.continue:0 "继续指派其他席位"')
    loc.append(' auto_qol_council_assign.success.view_roster:0 "查看当前已任职内阁名册"')
    loc.append(' auto_qol_council_assign.success.close:0 "完成并关闭"')

    loc.append(' auto_qol_council_assign.90.name:0 "帝国政务内阁 · 现任官员名册"')
    loc.append(' auto_qol_council_assign.90.desc:0 "以下为当前正在帝国政务内阁中实际任职的领袖名册（无论原版 UI 是否能全部塞下，均在此实效运转）："')
    loc.append(' auto_qol_assign.roster_1:0 "在任官员：[auto_qol_in_office_1.GetName] ([auto_qol_in_office_1.GetClass])"')
    loc.append(' auto_qol_assign.roster_2:0 "在任官员：[auto_qol_in_office_2.GetName] ([auto_qol_in_office_2.GetClass])"')
    loc.append(' auto_qol_assign.roster_3:0 "在任官员：[auto_qol_in_office_3.GetName] ([auto_qol_in_office_3.GetClass])"')
    loc.append(' auto_qol_assign.roster_4:0 "在任官员：[auto_qol_in_office_4.GetName] ([auto_qol_in_office_4.GetClass])"')
    loc.append(' auto_qol_assign.roster_refresh:0 "【下一批现任名册】"')

    for cat in POSITIONS_CATEGORIES:
        cid = cat["cat_id"]
        ctag = cat["cat_tag"]
        loc.append(f' auto_qol_council_assign.cat_{ctag}:0 "{cat["cat_name"]}"')
        loc.append(f' auto_qol_council_assign.{cid}.name:0 "{cat["cat_name"]}"')
        loc.append(f' auto_qol_council_assign.{cid}.desc:0 "{cat["cat_desc"]}\\n\\n请挑选具体的席位职位："')
        for pos in cat["positions"]:
            pos_key = pos["key"]
            pos_title = pos["title"]
            pos_desc = pos["desc"]
            loc.append(f' auto_qol_council_assign.{pos_key}.btn:0 "派驻：{pos_title}"')
            loc.append(f' auto_qol_council_assign.{pos_key}.tt:0 "§H{pos_title}§!\\n{pos_desc}\\n\\n§G点击挑选领袖并派遣上任§!"')
            loc.append(f' auto_qol_council_assign.{pos_key}.pick_name:0 "任命席位：{pos_title}"')

    return "\n".join(loc)

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    events_dir = os.path.join(base_dir, "events")
    loc_dir = os.path.join(base_dir, "localisation", "simp_chinese")
    os.makedirs(events_dir, exist_ok=True)
    os.makedirs(loc_dir, exist_ok=True)

    event_content = build_events()
    event_file = os.path.join(events_dir, "auto_qol_council_assign_events.txt")
    with open(event_file, "w", encoding="utf-8") as f:
        f.write(event_content)
    print(f"Generated {event_file}")

    loc_content = build_loc()
    loc_file = os.path.join(loc_dir, "auto_qol_council_assign_l_simp_chinese.yml")
    with open(loc_file, "w", encoding="utf-8-sig") as f:
        f.write("l_simp_chinese:\n" + loc_content + "\n")
    print(f"Generated {loc_file}")

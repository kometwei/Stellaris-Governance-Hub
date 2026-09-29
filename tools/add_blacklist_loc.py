from paths import LOCALISATION_DIR

loc_path = LOCALISATION_DIR / 'auto_qol_l_simp_chinese.yml'
text = loc_path.read_text(encoding='utf-8')

blacklist_locs = """
 tr_node_blocked_tt:0 "§R⚠️ 【事前安全熔断已生效】§!\\n检测到该传统包含恶性词条 (-10000 劳工政治权重)。\\n若激活会导致群星引擎在 F2 外交界面除以零崩溃 (CTD)。\\n助手已为您事前熔断拦截，跳过此项以确保游戏安全稳定！"
 tr_node_blocked_tr_tt_ultralimit_adopt:0 "§R🛡️ 【安全熔断已跳过】§! 极限传统 (tr_tt_ultralimit_adopt)"
 tr_node_blocked_tr_tt_ultralimit_1:0 "§R🛡️ 【安全熔断已跳过】§! 秩序井然的星球 (tr_tt_ultralimit_1)"
 tr_node_blocked_tr_tt_ultralimit_2:0 "§R🛡️ 【安全熔断已跳过】§! 极致稳定的社会 (tr_tt_ultralimit_2)"
 tr_node_blocked_tr_tt_ultralimit_3:0 "§R🛡️ 【安全熔断已跳过】§! 至臻完美的住所 (tr_tt_ultralimit_3)"
 tr_node_blocked_tr_tt_ultralimit_4:0 "§R🛡️ 【安全熔断已跳过】§! 突破限制的改造 (tr_tt_ultralimit_4)"
 tr_node_blocked_tr_tt_ultralimit_5:0 "§R🛡️ 【安全熔断已跳过】§! 完美的终极导师 (tr_tt_ultralimit_5)"
 tr_node_blocked_tr_tt_ultralimit_finish:0 "§R🛡️ 【安全熔断已跳过】§! 极限传统完成 (tr_tt_ultralimit_finish)"
"""

if "tr_node_blocked_tt" not in text:
    text = text.rstrip() + "\n" + blacklist_locs.strip() + "\n"
    loc_path.write_text(text, encoding='utf-8-sig')
    print("Added blacklist locs!")
else:
    print("Already present")

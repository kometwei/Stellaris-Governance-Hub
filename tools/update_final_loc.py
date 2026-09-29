from paths import LOCALISATION_DIR

loc_path = LOCALISATION_DIR / "auto_qol_l_simp_chinese.yml"
text = loc_path.read_text(encoding='utf-8', errors='ignore')

# 1. 替换传统界面的本地化文本
tr_loc_text = """ tradition_unlock_menu.1.name:0 "Mod 传统智能激活助手"
 tradition_unlock_menu.1.desc:0 "欢迎使用智能条件匹配版传统助手。本系统拥有事前安全审计功能：\n\n1. §H【智能条件审计激活】§!：自动根据你当前帝国的政体与身份（普通帝国、机械、蜂巢或巨企）动态匹配符合条件的传统，不合条件的绝不强加；\n2. §H【跳过领袖初始特质】§!：自动剔除导致领袖池特质堆叠卡顿的恶性节点；\n3. §H【彻底杜绝卡顿】§!：后台秒级激活，界面丝滑不冻结。"
 tradition_unlock_menu.opt_smart:0 "£trigger_yes£ §G【智能条件匹配一键激活全部传统】§! (强烈推荐)"
 tradition_unlock_menu.opt_smart_tt:0 "自动审计当前帝国身份，仅点亮符合本国政体与前置条件的传统，智能跳过非本国专属（如蜂巢/机械专属），彻底杜绝违和感与报错！"
 tradition_unlock_menu.opt_universal:0 "【仅激活纯通用无门槛传统】"
 tradition_unlock_menu.opt_universal_tt:0 "仅激活没有任何政体、思潮或外部门槛的普适传统。"
 tradition_unlock_menu.back:0 "返回助手主控制台"
"""

# 2. 替换内阁界面的本地化文本
council_loc_text = """ auto_qol_council_menu.1.name:0 "帝国政务内阁辅助助手"
 auto_qol_council_menu.1.desc:0 "本模块为你提供安全原生的内阁槽位解锁与加速服务：\n\n1. 点击下方按钮可一次性解锁帝国内阁的全部可用空位槽位；\n2. 解锁后，直接按 §YF1§! 打开官方【政府 -> 内阁】面板，点击任意空余席位卡片，即可自由挑选你帝国里的任何领袖（享受官方原版完整的立绘、经验等级与特质面板，绝无任何缺失）！"
 auto_qol_council_menu.unlock_all_slots:0 "£trigger_yes£ §G【一键解锁全部内阁席位槽位】§!"
 auto_qol_council_menu.unlock_all_slots_tt:0 "立即将当前帝国内阁的所有空余席位槽位全部解锁开放，允许你安排更多内阁要员。"
 auto_qol_council_menu.buff_council:0 "§Y【启用内阁领袖专注协议】§!"
 auto_qol_council_menu.buff_council_tt:0 "为帝国所有内阁要员提供 +50% 经验获取加速与 -25% 领袖维护费优化。"
 auto_qol_council_menu.back:0 "返回助手主控制台"
 auto_qol_council_buff:0 "内阁领袖专注协议"
 auto_qol_council_buff_desc:0 "来自助手控制台的内阁效能优化，提升经验并降低维护费。"
"""

# 清理旧传统和内阁文本并替换
text = re.sub(r' tradition_unlock_menu\.1\.name:0[\s\S]*?tradition_unlock_menu\.back_to_tr_main:0[^\n]*\n', tr_loc_text, text)
text = re.sub(r' auto_qol_council_menu\.1\.name:0[\s\S]*?auto_qol_council_menu\.back:0[^\n]*\n', council_loc_text, text)

# 确保以 UTF-8 with BOM 写入
loc_path.write_text(text, encoding='utf-8-sig')
print("Localization successfully updated with UTF-8 BOM!")

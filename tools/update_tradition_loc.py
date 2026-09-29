import re

from paths import LOCALISATION_DIR

def update_loc():
    file_path = LOCALISATION_DIR / 'auto_qol_l_simp_chinese.yml'
    with open(file_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()

    # Replace 【已勾选】 with 【✔ 帝国已激活】
    content = content.replace("【已勾选】", "【✔ 帝国已激活】")
    # Replace 【未勾选】 with 【⚡ 点击直接激活】
    content = content.replace("【未勾选】", "【⚡ 点击直接激活】")

    # Add new button descriptions if not present
    new_keys = """
 tradition_tree_unlock_all:0 "⚡ 【立即一键激活本树全部传统】"
 tradition_tree_unlock_all_tt:0 "点击立即点亮本传统树的入门、全部分支及收关效果！"
 tradition_mod_unlock_all:0 "⚡ 【立即一键激活此 Mod 全部传统】"
 tradition_mod_unlock_all_tt:0 "点击立即解锁并激活此 Mod 旗下的所有传统树！"
 tradition_all_unlock_all:0 "⚡ 【一键激活当前已安装 Mod 全部传统】"
 tradition_all_unlock_all_tt:0 "一键解锁并激活当前检测到的所有 Mod 全部传统！"
"""
    if "tradition_tree_unlock_all" not in content:
        # Insert after tradition_unlock_menu.back
        content = content.replace('tradition_unlock_menu.back:0 "返回主菜单"', 'tradition_unlock_menu.back:0 "返回主菜单"' + new_keys)

    with open(file_path, 'w', encoding='utf-8-sig') as f:
        f.write(content)
        
    print("Successfully updated localization!")

if __name__ == '__main__':
    update_loc()

"""Generate native per-job automation ratio modifiers from official jobs only."""
from pathlib import Path
import re
from paths import GAME_INSTALL_DIR
from build_smart_council_system import strip_comments, find_matching_brace

RELATIVE = "common/static_modifiers/auto_qol_automation_ratio_modifiers.txt"
# These represent population states or forced/special assignments, not normal work.
EXCLUDED = {"purge", "pre_sapients", "criminal", "deviant_drone", "corrupt_drone",
            "civilian", "assimilation", "deep_sleep", "cruise_passenger", "xeno_ward"}


def jobs(game_root=GAME_INSTALL_DIR):
    definitions = {}
    for path in sorted((Path(game_root) / "common/pop_jobs").glob("*.txt")):
        text = strip_comments(path.read_text(encoding="utf-8-sig"))
        for match in re.finditer(r"(?m)^([A-Za-z_][\w]*)\s*=\s*\{", text):
            opening = text.index("{", match.start())
            definitions[match[1]] = text[opening + 1:find_matching_brace(text, opening)]
    eligible = []
    for name, block in sorted(definitions.items()):
        # Inspect inline scripts too, so an explicit native opt-out stays an opt-out.
        pending, seen = [block], set()
        while pending:
            current = pending.pop()
            for match in re.finditer(r'(?:inline_script\s*=\s*"([^"\n]+)"|script\s*=\s*"?([\w/]+)"?)', current):
                relative = match[1] or match[2]
                path = Path(game_root) / "common/inline_scripts" / (relative + ".txt")
                if relative in seen or not path.exists():
                    continue
                seen.add(relative)
                expanded = strip_comments(path.read_text(encoding="utf-8-sig"))
                block += "\n" + expanded
                pending.append(expanded)
        if re.search(r"\bcan_be_automated\s*=\s*no\b", block):
            continue
        category = re.search(r"(?m)^\s*category\s*=\s*(\w+)", block)
        category = category[1] if category else ""
        if category in EXCLUDED or "unemployment" in category:
            continue
        eligible.append(name)
    if not eligible:
        raise ValueError("No official jobs found for automation ratio generation")
    return eligible


def generate(game_root=GAME_INSTALL_DIR):
    lines = ["# Generated from official jobs; native job automation restrictions still apply.",
             "qol_custom_automated_ratio_modifier = {"]
    lines.extend(f"    job_{name}_automated_workforce_mult = 0.01" for name in jobs(game_root))
    return "\n".join(lines + ["}", ""])


def build(root, game_root=GAME_INSTALL_DIR):
    path = Path(root) / RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(generate(game_root), encoding="utf-8")


if __name__ == "__main__":
    build(Path(__file__).resolve().parents[1])
    print(f"Generated automation ratio modifiers for {len(jobs())} official jobs.")

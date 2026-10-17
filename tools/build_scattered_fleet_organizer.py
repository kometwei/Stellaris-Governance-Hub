"""Build an isolated on-demand scattered-fleet organizer. No background hooks."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist/scattered_fleet_organizer"
NS = "qol_fleet_sort"
PAGE = 8
BATCH = 256

# Operations to preserve. Ordinary navigation is intentionally NOT blocked;
# only source navigation is replaced after explicit confirmation.
ORDERS = (
    "merge_fleet_order",
    "build_orbital_station_order",
    # 4.5.2 rejects build_space_station_order and the documented typo
    # research_discovery_orde; neither is used by ordinary military ships.
    "colonize_planet_order", "survey_planet_order",
    "research_anomaly_order", "collect_data_fleet_order",
    "upgrade_design_at_starbase_fleet_order", "upgrade_design_at_orbitable_fleet_order",
    "repair_fleet_order", "evade_hostiles_order",
    "land_armies_order", "aggressive_stance_fleet_order",
    "auto_explore_order", "build_megastructure_fleet_order", "destroy_planet_order",
    "planet_killer_weapon_windup_order", "planet_killer_weapon_fire_order",
    "explore_bypass_order", "jumpdrive_order", "jumpdrive_windup",
    "experimental_subspace_navigation_fleet_order", "excavate_archaeological_site_fleet_order",
)


def write(relative, text, *, bom=False):
    if relative.startswith("common/scripted_effects/"):
        text = text.replace("[", r"\\[")
    path = OUT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.strip() + "\n", encoding="utf-8-sig" if bom else "utf-8")


def option(key, effect="", trigger="", tooltip=""):
    result = f' option = {{\n  name = "{NS}.{key}"\n'
    if key in ("cancel", "close"):
        result += "  default_hide_option = yes\n"
    if trigger:
        result += f"  trigger = {{ {trigger} }}\n"
    if tooltip:
        result += f'  custom_tooltip = "{NS}.{tooltip}"\n'
    if effect:
        result += f"  hidden_effect = {{ {effect} }}\n"
    return result + " }\n"


def event(number, title, body, *, hidden=False):
    head = f"country_event = {{\n id = {NS}.{number}\n is_triggered_only = yes\n trigger = {{ is_ai = no }}\n"
    if hidden:
        head += " hide_window = yes\n"
    else:
        head += f' title = "{NS}.{title}.title"\n desc = "{NS}.{title}.desc"\n picture = GFX_evt_fleet_neutral\n'
    return head + body + "}\n"


def same_set(peer, ship_peer=None):
    """Fleet-set equality in both directions; quantities and ship order don't matter.

    ship_peer resolves the peer while inside an any_owned_ship scope. Native
    PREVPREV/PREVPREVPREV walk saved scope history. Dot-chaining PREV instead
    performs consecutive context switches and can bounce back to a ship.
    """
    ship_peer = ship_peer or peer
    return f"""
 exists = {peer}
 NOT = {{ any_owned_ship = {{ NOT = {{
  {ship_peer} = {{ any_owned_ship = {{
   design = {{ is_same_value = prevprevprev.design }}
  }} }}
 }} }} }}
 {peer} = {{ NOT = {{ any_owned_ship = {{ NOT = {{
  prevprev = {{ any_owned_ship = {{
   design = {{ is_same_value = prevprevprev.design }}
  }} }}
 }} }} }} }}
"""


def build_triggers():
    orders = "\n".join(f"  has_fleet_order = {key}" for key in ORDERS)
    write("common/scripted_triggers/qol_fleet_sort.txt", f"""
qol_sort_owned = {{
 exists = owner
 owner = {{ is_ai = no }}
 is_controlled_by = owner
 is_mobile = yes
 is_leased = no
 is_alliance_fleet = no
 has_ship_owner_type = country
 is_ship_class = shipclass_military
 num_ships > 0
 exists = solar_system
 NOT = {{
  any_owned_ship = {{
   OR = {{
    is_designable = no
    NOT = {{ exists = design }}
    is_ship_size = juggernaut
    is_ship_size = colossus
    is_ship_size = star_eater
   }}
  }}
 }}
}}

qol_sort_available = {{
 is_in_combat = no
 NOR = {{
{orders}
 }}
}}

qol_sort_candidate = {{
 OR = {{
  AND = {{
   NOT = {{ has_fleet_flag = qol_sort_auto_protected }}
  }}
  AND = {{
   has_fleet_flag = qol_sort_auto_protected
   has_fleet_flag = qol_sort_regroup_ready
   is_variable_set = qol_sort_reserved_total
   check_variable = {{ which = qol_sort_reserved_total value <= trigger:fleet_size }}
  }}
 }}
 NOT = {{ has_fleet_flag = qol_sort_protected }}
 NOT = {{ has_fleet_flag = qol_sort_excluded }}
 NOT = {{ exists = leader }}
 exists = owner
 fleet_size <= owner.trigger:command_limit
 qol_sort_available = yes
 qol_sort_owned = yes
}}

# qol_sort_design is captured from one ship, then EVERY ship must match it.
qol_sort_same_design = {{
 exists = event_target:qol_sort_design
 NOT = {{
  any_owned_ship = {{
   NOT = {{ design = {{ is_same_value = event_target:qol_sort_design }} }}
  }}
 }}
}}

qol_sort_same_set_as_source = {{ {same_set('event_target:qol_sort_source')} }}
qol_sort_same_set_as_assignment = {{
 {same_set('event_target:qol_sort_assignment@this', 'event_target:qol_sort_assignment@prev')}
}}
qol_sort_same_set_as_from = {{ {same_set('from')} }}

# Conservative preview snapshot: changed membership or designs require refresh.
qol_sort_snapshot_valid = {{
 num_ships = qol_sort_snapshot_count
 NOT = {{ any_owned_ship = {{
  OR = {{
   NOT = {{ exists = event_target:qol_sort_snapshot_design@this }}
   NOT = {{ design = {{ is_same_value = event_target:qol_sort_snapshot_design@prev }} }}
  }}
 }} }}
}}

qol_sort_valid_target = {{
 has_fleet_flag = qol_sort_plan_target
 NOT = {{ exists = leader }}
 NOT = {{ has_fleet_flag = qol_sort_protected }}
 NOT = {{ has_fleet_flag = qol_sort_excluded }}
 qol_sort_available = yes
 qol_sort_owned = yes
}}

# Outstanding receivers are destinations only; explicitly released receivers
# participate in the later planning pass and may become regrouping sources.
qol_sort_receiver = {{
 has_fleet_flag = qol_sort_auto_protected
 NOT = {{ has_fleet_flag = qol_sort_regroup_ready }}
 is_variable_set = qol_sort_reserved_total
 NOT = {{ has_fleet_flag = qol_sort_protected }}
 NOT = {{ has_fleet_flag = qol_sort_excluded }}
 NOT = {{ exists = leader }}
 exists = owner
 fleet_size < owner.trigger:command_limit
 check_variable = {{ which = qol_sort_reserved_total value < owner.trigger:command_limit }}
 qol_sort_available = yes
 qol_sort_owned = yes
}}
""")


def build_effects():
    write("common/scripted_effects/qol_fleet_sort.txt", f"""
# Country scope. Only preview metadata is reset, never persistent protection.
qol_sort_clear_plan = {{
 every_owned_fleet = {{
  remove_fleet_flag = qol_sort_plan_source
  remove_fleet_flag = qol_sort_plan_target
  remove_fleet_flag = qol_sort_group_seen
  remove_fleet_flag = qol_sort_mixed_plan
  remove_fleet_flag = qol_sort_set_representative
  remove_fleet_flag = qol_sort_seed_receiver
  clear_variable = qol_sort_room
  clear_variable = qol_sort_commit_room
  clear_variable = qol_sort_planned_size
  clear_variable = qol_sort_design_index
  clear_variable = qol_sort_snapshot_count
 }}
}}

# Single-design fast path keeps three fleet passes. Mixed fleets additionally
# search preview representatives, bounded by BATCH, comparing actual ship sets.
# No timers. Whole fleets use next-fit packing.
qol_sort_preview = {{
 qol_sort_clear_plan = yes
 set_variable = {{ which = qol_sort_limit value = trigger:command_limit }}
 set_variable = {{ which = qol_sort_candidates value = 0 }}
 set_variable = {{ which = qol_sort_ships value = 0 }}
 set_variable = {{ which = qol_sort_designs value = 0 }}
 set_variable = {{ which = qol_sort_bins value = 0 }}
 set_variable = {{ which = qol_sort_requests value = 0 }}
 set_variable = {{ which = qol_sort_deferred value = 0 }}
 set_variable = {{ which = qol_sort_mixed value = 0 }}
 set_variable = {{ which = qol_sort_group_offset value = 0 }}
 set_variable = {{ which = qol_sort_group_page value = 1 }}
 # Seed one reusable receiver per exact design before considering small sources.
 # Reservations are a conservative high-water mark: arriving ships must not be
 # counted twice, and cancelled orders never silently release capacity.
 every_owned_fleet = {{
  limit = {{ qol_sort_receiver = yes }}
  random_owned_ship = {{ design = {{ save_event_target_as = qol_sort_design }} }}
  if = {{
   limit = {{
    qol_sort_same_design = yes
    root = {{ check_variable = {{ which = qol_sort_candidates value < {BATCH} }} }}
    NAND = {{
     exists = event_target:qol_sort_bucket@event_target:qol_sort_design
     event_target:qol_sort_bucket@event_target:qol_sort_design = {{ has_fleet_flag = qol_sort_plan_target }}
    }}
   }}
   root = {{
    change_variable = {{ which = qol_sort_candidates value = 1 }}
    change_variable = {{ which = qol_sort_ships value = prev.trigger:num_ships }}
    change_variable = {{ which = qol_sort_designs value = 1 }}
    change_variable = {{ which = qol_sort_bins value = 1 }}
   }}
   set_variable = {{ which = qol_sort_design_index value = root.qol_sort_designs }}
   set_fleet_flag = qol_sort_plan_target
   qol_sort_init_room = yes
   save_event_target_as = qol_sort_bucket@event_target:qol_sort_design
  }}
  else = {{
   if = {{ limit = {{ qol_sort_same_design = no }}
    set_fleet_flag = qol_sort_seed_receiver
    qol_sort_plan_mixed = yes
    remove_fleet_flag = qol_sort_seed_receiver
   }}
  }}
 }}
 every_owned_fleet = {{
  limit = {{ qol_sort_candidate = yes }}
  random_owned_ship = {{ design = {{ save_event_target_as = qol_sort_design }} }}
  if = {{
   limit = {{ qol_sort_same_design = yes }}
   if = {{
    limit = {{ root = {{ check_variable = {{ which = qol_sort_candidates value < {BATCH} }} }} }}
    root = {{
     change_variable = {{ which = qol_sort_candidates value = 1 }}
     change_variable = {{ which = qol_sort_ships value = prev.trigger:num_ships }}
    }}
    save_event_target_as = qol_sort_source
    event_target:qol_sort_design = {{ save_event_target_as = qol_sort_planned_design@event_target:qol_sort_source }}
    set_variable = {{ which = qol_sort_planned_size value = trigger:fleet_size }}
    # Check whether this design already has a bin in THIS preview. Old event
    # targets inherited from a previous preview have no plan flag after reset.
    if = {{
     limit = {{
      NAND = {{
       exists = event_target:qol_sort_bucket@event_target:qol_sort_design
       event_target:qol_sort_bucket@event_target:qol_sort_design = {{ has_fleet_flag = qol_sort_plan_target }}
      }}
     }}
     root = {{ change_variable = {{ which = qol_sort_designs value = 1 }} }}
     set_variable = {{ which = qol_sort_design_index value = root.qol_sort_designs }}
    }}
    else = {{
     event_target:qol_sort_bucket@event_target:qol_sort_design = {{
      event_target:qol_sort_source = {{ set_variable = {{ which = qol_sort_design_index value = prev.qol_sort_design_index }} }}
     }}
    }}
    if = {{
     limit = {{
      exists = event_target:qol_sort_bucket@event_target:qol_sort_design
      event_target:qol_sort_bucket@event_target:qol_sort_design = {{
       has_fleet_flag = qol_sort_plan_target
       check_variable = {{ which = qol_sort_room value >= prev.trigger:fleet_size }}
      }}
     }}
     set_fleet_flag = qol_sort_plan_source
     event_target:qol_sort_bucket@event_target:qol_sort_design = {{
      subtract_variable = {{ which = qol_sort_room value = prev.trigger:fleet_size }}
      save_event_target_as = qol_sort_assignment@event_target:qol_sort_source
     }}
     root = {{ change_variable = {{ which = qol_sort_requests value = 1 }} }}
    }}
    else = {{
     set_fleet_flag = qol_sort_plan_target
     qol_sort_init_room = yes
     save_event_target_as = qol_sort_bucket@event_target:qol_sort_design
     root = {{ change_variable = {{ which = qol_sort_bins value = 1 }} }}
    }}
   }}
   else = {{ root = {{ change_variable = {{ which = qol_sort_deferred value = 1 }} }} }}
  }}
  else = {{ qol_sort_plan_mixed = yes }}
 }}
 log = "QOL_SORT PREVIEW version=0.2.4 limit=[This.qol_sort_limit] candidates=[This.qol_sort_candidates] designs=[This.qol_sort_designs] bins=[This.qol_sort_bins] requests=[This.qol_sort_requests] deferred=[This.qol_sort_deferred]"
}}

# Fleet scope. Keep one representative and a current next-fit bucket per set.
qol_sort_plan_mixed = {{
 if = {{
  limit = {{ root = {{ check_variable = {{ which = qol_sort_candidates value < {BATCH} }} }} }}
  save_event_target_as = qol_sort_source
  set_variable = {{ which = qol_sort_set_found value = 0 }}
  root = {{ ordered_owned_fleet = {{
   limit = {{ has_fleet_flag = qol_sort_set_representative qol_sort_same_set_as_source = yes }}
   order_by = qol_sort_design_index
   position = 0
   save_event_target_as = qol_sort_set_group
   event_target:qol_sort_source = {{
    set_variable = {{ which = qol_sort_set_found value = 1 }}
    set_variable = {{ which = qol_sort_design_index value = prev.qol_sort_design_index }}
   }}
  }} }}
  # An unreleased receiver can seed a group, but must never become a source.
  if = {{ limit = {{ NAND = {{ has_fleet_flag = qol_sort_seed_receiver check_variable = {{ which = qol_sort_set_found value = 1 }} }} }}
   root = {{
    change_variable = {{ which = qol_sort_candidates value = 1 }}
    change_variable = {{ which = qol_sort_ships value = prev.trigger:num_ships }}
    change_variable = {{ which = qol_sort_mixed value = 1 }}
   }}
   set_fleet_flag = qol_sort_mixed_plan
   set_variable = {{ which = qol_sort_planned_size value = trigger:fleet_size }}
   qol_sort_snapshot = yes
   if = {{ limit = {{ check_variable = {{ which = qol_sort_set_found value = 0 }} }}
    root = {{ change_variable = {{ which = qol_sort_designs value = 1 }} }}
    set_variable = {{ which = qol_sort_design_index value = root.qol_sort_designs }}
    set_fleet_flag = qol_sort_set_representative
    save_event_target_as = qol_sort_set_group
   }}
   if = {{ limit = {{
    check_variable = {{ which = qol_sort_set_found value = 1 }}
    exists = event_target:qol_sort_set_bucket@event_target:qol_sort_set_group
    event_target:qol_sort_set_bucket@event_target:qol_sort_set_group = {{
     check_variable = {{ which = qol_sort_room value >= prev.trigger:fleet_size }}
    }}
   }}
    set_fleet_flag = qol_sort_plan_source
    event_target:qol_sort_set_bucket@event_target:qol_sort_set_group = {{
     subtract_variable = {{ which = qol_sort_room value = prev.trigger:fleet_size }}
     save_event_target_as = qol_sort_assignment@event_target:qol_sort_source
    }}
    root = {{ change_variable = {{ which = qol_sort_requests value = 1 }} }}
   }}
   else = {{
    set_fleet_flag = qol_sort_plan_target
    qol_sort_init_room = yes
    save_event_target_as = qol_sort_set_bucket@event_target:qol_sort_set_group
    root = {{ change_variable = {{ which = qol_sort_bins value = 1 }} }}
   }}
  }}
 }}
 else = {{
  if = {{ limit = {{ NOT = {{ has_fleet_flag = qol_sort_seed_receiver }} }}
   root = {{ change_variable = {{ which = qol_sort_deferred value = 1 }} }}
  }}
 }}
}}

qol_sort_snapshot = {{
 set_variable = {{ which = qol_sort_snapshot_count value = trigger:num_ships }}
 every_owned_ship = {{
  save_event_target_as = qol_sort_snapshot_ship
  design = {{ save_event_target_as = qol_sort_snapshot_design@event_target:qol_sort_snapshot_ship }}
 }}
}}

qol_sort_commit = {{
 set_variable = {{ which = qol_sort_issued value = 0 }}
 set_variable = {{ which = qol_sort_skipped value = 0 }}
 # Reserve against current target size and current country command limit.
 every_owned_fleet = {{
  limit = {{ has_fleet_flag = qol_sort_plan_target }}
  set_variable = {{ which = qol_sort_commit_room value = owner.trigger:command_limit }}
  subtract_variable = {{ which = qol_sort_commit_room value = trigger:fleet_size }}
  if = {{
   limit = {{ check_variable = {{ which = qol_sort_reserved_total value > trigger:fleet_size }} }}
   set_variable = {{ which = qol_sort_commit_room value = owner.trigger:command_limit }}
   subtract_variable = {{ which = qol_sort_commit_room value = qol_sort_reserved_total }}
  }}
 }}
 every_owned_fleet = {{
  limit = {{ has_fleet_flag = qol_sort_plan_source }}
  if = {{
   limit = {{
    qol_sort_candidate = yes
    fleet_size = qol_sort_planned_size
    exists = event_target:qol_sort_assignment@this
    OR = {{
     AND = {{ has_fleet_flag = qol_sort_mixed_plan qol_sort_snapshot_valid = yes }}
     AND = {{ NOT = {{ has_fleet_flag = qol_sort_mixed_plan }} exists = event_target:qol_sort_planned_design@this }}
    }}
   }}
   if = {{ limit = {{ NOT = {{ has_fleet_flag = qol_sort_mixed_plan }} }}
    event_target:qol_sort_planned_design@this = {{ save_event_target_as = qol_sort_design }}
   }}
   event_target:qol_sort_assignment@this = {{ save_event_target_as = qol_sort_destination }}
   if = {{
    limit = {{
     OR = {{
      AND = {{ has_fleet_flag = qol_sort_mixed_plan qol_sort_same_set_as_assignment = yes }}
      AND = {{ NOT = {{ has_fleet_flag = qol_sort_mixed_plan }} qol_sort_same_design = yes }}
     }}
     # Use the already-saved mapping in conditions. UI effect inspection can
     # evaluate limits without running the save_event_target_as effects above.
     event_target:qol_sort_assignment@this = {{
      qol_sort_valid_target = yes
      OR = {{
       AND = {{ has_fleet_flag = qol_sort_mixed_plan qol_sort_snapshot_valid = yes }}
       AND = {{ NOT = {{ has_fleet_flag = qol_sort_mixed_plan }} qol_sort_same_design = yes }}
      }}
      is_owned_by = root
      is_controlled_by = root
      check_variable = {{ which = qol_sort_commit_room value >= prev.trigger:fleet_size }}
     }}
    }}
    event_target:qol_sort_destination = {{ subtract_variable = {{ which = qol_sort_commit_room value = prev.trigger:fleet_size }} }}
    # A new incoming request revokes permission to move this receiver.
    event_target:qol_sort_destination = {{
     set_fleet_flag = qol_sort_auto_protected
     remove_fleet_flag = qol_sort_regroup_ready
    }}
    event_target:qol_sort_destination = {{
     set_variable = {{ which = qol_sort_reserved_total value = owner.trigger:command_limit }}
     subtract_variable = {{ which = qol_sort_reserved_total value = qol_sort_commit_room }}
    }}
    fleet_event = {{ id = {NS}.20 scopes = {{ from = event_target:qol_sort_destination }} }}
    root = {{ change_variable = {{ which = qol_sort_issued value = 1 }} }}
   }}
   else = {{ root = {{ change_variable = {{ which = qol_sort_skipped value = 1 }} }} }}
  }}
  else = {{ root = {{ change_variable = {{ which = qol_sort_skipped value = 1 }} }} }}
 }}
 log = "QOL_SORT COMMIT version=0.2.4 issued=[This.qol_sort_issued] skipped=[This.qol_sort_skipped]"
 qol_sort_clear_plan = yes
}}

qol_sort_init_room = {{
 set_variable = {{ which = qol_sort_room value = owner.trigger:command_limit }}
 subtract_variable = {{ which = qol_sort_room value = trigger:fleet_size }}
 if = {{
  limit = {{ check_variable = {{ which = qol_sort_reserved_total value > trigger:fleet_size }} }}
  set_variable = {{ which = qol_sort_room value = owner.trigger:command_limit }}
  subtract_variable = {{ which = qol_sort_room value = qol_sort_reserved_total }}
 }}
}}

# Manual recovery only: no timer or assumption that an order has completed.
qol_sort_release_reservations = {{
 every_owned_fleet = {{
  limit = {{ has_fleet_flag = qol_sort_auto_protected }}
  set_variable = {{ which = qol_sort_reserved_total value = trigger:fleet_size }}
  set_fleet_flag = qol_sort_regroup_ready
 }}
 qol_sort_clear_plan = yes
}}

qol_sort_roster_clamp = {{
 # Normalize saved four-entry-page offsets when upgrading to eight entries.
 divide_variable = {{ which = qol_sort_roster_offset value = {PAGE} }}
 floor_variable = qol_sort_roster_offset
 multiply_variable = {{ which = qol_sort_roster_offset value = {PAGE} }}
 if = {{
  limit = {{ check_variable = {{ which = qol_sort_roster_offset value < 0 }} }}
  set_variable = {{ which = qol_sort_roster_offset value = 0 }}
 }}
 if = {{
  limit = {{ check_variable = {{ which = qol_sort_roster_total value <= 0 }} }}
  set_variable = {{ which = qol_sort_roster_offset value = 0 }}
 }}
 else = {{
  if = {{
   limit = {{ check_variable = {{ which = qol_sort_roster_offset value >= qol_sort_roster_total }} }}
   set_variable = {{ which = qol_sort_roster_offset value = qol_sort_roster_total }}
   change_variable = {{ which = qol_sort_roster_offset value = -1 }}
   divide_variable = {{ which = qol_sort_roster_offset value = {PAGE} }}
   floor_variable = qol_sort_roster_offset
   multiply_variable = {{ which = qol_sort_roster_offset value = {PAGE} }}
  }}
 }}
 set_variable = {{ which = qol_sort_roster_page value = qol_sort_roster_offset }}
 divide_variable = {{ which = qol_sort_roster_page value = {PAGE} }}
 change_variable = {{ which = qol_sort_roster_page value = 1 }}
}}
""")


def build_events():
    text = f"namespace = {NS}\n"
    text += event(1, "menu", """
 immediate = {
  qol_sort_clear_plan = yes
  every_owned_fleet = { remove_fleet_flag = qol_sort_excluded remove_fleet_flag = qol_sort_roster_seen }
 }
""" + option("preview", f"qol_sort_preview = yes country_event = {{ id = {NS}.2 }}", tooltip="preview.tt")
        + option("protection", f"country_event = {{ id = {NS}.9 }}")
        + option("protect_all", f"country_event = {{ id = {NS}.11 }}", tooltip="protect_all.tt")
        + option("unprotect_all", f"country_event = {{ id = {NS}.13 }}")
        + option("release", f"country_event = {{ id = {NS}.12 }}")
        + option("close"))
    text += event(2, "preview", option("execute", f"qol_sort_commit = yes country_event = {{ id = {NS}.4 }}",
        "check_variable = { which = qol_sort_requests value > 0 }", "execute.tt")
        + option("groups", f"country_event = {{ id = {NS}.3 }}")
        + option("refresh", f"qol_sort_preview = yes country_event = {{ id = {NS}.2 }}")
        + option("reset_exclusions", f"every_owned_fleet = {{ remove_fleet_flag = qol_sort_excluded }} qol_sort_preview = yes country_event = {{ id = {NS}.2 }}")
        + option("back", f"country_event = {{ id = {NS}.1 }}")
        + option("cancel", "qol_sort_clear_plan = yes"))
    text += event(4, "result", option("preview_next", f"qol_sort_preview = yes country_event = {{ id = {NS}.2 }}", tooltip="preview_next.tt")
        + option("back", f"country_event = {{ id = {NS}.1 }}") + option("close"))
    text += event(11, "protect_all", option("protect_all.confirm", f"every_owned_fleet = {{ set_fleet_flag = qol_sort_protected }} country_event = {{ id = {NS}.1 }}")
        + option("cancel", f"country_event = {{ id = {NS}.1 }}"))
    text += event(12, "release", option("release.confirm", f"qol_sort_release_reservations = yes country_event = {{ id = {NS}.1 }}")
        + option("cancel", f"country_event = {{ id = {NS}.1 }}"))
    text += event(13, "unprotect_all", option("unprotect_all.confirm", f"every_owned_fleet = {{ remove_fleet_flag = qol_sort_protected }} country_event = {{ id = {NS}.1 }}")
        + option("cancel", f"country_event = {{ id = {NS}.1 }}"))

    # Assign a stable snapshot index once, not 'seen' flags that change when a
    # toggle reopens the screen. Explicit refresh rebuilds this snapshot.
    text += event(9, "", f""" immediate = {{
 set_variable = {{ which = qol_sort_roster_total value = 0 }}
 if = {{
  limit = {{ NOT = {{ is_variable_set = qol_sort_roster_offset }} }}
  set_variable = {{ which = qol_sort_roster_offset value = 0 }}
 }}
 every_owned_fleet = {{
  clear_variable = qol_sort_roster_index
  if = {{
   limit = {{
    qol_sort_owned = yes
    OR = {{
     root = {{ NOT = {{ has_country_flag = qol_sort_roster_protected_only }} }}
     has_fleet_flag = qol_sort_protected
    }}
   }}
   set_variable = {{ which = qol_sort_roster_index value = root.qol_sort_roster_total }}
   root = {{ change_variable = {{ which = qol_sort_roster_total value = 1 }} }}
  }}
 }}
 qol_sort_roster_clamp = yes
 country_event = {{ id = {NS}.10 }}
}}
""", hidden=True)

    def navigation(number, prefix, total):
        last = f"set_variable = {{ which = qol_sort_{prefix}_page value = {total} }} change_variable = {{ which = qol_sort_{prefix}_page value = -1 }} divide_variable = {{ which = qol_sort_{prefix}_page value = {PAGE} }} floor_variable = qol_sort_{prefix}_page set_variable = {{ which = qol_sort_{prefix}_offset value = qol_sort_{prefix}_page }} multiply_variable = {{ which = qol_sort_{prefix}_offset value = {PAGE} }} change_variable = {{ which = qol_sort_{prefix}_page value = 1 }} country_event = {{ id = {NS}.{number} }}"
        return (option("page_home", f"set_variable = {{ which = qol_sort_{prefix}_offset value = 0 }} set_variable = {{ which = qol_sort_{prefix}_page value = 1 }} country_event = {{ id = {NS}.{number} }}", f"check_variable = {{ which = qol_sort_{prefix}_offset value > 0 }}")
            + option("previous", f"change_variable = {{ which = qol_sort_{prefix}_offset value = -{PAGE} }} change_variable = {{ which = qol_sort_{prefix}_page value = -1 }} country_event = {{ id = {NS}.{number} }}",
            f"check_variable = {{ which = qol_sort_{prefix}_offset value >= {PAGE} }}")
            + option("next", f"change_variable = {{ which = qol_sort_{prefix}_offset value = {PAGE} }} change_variable = {{ which = qol_sort_{prefix}_page value = 1 }} country_event = {{ id = {NS}.{number} }}",
            f"check_variable_arithmetic = {{ which = qol_sort_{prefix}_offset add = {PAGE} value < {total} }}")
            + option("page_end", last, f"check_variable_arithmetic = {{ which = qol_sort_{prefix}_offset add = {PAGE} value < {total} }}"))

    clear_slots = " ".join(f"remove_fleet_flag = qol_sort_slot_{i}" for i in range(1, PAGE+1))
    body = f" immediate = {{ every_owned_fleet = {{ {clear_slots} }}\n"
    for i in range(1, PAGE+1):
        body += f"""
 set_variable = {{ which = qol_sort_roster_position value = qol_sort_roster_offset }}
 change_variable = {{ which = qol_sort_roster_position value = {i-1} }}
 ordered_owned_fleet = {{
  limit = {{
   qol_sort_owned = yes
   is_variable_set = qol_sort_roster_index
   check_variable = {{ which = qol_sort_roster_index value = root.qol_sort_roster_position }}
  }}
  order_by = qol_sort_roster_index
  position = 0
  set_fleet_flag = qol_sort_slot_{i}
  save_event_target_as = qol_sort_slot_{i}
 }}
"""
    body += " }\n"
    for i in range(1, PAGE+1):
        target = f"event_target:qol_sort_slot_{i}"
        for protected in (False, True):
            flag = "has_fleet_flag = qol_sort_protected" if protected else "NOT = { has_fleet_flag = qol_sort_protected }"
            key = "unprotect" if protected else "protect"
            valid = f"exists = {target} {target} = {{ is_owned_by = root has_fleet_flag = qol_sort_slot_{i} {flag} }}"
            mutation = "remove_fleet_flag = qol_sort_protected" if protected else "set_fleet_flag = qol_sort_protected"
            effect = f"{target} = {{ {mutation} }} if = {{ limit = {{ has_country_flag = qol_sort_roster_protected_only }} country_event = {{ id = {NS}.9 }} }} else = {{ country_event = {{ id = {NS}.10 }} }}"
            body += option(f"{key}.{i}", effect, valid)
    body += navigation(10, "roster", "qol_sort_roster_total")
    body += option("protected_only", f"set_country_flag = qol_sort_roster_protected_only set_variable = {{ which = qol_sort_roster_offset value = 0 }} country_event = {{ id = {NS}.9 }}", "NOT = { has_country_flag = qol_sort_roster_protected_only }")
    body += option("show_all", f"remove_country_flag = qol_sort_roster_protected_only set_variable = {{ which = qol_sort_roster_offset value = 0 }} country_event = {{ id = {NS}.9 }}", "has_country_flag = qol_sort_roster_protected_only")
    body += option("refresh_roster", f"country_event = {{ id = {NS}.9 }}")
    body += option("back", f"country_event = {{ id = {NS}.1 }}")
    body += option("close", "qol_sort_clear_plan = yes")
    text += event(10, "protection", body)

    clear_groups = " ".join(f"remove_fleet_flag = qol_sort_group_slot_{i}" for i in range(1,PAGE+1))
    body = f" immediate = {{ every_owned_fleet = {{ {clear_groups} }}\n"
    for i in range(1, PAGE+1):
        body += f"""
 set_variable = {{ which = qol_sort_group_position value = qol_sort_group_offset }}
 change_variable = {{ which = qol_sort_group_position value = {i} }}
 ordered_owned_fleet = {{
  limit = {{
   has_fleet_flag = qol_sort_plan_target
   check_variable = {{ which = qol_sort_design_index value = root.qol_sort_group_position }}
  }}
  order_by = trigger:fleet_size
  position = 0
  set_fleet_flag = qol_sort_group_slot_{i}
  save_event_target_as = qol_sort_group_{i}
  random_owned_ship = {{
   save_event_target_as = qol_sort_group_ship_{i}
   design = {{ save_event_target_as = qol_sort_design save_event_target_as = qol_sort_design_{i} }}
  }}
 }}
"""
    body += " }\n"
    for i in range(1, PAGE+1):
        valid = f"exists = event_target:qol_sort_group_{i} exists = event_target:qol_sort_group_ship_{i} event_target:qol_sort_group_{i} = {{ is_owned_by = root has_fleet_flag = qol_sort_group_slot_{i} }}"
        effects = f"""
every_owned_fleet = {{
 limit = {{
  OR = {{ has_fleet_flag = qol_sort_plan_source has_fleet_flag = qol_sort_plan_target }}
  check_variable = {{ which = qol_sort_design_index value = root.qol_sort_group_position }}
 }}
 set_fleet_flag = qol_sort_excluded
}}
qol_sort_preview = yes
country_event = {{ id = {NS}.2 }}
"""
        # Each button must retain its own group index; group_position is reused
        # while rendering the other seven slots.
        effects = f"event_target:qol_sort_group_{i} = {{ root = {{ set_variable = {{ which = qol_sort_group_position value = prev.qol_sort_design_index }} }} }}\n" + effects
        body += option(f"exclude.{i}", effects, valid)
    body += navigation(3, "group", "qol_sort_designs")
    body += option("back_preview", f"country_event = {{ id = {NS}.2 }}")
    body += option("cancel", "qol_sort_clear_plan = yes")
    text += event(3, "groups", body)

    # Immediate one-shot dispatch; no retries, delayed events or background scan.
    # The native merge action must be verified in game, including cross-system
    # pathfinding and scope preservation. Report 'issued', never 'merged'.
    text += f"""
fleet_event = {{
 id = {NS}.20
 hide_window = yes
 is_triggered_only = yes
 trigger = {{ exists = owner owner = {{ is_ai = no }} }}
 immediate = {{
  if = {{
   limit = {{
    qol_sort_candidate = yes
    exists = from
    qol_sort_same_set_as_from = yes
    from = {{
     qol_sort_owned = yes
     is_owned_by = root.owner
     is_controlled_by = root.owner
     is_in_combat = no
     qol_sort_available = yes
     NOT = {{ exists = leader }}
     NOT = {{ has_fleet_flag = qol_sort_protected }}
    }}
   }}
   from = {{ save_event_target_as = qol_sort_execution_destination }}
   log = "QOL_SORT ORDER source=[This.GetName] destination=[From.GetName]"
   # Replace source navigation only after confirmation. Receiver keeps moving.
   clear_orders = yes
   queue_actions = {{
    # 4.5.2 block target handling also reads the scope token as a boolean.
    # The scalar constructor supplies the target and defaults allow_ftl to yes.
    # Native execution and cross-system travel still need in-game checking.
    merge_fleet = event_target:qol_sort_execution_destination
   }}
  }}
  else = {{
   log = "QOL_SORT DISPATCH_REJECT source=[This.GetName] reason=source_target_state_or_design_set"
  }}
 }}
}}
"""
    write("events/qol_fleet_sort.txt", text)


def build_localisation():
    loc = {
        "edict_qol_fleet_sort": "散舰整理工具（试验）",
        "edict_qol_fleet_sort_desc": "按需预览并整理零散舰队。平时没有定时扫描，也不追踪补员。",
        f"{NS}.menu.title": "散舰整理工具 · 0.2.4",
        f"{NS}.menu.desc": "批量整理所有符合条件、未手动保护的军事舰队，不限舰船数量，无需逐页挑选散舰。按完全相同的设计集合、当前指挥上限规划整队合并；每种设计数量可以不同。\\n\\n单一设计与混编分别按设计集合分组，只做整队合并，不拆船；想保留的例外请手动保护。交战、有领袖、正常补员合并、维修升级、租借等不适合整理的舰队仍跳过。\\n\\n确认才替换来源的普通移动命令；接收队保留原有移动。每批最多256支，更多候选可预览下一批。没有后台扫描。",
        f"{NS}.release": "归队已全部结束：释放旧容量预留",
        f"{NS}.release.title": "确认所有归队都已结束",
        f"{NS}.release.desc": "仅在本工具安排的归队已全部完成或取消后使用。此操作将接收队的预留重设为实际舰队规模，允许旧接收队重新参与批量合并。仅停止接收队、不确认在途舰船是否归队，不代表可以释放。\\n\\n接收新请求的目标会再次限制为只能接收，避免重复编走。玩家手动保护仍有效；普通未保护的舰队无需执行这一步即可参与。",
        f"{NS}.release.confirm": "归队已全部完成或取消，释放预留",
        f"{NS}.preview": "扫描并预览本批散舰",
        f"{NS}.preview.tt": "点击后批量扫描全部符合条件的舰队，不限数量大小，不必进入保护名单逐队选择。每批最多256支；只保护想保留的例外即可。",
        f"{NS}.protection": "保护名单：添加或解除舰队保护",
        f"{NS}.protect_all": "将当前所有舰队加入保护名单",
        f"{NS}.protect_all.tt": "适合事故发生前做一次保护。若事故已发生，请先逐个保护需要保留的小队；保护全部也会排除当前散舰。",
        f"{NS}.protect_all.title": "保护当前所有舰队？",
        f"{NS}.protect_all.desc": "此操作会保护你现在拥有的全部舰队，包括已经散落的小队。以后整理会跳过它们。\\n\\n适合在事故发生前使用；如果已经有大量散舰，请返回，只保护想保留的小队。",
        f"{NS}.protect_all.confirm": "确认：保护当前全部舰队",
        f"{NS}.unprotect_all": "一键取消全部手动保护",
        f"{NS}.unprotect_all.title": "取消全部手动保护？",
        f"{NS}.unprotect_all.desc": "清除当前全部自有舰队的手动保护，包括逐支添加和“保护当前全部舰队”设置的保护。符合条件的舰队会重新参与批量整理，不限数量大小。\\n\\n接收队身份、在途容量预留和现有舰队命令仍保留。返回后可重新保护需要保留的少数例外。",
        f"{NS}.unprotect_all.confirm": "确认：取消全部手动保护",
        f"{NS}.preview.title": "批量整理预览 · 0.2.4",
        f"{NS}.preview.desc": "本次读取的国家指挥上限：§H[Root.qol_sort_limit]§!\\n本批参与：§H[Root.qol_sort_candidates]§!支，共§H[Root.qol_sort_ships]§!艘\\n设计集合组数：§H[Root.qol_sort_designs]§!\\n预计保留编队：§H[Root.qol_sort_bins]§!支\\n计划合并请求：§H[Root.qol_sort_requests]§!条\\n留待下一批：§H[Root.qol_sort_deferred]§!支\\n其中参与的混编舰队：§H[Root.qol_sort_mixed]§!支\\n\\n不限制舰船数量，按完全相同的设计集合将整支舰队装入；放不下就另开一队，不拆船，不保证恰好满编。无需逐页选择散舰；手动保护及本次排除的设计保持不动。\\n\\n在途舰船持续预留容量。交战、有领袖、正常补员合并和维修升级等会跳过。混编组成在预览后变化时须重新预览。确认前再次校验；本页仅为计划，不代表合并成功。",
        f"{NS}.execute": "确认：下达本批合并命令",
        f"{NS}.execute.tt": "替换来源小队的普通移动命令并尝试合并，接收队保留原有移动。跨星系需要正常航行，路径与合并限制由游戏决定。不传送、不复制、不删除舰船。",
        f"{NS}.groups": "查看分组／整组排除",
        f"{NS}.refresh": "重新计算本批预览",
        f"{NS}.reset_exclusions": "清除本次排除，重新预览",
        f"{NS}.cancel": "取消（不发出命令）",
        f"{NS}.result.title": "本批命令已尝试下达",
        f"{NS}.result.desc": "已尝试下达：§H[Root.qol_sort_issued]§!条\\n因状态变化等原因跳过：§H[Root.qol_sort_skipped]§!支\\n\\n此数量不是实际合并成功数。舰队会按游戏原版命令行动；路径、战斗或原版限制可能阻止合并。已发出的命令可在原版舰队界面取消。\\n\\n下一批会跳过正在合并的来源；此前接收队可继续接收，计算容量时保留此前请求的预留。请求失败或取消后，须在确认所有归队已结束后，从首页释放容量预留。",
        f"{NS}.preview_next": "预览下一批",
        f"{NS}.preview_next.tt": "再次按需扫描；不会自动持续处理。",
        f"{NS}.protection.title": "保护名单：自有军事舰队",
        f"{NS}.protection.desc": "当前第§H[Root.qol_sort_roster_page]§!页，名单共§H[Root.qol_sort_roster_total]§!支，每页八支。切换保护状态保留当前页；新建或销毁舰队后可刷新，返回重进会记住当前页。可切换只看已手动保护舰队；切换筛选回第一页。\\n\\n这里只设置少数要保留的例外，无需逐页选择待整理舰队。取消保护后，普通舰队不限数量大小即可参加扫描；混编按完全相同的设计集合整队合并。\\n\\n接收队身份和在途容量预留会保留。先返回首页扫描、核对预览，再确认批量合并。",
        f"{NS}.groups.title": "设计集合分组（点击可排除整组）",
        f"{NS}.groups.desc": "当前第§H[Root.qol_sort_group_page]§!页，共§H[Root.qol_sort_designs]§!个设计集合组，每页最多八个。同集合的不同容量分队只显示一次，可前后翻页。\\n\\n按钮显示样本舰队名及其中一种设计；混编请结合样本舰队组成核对。点击将本批该设计集合组全部排除并重新计算，不影响共享某种设计的其他集合组。取消排除可返回预览使用“清除本次排除”。",
        f"{NS}.previous": "上一页",
        f"{NS}.page_home": "跳到首页",
        f"{NS}.page_end": "跳到末页",
        f"{NS}.protected_only": "只看已手动保护舰队",
        f"{NS}.show_all": "查看全部舰队",
        f"{NS}.refresh_roster": "刷新名单",
        f"{NS}.next": "下一页",
        f"{NS}.back": "返回工具首页",
        f"{NS}.back_preview": "返回本批预览",
        f"{NS}.close": "关闭",
    }
    for i in range(1, PAGE+1):
        loc[f"{NS}.protect.{i}"] = f"加入保护：[qol_sort_slot_{i}.GetName]"
        loc[f"{NS}.unprotect.{i}"] = f"解除保护：[qol_sort_slot_{i}.GetName]"
        loc[f"{NS}.exclude.{i}"] = f"排除样本：[qol_sort_group_{i}.GetName] / [qol_sort_group_ship_{i}.GetDesignName]（[qol_sort_group_ship_{i}.GetShipSizeName]）"
    write("localisation/simp_chinese/qol_fleet_sort_l_simp_chinese.yml", "l_simp_chinese:\n" + "\n".join(f' {k}:0 "{v}"' for k,v in loc.items()), bom=True)


def build_fixture():
    """Manual console-only fixture. Never referenced by the normal edict/menu."""
    sample = f""" immediate = {{
 remove_country_flag = qol_sort_fixture_sample
 remove_country_flag = qol_sort_fixture_second
 if = {{
  limit = {{ exists = capital_scope }}
  capital_scope = {{ star = {{ save_event_target_as = qol_sort_fixture_location }} }}
  random_owned_fleet = {{
   limit = {{ qol_sort_owned = yes }}
   random_owned_ship = {{ design = {{ save_event_target_as = qol_sort_fixture_design }} }}
   root = {{ set_country_flag = qol_sort_fixture_sample }}
  }}
 }}
 if = {{ limit = {{ has_country_flag = qol_sort_fixture_sample }}
  every_owned_fleet = {{
   limit = {{
    root = {{ NOT = {{ has_country_flag = qol_sort_fixture_second }} }}
    qol_sort_owned = yes
   }}
   random_owned_ship = {{
    limit = {{ NOT = {{ design = {{ is_same_value = event_target:qol_sort_fixture_design }} }} }}
    design = {{ save_event_target_as = qol_sort_fixture_design_b }}
    root = {{ set_country_flag = qol_sort_fixture_second }}
   }}
  }}
 }}
}}
"""
    ready = "has_country_flag = qol_sort_fixture_sample exists = event_target:qol_sort_fixture_design exists = event_target:qol_sort_fixture_location"
    text = "# Test-save fixture; enter explicitly with event qol_fleet_sort.50.\n"
    for i, count in enumerate((20, 100, 300, 600), 51):
        sample += option(f"fixture.spawn.{count}", f"country_event = {{ id = {NS}.{i} }}", ready)
        text += event(i, "", f""" immediate = {{
 set_variable = {{ which = qol_sort_fixture_created value = 0 }}
 if = {{
  limit = {{ {ready} }}
  change_variable = {{ which = qol_sort_fixture_batch value = 1 }}
  while = {{
   count = {count}
   create_fleet = {{
    name = "{NS}.fixture.fleet"
    effect = {{
     set_owner = root
     create_ship = {{ name = random design = event_target:qol_sort_fixture_design }}
     set_location = event_target:qol_sort_fixture_location
     set_fleet_flag = qol_sort_fixture
     set_variable = {{ which = qol_sort_fixture_batch value = root.qol_sort_fixture_batch }}
    }}
   }}
  }}
  every_owned_fleet = {{
   limit = {{
    has_fleet_flag = qol_sort_fixture
    check_variable = {{ which = qol_sort_fixture_batch value = root.qol_sort_fixture_batch }}
    num_ships = 1
   }}
   root = {{ change_variable = {{ which = qol_sort_fixture_created value = 1 }} }}
  }}
 }}
 remove_country_flag = qol_sort_fixture_sample
 log = "QOL_SORT FIXTURE requested={count} observed_single_ship_fleets=[This.qol_sort_fixture_created]"
 country_event = {{ id = {NS}.55 }}
}}
""", hidden=True)
    mixed_ready = ready + " has_country_flag = qol_sort_fixture_second exists = event_target:qol_sort_fixture_design_b"
    sample += option("fixture.mixed", f"country_event = {{ id = {NS}.56 }}", mixed_ready)
    matrix = ""
    for label, designs, protected in (
        ("ab", "ab", False), ("ba", "ba", False), ("aab", "aab", False),
        ("protected", "ab", True), ("a", "a", False), ("a", "a", False),
        ("b", "b", False), ("b", "b", False),
    ):
        ships = "\n".join(
            "create_ship = { name = random design = event_target:qol_sort_fixture_design" + ("_b" if d=="b" else "") + " }"
            for d in designs
        )
        matrix += f"""
 create_fleet = {{ name = "{NS}.fixture.mixed.{label}" effect = {{
  set_owner = root
  {ships}
  set_location = event_target:qol_sort_fixture_location
  set_fleet_flag = qol_sort_fixture
  set_variable = {{ which = qol_sort_fixture_batch value = root.qol_sort_fixture_batch }}
  {'set_fleet_flag = qol_sort_protected' if protected else ''}
 }} }}
"""
    text += event(56, "", f""" immediate = {{
 set_variable = {{ which = qol_sort_fixture_mixed_created value = 0 }}
 if = {{ limit = {{ {mixed_ready} }}
  change_variable = {{ which = qol_sort_fixture_batch value = 1 }}
  {matrix}
  every_owned_fleet = {{ limit = {{
   has_fleet_flag = qol_sort_fixture
   check_variable = {{ which = qol_sort_fixture_batch value = root.qol_sort_fixture_batch }}
  }}
   root = {{ change_variable = {{ which = qol_sort_fixture_mixed_created value = 1 }} }}
  }}
 }}
 remove_country_flag = qol_sort_fixture_sample
 remove_country_flag = qol_sort_fixture_second
 country_event = {{ id = {NS}.57 }}
}}
""", hidden=True)
    text += event(50, "fixture", sample + option("close"))
    text += event(55, "fixture_result", option("back", f"country_event = {{ id = {NS}.1 }}") + option("close"))
    text += event(57, "fixture_mixed_result", option("back", f"country_event = {{ id = {NS}.1 }}") + option("close"))
    write("events/qol_fleet_sort_test.txt", text)
    loc = {
        "fixture.title": "生成测试散舰（仅测试存档）",
        "fixture.desc": "数量按钮生成同一现有设计的一船舰队；另有8支混编／单设计对照组按钮，需要至少两种不同的现有军舰设计。全部出生在首都恒星旁。现有舰队不移动、不拆分；对照组中只有标注手动保护的AB自带保护。\\n\\n需要有首都和至少一支符合条件的常规军事舰队，否则不显示数量选项。生成会增加军力和维护费；请在测试存档使用，先保护现有舰队，结束后读取生成前的存档。",
        "fixture.fleet": "测试散舰",
        "fixture.mixed": "生成8支混编／单设计对照舰队（需要两种现有设计）",
        "fixture.mixed.ab": "混编测试 AB",
        "fixture.mixed.ba": "混编测试 BA",
        "fixture.mixed.aab": "混编测试 AAB",
        "fixture.mixed.protected": "混编测试 AB 手动保护",
        "fixture.mixed.a": "混编对照 A 单设计",
        "fixture.mixed.b": "混编对照 B 单设计",
        "fixture_mixed_result.title": "混编测试舰队生成检查",
        "fixture_mixed_result.desc": "本批实际读到：§H[Root.qol_sort_fixture_mixed_created]§!支舰队。应为AB、BA、AAB、已手动保护的AB，以及各两支单设计A和B，共8支。\\n\\nAB／BA／AAB应按容量整队归为同一设计集合；保护AB保持不动，单设计A和B各自成组。指挥上限足够且其他舰队已保护时，应为7支参与、3个集合组、4条请求。\\n\\n这是生成检查，不是合并成功数。推进时间检查舰船实际到达、设计和总数保持。",
        "fixture_result.title": "测试散舰生成检查",
        "fixture_result.desc": "本批实际读到的一船舰队：§H[Root.qol_sort_fixture_created]§!支。\\n\\n这只是生成结果，不是合并结果。返回整理工具扫描、预览、确认，再推进时间观察实际归队。超过256支时使用下一批，无需逐队选择。",
    }
    for count in (20, 100, 300, 600):
        loc[f"fixture.spawn.{count}"] = f"立即生成{count}支同设计散舰（每队1艘）"
    write("localisation/simp_chinese/qol_fleet_sort_test_l_simp_chinese.yml", "l_simp_chinese:\n" + "\n".join(f' {NS}.{k}:0 "{v}"' for k,v in loc.items()), bom=True)


def validate():
    paths = list(OUT.rglob("*.txt"))
    texts = [p.read_text(encoding="utf-8-sig") for p in paths]
    for text in texts:
        clean = re.sub(r'"[^"\n]*"|#[^\n]*', "", text)
        depth = 0
        for token in re.findall(r"[{}]", clean):
            depth += 1 if token == "{" else -1
            assert depth >= 0
        assert depth == 0
    text = "\n".join(t for p,t in zip(paths,texts) if p.name != "qol_fleet_sort_test.txt")
    events = (OUT / "events/qol_fleet_sort.txt").read_text(encoding="utf-8")
    fixture = (OUT / "events/qol_fleet_sort_test.txt").read_text(encoding="utf-8")
    assert not re.search(r"id = qol_fleet_sort\.5[0-9]\b", events), "Console fixture must stay outside ordinary menu"
    events += "\n" + fixture
    ids = re.findall(r"(?m)^ id = (qol_fleet_sort\.\d+)", events)
    assert len(ids) == len(set(ids))
    assert set(re.findall(r"id = (qol_fleet_sort\.\d+)", events)) <= set(ids)
    assert not (OUT / "common/on_actions").exists()
    assert not re.search(r"\bdays\s*=", events), "No delayed events"
    for forbidden in ("set_location", "create_ship", "destroy_fleet", "delete_fleet", "set_mia_return_delay"):
        assert not re.search(r"\b"+forbidden+r"\s*=", text)
    assert events.count("queue_actions =") == 1
    assert events.count("clear_orders = yes") == 1
    effects = (OUT / "common/scripted_effects/qol_fleet_sort.txt").read_text(encoding="utf-8")
    assert not re.search(r"\bprev\.prev\b", text), "Use native prevprev scope history, not chained prev switches"
    assert not re.search(r"(?<!\\)\[", effects)
    preview = effects.split("qol_sort_preview = {",1)[1].split("qol_sort_commit = {",1)[0]
    assert not any(k in preview for k in ("queue_actions", "fleet_event =", "clear_orders"))
    keys = set()
    for path in OUT.rglob("*.yml"):
        loc = path.read_bytes()
        assert loc.startswith(b"\xef\xbb\xbf") and not loc.startswith(b"\xef\xbb\xbf"*2)
        keys.update(re.findall(r"(?m)^\s*([^\s:#]+):0",loc.decode("utf-8-sig")))
    refs = set(re.findall(r'(?:name|title|desc|custom_tooltip)\s*=\s*"([^"]+)"',"\n".join(texts)))
    assert refs <= keys, refs-keys
    print("PASS: blocks, event links, localisation, no background hooks/timers, preview cannot issue orders")


def build():
    write("descriptor.mod", 'name="散舰整理工具（试验）"\nversion="0.2.4"\nsupported_version="4.5.*"')
    write("common/edicts/qol_fleet_sort.txt", f"""qol_fleet_sort = {{
 length = 1
 icon = "GFX_edict_type_policy"
 potential = {{ is_ai = no }}
 effect = {{ hidden_effect = {{ country_event = {{ id = {NS}.1 }} }} }}
 ai_weight = {{ weight = 0 }}
}}""")
    build_triggers()
    build_effects()
    build_events()
    build_localisation()
    build_fixture()
    launcher = OUT.parent / "scattered_fleet_organizer.mod"
    launcher.write_text((OUT / "descriptor.mod").read_text(encoding="utf-8")+f'path="{OUT.as_posix()}"\n',encoding="utf-8")
    validate()
    print(f"Built: {OUT}")
    print(f"Launcher descriptor: {launcher}")


if __name__ == "__main__":
    build()

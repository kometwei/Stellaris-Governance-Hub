"""Execute the generated planning DSL in a limited model, not the game engine.

Checks actual preview/commit branches and reservations. Native action parsing,
event-target scoping in the game and pathfinding still require in-game tests.
"""
from dataclasses import dataclass, field
from pathlib import Path
import re
import math
import unittest
import build_scattered_fleet_organizer as builder


def parse(text):
    text = re.sub(r"#[^\n]*", "", text)
    tokens = re.findall(r'"(?:\\.|[^"\\])*"|<=|>=|!=|[{}=<>]|[^\s{}=<>!]+', text)
    def walk(index):
        rows = []
        while index < len(tokens) and tokens[index] != "}":
            key, op = tokens[index:index+2]
            index += 2
            if tokens[index] == "{":
                value, index = walk(index+1)
            else:
                value = tokens[index].strip('"')
                index += 1
            rows.append((key, op, value))
        return rows, index+1
    return walk(0)[0]


@dataclass(eq=False)
class Obj:
    kind: str
    uid: int
    owner: object = None
    design: object = None
    ships: list = field(default_factory=list)
    vars: dict = field(default_factory=dict)
    flags: set = field(default_factory=set)
    orders: set = field(default_factory=set)
    leader: object = None
    solar_system: object = None
    alive: bool = True
    unit: int = 1
    combat: bool = False


class Model:
    def __init__(self, cap=20):
        self.country = Obj("country", 0, vars={"command_limit": cap})
        self.system = Obj("system", -1)
        self.fleets, self.targets, self.dispatched = [], {}, []
        self.from_scope = None
        self.native_orders = []
        self.stack = [self.country]
        self.fleet_visits = 0
        self.ship_checks = 0
        self.scripts = {}
        for folder in ("scripted_effects", "scripted_triggers"):
            for path in (builder.OUT / "common" / folder).glob("*.txt"):
                self.scripts.update({k:v for k,op,v in parse(path.read_text(encoding="utf-8"))})
        self.events = {}
        for kind,op,body in parse((builder.OUT/"events/qol_fleet_sort.txt").read_text(encoding="utf-8")):
            if kind in ("country_event", "fleet_event"):
                self.events[next(v for k,o,v in body if k=="id")] = body

    def add(self, design, ships=1, unit=1):
        fleet = Obj("fleet", len(self.fleets)+1, owner=self.country, solar_system=self.system)
        fleet.ships = [Obj("ship", 1000000*fleet.uid+i, owner=self.country, design=design, unit=unit) for i in range(ships)]
        self.fleets.append(fleet)
        return fleet

    def scope(self, ref):
        if re.search(r"\bprev\.prev\b",ref):
            raise AssertionError("Native prev.prev switches contexts; use prevprev for scope history")
        if ref.startswith("event_target:"):
            return self.targets.get(self.target_key(ref.removeprefix("event_target:")))
        parts = ref.split(".")
        if parts[0] in ("prev","prevprev","prevprevprev","prevprevprevprev"):
            depth = len(parts.pop(0))//len("prev")
            obj = self.stack[-1-depth] if depth<len(self.stack) else None
            for part in parts:
                obj = getattr(obj,part,None) if obj else None
            return obj
        first = parts.pop(0)
        obj = {"this":self.stack[-1], "root":self.stack[0],
               "from":self.from_scope}.get(first)
        if first not in ("this", "root", "from"):
            obj = getattr(self.stack[-1],first,None)
        for part in parts:
            obj = getattr(obj,part,None) if obj else None
        return obj

    def target_key(self, key):
        if "@" not in key:
            return key
        base, scope = key.split("@",1)
        obj = self.scope(scope)
        return base, (obj.kind,obj.uid) if obj else None

    def native(self, obj, key):
        if key == "num_ships": return len(obj.ships)
        if key == "fleet_size": return sum(s.unit for s in obj.ships)
        if key == "command_limit": return obj.vars["command_limit"]
        raise AssertionError(key)

    def num(self, value):
        try: return float(value)
        except ValueError: pass
        if value.startswith("trigger:"):
            return self.native(self.stack[-1],value[8:])
        if ".trigger:" in value:
            scope,key = value.split(".trigger:",1)
            return self.native(self.scope(scope),key)
        if "." in value:
            scope,key = value.rsplit(".",1)
            return self.scope(scope).vars.get(key,0)
        return self.stack[-1].vars.get(value,0)

    def compare(self, left, op, right):
        return {"=":left==right,"!=":left!=right,"<":left<right,">":left>right,"<=":left<=right,">=":left>=right}[op]

    def in_scope(self, obj, fn, body):
        if obj is None or not obj.alive: return False
        self.stack.append(obj)
        try: return fn(body)
        finally: self.stack.pop()

    def condition(self, rows):
        return all(self.one(k,op,v) for k,op,v in rows)

    def one(self,key,op,value):
        obj = self.stack[-1]
        if key in self.scripts: return self.condition(self.scripts[key]) == (value=="yes")
        if key == "AND": return self.condition(value)
        if key in ("NOT","NAND"): return not self.condition(value)
        if key == "OR": return any(self.one(*row) for row in value)
        if key == "NOR": return not any(self.one(*row) for row in value)
        if key == "exists":
            result = self.scope(value)
            return result is not None and result.alive
        if key == "check_variable":
            name = next(v for k,o,v in value if k=="which")
            _,op,rhs = next(row for row in value if row[0]=="value")
            return self.compare(obj.vars.get(name,0),op,self.num(rhs))
        if key == "is_variable_set": return value in obj.vars
        if key == "check_variable_arithmetic":
            name = next(v for k,o,v in value if k=="which")
            result = obj.vars.get(name,0)
            for k,o,v in value:
                if k=="add": result += self.num(v)
            _,operator,rhs = next(row for row in value if row[0]=="value")
            return self.compare(result,operator,self.num(rhs))
        if key == "any_owned_ship":
            assert obj.kind in ("country","fleet"), f"Wrong scope for any_owned_ship: {obj.kind}"
            ships = obj.ships if obj.kind=="fleet" else [s for f in self.fleets if f.owner is obj for s in f.ships]
            for ship in ships:
                self.ship_checks += 1
                if self.in_scope(ship,self.condition,value): return True
            return False
        if key in ("num_ships","fleet_size"): return self.compare(self.native(obj,key),op,self.num(value))
        if key in ("has_fleet_flag","has_country_flag"): return value in obj.flags
        if key == "has_fleet_order": return value in obj.orders
        if key == "is_same_value": return obj is self.scope(value)
        if key in ("is_owned_by","is_controlled_by"): return obj.owner is self.scope(value)
        if key == "is_in_combat": return obj.combat == (value=="yes")
        if key == "is_ai": return value=="no"
        if key in ("is_mobile","is_designable"): return value=="yes"
        if key in ("is_leased","is_alliance_fleet"): return value=="no"
        if key == "has_ship_owner_type": return value=="country"
        if key == "is_ship_class": return value=="shipclass_military"
        if key == "is_ship_size": return value=="corvette"
        if isinstance(value,list): return self.in_scope(self.scope(key),self.condition,value)
        raise AssertionError((key,op,value))

    def run(self, rows):
        branch = False
        for key,op,value in rows:
            obj = self.stack[-1]
            if key in self.scripts:
                self.run(self.scripts[key])
            elif key == "if":
                limit = next(v for k,o,v in value if k=="limit")
                branch = self.condition(limit)
                if branch: self.run([row for row in value if row[0]!="limit"])
            elif key == "else":
                if not branch: self.run(value)
            elif key == "every_owned_fleet":
                limit = next((v for k,o,v in value if k=="limit"),[])
                effects = [row for row in value if row[0]!="limit"]
                for fleet in self.fleets:
                    self.fleet_visits += 1
                    def visit(_):
                        if self.condition(limit): self.run(effects)
                    self.in_scope(fleet,visit,[])
            elif key in ("random_owned_ship","random_owned_fleet"):
                limit = next((v for k,o,v in value if k=="limit"),[])
                effects = [row for row in value if row[0]!="limit"]
                candidates = obj.ships if key=="random_owned_ship" else self.fleets
                chosen = next((x for x in candidates if self.in_scope(x,self.condition,limit)),None)
                self.in_scope(chosen,self.run,effects)
            elif key == "every_owned_ship":
                for ship in obj.ships:
                    self.in_scope(ship,self.run,value)
            elif key == "while":
                count = next(v for k,o,v in value if k=="count")
                effects = [row for row in value if row[0]!="count"]
                for _ in range(int(self.num(count))): self.run(effects)
            elif key == "create_fleet":
                fleet = Obj("fleet",len(self.fleets)+1)
                self.fleets.append(fleet)
                self.in_scope(fleet,self.run,next(v for k,o,v in value if k=="effect"))
            elif key == "create_ship":
                design = self.scope(next(v for k,o,v in value if k=="design"))
                obj.ships.append(Obj("ship",1000000*obj.uid+len(obj.ships),owner=obj.owner,design=design))
            elif key == "set_owner": obj.owner = self.scope(value)
            elif key == "set_location": obj.solar_system = self.scope(value)
            elif key == "ordered_owned_fleet":
                limit = next((v for k,o,v in value if k=="limit"),[])
                order = next(v for k,o,v in value if k=="order_by")
                position = int(next(v for k,o,v in value if k=="position"))
                candidates = [f for f in self.fleets if self.in_scope(f,self.condition,limit)]
                candidates.sort(key=lambda f:self.in_scope(f,lambda _:self.num(order),[]),reverse=True)
                if len(candidates)>position:
                    self.in_scope(candidates[position],self.run,[row for row in value if row[0] not in ("limit","order_by","position")])
            elif key == "save_event_target_as": self.targets[self.target_key(value)] = obj
            elif key in ("set_fleet_flag","set_country_flag"): obj.flags.add(value)
            elif key in ("remove_fleet_flag","remove_country_flag"): obj.flags.discard(value)
            elif key == "clear_variable": obj.vars.pop(value,None)
            elif key == "floor_variable": obj.vars[value] = math.floor(obj.vars.get(value,0))
            elif key in ("multiply_variable","divide_variable"):
                name = next(v for k,o,v in value if k=="which")
                number = self.num(next(v for k,o,v in value if k=="value"))
                obj.vars[name] = obj.vars.get(name,0) * number if key=="multiply_variable" else obj.vars.get(name,0) / number
            elif key in ("set_variable","change_variable","subtract_variable"):
                name = next(v for k,o,v in value if k=="which")
                number = self.num(next(v for k,o,v in value if k=="value"))
                if key == "set_variable": obj.vars[name] = number
                else: obj.vars[name] = obj.vars.get(name,0) + number * (-1 if key=="subtract_variable" else 1)
            elif key == "fleet_event":
                scopes = next(v for k,o,v in value if k=="scopes")
                target = self.scope(next(v for k,o,v in scopes if k=="from"))
                self.dispatched.append((obj,target))
            elif key == "country_event":
                name = next(v for k,o,v in value if k=="id")
                self.call_event(name)
            elif key == "log": pass
            elif key == "clear_orders": obj.orders.clear()
            elif key == "queue_actions":
                target = self.scope(next(v for k,o,v in value if k=="merge_fleet"))
                self.native_orders.append((obj,target))
            elif isinstance(value,list): self.in_scope(self.scope(key),self.run,value)
            else: raise AssertionError((key,op,value))

    def call(self,name): self.run(self.scripts[name])

    def call_event(self,name):
        if isinstance(name,int): name = f"qol_fleet_sort.{name}"
        self.current_event = name
        body = self.events[name]
        self.run(next((v for k,o,v in body if k=="immediate"),[]))

    def activate(self,key):
        options = [v for k,o,v in self.events[self.current_event] if k=="option"]
        body = next(v for v in options if ("name","=",f"qol_fleet_sort.{key}") in v)
        trigger = next((v for k,o,v in body if k=="trigger"),[])
        if not self.condition(trigger): return False
        self.run(next((v for k,o,v in body if k=="hidden_effect"),[]))
        return True


class PlanningTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): builder.build()

    def mixed(self, model, designs, unit=1):
        fleet = model.add(designs[0],ships=len(designs),unit=unit)
        for ship,design in zip(fleet.ships,designs): ship.design = design
        return fleet

    def test_native_prev_history_tokens_and_invalid_ship_iteration(self):
        m = Model()
        a,b = Obj("design",1),Obj("design",2)
        source,target = [self.mixed(m,[a,b]) for _ in range(2)]
        m.stack=[m.country,source,target,target.ships[0]]
        self.assertIs(m.scope("prevprev"),source)
        m.stack=[m.country,source,source.ships[0],target,target.ships[1],b]
        self.assertIs(m.scope("prevprevprev.design"),a)
        with self.assertRaisesRegex(AssertionError,"Native prev.prev"):
            m.scope("prev.prev")
        m.stack=[source.ships[0]]
        with self.assertRaisesRegex(AssertionError,"Wrong scope for any_owned_ship: ship"):
            m.one("any_owned_ship","=",[])

    def test_commit_assignments_reach_dispatch_branch_with_correct_scope_history(self):
        m = Model(cap=100)
        a,b,c = [Obj("design",i) for i in range(3)]
        for designs in ([a,b],[b,a,a],[a,b],[a],[a],[a,c],[c,a]):
            f=self.mixed(m,designs)
            f.orders.add("move_to_system_point_order")
        m.call("qol_sort_preview")
        m.call("qol_sort_commit")
        assignments=list(m.dispatched)
        self.assertEqual(len(assignments),4)
        # Execute the actual dispatch DSL after clear_plan to catch reliance on
        # preview-only flags or country ROOT inside the fleet event.
        for source,target in assignments:
            m.stack=[source]
            m.from_scope=target
            m.call_event(20)
        self.assertEqual(m.native_orders,assignments)
        for source,target in assignments:
            self.assertFalse(source.orders)
            self.assertEqual(target.orders,{"move_to_system_point_order"})

    def test_mixed_exact_set_ignores_order_and_quantities(self):
        m = Model(cap=20)
        a,b = Obj("design",1),Obj("design",2)
        target = self.mixed(m,[a,b])
        sources = [self.mixed(m,[b,a,a]),self.mixed(m,[b,b,a])]
        before = [list(f.ships) for f in m.fleets]
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_designs"],1)
        self.assertEqual(m.country.vars["qol_sort_mixed"],3)
        self.assertEqual(m.country.vars["qol_sort_requests"],2)
        self.assertFalse(m.dispatched)
        m.call("qol_sort_commit")
        self.assertEqual(m.dispatched,[(s,target) for s in sources])
        self.assertEqual(target.vars["qol_sort_reserved_total"],8)
        self.assertEqual(before,[f.ships for f in m.fleets])

    def test_mixed_subsets_supersets_overlaps_and_versions_stay_separate(self):
        m = Model(cap=100)
        a,b,c,other_b = [Obj("design",i) for i in range(4)]
        sets = ([a,b],[a],[a,b,c],[a,c],[a,other_b])
        for designs in sets:
            self.mixed(m,designs)
            self.mixed(m,list(reversed(designs)))
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_designs"],5)
        m.call("qol_sort_commit")
        self.assertEqual(len(m.dispatched),5)
        for s,t in m.dispatched:
            self.assertEqual(set(x.design for x in s.ships),set(x.design for x in t.ships))

    def test_mixed_next_fit_keeps_whole_fleets_and_separate_set_bins(self):
        m = Model(cap=7)
        a,b = Obj("design",1),Obj("design",2)
        fleets = [self.mixed(m,[a,b],unit=2) for _ in range(4)]
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_designs"],1)
        self.assertEqual(m.country.vars["qol_sort_bins"],4)
        self.assertEqual(m.country.vars["qol_sort_requests"],0)
        for f in fleets:
            for s in f.ships: s.unit=1
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_bins"],2)
        m.call("qol_sort_commit")
        self.assertEqual(m.dispatched,[(fleets[1],fleets[0]),(fleets[2],fleets[0])])
        self.assertEqual(fleets[0].vars["qol_sort_reserved_total"],6)

    def test_mixed_receiver_retains_pending_capacity_across_previews(self):
        m = Model(cap=12)
        a,b = Obj("design",1),Obj("design",2)
        receiver = self.mixed(m,[a,b])
        receiver.flags.add("qol_sort_auto_protected")
        receiver.vars["qol_sort_reserved_total"]=8
        for _ in range(5): self.mixed(m,[b,a])
        m.call("qol_sort_preview")
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_designs"],1)
        m.call("qol_sort_commit")
        self.assertEqual(sum(t is receiver for s,t in m.dispatched),2)
        self.assertEqual(receiver.vars["qol_sort_reserved_total"],12)
        self.assertFalse(any(s is receiver for s,t in m.dispatched))

    def test_duplicate_unreleased_mixed_receivers_never_become_sources(self):
        m = Model(cap=12)
        a,b = Obj("design",1),Obj("design",2)
        receivers = [self.mixed(m,[a,b]) for _ in range(2)]
        for f in receivers:
            f.flags.add("qol_sort_auto_protected")
            f.vars["qol_sort_reserved_total"]=2
        source = self.mixed(m,[b,a])
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],2)
        m.call("qol_sort_commit")
        self.assertEqual(m.dispatched,[(source,receivers[0])])

    def test_mixed_released_receivers_can_regroup(self):
        m = Model()
        a,b = Obj("design",1),Obj("design",2)
        first,second = [self.mixed(m,[a,b]) for _ in range(2)]
        for f in (first,second): f.flags.add("qol_sort_auto_protected")
        m.call("qol_sort_release_reservations")
        m.call("qol_sort_preview")
        m.call("qol_sort_commit")
        self.assertEqual(m.dispatched,[(second,first)])

    def test_mixed_post_preview_mutations_require_refresh(self):
        for who in (0,1,"both"):
            for mutation in ("design","count","replace","protect","combat","destroy"):
                with self.subTest(who=who,mutation=mutation):
                    m = Model()
                    a,b,c = [Obj("design",i) for i in range(3)]
                    fleets = [self.mixed(m,[a,b]) for _ in range(2)]
                    m.call("qol_sort_preview")
                    for f in (fleets if who=="both" else [fleets[who]]):
                        if mutation=="design": f.ships[1].design=c
                        if mutation=="count": f.ships.append(Obj("ship",90000000+f.uid,design=a))
                        if mutation=="replace": f.ships[1]=Obj("ship",90000000+f.uid,design=b)
                        if mutation=="protect": f.flags.add("qol_sort_protected")
                        if mutation=="combat": f.combat=True
                        if mutation=="destroy": f.alive=False
                    m.call("qol_sort_commit")
                    self.assertFalse(m.dispatched)

    def test_mixed_capacity_reduction_rechecks_current_limit(self):
        m = Model(cap=20)
        a,b = Obj("design",1),Obj("design",2)
        for _ in range(6): self.mixed(m,[a,b])
        m.call("qol_sort_preview")
        m.country.vars["command_limit"]=7
        m.call("qol_sort_commit")
        self.assertEqual(len(m.dispatched),2)
        self.assertEqual(m.country.vars["qol_sort_skipped"],3)

    def test_mixed_batch_bound_includes_deferred_mixed_fleets(self):
        m = Model(cap=20)
        a,b = Obj("design",1),Obj("design",2)
        for _ in range(300): self.mixed(m,[a,b])
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],256)
        self.assertEqual(m.country.vars["qol_sort_deferred"],44)
        self.assertEqual(m.country.vars["qol_sort_mixed"],256)
        self.assertEqual(m.country.vars["qol_sort_bins"],26)
        self.assertEqual(m.country.vars["qol_sort_requests"],230)

    def test_group_exclusion_uses_selected_set_not_shared_first_design(self):
        for slot in (1,2,3):
            with self.subTest(slot=slot):
                m = Model()
                a,b,c = [Obj("design",i) for i in range(3)]
                groups = [[self.mixed(m,designs) for _ in range(2)] for designs in ([a,b],[a,c],[a])]
                m.call("qol_sort_preview")
                m.call_event(3)
                m.activate(f"exclude.{slot}")
                self.assertEqual(m.country.vars["qol_sort_candidates"],4)
                for i,group in enumerate(groups,1):
                    for f in group:
                        self.assertEqual("qol_sort_excluded" in f.flags,i==slot)

    def test_mixed_native_dispatch_rechecks_both_set_directions(self):
        a,b,c = [Obj("design",i) for i in range(3)]
        for designs,expected in (([b,a,a],True),([a],False),([a,b,c],False),([a,c],False)):
            with self.subTest(designs=designs):
                m = Model()
                source = self.mixed(m,[a,b])
                target = self.mixed(m,designs)
                source.orders.add("move_to_system_point_order")
                target.orders.add("follow_order")
                m.stack=[source]
                m.from_scope=target
                m.call_event(20)
                self.assertEqual(m.native_orders,[(source,target)] if expected else [])
                self.assertEqual(source.orders,set() if expected else {"move_to_system_point_order"})
                self.assertEqual(target.orders,{"follow_order"})

    def fixture_model(self, ready=True):
        m = Model(cap=1100)
        original = m.add(Obj("design",1),ships=4)
        for kind,op,rows in parse((builder.OUT/"events/qol_fleet_sort_test.txt").read_text(encoding="utf-8")):
            m.events[next(v for k,o,v in rows if k=="id")] = rows
        if ready:
            m.country.flags.add("qol_sort_fixture_sample")
            m.targets["qol_sort_fixture_design"] = original.ships[0].design
            m.targets["qol_sort_fixture_location"] = m.system
        return m,original

    def test_fixture_creates_requested_single_ship_fleets_without_touching_original(self):
        for event,count in enumerate((20,100,300,600),51):
            with self.subTest(count=count):
                m,original = self.fixture_model()
                before = list(original.ships)
                m.call_event(event)
                created=m.fleets[1:]
                self.assertEqual(len(created),count)
                self.assertEqual(m.country.vars["qol_sort_fixture_created"],count)
                self.assertEqual(original.ships,before)
                self.assertTrue(all(len(f.ships)==1 and f.ships[0].design is before[0].design and f.owner is m.country and f.solar_system is m.system for f in created))
                self.assertTrue(all("qol_sort_protected" not in f.flags for f in created))
                self.assertFalse(m.dispatched)
                self.assertNotIn("qol_sort_fixture_sample",m.country.flags)

    def test_fixture_missing_sample_creates_nothing(self):
        m,original = self.fixture_model(ready=False)
        m.call_event(53)
        self.assertEqual(m.fleets,[original])
        self.assertEqual(m.country.vars["qol_sort_fixture_created"],0)

    def test_mixed_fixture_menu_samples_distinct_designs_and_reset_hides_stale_sample(self):
        m,original = self.fixture_model()
        m.country.capital_scope = Obj("planet",-2)
        m.country.capital_scope.star = m.system
        m.call_event(50)
        self.assertFalse(m.activate("fixture.mixed"))
        other = m.add(Obj("design",2))
        m.call_event(50)
        self.assertIs(m.targets["qol_sort_fixture_design_b"],other.ships[0].design)
        m.fleets.remove(other)
        m.call_event(50)
        self.assertFalse(m.activate("fixture.mixed"))

    def test_mixed_fixture_generates_eight_fleets_with_one_protected_control(self):
        m,original = self.fixture_model()
        m.country.capital_scope = Obj("planet",-2)
        m.country.capital_scope.star = m.system
        other = m.add(Obj("design",2))
        original.flags.add("qol_sort_protected")
        other.flags.add("qol_sort_protected")
        before = [list(f.ships) for f in m.fleets]
        m.call_event(50)
        self.assertTrue(m.activate("fixture.mixed"))
        self.assertEqual(m.country.vars["qol_sort_fixture_mixed_created"],8)
        self.assertEqual(before,[f.ships for f in m.fleets[:2]])
        created = m.fleets[2:]
        self.assertEqual([len(f.ships) for f in created],[2,2,3,2,1,1,1,1])
        self.assertEqual(sum("qol_sort_protected" in f.flags for f in created),1)
        self.assertTrue(all(f.owner is m.country and f.solar_system is m.system for f in created))
        self.assertFalse(m.dispatched)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],7)
        self.assertEqual(m.country.vars["qol_sort_designs"],3)
        self.assertEqual(m.country.vars["qol_sort_requests"],4)
        m.call("qol_sort_commit")
        self.assertEqual(len(m.dispatched),4)
        self.assertFalse(any(s is created[3] or t is created[3] for s,t in m.dispatched))

    def test_original_first_and_fourth_merge_without_per_fleet_opt_in(self):
        m = Model(cap=1100)
        a = Obj("design",3694)
        first = m.add(a,ships=5,unit=40)
        fourth = m.add(a,ships=5,unit=40)
        mixed = m.add(a,ships=6,unit=40)
        mixed.ships[-1].design = Obj("design",3695)
        protected = m.add(a,ships=5,unit=40)
        protected.flags.add("qol_sort_protected")
        original_ships = list(mixed.ships)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],3)
        self.assertEqual(m.country.vars["qol_sort_mixed"],1)
        self.assertEqual(m.country.vars["qol_sort_requests"],1)
        self.assertFalse(m.dispatched)
        m.call("qol_sort_commit")
        self.assertEqual(m.dispatched,[(fourth,first)])
        self.assertEqual(first.vars["qol_sort_reserved_total"],400)
        self.assertEqual(mixed.ships,original_ships)
        self.assertFalse(mixed.orders)

    def test_hundreds_of_varied_size_fleets_need_no_roster_selection(self):
        m = Model(cap=1100)
        a = Obj("design",1)
        for i in range(500): m.add(a,ships=(1,4,5)[i%3],unit=10)
        protected = m.add(a,ships=8,unit=10)
        protected.flags.add("qol_sort_protected")
        mixed = m.add(a,ships=7,unit=10)
        mixed.ships[-1].design = Obj("design",2)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],256)
        self.assertEqual(m.country.vars["qol_sort_deferred"],245)
        self.assertEqual(m.country.vars["qol_sort_mixed"],0)
        m.call("qol_sort_commit")
        self.assertTrue(m.dispatched)
        totals = {}
        for source,target in m.dispatched:
            self.assertNotIn(source,(protected,mixed))
            self.assertNotIn(target,(protected,mixed))
            totals.setdefault(target,m.native(target,"fleet_size"))
            totals[target] += m.native(source,"fleet_size")
        self.assertTrue(all(value<=1100 for value in totals.values()))

    def test_two_released_receivers_regroup_without_touching_original_large_fleet(self):
        m = Model(cap=1100)
        a = Obj("design",3692)
        eighth = m.add(a,ships=2,unit=10)
        eleventh = m.add(a,ships=4,unit=10)
        original = m.add(a,ships=5,unit=40)
        original.flags.add("qol_sort_protected")
        protected = m.add(a,ships=4,unit=10)
        for fleet in (eighth,eleventh,protected):
            fleet.flags.add("qol_sort_auto_protected")
            fleet.vars["qol_sort_reserved_total"] = m.native(fleet,"fleet_size")
        protected.flags.add("qol_sort_protected")
        m.call("qol_sort_release_reservations")
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],2)
        self.assertEqual(m.country.vars["qol_sort_requests"],1)
        m.call("qol_sort_commit")
        self.assertEqual(m.dispatched,[(eleventh,eighth)])
        self.assertEqual(eighth.vars["qol_sort_reserved_total"],60)
        self.assertNotIn("qol_sort_regroup_ready",eighth.flags)
        self.assertFalse(any(s is original or t is original or s is protected or t is protected for s,t in m.dispatched))

    def test_unreleased_receivers_never_become_sources_even_if_reservation_equals_size(self):
        m = Model(cap=1100)
        a = Obj("design",1)
        for count in (2,4):
            f=m.add(a,ships=count,unit=10)
            f.flags.add("qol_sort_auto_protected")
            f.vars["qol_sort_reserved_total"]=count*10
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_requests"],0)
        self.assertTrue(all("qol_sort_plan_source" not in f.flags for f in m.fleets))

    def test_regroup_rechecks_reservations_before_moving_old_receiver(self):
        m = Model(cap=1100)
        a = Obj("design",1)
        for count in (2,4):
            f=m.add(a,ships=count,unit=10)
            f.flags.add("qol_sort_auto_protected")
        m.call("qol_sort_release_reservations")
        m.call("qol_sort_preview")
        m.fleets[1].vars["qol_sort_reserved_total"]=50
        m.call("qol_sort_commit")
        self.assertFalse(m.dispatched)

    def test_large_batch_is_bounded_and_has_three_fleet_passes(self):
        m = Model(cap=20)
        design = Obj("design",1)
        for _ in range(2000): m.add(design)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],256)
        self.assertEqual(m.country.vars["qol_sort_deferred"],1744)
        self.assertEqual(m.country.vars["qol_sort_bins"],13)
        self.assertEqual(m.country.vars["qol_sort_requests"],243)
        self.assertEqual(m.fleet_visits,6000)
        self.assertFalse(m.dispatched)

    def test_exact_design_and_non_unit_capacity(self):
        m = Model(cap=8)
        a,b = Obj("design",1), Obj("design",2)
        for _ in range(6): m.add(a,unit=2)
        for _ in range(4): m.add(b,unit=4)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_designs"],2)
        self.assertEqual(m.country.vars["qol_sort_bins"],4)
        m.call("qol_sort_commit")
        totals = {}
        for source,target in m.dispatched:
            self.assertIs(source.ships[0].design,target.ships[0].design)
            totals.setdefault(target,m.native(target,"fleet_size"))
            totals[target] += m.native(source,"fleet_size")
        self.assertTrue(all(n<=8 for n in totals.values()))

    def test_protected_ordered_combat_and_mia_excluded_but_mixed_participates(self):
        m = Model()
        a,b = Obj("design",1),Obj("design",2)
        m.add(a).flags.add("qol_sort_protected")
        m.add(a).orders.add("merge_fleet_order")
        m.add(a).combat = True
        m.add(a).solar_system = None
        mixed = m.add(a,ships=2)
        mixed.ships[1].design = b
        m.add(a)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],2)
        self.assertEqual(m.country.vars["qol_sort_mixed"],1)
        m.call("qol_sort_clear_plan")
        self.assertIn("qol_sort_protected",m.fleets[0].flags)
        self.assertFalse(m.dispatched)

    def test_capacity_reduction_rechecks_and_reserves_all_sources(self):
        m = Model(cap=12)
        design = Obj("design",1)
        for _ in range(10): m.add(design)
        m.call("qol_sort_preview")
        m.country.vars["command_limit"] = 5
        m.call("qol_sort_commit")
        self.assertEqual(len(m.dispatched),4)
        self.assertEqual(m.country.vars["qol_sort_skipped"],5)

    def test_design_or_protection_changed_after_preview(self):
        for mutation in ("design","protection","destroy"):
            with self.subTest(mutation=mutation):
                m = Model()
                a,b = Obj("design",1),Obj("design",2)
                target = m.add(a)
                for _ in range(4): m.add(a)
                m.call("qol_sort_preview")
                if mutation=="design": target.ships[0].design=b
                if mutation=="protection": target.flags.add("qol_sort_protected")
                if mutation=="destroy": target.alive=False
                m.call("qol_sort_commit")
                self.assertFalse(m.dispatched)

    def test_refresh_does_not_reuse_previous_bucket_reservations(self):
        m = Model(cap=4)
        a = Obj("design",1)
        for _ in range(10): m.add(a)
        m.call("qol_sort_preview")
        expected = dict(m.country.vars)
        m.call("qol_sort_preview")
        self.assertEqual(expected,m.country.vars)
        self.assertEqual(m.country.vars["qol_sort_bins"],3)

    def test_next_batch_never_reassigns_a_receiver_with_ships_enroute(self):
        m = Model(cap=20)
        a = Obj("design",1)
        for _ in range(300): m.add(a)
        m.call("qol_sort_preview")
        m.call("qol_sort_commit")
        receivers = {target for source,target in m.dispatched}
        for source,target in m.dispatched:
            source.orders.add("merge_fleet_order")
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],45)
        self.assertTrue(all("qol_sort_auto_protected" in target.flags for target in receivers))
        self.assertTrue(all("qol_sort_plan_source" not in target.flags for target in receivers))

    def test_existing_large_receiver_accepts_sources_up_to_command_limit(self):
        m = Model(cap=1100)
        a = Obj("design", 1)
        receiver = m.add(a, ships=4, unit=10)
        receiver.flags.add("qol_sort_auto_protected")
        receiver.vars["qol_sort_reserved_total"] = 40
        # Intentional exceptions now use manual protection regardless of size.
        intentional = m.add(a, ships=5, unit=10)
        intentional.flags.add("qol_sort_protected")
        for _ in range(120): m.add(a, unit=10)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_limit"],1100)
        m.call("qol_sort_commit")
        to_receiver = [s for s,t in m.dispatched if t is receiver]
        self.assertEqual(len(to_receiver), 106)
        self.assertEqual(receiver.vars["qol_sort_reserved_total"], 1100)
        self.assertFalse(any(s is receiver or s is intentional or t is intentional for s,t in m.dispatched))

    def test_pending_capacity_survives_refresh_and_next_batch_without_double_counting(self):
        m = Model(cap=100)
        a = Obj("design", 1)
        receiver = m.add(a, ships=4, unit=10)
        receiver.flags.add("qol_sort_auto_protected")
        receiver.vars["qol_sort_reserved_total"] = 70  # 40 present + 30 en route
        for _ in range(8): m.add(a, unit=10)
        m.call("qol_sort_preview")
        m.call("qol_sort_preview")
        m.call("qol_sort_commit")
        self.assertEqual(sum(t is receiver for s,t in m.dispatched), 3)
        self.assertEqual(receiver.vars["qol_sort_reserved_total"],100)
        for source,target in m.dispatched: source.orders.add("merge_fleet_order")
        m.add(a,unit=10)
        m.call("qol_sort_preview")
        self.assertNotIn("qol_sort_plan_target",receiver.flags)

    def test_old_receivers_need_manual_reservation_reset_and_manual_locks_survive(self):
        m = Model(cap=100)
        a = Obj("design",1)
        receiver = m.add(a,ships=4,unit=10)
        receiver.flags.update(("qol_sort_auto_protected","qol_sort_protected"))
        m.add(a,unit=10)
        m.call("qol_sort_release_reservations")
        self.assertEqual(receiver.vars["qol_sort_reserved_total"],40)
        self.assertIn("qol_sort_protected",receiver.flags)
        m.call("qol_sort_preview")
        self.assertNotIn("qol_sort_plan_target",receiver.flags)
        receiver.flags.remove("qol_sort_protected")
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_requests"],1)

    def test_receiver_actual_size_exceeding_reservation_is_used(self):
        m = Model(cap=100)
        a = Obj("design",1)
        receiver = m.add(a,ships=8,unit=10)
        receiver.flags.add("qol_sort_auto_protected")
        receiver.vars["qol_sort_reserved_total"] = 50
        for _ in range(5): m.add(a,unit=10)
        m.call("qol_sort_preview")
        m.call("qol_sort_commit")
        self.assertEqual(sum(t is receiver for s,t in m.dispatched),2)

    def test_native_merge_uses_scalar_target_without_faulty_target_block(self):
        # Shape regression only: this does not execute the native action parser.
        events = (builder.OUT/"events/qol_fleet_sort.txt").read_text(encoding="utf-8")
        self.assertIn("merge_fleet = event_target:qol_sort_execution_destination",events)
        self.assertNotIn("merge_fleet = {",events)

    def test_ineligible_fleets_do_not_add_per_ship_checks_during_preview(self):
        design = Obj("design",1)
        baseline = Model(cap=100)
        for _ in range(2): baseline.add(design)
        baseline.call("qol_sort_preview")
        large = Model(cap=100)
        for _ in range(2): large.add(design)
        for _ in range(100): large.add(design,ships=100).flags.add("qol_sort_protected")
        large.add(design).flags.add("qol_sort_protected")
        large.add(design).combat = True
        large.add(design).orders.add("merge_fleet_order")
        full = large.add(design,ships=50)
        full.flags.add("qol_sort_auto_protected")
        full.vars["qol_sort_reserved_total"] = 100
        large.call("qol_sort_preview")
        self.assertEqual(large.ship_checks,baseline.ship_checks)
        self.assertEqual(large.country.vars,baseline.country.vars)

    def test_ordinary_navigation_is_included_but_tasks_are_preserved(self):
        m = Model(cap=20)
        a = Obj("design",1)
        for order in ("move_to_system_point_order","orbit_planet_order","follow_order","return_fleet_order","use_bypass_order"):
            m.add(a).orders.add(order)
        for order in ("merge_fleet_order","repair_fleet_order","upgrade_design_at_starbase_fleet_order","jumpdrive_windup"):
            m.add(a).orders.add(order)
        before = [set(f.orders) for f in m.fleets]
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],5)
        self.assertEqual(before,[f.orders for f in m.fleets])
        m.call("qol_sort_commit")
        self.assertEqual(len(m.dispatched),4)

    def test_roster_previous_next_toggle_and_last_page(self):
        m = Model()
        for _ in range(17): m.add(Obj("design",1))
        m.call_event(9)
        self.assertFalse(m.activate("previous"))
        self.assertTrue(m.activate("next"))
        self.assertEqual([m.targets[f"qol_sort_slot_{i}"].uid for i in range(1,9)],list(range(9,17)))
        self.assertTrue(m.activate("protect.1"))
        self.assertEqual(m.country.vars["qol_sort_roster_page"],2)
        self.assertEqual(m.targets["qol_sort_slot_1"].uid,9)
        self.assertTrue(m.activate("unprotect.1"))
        m.activate("next")
        self.assertEqual(m.country.vars["qol_sort_roster_page"],3)
        self.assertEqual(m.targets["qol_sort_slot_1"].uid,17)
        self.assertFalse(m.activate("next"))
        m.activate("previous")
        self.assertEqual(m.targets["qol_sort_slot_1"].uid,9)

    def test_home_end_handle_empty_exact_and_partial_pages(self):
        for count in (0,8,16,17):
            with self.subTest(count=count):
                m = Model()
                for _ in range(count): m.add(Obj("design",1))
                m.call_event(9)
                self.assertFalse(m.activate("page_home"))
                self.assertEqual(m.activate("page_end"),count>8)
                self.assertEqual(m.country.vars["qol_sort_roster_offset"],((count-1)//8)*8 if count else 0)
                self.assertFalse(m.activate("page_end"))
                if count>8: self.assertTrue(m.activate("page_home"))
                self.assertEqual(m.country.vars["qol_sort_roster_offset"],0)

    def test_old_four_item_page_offset_is_normalized_on_reentry(self):
        m = Model()
        for _ in range(25): m.add(Obj("design",1))
        m.country.vars["qol_sort_roster_offset"]=12
        m.call_event(9)
        self.assertEqual(m.country.vars["qol_sort_roster_offset"],8)
        self.assertEqual(m.country.vars["qol_sort_roster_page"],2)
        self.assertEqual(m.targets["qol_sort_slot_1"].uid,9)

    def test_protected_filter_compacts_clamps_and_remembers_position(self):
        m = Model()
        for i in range(25):
            fleet=m.add(Obj("design",1))
            if i<17: fleet.flags.add("qol_sort_protected")
        m.call_event(9)
        m.activate("page_end")
        m.activate("protected_only")
        self.assertEqual(m.country.vars["qol_sort_roster_total"],17)
        self.assertEqual(m.country.vars["qol_sort_roster_offset"],0)
        m.activate("page_end")
        self.assertEqual(m.targets["qol_sort_slot_1"].uid,17)
        m.activate("unprotect.1")
        self.assertEqual(m.country.vars["qol_sort_roster_total"],16)
        self.assertEqual(m.country.vars["qol_sort_roster_offset"],8)
        self.assertEqual(m.targets["qol_sort_slot_1"].uid,9)
        for i in range(1,9): self.assertIn("qol_sort_protected",m.targets[f"qol_sort_slot_{i}"].flags)
        m.activate("back")
        m.activate("protection")
        self.assertEqual(m.country.vars["qol_sort_roster_page"],2)
        m.activate("show_all")
        self.assertEqual(m.country.vars["qol_sort_roster_total"],25)
        self.assertEqual(m.country.vars["qol_sort_roster_offset"],0)

    def test_design_group_home_end(self):
        m = Model()
        for i in range(17): m.add(Obj("design",i))
        m.call("qol_sort_preview")
        m.call_event(3)
        m.activate("page_end")
        self.assertEqual(m.targets["qol_sort_design_1"].uid,16)
        self.assertEqual(m.country.vars["qol_sort_group_page"],3)
        m.activate("page_home")
        self.assertEqual(m.targets["qol_sort_design_1"].uid,0)

    def test_large_manually_protected_fleet_can_be_found_and_unprotected(self):
        m = Model(cap=1100)
        a = Obj("design",1)
        first = m.add(a,ships=5,unit=40)
        first.flags.add("qol_sort_protected")
        for _ in range(4): m.add(a)
        m.call_event(9)
        self.assertEqual(m.country.vars["qol_sort_roster_total"],5)
        self.assertIs(m.targets["qol_sort_slot_1"],first)
        self.assertTrue(m.activate("unprotect.1"))
        self.assertNotIn("qol_sort_protected",first.flags)
        m.call("qol_sort_preview")
        self.assertEqual(m.country.vars["qol_sort_candidates"],5)
        self.assertNotIn("qol_sort_plan_source",first.flags)
        self.assertIn("qol_sort_plan_target",first.flags)

    def test_group_pages_are_distinct_and_back_keeps_current_page(self):
        m = Model()
        designs = [Obj("design",i) for i in range(1,18)]
        for d in designs:
            m.add(d)
            m.add(d)
        m.call("qol_sort_preview")
        m.call_event(3)
        self.assertFalse(m.activate("previous"))
        self.assertEqual([m.targets[f"qol_sort_design_{i}"].uid for i in range(1,9)],list(range(1,9)))
        m.activate("next")
        self.assertEqual([m.targets[f"qol_sort_design_{i}"].uid for i in range(1,9)],list(range(9,17)))
        m.activate("back_preview")
        m.activate("groups")
        self.assertEqual(m.country.vars["qol_sort_group_page"],2)
        m.activate("next")
        self.assertEqual(m.targets["qol_sort_design_1"].uid,17)
        self.assertFalse(m.activate("next"))
        m.activate("previous")
        m.activate("previous")
        self.assertEqual(m.targets["qol_sort_design_1"].uid,1)

    def test_no_duplicate_home_control_and_refresh_remains_explicit(self):
        m = Model()
        for number in (3,10):
            body = m.events[f"qol_fleet_sort.{number}"]
            names = [next(v for k,o,v in item if k=="name") for key,op,item in body if key=="option"]
            self.assertNotIn("qol_fleet_sort.first",names)
            if number==10: self.assertEqual(names.count("qol_fleet_sort.refresh_roster"),1)

    def test_design_buttons_read_name_from_a_live_ship_not_design_scope(self):
        m = Model()
        designs = [Obj("design",i) for i in (1,2,3)]
        for d in designs: m.add(d)
        m.call("qol_sort_preview")
        m.call_event(3)
        for i,d in enumerate(designs,1):
            self.assertIs(m.targets[f"qol_sort_group_ship_{i}"].design,d)
        loc = next((builder.OUT/"localisation").rglob("*.yml")).read_text(encoding="utf-8-sig")
        for i in range(1,builder.PAGE+1):
            self.assertIn(f"[qol_sort_group_ship_{i}.GetDesignName]",loc)
            self.assertIn(f"[qol_sort_group_ship_{i}.GetShipSizeName]",loc)
            self.assertNotIn(f"[qol_sort_design_{i}.GetName]",loc)


if __name__ == "__main__": unittest.main()

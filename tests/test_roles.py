#!/usr/bin/env python3
"""
Role layer contracts (increment 1 of roles-design.md, owner-approved
2026-08-25).

  R1  role book ships in the dataset: every role has a known class, every
      weapon/item membership resolves to a catalog id, every membership
      carries an evidence source; per-weapon role_menu is the exact
      inverse index of role membership (evidence-ordered).
  R2  ruled memberships hold: Grailseeker menus stopper_tank (owner
      2026-08-25), Realmbreaker menus both a dps role and aura_support
      (comp + research evidence), Lifecurse menus curse_support, Longbow
      menus ranged_aoe.
  R3  detection reads the kit: a Longbow in a plate chest detects with a
      kit mismatch (no Longbow role wears plate); a Longbow in cloth does
      not; a weapon with no menu falls back to its coarse class with no
      flag.
  R4  the owner's comp flag: three Heavy Maces and no clump maker at 20
      raises the no-engage-tank advisory; adding Hand of Justice clears
      it.
  R5  the advisory layer is DESCRIPTIVE: computing it never moves
      comp_score.
  R6  the original bug case: Incubus Mace / Grailseeker wearing Hellion
      Jacket (leather) flag off-role kit — their menu roles wear plate.

Run:  py -3 tests/test_roles.py
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "engine"))
from engine import Engine  # noqa: E402

RESULTS = []


def check(name, cond, detail=""):
    RESULTS.append((name, bool(cond), detail))
    print(f"{'PASS' if cond else 'FAIL'}  {name}")
    if detail:
        print(f"      {detail}")


def t_role_book():
    e = Engine()
    roles = e.data.get("roles") or []
    classes = {"frontline", "healer", "support", "dps", "meta"}
    ok_cls = roles and all(r.get("class") in classes for r in roles)
    ids = {r["id"] for r in roles}
    ok_members, ok_sources, bad = True, True, []
    menu_from_roles = {}
    for r in roles:
        for m in r.get("weapons", []) or []:
            if m.get("id") not in e.weapons:
                ok_members = False
                bad.append(f"{r['id']}:{m.get('id')}")
            if not (m.get("source") or "").strip():
                ok_sources = False
                bad.append(f"{r['id']}:{m.get('id')}:no-source")
            menu_from_roles.setdefault(m.get("id"), []).append(r["id"])
        for m in r.get("items", []) or []:
            if m.get("id") not in e.gear:
                ok_members = False
                bad.append(f"{r['id']}:item:{m.get('id')}")
    ok_menu = True
    for wk, w in e.weapons.items():
        menu = (w.get("role_menu") or []) + \
            (w.get("role_menu_secondary") or [])
        if sorted(menu) != sorted(menu_from_roles.get(wk, [])):
            ok_menu = False
            bad.append(f"menu:{wk}")
        if any(rid not in ids for rid in menu):
            ok_menu = False
    check("R1 role book: known classes, resolvable cited memberships, "
          "role_menu is the exact inverse index",
          ok_cls and ok_members and ok_sources and ok_menu,
          f"roles={len(roles)}, problems={bad[:6]}")


def t_ruled_memberships():
    # Function-named roles (owner correction 2026-08-25): the function is
    # the role, never the weapon tree — Lifecurse sits in PURGE, Damnation
    # and Spirithunter share PIERCE, the heal-cut roster shares ANTI_HEAL;
    # aura support dissolved into gear_effects (Realmbreaker is a
    # cooldown/energy CARRIER, not an "aura role" member).
    e = Engine()
    menu = lambda w: set(e.weapons[w].get("role_menu") or [])
    grail = "stopper_tank" in menu("2H_QUARTERSTAFF_AVALON")
    realm = "sustained_brawler" in menu("2H_AXE_AVALON")
    lifecurse = "purge" in menu("MAIN_CURSEDSTAFF_UNDEAD")
    pierce = ("pierce" in menu("2H_CURSEDSTAFF_MORGANA")
              and "pierce" in menu("2H_HARPOON_HELL"))
    heal_cut = ("anti_heal" in menu("MAIN_CURSEDSTAFF_CRYSTAL")
                and "anti_heal" in menu("2H_HALBERD_MORGANA")
                and "anti_heal" in menu("MAIN_MACE_HELL"))
    ge = {g.get("id"): g for g in (e.data.get("gear_effects") or [])}
    carriers = {c.get("id") for c in (ge.get("cooldown_banner") or {})
                .get("carriers", [])}
    realm_carries = "2H_AXE_AVALON" in carriers
    bow = "ranged_aoe" in menu("2H_LONGBOW")
    check("R2 function-named memberships: Grailseeker stopper, Lifecurse "
          "purge, Damnation+Spirithunter pierce, heal-cut roster in "
          "anti_heal, Realmbreaker brawler + cooldown carrier, Longbow "
          "ranged_aoe",
          grail and realm and lifecurse and pierce and heal_cut
          and realm_carries and bow,
          f"grail={sorted(menu('2H_QUARTERSTAFF_AVALON'))} "
          f"realm={sorted(menu('2H_AXE_AVALON'))} carriers={sorted(carriers)}")


def t_detection():
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    plate = e.detect_role("2H_LONGBOW", chest="ARMOR_PLATE_FEY")
    cloth = e.detect_role("2H_LONGBOW", chest="ARMOR_CLOTH_FEY")
    bare = e.detect_role("2H_LONGBOW", chest=None)
    plate_ok = plate["role"] == "ranged_aoe" and plate["kit_match"] is False
    cloth_ok = cloth["role"] == "ranged_aoe" and cloth["kit_match"] is True
    bare_ok = bare["role"] == "ranged_aoe" and bare["kit_match"] is None
    # a weapon without any menu falls back to its coarse class, unflagged
    no_menu = next((w for w in e.pool if not e.weapons[w].get("role_menu")),
                   None)
    fb_ok = True
    if no_menu:
        fb = e.detect_role(no_menu, chest="ARMOR_PLATE_FEY")
        fb_ok = fb["role"] is None and fb["kit_match"] is None \
            and fb["class"] == e.role_of(no_menu)
    check("R3 detection: plate Longbow mismatches, cloth fits, bare is "
          "unjudged, menu-less weapons fall back unflagged",
          plate_ok and cloth_ok and bare_ok and fb_ok,
          f"plate={plate} bare={bare} no_menu={no_menu}")


def t_engage_flag():
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    healers = ["MAIN_HOLYSTAFF_AVALON", "2H_HOLYSTAFF_UNDEAD",
               "2H_NATURESTAFF_HELL"]
    stoppers = ["2H_MACE", "2H_MACE", "2H_MACE"]
    adv = e.role_advisory(stoppers + healers)
    flagged = any(f.get("kind") == "no_engage_tank" for f in adv["flags"])
    adv2 = e.role_advisory(stoppers + ["2H_HAMMER_AVALON"] + healers)
    cleared = not any(f.get("kind") == "no_engage_tank"
                      for f in adv2["flags"])
    check("R4 comp flag: 3 Heavy Maces + no clump maker raises "
          "no_engage_tank; Hand of Justice clears it",
          flagged and cleared,
          f"flags={[f.get('kind') for f in adv['flags']]}")


def t_descriptive_only():
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    party = ["2H_MACE", "2H_MACE", "2H_MACE", "MAIN_HOLYSTAFF_AVALON",
             "2H_AXE_AVALON", "2H_LONGBOW"]
    before = e.comp_score(party)
    e.role_advisory(party, chests={0: "ARMOR_LEATHER_HELL"})
    e.detect_role("2H_LONGBOW", chest="ARMOR_PLATE_FEY")
    after = e.comp_score(party)
    check("R5 advisory is descriptive: comp_score untouched",
          before == after, f"before={before} after={after}")


def t_original_bug_case():
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    party = ["MAIN_MACE_HELL", "2H_QUARTERSTAFF_AVALON",
             "MAIN_HOLYSTAFF_AVALON"]
    adv = e.role_advisory(party, chests={0: "ARMOR_LEATHER_HELL",
                                         1: "ARMOR_LEATHER_HELL"})
    m0, m1 = adv["members"][0], adv["members"][1]
    check("R6 the reproduced bug: Incubus + Grailseeker in Hellion "
          "Jacket both flag off-role kit (their SEATS wear plate; the "
          "anti-heal FUNCTION rides along, never excuses the chest)",
          m0.get("kit_match") is False and m1.get("kit_match") is False
          and "anti_heal" in (m0.get("functions") or []),
          f"incubus={m0} grailseeker={m1}")


def t_gear_effects():
    # Typed gear-carried effects (owner 2026-08-25): each aura/active is
    # its own effect, attached to whatever role wears it — the advisory
    # reports "role + carrying".
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    effects = e.data.get("gear_effects") or []
    ok_shape = all(g.get("id") and (g.get("items") or g.get("carriers"))
                   for g in effects)
    party = ["2H_AXE_AVALON", "2H_MACE", "2H_LONGBOW"]
    adv = e.role_advisory(party, chests={0: "ARMOR_LEATHER_ROYAL",
                                         1: "ARMOR_PLATE_HELL"})
    royal = adv["members"][0]["carrying"] == ["cooldown_banner"]
    demon = adv["members"][1]["carrying"] == ["reflect_shell"]
    bare = adv["members"][2]["carrying"] == []
    check("R7 gear effects: typed catalog ships; Royal Jacket reads as "
          "cooldown_banner, Demon Armor as reflect_shell, bare as none",
          bool(effects) and ok_shape and royal and demon and bare,
          f"effects={[g.get('id') for g in effects]} "
          f"m0={adv['members'][0]['carrying']}")


def t_tiered_sweep():
    # E-first tiered sweep (owner 2026-08-25): "the primary roles for a
    # weapon should come from its e spell"; Q/W abilities are "a
    # secondary level role". Derived from the sheets' slot structure
    # across ALL weapons — the owner's own examples pinned:
    e = Engine()
    menu = lambda w: e.weapons[w].get("role_menu") or []
    menu2 = lambda w: e.weapons[w].get("role_menu_secondary") or []
    # Carving Sword's E cuts resistances 20% through the dash line
    carving = "pierce" in menu("2H_CLEAVER_HELL")
    # the axe tree's bleed heal-cut and Axe Smash shred are Q/W picks
    axe = ("anti_heal" in menu2("2H_AXE")
           and "pierce" in menu2("2H_AXE")
           and "anti_heal" not in menu("2H_AXE"))
    # the curse tree's Armor Piercer W: secondary pierce for the line —
    # but never for Damnation, whose E already pierces (primary, hand-cited)
    shadow = "pierce" in menu2("MAIN_CURSEDSTAFF_AVALON")
    damn = ("pierce" in menu("2H_CURSEDSTAFF_MORGANA")
            and "pierce" not in menu2("2H_CURSEDSTAFF_MORGANA"))
    d = e.detect_role("2H_AXE", chest=None)
    detected = "anti_heal" in (d.get("secondary") or [])
    check("R8 E-first tiered sweep: Carving E-pierce primary; axe bleed "
          "heal-cut + Axe Smash shred secondary; curse Armor Piercer W "
          "secondary (Damnation stays E-primary); detection carries the "
          "secondary list",
          carving and axe and shadow and damn and detected,
          f"carving={menu('2H_CLEAVER_HELL')} axe2={menu2('2H_AXE')} "
          f"shadow2={menu2('MAIN_CURSEDSTAFF_AVALON')}")


def t_shield_break_split():
    # Owner 2026-08-25: "hammers i think only break shield on q, it isnt
    # really a purge. shield break is like the primary role of black
    # monk" — the shield_break role claims its evidence spells
    # (Iron Breaker / Black Monk's E / Claws' E) away from true purge.
    e = Engine()
    menu = lambda w: e.weapons[w].get("role_menu") or []
    menu2 = lambda w: e.weapons[w].get("role_menu_secondary") or []
    monk = ("shield_break" in menu("2H_COMBATSTAFF_MORGANA")
            and "purge" not in menu("2H_COMBATSTAFF_MORGANA")
            and "purge" not in menu2("2H_COMBATSTAFF_MORGANA"))
    hammer = ("shield_break" in menu2("2H_HAMMER")
              and "purge" not in menu("2H_HAMMER")
              and "purge" not in menu2("2H_HAMMER"))
    claws = "shield_break" in menu("2H_CLAWPAIR")
    # true purges untouched: Heavy Mace's Battle Howl stays E-primary
    hm = "purge" in menu("2H_MACE")
    lc = "purge" in menu("MAIN_CURSEDSTAFF_UNDEAD")
    check("R9 shield-break split: Black Monk E-primary shield_break (not "
          "purge), hammers Q-secondary, Claws E shield-break; true "
          "purges (Heavy Mace, Lifecurse) untouched",
          monk and hammer and claws and hm and lc,
          f"monk={menu('2H_COMBATSTAFF_MORGANA')} "
          f"hammer2={menu2('2H_HAMMER')} heavy={menu('2H_MACE')}")


def t_gear_classification():
    # Equipment classification (owner 2026-08-25): tree stats carry the
    # class identity — "you need to pull numbers to classify items" —
    # and the numbers must agree with the tree id wherever stats exist.
    import json as _json
    rep = _json.load(open(os.path.join(ROOT, "pipeline", "out",
                                       "roles_report.json"),
                          encoding="utf-8"))
    items = rep.get("items") or []
    e = Engine()
    worn = [k for k, g in e.gear.items()
            if g.get("slot") in ("armor", "head", "shoes", "offhand")]
    covered = {it["id"] for it in items} == set(worn)
    statted = [it for it in items if it["class_basis"] == "stats"]
    agree = all(it["class"] in it["id"].lower().split("_")
                or it["class"] in it["id"].lower()
                for it in statted if it["class"])
    hellion = next(it for it in items if it["id"] == "ARMOR_LEATHER_HELL")
    affinity = ("sustained_brawler" in hellion["role_affinity"]
                and "stopper_tank" not in hellion["role_affinity"])
    plate = next(it for it in items if it["id"] == "ARMOR_PLATE_KEEPER")
    plate_ok = "stopper_tank" in plate["role_affinity"]
    # tree passives count toward the class identity (owner: "most cloth
    # users will take the damage passive")
    cloth = next(it for it in items if it["id"] == "ARMOR_CLOTH_FEY")
    passives = ("PASSIVE_ARMOR_INCREASED_DAMAGE" in cloth["tree_passives"]
                and len(next(it for it in items
                             if it["id"] == "ARMOR_PLATE_SET2")
                        ["tree_passives"]) > 0)
    check("R10 gear classification: every worn item on the board, "
          "numbers-derived class agrees with the tree id, Hellion "
          "affines to brawler seats, Judicator to tank seats, tree "
          "passives recorded (cloth carries the damage passive)",
          covered and agree and affinity and plate_ok and passives,
          f"items={len(items)} statted={len(statted)} "
          f"hellion={hellion['role_affinity']} "
          f"cloth_passives={cloth['tree_passives']}")


def t_offhand_profiles():
    # Owner 2026-08-25: "for offhands, they have no active ability, their
    # usefulness comes from the stats. so to properly classify them, you
    # have to get the stats" — the bank had them all along; the dataset
    # now carries the identity fields and classification reads them.
    e = Engine()
    horn = e.gear["OFF_HORN_KEEPER"].get("stats") or {}
    cdr = horn.get("magiccooldownreduction", 0) > 0
    tower = e.gear["OFF_TOWERSHIELD_UNDEAD"]
    tower_tank = ("stopper_tank" in (tower.get("role_affinity") or [])
                  and (tower.get("stats") or {})
                  .get("bonusdefensevsplayers", 0) > 0)
    horn_aff = e.gear["OFF_HORN_KEEPER"].get("role_affinity") or []
    horn_ok = "main_healer" in horn_aff and "stopper_tank" not in horn_aff
    check("R11 offhand stat profiles: Mistcaller carries its cooldown "
          "reduction and affines to caster/healer seats (not tank); "
          "Tower Shield's defense+threat affines to tank seats",
          cdr and tower_tank and horn_ok,
          f"horn={horn} horn_aff={horn_aff}")


if __name__ == "__main__":
    t_role_book()
    t_ruled_memberships()
    t_detection()
    t_engage_flag()
    t_descriptive_only()
    t_original_bug_case()
    t_gear_effects()
    t_tiered_sweep()
    t_shield_break_split()
    t_gear_classification()
    t_offhand_profiles()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} role-layer tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)

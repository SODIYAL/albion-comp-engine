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

Increment 2 (kit doctrine, owner-approved 2026-08-25: "yes its the whole
build. infact we might even need to include food, potion and capes and
you are right about passive defaults"):

  R12 generated kits wear the seat's uniform: Incubus/Grailseeker chest
      options are plate only under role="auto" (the everyone-gets-Hellion
      bug is dead); role=None keeps the ungated back-compat pool; manual
      scoring is never blocked.
  R13 the Leering Cane pairing is EMERGENT physics, not a hand list: the
      CC-duration stat ships in the dataset and multiplies the wearer's
      own CC caps, so the cane is worth something on Incubus (root 5)
      and exactly nothing on Great Fire (no CC).
  R14 passive doctrine (owner defaults): cloth pieces resolve the damage
      passive for every seat class, plate resolves CC-duration for
      frontline and CCR otherwise — dumps-cited ids and magnitudes
      stamped per piece; build_extra(role=) applies the stat channel.
  R15 kit doctrine pools derive from observed reference builds (cited
      build ids) and ship per role; chest doctrine never leaves the
      uniform.
  R16 options carry doctrine/carries annotations: Realmbreaker's chest
      options include Royal Jacket flagged as the cooldown_banner
      carrier; when a slot has doctrine evidence the kit picks from it.

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


def t_kit_uniform_gate():
    # R12 — increment 2's kill shot for the original bug: a GENERATED kit
    # starts from the seat's uniform; the comp-marginal only ranks within
    # it. Manual picks still score anything (role_advisory flags them).
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    classes = lambda ko: {e.gear[o["gear"]].get("gear_class")
                          for o in ko["options"].get("armor", [])}
    inc = e.kit_options("MAIN_MACE_HELL", top_n=300)
    grail = e.kit_options("2H_QUARTERSTAFF_AVALON", top_n=300)
    inc_ids = [o["gear"] for o in inc["options"]["armor"]]
    gated = (classes(inc) == {"plate"} and classes(grail) == {"plate"}
             and "ARMOR_LEATHER_HELL" not in inc_ids)
    unc = e.kit_options("MAIN_MACE_HELL", top_n=300, role=None)
    back_compat = "ARMOR_LEATHER_HELL" in [
        o["gear"] for o in unc["options"]["armor"]]
    # manual scoring untouched: a Hellion-Jacket Incubus build still
    # evaluates (build_extra never gates)
    manual = e.build_extra("MAIN_MACE_HELL", None, ["ARMOR_LEATHER_HELL"])
    check("R12 uniform-gated kits: Incubus + Grailseeker chests are plate "
          "only; role=None keeps the ungated pool; manual builds score",
          gated and back_compat and bool(manual),
          f"incubus classes={sorted(str(c) for c in classes(inc))} "
          f"armor={inc_ids[:3]}")


def t_cc_duration_pairing():
    # R13 — the owner's Leering Cane ruling ("incubus is mostly paired
    # with leering cane for its +cc duration"), wired as PHYSICS: the
    # stat multiplies the wearer's own CC caps, so the pairing emerges
    # for every CC weapon and never for a CC-less one. No hand list.
    e = Engine()
    cane = e.gear["OFF_JESTERCANE_HELL"].get("stats") or {}
    shipped = cane.get("bonusccdurationvsplayers", 0) > 0
    cc = ("stun", "root", "slow", "silence")
    gain = lambda w: sum(
        e.build_extra(w, None, ["OFF_JESTERCANE_HELL"]).get(c, 0.0)
        - e.member_extra(w).get(c, 0.0) for c in cc)
    inc_gain, fire_gain = gain("MAIN_MACE_HELL"), gain("2H_FIRESTAFF")
    check("R13 emergent CC-duration pairing: Leering Cane's stat ships "
          "and multiplies Incubus's CC caps; Great Fire (no CC) gains 0",
          shipped and inc_gain > 1e-9 and abs(fire_gain) < 1e-9,
          f"cane stats={cane} incubus_gain={inc_gain:.3f} "
          f"fire_gain={fire_gain:.3f}")


def t_passive_doctrine():
    # R14 — owner-confirmed defaults (2026-08-25): cloth = the damage
    # passive (Aggression, +8% damage & healing cast), plate = CC
    # duration for tanks (Authority) and CCR otherwise (Tenacity),
    # leather = cooldown rate (Quick Thinker, display-only channel).
    # Ids resolve from each piece's own dumps passive menu; magnitudes
    # parse from the spell descriptions — nothing hand-numbered.
    e = Engine()
    cloth = (e.gear["ARMOR_CLOTH_SET1"].get("doctrine_passives") or {})
    plate = (e.gear["ARMOR_PLATE_KEEPER"].get("doctrine_passives") or {})
    leather = (e.gear["ARMOR_LEATHER_HELL"].get("doctrine_passives") or {})
    cloth_ok = all(
        (cloth.get(sc) or {}).get("id") == "PASSIVE_ARMOR_INCREASED_DAMAGE"
        and abs((cloth.get(sc) or {}).get("value", 0) - 0.08) < 1e-9
        for sc in ("dps", "healer", "support", "frontline"))
    plate_ok = ((plate.get("frontline") or {}).get("id")
                == "PASSIVE_ARMOR_CCDURATION"
                and (plate.get("dps") or {}).get("id")
                == "PASSIVE_ARMOR_INCREASED_CCR")
    leather_ok = ((leather.get("dps") or {}).get("id")
                  == "PASSIVE_ARMOR_CD_REDUCTION")
    # the stat channel: a cloth chest on a ranged_aoe seat multiplies
    # damage caps by the passive on top of the chest's own % stat
    with_role = e.build_extra("2H_FIRESTAFF", None, ["ARMOR_CLOTH_SET1"],
                              role="ranged_aoe")
    without = e.build_extra("2H_FIRESTAFF", None, ["ARMOR_CLOTH_SET1"])
    dmg = lambda x: x.get("burst_aoe", 0.0) + x.get("sustained_dps", 0.0)
    channel = dmg(with_role) > dmg(without) + 1e-9
    # frontline plate: Authority multiplies the wearer's own CC caps —
    # Incubus's DEFAULT combo carries slow (Snare Charge, the owner's
    # doctrine pick), so slow is the cap the channel must move
    tank_role = e.build_extra("MAIN_MACE_HELL", None, ["ARMOR_PLATE_KEEPER"],
                              role="stopper_tank")
    tank_bare = e.build_extra("MAIN_MACE_HELL", None, ["ARMOR_PLATE_KEEPER"])
    cc_channel = (tank_role.get("slow", 0.0) > tank_bare.get("slow", 0.0)
                  + 1e-9)
    check("R14 passive doctrine: dumps-resolved ids + magnitudes per seat "
          "class; damage passive and Authority feed the stat channels",
          cloth_ok and plate_ok and leather_ok and channel and cc_channel,
          f"cloth={cloth.get('dps')} plate_fl={plate.get('frontline')} "
          f"dmg {dmg(without):.2f}->{dmg(with_role):.2f}")


def t_kit_doctrine_evidence():
    # R15 — doctrine pools are evidence-led (roles-design.md increment 2:
    # "kit = the assigned role's uniform, evidence-led — reference builds
    # first"): observed kits of a seat's member weapons, cited by
    # build_id, shipped per role; chest doctrine never leaves the
    # uniform.
    import json as _json
    e = Engine()
    rep = _json.load(open(os.path.join(ROOT, "pipeline", "out",
                                       "roles_report.json"),
                          encoding="utf-8"))
    kd = rep.get("kit_doctrine") or {}
    roles = {r["id"]: r for r in (e.data.get("roles") or [])}
    seats = [rid for rid, r in roles.items()
             if ((r.get("uniform") or {}).get("chest"))]
    shipped = any((roles[rid].get("kit") or {}) for rid in seats)
    cited = all(
        ent.get("sources")
        for rid in kd for slot in (kd[rid].get("slots") or {})
        for ent in (kd[rid]["slots"][slot] or []))
    uniform_ok = True
    for rid in seats:
        uni = set((roles[rid].get("uniform") or {}).get("chest") or [])
        for gid in (roles[rid].get("kit") or {}).get("armor", []):
            if (e.gear.get(gid) or {}).get("gear_class") not in uni:
                uniform_ok = False
    in_catalog = all(gid in e.gear
                     for rid in seats
                     for slot, ids in (roles[rid].get("kit") or {}).items()
                     for gid in ids)
    check("R15 kit doctrine: observed-build pools ship per seat with "
          "build-id citations; chest doctrine stays inside the uniform",
          shipped and cited and uniform_ok and in_catalog and bool(kd),
          f"seats with doctrine="
          f"{[r for r in seats if roles[r].get('kit')][:5]}")


def t_kit_annotations():
    # R16 — variants surface where the evidence says they live: Royal
    # Jacket (leather, uniform-legal for the brawler seat) appears in
    # Realmbreaker's chest options carrying cooldown_banner — the
    # owner's "royal jacket for extra cooldowns if team needs" example.
    # Options carry doctrine/carries keys; a slot with doctrine evidence
    # picks its kit from the doctrine tier.
    e = Engine(content="blackzone_roam", size=20, style="brawl")
    ko = e.kit_options("2H_AXE_AVALON", top_n=300)
    armor = ko["options"]["armor"]
    royal = next((o for o in armor if o["gear"] == "ARMOR_LEATHER_ROYAL"),
                 None)
    carries = royal is not None and "cooldown_banner" in (
        royal.get("carries") or [])
    annotated = all("doctrine" in o and "carries" in o
                    for slot in ko["options"] for o in ko["options"][slot])
    tiered = True
    for slot, opts in ko["options"].items():
        if any(o["doctrine"] for o in opts):
            if not ko["kit"][slot]["doctrine"]:
                tiered = False
    check("R16 kit annotations: Royal Jacket surfaces on Realmbreaker "
          "carrying cooldown_banner; options annotated; doctrine tier "
          "wins the pick",
          carries and annotated and tiered,
          f"royal={royal and {k: royal[k] for k in ('doctrine', 'carries')}} "
          f"slots={sorted(ko['options'])}")


def t_grading_rulings():
    # R17 — the 2026-08-26 owner grading pass (15 rulings, the first full
    # roles_report board review): memberships corrected in roles.yaml,
    # kit-doctrine drop/add overrides applied on the mined pools, the
    # Leering Cane affinity override, and the dive-dagger 7+ viability
    # exclusion. Pins the whole batch so a rebuild can never regress it.
    import json as _json
    e = Engine()
    menus = {w: (e.weapons[w].get("role_menu") or []) for w in e.weapons}
    memb = (
        menus.get("MAIN_ARCANESTAFF_UNDEAD") == ["engage_tank"]        # Witchwork: clump, not cleanse
        # Black Monk: purges ENEMY shields (never shield_support); the
        # seat-all pass (owner:2026-09-01) added its off_tank SEAT — the
        # 2026-08-26 ruling's substance (function, not support seat) holds
        and menus.get("2H_COMBATSTAFF_MORGANA") == ["off_tank", "shield_break"]
        and menus.get("2H_HOLYSTAFF") == ["brawl_healer"]              # Great Holy: brawl anchor only
        and menus.get("2H_GLACIALSTAFF") == ["ranged_aoe"]             # Glacial: dps, not support
        and menus.get("2H_ICECRYSTAL_UNDEAD") == ["ranged_aoe"]        # Permafrost: dps
        # NAME MIX-UP resolved owner:2026-09-02 — this id is STILLGAZE
        # ("a d tank" -> stopper_tank; killboard 6/6 plate), not
        # Chillhowl; Chillhowl is MAIN_FROSTSTAFF_AVALON, now off every
        # menu ("mostly a corrupted dungeon weapon") beside its standing
        # >=10 exclusion
        and menus.get("2H_SHAPESHIFTER_CRYSTAL") == ["stopper_tank"]
        and not menus.get("MAIN_FROSTSTAFF_AVALON")
        and menus.get("2H_ARCANESTAFF") == ["shield_support"]          # Great Arcane: the setup role
        and not menus.get("2H_IRONCLADEDSTAFF"))                       # Iron-clad: off stopper menu
    rep = _json.load(open(os.path.join(ROOT, "pipeline", "out",
                                       "roles_report.json"),
                          encoding="utf-8"))
    kd = rep["kit_doctrine"]

    def pool(rid, slot):
        return [x["id"] for x in kd[rid]["slots"].get(slot) or []]
    kits = (
        "T7_POTION_STONESKIN" not in pool("engage_tank", "potion")
        and "CAPEITEM_FW_LYMHURST" not in pool("stopper_tank", "cape")
        and "OFF_TOME_CRYSTAL" not in pool("stopper_tank", "offhand")
        and "OFF_JESTERCANE_HELL" in pool("stopper_tank", "offhand")
        and "OFF_TOWERSHIELD_UNDEAD" not in pool("brawl_healer", "offhand")
        and "OFF_TORCH_CRYSTAL" in pool("brawl_healer", "offhand")
        and all("overrides" in kd[r] for r in ("engage_tank",
                                               "stopper_tank",
                                               "brawl_healer")))
    cane = (e.gear.get("OFF_JESTERCANE_HELL") or {}).get("role_affinity")
    e7 = Engine(content="blackzone_roam", size=7)
    e3 = Engine(content="blackzone_roam", size=3)
    daggers = {"2H_DAGGERPAIR", "2H_DUALSICKLE_UNDEAD"}
    dag = (not (daggers & set(e7.suggest_pool()))
           and daggers <= set(e3.suggest_pool())
           and daggers <= e7._excluded)
    check("R17 owner grading 2026-08-26: eight menu corrections, five "
          "kit-doctrine overrides, Leering Cane is stopper kit, dive "
          "daggers excluded at 7+ (trio stays open)",
          memb and kits and cane == ["stopper_tank"] and dag,
          f"monk={menus.get('2H_COMBATSTAFF_MORGANA')} "
          f"stopper_offhand={pool('stopper_tank', 'offhand')} "
          f"cane={cane} daggers@7={not (daggers & set(e7.suggest_pool()))}")


def t_weapon_doctrine():
    # R18 — per-weapon doctrine + effect quotas (owner design 2026-08-26,
    # the Demon-Armor-on-Hand-of-Justice case): a weapon's OWN observed
    # kit outranks the seat aggregate (Polehammer wears Knight in 5 of
    # its 6 builds); chests granting a typed gear effect are comp-level
    # allocations — excluded from the per-weapon tier, tagged in the
    # seat pool, and quota-mined per observed roster (cb_clonepeek
    # fields 4 reflect shells; that is why its HoJ wears Demon Armor).
    import json as _json
    e = Engine(content="blackzone_roam", size=20)
    ko = e.kit_options("2H_POLEHAMMER", top_n=5)
    top = ko["kit"]["armor"]
    # doctrine_n TRACKS CORPUS SIZE — [5, 5] until the 23 albioncompo comps
    # (2026-08-29), [9, 12] until the killboard stream joined the mining
    # (2026-09-01, owner: "base it on seen evidence from the data we
    # harvested"), [63, 95] now. The MECHANISM is what this pins:
    # Polehammer's own observed kit (weapon-level doctrine) outranks the
    # seat aggregate, and it still resolves to Knight by a clear majority.
    # A change here after an evidence import is expected; a change in
    # `gear` or `doctrine` is not.
    ph = (top["gear"] == "ARMOR_PLATE_SET2"
          and top["doctrine"] == "weapon" and top["doctrine_n"] == [63, 95])
    hoj = e.kit_options("2H_HAMMER_AVALON", top_n=10)
    demon = next((o for o in hoj["options"]["armor"]
                  if o["gear"] == "ARMOR_PLATE_HELL"), None)
    dem = (demon is not None and demon["doctrine"] == "seat"
           and "reflect_shell" in (demon["carries"] or []))
    kw = ((e.roles.get("engage_tank") or {}).get("kit_weapon")
          or {}).get("2H_HAMMER_AVALON") or {}
    effect_items = {"ARMOR_PLATE_HELL", "ARMOR_PLATE_KEEPER",
                    "ARMOR_PLATE_SET3", "ARMOR_LEATHER_ROYAL",
                    "ARMOR_LEATHER_HELL"}
    clean = not (effect_items
                 & {p[0] for slot in kw for p in kw[slot]})
    rep = _json.load(open(os.path.join(ROOT, "pipeline", "out",
                                       "roles_report.json"),
                          encoding="utf-8"))
    q = rep.get("effect_quotas") or {}
    cb = next((r for r in q.get("comps") or []
               if r["comp"].startswith("cb_clonepeek")), None)
    quota = (cb is not None and cb["copies"].get("reflect_shell") == 4
             and (q["summary"]["reflect_shell"]["with_any"] or 0) >= 6)
    check("R18 per-weapon doctrine: Polehammer wears its own observed "
          "Knight (5/5); Demon Armor on HoJ reads as seat-pool reflect "
          "carrier, never weapon identity; quotas mined per roster",
          ph and dem and clean and quota,
          f"pole_top={top['gear']}/{top['doctrine']}/{top['doctrine_n']} "
          f"demon={demon and (demon['doctrine'], demon['carries'])} "
          f"cb_reflect={cb and cb['copies'].get('reflect_shell')}")


def t_fail_closed_generation():
    # R19 — FAIL-CLOSED GENERATION (owner ruling 2026-09-01, "fix the
    # underlying issue which allows these items and builds and kits to
    # slide into the team comp"): the kit-suggestion channel only speaks
    # evidence. (a) A seatless weapon gets NO kit and NO options — the
    # old ungated fallback marginal-ranked the whole catalog, and in any
    # full comp the one uncovered capability (usually silence) handed
    # the same off-role helm (Hellion Hood) to every seatless member.
    # (b) A seated slot with no doctrine tier stays UNSET. (c) role=None
    # stays the explicit diagnostic escape. (d) Manual builds still
    # score anything — the gate is suggestion-layer only.
    e = Engine(content="faction_war", size=15, style="brawl")
    # since the seat-all pass (owner:2026-09-01) every weapon holds a seat,
    # so the seatless fixture is SYNTHESIZED: strip one weapon's menu
    # in-memory — the fail-closed mechanism itself is what this pins
    seatless = "MAIN_1HCROSSBOW"
    e.weapons[seatless]["role_menu"] = []
    assert e.primary_seat(seatless) is None, "fixture: menu strip failed"
    ko = e.kit_options(seatless, top_n=300)
    a = ko["kit"] == {} and ko["options"] == {} and ko["seat"] is None
    ko_party = e.kit_options(seatless, party=["MAIN_MACE"], top_n=300)
    a2 = ko_party["kit"] == {} and ko_party["options"] == {}
    # (b) every option every seated weapon is offered is doctrine-cited
    seated = e.kit_options("MAIN_MACE", top_n=300)
    b = (seated["seat"] == "engage_tank" and seated["kit"]
         and all(o["doctrine"] in ("weapon", "seat")
                 for opts in seated["options"].values() for o in opts))
    # (c) the diagnostic escape still serves the full catalog
    unc = e.kit_options(seatless, top_n=300, role=None)
    c = bool(unc["options"].get("head"))
    # (d) manual builds score: the exact Hellion kit still evaluates
    d = bool(e.build_extra(seatless, None, ["HEAD_LEATHER_HELL"]))
    check("R19 fail-closed generation: seatless weapon -> no kit/options "
          "(context-free and comp-aware); seated options all doctrine-"
          "cited; role=None diagnostic escape intact; manual builds score",
          a and a2 and b and c and d,
          f"seatless kit={ko['kit']} seat={ko['seat']} "
          f"seated_seat={seated['seat']} "
          f"seated_slots={sorted(seated['options'])} manual={d}")


def t_observed_build_overlay():
    # R20 — THE OBSERVED-BUILD OVERLAY (owner ruling 2026-09-01: "i want
    # gear that each seat is wearing to actually be based on what real
    # people wear. the engine keeps making up some random builds"): the
    # KIT pick follows the conditional-modal build mined from killboard
    # builds — a coherent fielded combination, never per-slot marginal
    # assembly. (a) archetypes ship in the book with step counts;
    # (b) the kit pick carries observed_build [n, of] and matches the
    # archetype item; (c) a slot the weapon's own archetype lacks falls
    # back to the seat archetype or plain ranking; (d) role=None
    # (diagnostic) gets no overlay.
    e = Engine(content="blackzone_roam", size=20)
    rec = e.roles.get("engage_tank") or {}
    wb = (rec.get("kit_weapon_build") or {}).get("2H_POLEHAMMER") or {}
    a = ("armor" in wb and wb["armor"][0] == "ARMOR_PLATE_SET2"
         and wb["armor"][1] >= 2 and rec.get("kit_build"))
    ko = e.kit_options("2H_POLEHAMMER", top_n=5)
    top = ko["kit"].get("armor") or {}
    b = (top.get("gear") == wb["armor"][0]        # the fielded item leads
         and top.get("observed_build") == wb["armor"][1:3])   # [n, of]
    # (c) every kit slot is either archetype-annotated or plain-ranked —
    # and at least one slot of a thin-basket weapon uses the fallback
    ko_lx = Engine(content="faction_war", size=15,
                   style="brawl").kit_options("MAIN_1HCROSSBOW")
    slots = ko_lx["kit"] or {}
    c = bool(slots) and any(not v.get("observed_build")
                            for v in slots.values()) \
        and any(v.get("observed_build") for v in slots.values())
    unc = e.kit_options("2H_POLEHAMMER", top_n=5, role=None)
    d = not any(o.get("observed_build")
                for opts in unc["options"].values() for o in opts)
    check("R20 observed-build overlay: archetype ships with step counts; "
          "the kit pick IS the fielded combination (observed_build "
          "annotated); thin slots fall back; diagnostic mode unoverlaid",
          bool(a) and b and c and d,
          f"pole_armor={wb.get('armor')} top={top.get('gear')}/"
          f"{top.get('observed_build')} lx_slots={len(slots)}")


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
    t_kit_uniform_gate()
    t_cc_duration_pairing()
    t_passive_doctrine()
    t_kit_doctrine_evidence()
    t_kit_annotations()
    t_grading_rulings()
    t_weapon_doctrine()
    t_fail_closed_generation()
    t_observed_build_overlay()
    passed = sum(1 for _n, ok, _d in RESULTS if ok)
    print("=" * 74)
    print(f"{passed}/{len(RESULTS)} role-layer tests passed")
    sys.exit(0 if passed == len(RESULTS) else 1)

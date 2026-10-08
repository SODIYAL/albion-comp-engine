"use strict";

/*
 * The build on the sheet (platform phase 12): the loadout the planner
 * saved for each slot of a CTA, named. A CTA's share hash carries, per
 * member of the comp, the gear and the Q/W/passive picks the planner
 * saved (the g= parameter, the codec in _loadout.js) beside the weapons
 * (p=). This module reads them for every slot of the sheet and names
 * them from the page's own tables: helm, armor, boots, cape, off-hand,
 * potion and food with their art (GEAR), the picked spells and the
 * weapon's E (SPELLS). A slot whose weapon no longer matches the comp's
 * member, a slot with no weapon, and a comp saved without loadouts each
 * say so.
 *
 * Display only: nothing here scores, and nothing is written. build.py
 * inlines this file as its own <script> after _roster.js. The sheet
 * hands its roster over as a DOM event (sheet-read) after every render;
 * this module paints into the su-build place each slot cell leaves
 * empty, which the sign-up module never fills. Two parts:
 *   pure    - the hash's members and loadouts, the build per slot
 *             (tests/test_sheet_build.js)
 *   UI      - the listener and the painter
 */


/* --------------------------------------------------------------- pure */

/* the gear slots of a build, in the codec's order, and their names */
const BUILD_GEAR = ["head", "armor", "shoes", "cape", "offhand", "potion", "food"];
const BUILD_GEAR_NAMES = { head: "Helm", armor: "Armor", shoes: "Boots", cape: "Cape", offhand: "Off-hand", potion: "Potion", food: "Food" };

/* the spell slots a build picks, the codec's field for each and the
   pool it indexes */
const BUILD_SPELLS = [["q", "Q", "q"], ["w", "W", "w"], ["p", "Passive", "passive"]];

/* what a slot's build place says when there is no build to show */
const BUILD_MSG = {
  none: "This slot takes any weapon: no build to show.",
  changed: "The slot's weapon changed after the comp was saved: no build for it. Set one in the planner and save the CTA again.",
  unset: "No build saved for this slot. Set it in the planner and save the CTA again."
};


/* the members and loadouts a share hash carries: the weapons by
   position (an empty entry is an open slot of a link built from a
   comp's slots, which keeps every later slot at its position) and the
   decoded loadout per member (an array with holes) */
function hashMembers(shareHash, decode) {
  const params = new URLSearchParams(String(shareHash || "").replace(/^#/, ""));
  const listed = params.get("p");
  const weapons = listed ? listed.split(",") : [];
  const loadouts = decode(params.get("g") || "") || [];
  return { weapons, loadouts };
}


/* The build per slot position. A slot is the comp's member at position
   minus one; its build holds when the slot still names that member's
   weapon. tables: { decode, gear, spells } (the codec, GEAR, SPELLS). */
function sheetBuilds(shareHash, slots, tables) {
  const { weapons, loadouts } = hashMembers(shareHash, tables.decode);
  const out = {};

  for (const slot of slots || []) {
    const i = Number(slot.position) - 1;
    const member = weapons[i] || null;
    if (!slot.weapon_id) { out[slot.position] = { state: "none" }; continue; }
    if (member !== slot.weapon_id) { out[slot.position] = { state: "changed", weapon: slot.weapon_id }; continue; }

    const L = loadouts[i] || {};
    const gear = BUILD_GEAR.map(s => {
      const key = L[s];
      const item = key && tables.gear && tables.gear[key];
      return item ? { slot: s, label: BUILD_GEAR_NAMES[s], key, name: item.name || key, item: item.example_item || "" } : null;
    }).filter(Boolean);
    const pools = (tables.spells && tables.spells[member]) || {};
    const spells = BUILD_SPELLS.map(([field, label, pool]) => {
      const pick = Number.isInteger(L[field]) ? (pools[pool] || [])[L[field]] : null;
      return pick ? { slot: field, label, name: pick[1] || pick[0] } : null;
    }).filter(Boolean);
    const e = (pools.e || []).map(x => x[1] || x[0]);

    out[slot.position] = gear.length || spells.length
      ? { state: "set", weapon: member, gear, spells, e }
      : { state: "unset", weapon: member };
  }

  return out;
}


/* ----------------------------------------------------------------- UI */

(function buildUI() {
  if (typeof document === "undefined") {
    return;
  }

  const page = document.getElementById("signup-page");

  if (!page) {
    return;
  }

  const tables = () => ({
    decode: typeof loadoutDecode === "function" ? loadoutDecode : () => [],
    gear: typeof GEAR !== "undefined" ? GEAR : {},
    spells: typeof SPELLS !== "undefined" ? SPELLS : {}
  });

  /* gear art is hotlinked (the planner's own policy for the picker): the
     page's icon when it has one, else the render service with a retry */
  function gearArt(piece) {
    const own = typeof ICONS !== "undefined" && ICONS[piece.key];
    const src = own || (piece.item ? `https://render.albiononline.com/v1/item/${encodeURIComponent(piece.item)}.png?size=64` : "");
    if (!src) return null;
    const img = document.createElement("img");
    img.src = src;
    img.alt = "";
    img.width = 24;
    img.height = 24;
    img.loading = "lazy";
    if (!own && typeof loArtRetry === "function") img.addEventListener("error", () => loArtRetry(img));
    return img;
  }

  function note(text) {
    const p = document.createElement("p");
    p.className = "su-build-note";
    p.textContent = text;
    return p;
  }

  function paint(place, build) {
    if (!build || build.state !== "set") {
      place.replaceChildren(note(BUILD_MSG[(build && build.state) || "unset"]));
      return;
    }
    const gear = document.createElement("ul");
    gear.className = "su-build-gear";
    gear.setAttribute("aria-label", "Gear");
    for (const piece of build.gear) {
      const li = document.createElement("li");
      li.className = "su-gear";
      li.title = `${piece.label}: ${piece.name}`;
      const art = gearArt(piece);
      if (art) li.append(art);
      const name = document.createElement("span");
      name.textContent = piece.name;
      li.append(name);
      gear.append(li);
    }
    const spells = document.createElement("p");
    spells.className = "su-build-spells";
    const bits = build.spells.map(s => [s.label, s.name]);
    if (build.e.length) bits.push(["E", build.e.join(" / ")]);
    for (const [label, name] of bits) {
      const pick = document.createElement("span");
      pick.className = "su-build-pick";
      const k = document.createElement("span");
      k.className = "su-build-key";
      k.textContent = label;
      pick.append(k, ` ${name}`);
      spells.append(pick);
    }
    place.replaceChildren(...(build.gear.length ? [gear] : []), ...(bits.length ? [spells] : []));
  }

  /* after every render of the sheet, every slot's place is filled, open
     or folded, so unfolding never waits */
  document.addEventListener("sheet-read", e => {
    const d = e.detail;
    const places = page.querySelectorAll("[data-su-build]");
    if (!d || !d.event || !d.slots) {
      for (const place of places) place.replaceChildren();
      return;
    }
    const builds = sheetBuilds(d.event.share_hash, d.slots, tables());
    for (const place of places) paint(place, builds[place.dataset.suBuild]);
  });
})();

#!/usr/bin/env python3
"""
Generate the effect -> capability reference page.

This is a REVIEW-BY-EXCEPTION page, not a data-entry form. The mapping in
pipeline/effect_map.yaml is already complete: every weapon-reachable effect is
analysed, with capabilities per target direction. The page exists so a domain
expert can scan it and flag what is wrong — which is expected to happen while
real comps are being built, not in one sitting.

Usage:  py -3 pipeline/build_effect_review.py   ->  review/effects.html
"""
import json, os, sys

try:
    import yaml
except ImportError:
    sys.exit("pip install pyyaml")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT = os.path.join(HERE, "out")

DIR_LABEL = {"enemy": "on enemies", "ally": "on allies", "self": "on self"}
GROUP_ORDER = ["control", "movement", "durability", "denial", "offense", "guard",
               "removal", "ignored"]


def group_of(key, cls):
    if cls == "removal":
        return "removal"
    if cls == "guard":
        return "guard"
    base = key.rstrip("+-")
    if base in ("stun", "root", "silence", "knockback", "forced_movement"):
        return "control"
    if base in ("dash", "invisibility") or base.startswith("movespeed"):
        return "movement"
    if ("armor" in base or "resistance" in base or "defense" in base
            or "hitpointsmax" in base or "invincibility" in base
            or "crowdcontrolresistance" in base or "regeneration" in base):
        return "durability"
    if "heal" in base:
        return "denial" if key.endswith("-") else "offense"
    return "denial" if key.endswith("-") else "offense"


def main():
    cat = json.load(open(os.path.join(OUT, "effect_catalogue.json"), encoding="utf-8"))
    spells = json.load(open(os.path.join(OUT, "spell_index.json"), encoding="utf-8"))
    lines_json = json.load(open(os.path.join(OUT, "weapon_lines.json"), encoding="utf-8"))
    emap = yaml.safe_load(open(os.path.join(HERE, "effect_map.yaml"), encoding="utf-8"))

    def wname(key):
        n = lines_json.get(key, {}).get("name", key)
        for p in ("Adept's ", "Novice's ", "Journeyman's ", "Expert's ",
                  "Master's ", "Grandmaster's ", "Elder's "):
            if n.startswith(p):
                return n[len(p):]
        return n

    owner = {}
    for wkey, line in lines_json.items():
        for slot, ids in line["spells"].items():
            for sid in ids:
                owner.setdefault(sid, []).append((wkey, slot))

    def spell_entry(sid, direct):
        own = owner.get(sid, [])
        return {"id": sid, "name": spells.get(sid, {}).get("name", sid),
                "slot": own[0][1].upper() if own else "",
                "weapon": wname(own[0][0]) if own else "", "direct": direct}

    rows = []
    for key, e in cat["effects"].items():
        if not e["weapon_line_count"]:
            continue
        m = emap["effects"].get(key, {}) or {}
        dirs = [{"dir": d, "label": DIR_LABEL.get(d, d), "caps": m[d]}
                for d in ("enemy", "ally", "self") if isinstance(m.get(d), list)]
        picks = ([spell_entry(s, True) for s in e["direct_spells"][:4]] +
                 [spell_entry(s, False) for s in e["via_spells"][:3]])[:5]
        ex = next((p["id"] for p in picks if p["direct"] and p["id"] in spells),
                  next((p["id"] for p in picks if p["id"] in spells), None))
        rows.append({
            "key": key,
            "group": "ignored" if m.get("ignore") else group_of(key, e["class"]),
            "cls": e["class"],
            "definition": e.get("definition") or "",
            "lines": e["weapon_line_count"],
            "targets": list(e["targets"])[:4],
            "prose": e["prose_flag"],
            "dirs": dirs,
            "ignored": bool(m.get("ignore")),
            "note": (m.get("note") or "").strip(),
            "grounds_nothing": bool(dirs) and all(not d["caps"] for d in dirs),
            "spells": picks,
            "weapons": [wname(w) for w in e.get("weapon_lines", [])[:6]],
            "weapons_more": max(0, e["weapon_line_count"] - 6),
            "ex_name": spells.get(ex, {}).get("name", ex) if ex else "",
            "ex_direct": bool(ex and any(p["id"] == ex and p["direct"] for p in picks)),
            "desc": (spells.get(ex, {}).get("description") or "")[:240] if ex else "",
        })
    rows.sort(key=lambda r: (GROUP_ORDER.index(r["group"]), -r["lines"]))

    payload = {"rows": rows, "proposed": emap.get("proposed_capabilities", {}),
               "groups": GROUP_ORDER}
    data = json.dumps(payload, separators=(",", ":")).replace("</", "<\\/")

    os.makedirs(os.path.join(ROOT, "review"), exist_ok=True)
    path = os.path.join(ROOT, "review", "effects.html")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(PAGE.replace("/*__DATA__*/", data))

    total_caps = sum(len(d["caps"]) for r in rows for d in r["dirs"])
    print(f"wrote review/effects.html — {len(rows)} effects, "
          f"{total_caps} capability assignments across "
          f"{sum(len(r['dirs']) for r in rows)} direction rules")


PAGE = r"""<title>Effect Capability Map</title>
<style>
:root{
  --bg:#E8EBEE; --surface:#F4F6F8; --surface-2:#DEE3E8; --sunk:#D6DCE2;
  --ink:#161C23; --ink-2:#4A5763; --ink-3:#71808D;
  --rule:#C6CED6; --rule-2:#B2BCC6;
  --brass:#8A6420; --brass-bright:#A87C32; --brass-wash:#EFE6D4;
  --gap:#A63D37; --gap-wash:#F2DEDC; --ok:#3F6B4C; --ok-wash:#DFEAE1;
  --over:#5E4E8C; --over-wash:#E6E1F2;
  --shadow:0 1px 2px rgba(22,28,35,.07), 0 8px 24px -12px rgba(22,28,35,.18);
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0D1218; --surface:#141B23; --surface-2:#1D262F; --sunk:#0A0F14;
  --ink:#E4E9EE; --ink-2:#94A3B1; --ink-3:#6B7A88;
  --rule:#29343E; --rule-2:#38454F;
  --brass:#D2A251; --brass-bright:#E5BC72; --brass-wash:#2A2416;
  --gap:#D4665E; --gap-wash:#2E1A18; --ok:#6FA983; --ok-wash:#17241B;
  --over:#9B87D4; --over-wash:#221C33;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.7);
}}
:root[data-theme="dark"]{
  --bg:#0D1218; --surface:#141B23; --surface-2:#1D262F; --sunk:#0A0F14;
  --ink:#E4E9EE; --ink-2:#94A3B1; --ink-3:#6B7A88;
  --rule:#29343E; --rule-2:#38454F;
  --brass:#D2A251; --brass-bright:#E5BC72; --brass-wash:#2A2416;
  --gap:#D4665E; --gap-wash:#2E1A18; --ok:#6FA983; --ok-wash:#17241B;
  --over:#9B87D4; --over-wash:#221C33;
  --shadow:0 1px 2px rgba(0,0,0,.4), 0 8px 24px -12px rgba(0,0,0,.7);
}
:root{
  --serif:"Iowan Old Style","Palatino Linotype",Palatino,Georgia,serif;
  --sans:"Segoe UI Variable Text","Segoe UI",-apple-system,system-ui,sans-serif;
  --mono:ui-monospace,"Cascadia Mono",Consolas,"SF Mono",Menlo,monospace;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--sans);
  font-size:15px;line-height:1.5;-webkit-font-smoothing:antialiased}
h1,h2{font-family:var(--serif);font-weight:600;margin:0;text-wrap:balance}
button,select,input,textarea{font:inherit;color:inherit}
:focus-visible{outline:2px solid var(--brass-bright);outline-offset:2px;border-radius:3px}

.masthead{border-bottom:1px solid var(--rule);background:var(--surface);
  padding:17px 26px;display:flex;flex-wrap:wrap;gap:14px 24px;align-items:baseline;
  position:sticky;top:0;z-index:10}
.masthead h1{font-size:21px}
.masthead .sub{font-family:var(--mono);font-size:11px;letter-spacing:.09em;
  text-transform:uppercase;color:var(--ink-3)}
.spacer{flex:1}
.count{font-family:var(--mono);font-size:12px;color:var(--ink-2)}
.count b{color:var(--gap);font-size:15px}

.wrap{max-width:1140px;margin:0 auto;padding:22px 26px 92px}
.intro{background:var(--surface);border:1px solid var(--rule);
  border-left:3px solid var(--brass);border-radius:0 4px 4px 0;
  padding:15px 18px;margin-bottom:20px;font-size:14px;line-height:1.6}
.intro p{margin:0 0 9px}.intro p:last-child{margin:0}
.intro code{font-family:var(--mono);font-size:12.5px;color:var(--brass)}

.newcaps{background:var(--over-wash);border:1px solid var(--over);border-radius:4px;
  padding:13px 16px;margin-bottom:20px;font-size:13.5px;line-height:1.6}
.newcaps h2{font-size:14px;font-family:var(--mono);letter-spacing:.06em;
  text-transform:uppercase;color:var(--over);margin-bottom:7px}
.newcaps dt{font-family:var(--mono);font-size:12.5px;color:var(--over);font-weight:600;margin-top:6px}
.newcaps dd{margin:1px 0 0;color:var(--ink-2)}

.controls{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:18px}
.filter{font-family:var(--mono);font-size:11.5px;padding:6px 11px;background:var(--surface);
  border:1px solid var(--rule-2);border-radius:2px;color:var(--ink-2);cursor:pointer}
.filter[aria-pressed="true"]{background:var(--brass);border-color:var(--brass);
  color:var(--surface);font-weight:600}
:root[data-theme="dark"] .filter[aria-pressed="true"],
html:not([data-theme="light"]) .filter[aria-pressed="true"]{color:#0D1218}

.grouphd{font-family:var(--mono);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--ink-3);margin:24px 0 9px;display:flex;align-items:center;gap:11px}
.grouphd::after{content:"";flex:1;height:1px;background:var(--rule)}

.eff{background:var(--surface);border:1px solid var(--rule);border-radius:4px;
  padding:14px 16px;margin-bottom:8px}
.eff.flagged{border-color:var(--gap);border-left:3px solid var(--gap)}
.eff.ignored{opacity:.72}
.hd{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.key{font-family:var(--mono);font-size:14px;font-weight:600}
.lines{font-family:var(--mono);font-size:11px;color:var(--ink-3)}
.definition{font-size:14px;line-height:1.55;margin-top:5px;max-width:66ch}
.note{font-size:12.5px;color:var(--ink-2);line-height:1.55;margin-top:6px;
  border-left:2px solid var(--rule-2);padding-left:10px;max-width:70ch}

.maps{display:flex;flex-direction:column;gap:5px;margin-top:11px}
.maprow{display:flex;align-items:baseline;gap:10px;flex-wrap:wrap}
.dir{font-family:var(--mono);font-size:10px;letter-spacing:.08em;text-transform:uppercase;
  color:var(--ink-3);min-width:74px}
.cap{font-family:var(--mono);font-size:11.5px;background:var(--brass-wash);color:var(--brass);
  border-radius:2px;padding:3px 8px;font-weight:600}
.cap.new{background:var(--over-wash);color:var(--over)}
.none{font-family:var(--mono);font-size:11.5px;color:var(--ink-3);font-style:italic}

.evid{margin-top:10px;padding-top:10px;border-top:1px dashed var(--rule)}
.wlist{font-size:12px;color:var(--ink-2);margin-top:5px;display:flex;flex-wrap:wrap;
  gap:4px 8px;align-items:baseline}
.wlist .lbl{font-family:var(--mono);font-size:9.5px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--ink-3);min-width:54px}
.wlist .sp{font-family:var(--mono);font-size:11px;background:var(--surface-2);
  border-radius:2px;padding:2px 6px}
.wlist .sp.via{background:transparent;border:1px dashed var(--rule-2);color:var(--ink-3)}
.desc{font-size:12.5px;color:var(--ink-2);margin-top:8px;line-height:1.5;
  border-left:2px solid var(--rule);padding-left:10px}
.exlbl{display:block;font-family:var(--mono);font-size:9.5px;letter-spacing:.08em;
  text-transform:uppercase;color:var(--ink-3);margin-bottom:3px}

.flagbar{margin-top:11px;display:flex;gap:9px;align-items:center;flex-wrap:wrap}
.flagbtn{font-family:var(--mono);font-size:11px;padding:5px 10px;background:transparent;
  border:1px solid var(--rule-2);border-radius:2px;color:var(--ink-3);cursor:pointer}
.flagbtn:hover{border-color:var(--gap);color:var(--gap)}
.flagbtn[aria-pressed="true"]{background:var(--gap);border-color:var(--gap);color:#fff;font-weight:600}
input[type=text]{flex:1;min-width:200px;padding:6px 9px;background:var(--surface);
  border:1px solid var(--rule-2);border-radius:3px;font-size:13px}

.export{position:fixed;left:0;right:0;bottom:0;background:var(--surface);
  border-top:2px solid var(--brass);box-shadow:0 -8px 32px -14px rgba(0,0,0,.4);
  padding:11px 26px;display:flex;gap:13px;align-items:center;z-index:20;flex-wrap:wrap}
.export .msg{font-family:var(--mono);font-size:12px;color:var(--ink-2);flex:1;min-width:180px}
.btn{padding:9px 15px;background:var(--brass);color:var(--surface);border:0;border-radius:3px;
  font-size:13.5px;font-weight:600;cursor:pointer}
:root[data-theme="dark"] .btn,html:not([data-theme="light"]) .btn{color:#0D1218}
.btn:hover{background:var(--brass-bright)}
.btn.ghost{background:transparent;color:var(--ink-2);border:1px solid var(--rule-2)}
dialog{border:1px solid var(--brass);border-radius:5px;background:var(--surface);color:var(--ink);
  max-width:min(740px,92vw);padding:0;box-shadow:var(--shadow)}
dialog::backdrop{background:rgba(0,0,0,.55)}
.dlg-hd{padding:14px 18px;border-bottom:1px solid var(--rule);display:flex;
  align-items:baseline;gap:12px}
.dlg-bd{padding:16px 18px}
textarea{width:100%;height:40vh;background:var(--sunk);color:var(--ink);border:1px solid var(--rule);
  border-radius:3px;padding:11px;font-family:var(--mono);font-size:12px;line-height:1.6}
</style>

<header class="masthead">
  <h1>Effect Capability Map</h1>
  <span class="sub">what each mechanic grounds</span>
  <span class="spacer"></span>
  <span class="count"><b id="nflag">0</b> flagged for revision</span>
</header>

<div class="wrap">
  <div class="intro">
    <p><b>This is already decided — you are reviewing, not filling in.</b> Every combat effect a weapon can reach has been analysed and mapped. Read what you like, flag what looks wrong, and come back to it when a real comp scores oddly.</p>
    <p><b>One effect can ground several capabilities, and direction changes the answer.</b> A damage-immunity window on <i>yourself</i> supports <code>engage</code>, <code>disengage</code> and <code>tankiness</code> — that is 1H Mace's Deep Leap. The same immunity granted to an <i>ally</i> is <code>peel</code>. The effect layer offers candidates; the weapon sheet picks which ones that weapon actually earns, with evidence.</p>
    <p><b>An empty list is a real answer.</b> A self-slow while channelling grounds nothing.</p>
  </div>

  <div class="newcaps" id="newcaps"></div>
  <div class="controls" id="filters"></div>
  <div id="list"></div>
</div>

<div class="export">
  <span class="msg" id="msg">Flags save in this browser. Nothing is required.</span>
  <button class="btn ghost" id="reset">Clear flags</button>
  <button class="btn" id="exp">Export flags</button>
</div>

<dialog id="dlg">
  <div class="dlg-hd"><h2 style="font-size:17px">Flagged for revision</h2>
    <span class="spacer"></span><button class="btn ghost" id="close">Close</button></div>
  <div class="dlg-bd">
    <textarea id="out" readonly></textarea>
    <div style="margin-top:11px"><button class="btn" id="copy">Copy to clipboard</button></div>
  </div>
</dialog>

<script>
"use strict";
const DATA = /*__DATA__*/;
const KEY = "albion-effect-flags-v2";
let flags = {};
try { flags = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch (e) { flags = {}; }
let filter = "all";

const esc = s => String(s).replace(/[&<>"']/g, c =>
  ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const $ = id => document.getElementById(id);
const NEW = Object.keys(DATA.proposed);

const FILTERS = [["all","All"],["flagged","Flagged"],["newcap","Uses a new capability"],
                 ["multi","Multi-capability"],["empty","Grounds nothing"],["ignored","Ignored"]];

function passes(r){
  switch (filter){
    case "flagged": return !!flags[r.key];
    case "ignored": return r.ignored;
    case "empty":   return r.grounds_nothing;
    case "newcap":  return r.dirs.some(d => d.caps.some(c => NEW.includes(c)));
    case "multi":   return r.dirs.some(d => d.caps.length > 1);
    default:        return true;
  }
}

function render(){
  const rows = DATA.rows.filter(passes);
  let html = "", seen = null;
  for (const r of rows){
    if (r.group !== seen){ seen = r.group; html += `<div class="grouphd">${esc(seen)}</div>`; }
    const f = flags[r.key];
    html += `<div class="eff ${f ? "flagged" : ""} ${r.ignored ? "ignored" : ""}">
      <div class="hd"><span class="key">${esc(r.key)}</span>
        <span class="lines">${r.lines} weapon lines · targets [${r.targets.map(esc).join(", ")}]${r.prose ? ` · prose: ${esc(r.prose)}` : ""}</span></div>
      <div class="definition">${esc(r.definition)}</div>
      ${r.ignored ? `<div class="maps"><div class="maprow"><span class="dir">ignored</span><span class="none">not a composition capability</span></div></div>`
        : `<div class="maps">${r.dirs.map(d => `<div class="maprow">
             <span class="dir">${esc(d.label)}</span>
             ${d.caps.length ? d.caps.map(c => `<span class="cap ${NEW.includes(c) ? "new" : ""}">${esc(c)}</span>`).join("")
                             : `<span class="none">grounds nothing</span>`}
           </div>`).join("")}</div>`}
      ${r.note ? `<div class="note">${esc(r.note)}</div>` : ""}
      <div class="evid">
        <div class="wlist"><span class="lbl">Weapons</span>${esc(r.weapons.join(" · "))}${r.weapons_more ? ` <span style="opacity:.6">+${r.weapons_more} more</span>` : ""}</div>
        <div class="wlist"><span class="lbl">Spells</span>${r.spells.map(s => `<span class="sp ${s.direct ? "" : "via"}">${esc(s.name)}${s.slot ? ` <span style="opacity:.55">[${esc(s.slot)}] ${esc(s.weapon)}</span>` : ""}</span>`).join("")}</div>
        ${r.desc ? `<div class="desc"><span class="exlbl">${esc(r.ex_name)}${r.ex_direct ? "" : " — applies this indirectly"}</span>${esc(r.desc)}</div>` : ""}
      </div>
      <div class="flagbar">
        <button class="flagbtn" data-flag="${esc(r.key)}" aria-pressed="${!!f}">${f ? "flagged" : "flag as wrong"}</button>
        ${f ? `<input type="text" data-note="${esc(r.key)}" placeholder="what should it be?" value="${esc(f.note || "")}">` : ""}
      </div>
    </div>`;
  }
  $("list").innerHTML = html || `<p class="none">Nothing in this filter.</p>`;
  $("nflag").textContent = Object.keys(flags).length;
  $("filters").innerHTML = FILTERS.map(([k, label]) => {
    const save = filter; filter = k;
    const n = DATA.rows.filter(passes).length; filter = save;
    return `<button class="filter" data-f="${k}" aria-pressed="${filter === k}">${esc(label)} · ${n}</button>`;
  }).join("");
  $("newcaps").innerHTML = `<h2>Proposed new capabilities</h2><dl>` +
    Object.entries(DATA.proposed).map(([k, v]) =>
      `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("") +
    `</dl><p style="margin:9px 0 0;color:var(--ink-2)">Neither exists in design doc §2.2 yet. Flag them if you would rather fold them into something existing.</p>`;
}

const save = () => localStorage.setItem(KEY, JSON.stringify(flags));

document.addEventListener("click", e => {
  const f = e.target.closest("[data-f]");
  if (f){ filter = f.dataset.f; render(); return; }
  const fl = e.target.closest("[data-flag]");
  if (fl){
    const k = fl.dataset.flag;
    if (flags[k]) delete flags[k]; else flags[k] = {note: ""};
    save(); render(); return;
  }
  if (e.target.closest("#reset")){
    if (confirm("Clear all flags?")){ flags = {}; save(); render(); } return;
  }
  if (e.target.closest("#exp")){ $("out").value = exportFlags(); $("dlg").showModal(); return; }
  if (e.target.closest("#close")){ $("dlg").close(); return; }
  if (e.target.closest("#copy")){
    $("out").select(); document.execCommand("copy");
    $("msg").textContent = "Copied. Paste it into the chat."; return;
  }
});
document.addEventListener("input", e => {
  const n = e.target.closest("[data-note]");
  if (n && flags[n.dataset.note]){ flags[n.dataset.note].note = n.value; save(); }
});

function exportFlags(){
  const keys = Object.keys(flags);
  if (!keys.length) return "# Nothing flagged — the map is accepted as-is.";
  const out = ["# Effect map corrections.", `# ${keys.length} flagged.`, ""];
  for (const k of keys){
    const r = DATA.rows.find(x => x.key === k);
    const cur = r ? r.dirs.map(d => `${d.dir}: [${d.caps.join(", ")}]`).join("  ") : "";
    out.push(`${k}:`);
    if (cur) out.push(`  # currently  ${cur}`);
    out.push(`  # should be  ${flags[k].note || "(no note given)"}`);
  }
  return out.join("\n");
}

render();
</script>
"""


if __name__ == "__main__":
    main()

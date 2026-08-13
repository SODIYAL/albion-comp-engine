#!/usr/bin/env python3
"""
Build the party-planner app — the Phase-1 product page (design doc §5, §6).

    out/dataset-latest.json + app_scoring.js  ->  app/index.html

Self-contained single file (repo pattern: dashboard, effects review): open it
directly, no server. The scoring math lives in app_scoring.js, a line-for-line
port of engine/engine.py; tests/test_js_parity.py proves the two engines agree
before this page ships.

Usage:  python3 build_app.py [--artifact-out PATH]
        --artifact-out also writes a variant without the outer <html> skeleton
        (title + style + body only) for publishing as a hosted artifact.
"""
import json, os, argparse, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, os.pardir)
OUT_HTML = os.path.join(ROOT, "app", "index.html")

# UI order of content templates; anything not listed goes after, alphabetical.
CONTENT_ORDER = ["blackzone_roam", "territory_defense", "castle_outpost"]

CSS = r"""
:root{
  --bg:#101318; --panel:#171c24; --panel2:#1d2430; --line:#2a3140;
  --text:#e8e4d8; --muted:#8b93a3; --accent:#d9a441; --accent-ink:#101318;
  --good:#63b26a; --warn:#d08a2f; --crit:#c9615c;
  --chip-healer:#63b26a; --chip-tank:#6f8fc9; --chip-support:#b08fd9;
  --chip-melee:#c98e6f; --chip-ranged:#d0b46a; --chip-caster:#6fb8c9;
}
@media (prefers-color-scheme: light){
  :root:not([data-theme="dark"]){
    --bg:#efeae0; --panel:#f8f5ec; --panel2:#fffdf6; --line:#d9d2c0;
    --text:#20242c; --muted:#6b7180; --accent:#9a6f1e; --accent-ink:#fffdf6;
    --good:#3e7d46; --warn:#a06414; --crit:#a84343;
    --chip-healer:#3e7d46; --chip-tank:#4a689c; --chip-support:#7a5aa5;
    --chip-melee:#a0603c; --chip-ranged:#8a7326; --chip-caster:#3d7f8f;
  }
}
:root[data-theme="light"]{
  --bg:#efeae0; --panel:#f8f5ec; --panel2:#fffdf6; --line:#d9d2c0;
  --text:#20242c; --muted:#6b7180; --accent:#9a6f1e; --accent-ink:#fffdf6;
  --good:#3e7d46; --warn:#a06414; --crit:#a84343;
  --chip-healer:#3e7d46; --chip-tank:#4a689c; --chip-support:#7a5aa5;
  --chip-melee:#a0603c; --chip-ranged:#8a7326; --chip-caster:#3d7f8f;
}
*{box-sizing:border-box}
html,body{margin:0;padding:0}
body{
  background:var(--bg); color:var(--text);
  font:15px/1.5 "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-variant-numeric: tabular-nums;
}
.wrap{max-width:1180px;margin:0 auto;padding:20px 20px 48px}
a{color:var(--accent)}
h1,h2{margin:0;text-wrap:balance}
h1{font:600 26px/1.15 "Iowan Old Style","Palatino Linotype","Book Antiqua",Palatino,Georgia,serif;letter-spacing:.2px}
h2{font-size:13px;text-transform:uppercase;letter-spacing:.09em;color:var(--muted);font-weight:600}
.top{display:flex;flex-wrap:wrap;gap:16px 28px;align-items:flex-end;justify-content:space-between;margin-bottom:14px}
.brand .sub{margin:2px 0 0;color:var(--muted);font-size:13px}
.content-pick{display:flex;gap:0;border:1px solid var(--line);border-radius:8px;overflow:hidden}
.content-pick button{
  appearance:none;border:0;background:var(--panel);color:var(--muted);
  padding:9px 16px;font:inherit;font-size:13.5px;cursor:pointer;border-left:1px solid var(--line);
  display:flex;flex-direction:column;align-items:flex-start;gap:1px;
}
.content-pick button:first-child{border-left:0}
.content-pick button .n{font-weight:600;color:inherit}
.content-pick button .s{font-size:11.5px;opacity:.8}
.content-pick button.on{background:var(--panel2);color:var(--text);box-shadow:inset 0 -2px 0 var(--accent)}
.content-pick button:focus-visible,button:focus-visible,input:focus-visible{outline:2px solid var(--accent);outline-offset:1px}
.notice{border:1px solid var(--line);border-left:3px solid var(--warn);
  background:var(--panel);border-radius:6px;padding:8px 12px;font-size:13px;color:var(--muted);margin-bottom:18px}
.cols{display:grid;grid-template-columns:minmax(300px,390px) 1fr;gap:18px;align-items:start}
@media (max-width:920px){.cols{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:18px}
.panel-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin-bottom:10px}
.hint{font-size:12px;color:var(--muted)}
.count{font-size:14px;color:var(--muted);display:flex;align-items:center;gap:8px}
.count b{color:var(--text);font-size:16px}
.size-ctl{display:inline-flex;border:1px solid var(--line);border-radius:6px;overflow:hidden}
.size-ctl button{appearance:none;border:0;background:var(--panel2);color:var(--text);width:26px;height:24px;cursor:pointer;font-size:14px;line-height:1}
.size-ctl button+button{border-left:1px solid var(--line)}
.search-wrap{position:relative;margin-bottom:10px}
#search{width:100%;padding:9px 12px;border-radius:8px;border:1px solid var(--line);
  background:var(--panel2);color:var(--text);font:inherit}
#search::placeholder{color:var(--muted)}
.results{position:absolute;z-index:20;top:calc(100% + 4px);left:0;right:0;max-height:320px;overflow:auto;
  background:var(--panel2);border:1px solid var(--line);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.35)}
.results .row{display:flex;align-items:center;gap:10px;width:100%;text-align:left;appearance:none;border:0;
  background:transparent;color:var(--text);padding:8px 12px;font:inherit;cursor:pointer}
.results .row:hover,.results .row.sel{background:var(--panel)}
.roster{list-style:none;margin:0;padding:0}
.roster li{display:flex;align-items:center;gap:10px;padding:7px 4px;border-top:1px solid var(--line)}
.roster li:first-child{border-top:0}
.roster .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.roster .rm{appearance:none;border:0;background:transparent;color:var(--muted);cursor:pointer;font-size:15px;padding:2px 6px;border-radius:5px}
.roster .rm:hover{color:var(--crit)}
.roster-empty{color:var(--muted);font-size:13.5px;padding:10px 2px}
.panel-foot{display:flex;gap:10px;margin-top:12px}
.ghost{appearance:none;font:inherit;font-size:13px;border:1px solid var(--line);background:transparent;
  color:var(--muted);border-radius:7px;padding:6px 12px;cursor:pointer}
.ghost:hover{color:var(--text);border-color:var(--muted)}
.chip{display:inline-block;font-size:11px;line-height:1;padding:4px 7px;border-radius:20px;
  border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.chip.r-healer{color:var(--chip-healer);border-color:var(--chip-healer)}
.chip.r-tank{color:var(--chip-tank);border-color:var(--chip-tank)}
.chip.r-support{color:var(--chip-support);border-color:var(--chip-support)}
.chip.r-melee{color:var(--chip-melee);border-color:var(--chip-melee)}
.chip.r-ranged{color:var(--chip-ranged);border-color:var(--chip-ranged)}
.chip.r-caster,.chip.r-mage{color:var(--chip-caster);border-color:var(--chip-caster)}
.fit-num{font-size:15px;color:var(--muted)}
.fit-num b{color:var(--text);font-size:20px}
.meter{height:10px;border-radius:6px;background:var(--panel2);border:1px solid var(--line);overflow:hidden}
.meter-fill{height:100%;background:var(--accent);width:0%;transition:width .25s}
@media (prefers-reduced-motion: reduce){*{transition:none !important}}
.flags{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}
.flag{font-size:12px;padding:4px 9px;border-radius:6px;border:1px solid var(--line);color:var(--muted)}
.flag.crit{border-color:var(--crit);color:var(--crit)}
.flag.warn{border-color:var(--warn);color:var(--warn)}
.gap-row{display:grid;grid-template-columns:130px 1fr 74px;gap:10px;align-items:center;padding:5px 0;font-size:13.5px}
.gap-row .cap{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.gap-track{height:7px;border-radius:5px;background:var(--panel2);border:1px solid var(--line);overflow:hidden}
.gap-fill{height:100%;background:var(--good)}
.gap-row.short .gap-fill{background:var(--crit)}
.gap-row .num{text-align:right;color:var(--muted);font-size:12.5px}
.rec{display:flex;gap:12px;align-items:flex-start;width:100%;text-align:left;appearance:none;font:inherit;
  border:1px solid var(--line);background:var(--panel2);color:var(--text);
  border-radius:9px;padding:10px 12px;margin-bottom:8px;cursor:pointer}
.rec:hover{border-color:var(--accent)}
.rec .rank{font:600 19px/1.2 "Iowan Old Style","Palatino Linotype","Book Antiqua",Palatino,Georgia,serif;color:var(--accent);min-width:20px}
.rec .body{flex:1;min-width:0}
.rec .name{font-weight:600}
.rec .why{margin-top:3px;font-size:12.5px;color:var(--muted);line-height:1.55}
.rec .why b{color:var(--good);font-weight:600}
.rec .score{font-size:13px;color:var(--muted);white-space:nowrap}
.rec .score b{color:var(--text)}
.full-note{color:var(--muted);font-size:13.5px;padding:6px 2px}
footer{margin-top:8px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}
"""

BODY = r"""
<div class="wrap">
<header class="top">
  <div class="brand">
    <h1>Warband Planner</h1>
    <p class="sub">Albion party composition &mdash; pick the content, build the party, see what&rsquo;s missing.</p>
  </div>
  <div class="content-pick" id="contentPick"></div>
</header>

<div class="notice">Pre-validation build &mdash; every score is an evidence-linted hypothesis; the Tier-2 expert blind test has not run yet. Treat recommendations as a strong draft, not doctrine.</div>

<main class="cols">
  <section>
    <div class="panel">
      <div class="panel-head">
        <h2>Party</h2>
        <div class="count"><span><b id="pcount">0</b>/<span id="psize">20</span></span>
          <span class="size-ctl"><button id="sizeMinus" aria-label="smaller party">&minus;</button><button id="sizePlus" aria-label="bigger party">+</button></span>
        </div>
      </div>
      <div class="search-wrap">
        <input id="search" placeholder="Add a weapon &mdash; type to search" autocomplete="off" aria-label="search weapons">
        <div class="results" id="results" hidden></div>
      </div>
      <ul class="roster" id="roster"></ul>
      <div class="roster-empty" id="rosterEmpty">No one yet. Add weapons here, or click a recommendation.</div>
      <div class="panel-foot">
        <button class="ghost" id="clearBtn">Clear party</button>
        <button class="ghost" id="shareBtn">Copy share link</button>
      </div>
    </div>
  </section>

  <section>
    <div class="panel">
      <div class="panel-head"><h2>Fitness</h2><div class="fit-num"><b id="fitVal">0.0</b> / <span id="fitMax">0</span></div></div>
      <div class="meter"><div class="meter-fill" id="fitBar"></div></div>
      <div class="flags" id="flags"></div>
    </div>
    <div class="panel">
      <h2>Biggest gaps</h2>
      <div id="gaps" style="margin-top:8px"></div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>Next pick</h2><span class="hint" id="recHint">click a card to add it</span></div>
      <div id="recs"></div>
    </div>
  </section>
</main>

<footer id="foot"></footer>
</div>
"""

UI_JS = r"""
(function(){
"use strict";
var engine = new CompEngine(DATA);
var order = CONTENT_ORDER.filter(function(c){ return DATA.templates[c]; })
  .concat(Object.keys(DATA.templates).filter(function(c){ return CONTENT_ORDER.indexOf(c)===-1; }).sort());
var state = { content: order[0], size: null, party: [] };

function tpl(c){ return DATA.templates[c]; }
function el(id){ return document.getElementById(id); }
function esc(s){ return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;"); }
function capName(c){ return c.replace(/_/g," "); }
function fmt(x,d){ return x.toFixed(d===undefined?1:d); }

function loadHash(){
  var h = location.hash.replace(/^#/,"");
  if(!h) return;
  var p = {};
  h.split("&").forEach(function(kv){ var i=kv.indexOf("="); if(i>0) p[kv.slice(0,i)]=decodeURIComponent(kv.slice(i+1)); });
  if(p.c && DATA.templates[p.c]) state.content = p.c;
  if(p.n && +p.n >= 2 && +p.n <= 60) state.size = +p.n;
  if(p.p) state.party = p.p.split(",").filter(function(w){ return DATA.weapons[w]; });
}
function saveHash(){
  var h = "c="+state.content+"&n="+state.size+(state.party.length?"&p="+state.party.join(","):"");
  history.replaceState(null,"","#"+h);
}

function setContent(c, keepSize){
  state.content = c;
  if(!keepSize) state.size = tpl(c).base_size;
  engine.setContent(c, state.size);
  render();
}

function addWeapon(w){
  if(state.party.length >= state.size) return;
  state.party.push(w);
  render();
}
function removeAt(i){ state.party.splice(i,1); render(); }

// ---- search ----
var WLIST = Object.keys(DATA.weapons).map(function(k){
  return {k:k, name:DATA.weapons[k].display_name, lower:DATA.weapons[k].display_name.toLowerCase(),
          role:DATA.weapons[k].role_hint||""};
}).sort(function(a,b){ return a.name<b.name?-1:1; });
var selIdx = -1;

function searchResults(q){
  q = q.trim().toLowerCase();
  if(!q) return [];
  var starts=[], contains=[];
  WLIST.forEach(function(w){
    var i = w.lower.indexOf(q);
    if(i===0) starts.push(w); else if(i>0) contains.push(w);
  });
  return starts.concat(contains).slice(0,12);
}
function renderResults(){
  var box = el("results"), q = el("search").value;
  var rs = searchResults(q);
  if(!rs.length){ box.hidden=true; box.innerHTML=""; selIdx=-1; return; }
  if(selIdx >= rs.length) selIdx = rs.length-1;
  box.innerHTML = rs.map(function(w,i){
    return '<button class="row'+(i===selIdx?' sel':'')+'" data-k="'+w.k+'">'
      +'<span class="nm">'+esc(w.name)+'</span>'
      +(w.role?'<span class="chip r-'+esc(w.role)+'">'+esc(w.role)+'</span>':'')
      +'</button>';
  }).join("");
  box.hidden = false;
}

// ---- rendering ----
function roleChip(role){ return role ? '<span class="chip r-'+esc(role)+'">'+esc(role)+'</span>' : ''; }

function render(){
  engine.setContent(state.content, state.size);
  saveHash();

  // content picker
  el("contentPick").innerHTML = order.map(function(c){
    var t = tpl(c);
    return '<button data-c="'+c+'"'+(c===state.content?' class="on"':'')+'>'
      +'<span class="n">'+esc(t.name)+'</span><span class="s">'+t.base_size+' players</span></button>';
  }).join("");

  // roster
  el("pcount").textContent = state.party.length;
  el("psize").textContent = state.size;
  el("roster").innerHTML = state.party.map(function(w,i){
    var d = DATA.weapons[w];
    return '<li><span class="nm">'+esc(d.display_name)+'</span>'+roleChip(d.role_hint)
      +'<button class="rm" data-i="'+i+'" aria-label="remove">&times;</button></li>';
  }).join("");
  el("rosterEmpty").style.display = state.party.length ? "none" : "";

  // fitness
  var fit = engine.fitness(state.party), max = engine.maxFitness();
  el("fitVal").textContent = fmt(fit);
  el("fitMax").textContent = fmt(max,0);
  el("fitBar").style.width = Math.max(0, Math.min(100, 100*fit/max)) + "%";

  // flags: hard floors, extrapolation, over-size
  var supply = engine.supply(state.party), flags = [];
  Object.keys(engine.floors).forEach(function(cap){
    var f = engine.floors[cap];
    if(state.size >= f.min_party_size && (supply[cap]||0) < f.floor_units)
      flags.push('<span class="flag crit">'+esc(capName(cap))+' below floor: '+fmt(supply[cap]||0,0)+'/'+fmt(f.floor_units,0)+'</span>');
  });
  if(engine.extrapolated())
    flags.push('<span class="flag warn">size '+state.size+' is extrapolated &mdash; template validated at '+ (tpl(state.content).validated_sizes||[tpl(state.content).base_size]).join(", ") +'</span>');
  var unc = state.party.length ? engine.uncoveredCaps(state.party) : [];
  if(unc.length >= 3 && state.party.length >= Math.floor(state.size/2))
    flags.push('<span class="flag warn">greedy trap: '+unc.length+' key capabilities under half &mdash; '+esc(unc.map(capName).join(", "))+'</span>');
  el("flags").innerHTML = flags.join("");

  // gaps
  var gaps = engine.weaknesses(state.party, 5);
  el("gaps").innerHTML = gaps.map(function(g){
    var frac = Math.max(0, Math.min(1, g.have/g.target));
    return '<div class="gap-row'+(frac < 0.5 ? ' short':'')+'">'
      +'<span class="cap">'+esc(capName(g.cap))+'</span>'
      +'<span class="gap-track"><span class="gap-fill" style="display:block;width:'+ (100*frac) +'%"></span></span>'
      +'<span class="num">'+fmt(g.have,0)+' / '+fmt(g.target)+'</span></div>';
  }).join("");

  // recommendations
  var recBox = el("recs");
  if(state.party.length >= state.size){
    recBox.innerHTML = '<div class="full-note">Party is full ('+state.size+'/'+state.size+'). Remove someone to see next picks.</div>';
    el("recHint").style.display = "none";
  } else {
    el("recHint").style.display = "";
    var recs = engine.recommend(state.party, 6);
    recBox.innerHTML = recs.map(function(r,i){
      var terms = engine.explain(state.party, r.weapon).slice(0,3);
      var why = terms.length
        ? terms.map(function(t){ return '<b>+'+fmt(t.delta,1)+'</b> '+esc(capName(t.cap))+' '+fmt(t.before,0)+'&rarr;'+fmt(t.after,0); }).join(' &nbsp;&middot;&nbsp; ')
        : 'no gap it meaningfully fills &mdash; party is broadly covered';
      var d = DATA.weapons[r.weapon];
      return '<button class="rec" data-k="'+r.weapon+'">'
        +'<span class="rank">'+(i+1)+'</span>'
        +'<span class="body"><span class="name">'+esc(r.display_name)+'</span> '+roleChip(d.role_hint)
        +'<div class="why">'+why+'</div></span>'
        +'<span class="score">score <b>'+fmt(r.score,2)+'</b></span></button>';
    }).join("");
  }
}

// ---- events ----
el("contentPick").addEventListener("click", function(e){
  var b = e.target.closest("button[data-c]"); if(b) setContent(b.dataset.c);
});
el("search").addEventListener("input", function(){ selIdx=-1; renderResults(); });
el("search").addEventListener("keydown", function(e){
  var rs = searchResults(el("search").value);
  if(e.key==="ArrowDown"){ selIdx=Math.min(selIdx+1, rs.length-1); renderResults(); e.preventDefault(); }
  else if(e.key==="ArrowUp"){ selIdx=Math.max(selIdx-1, 0); renderResults(); e.preventDefault(); }
  else if(e.key==="Enter" && rs.length){ addWeapon(rs[Math.max(0,selIdx)].k); el("search").value=""; renderResults(); }
  else if(e.key==="Escape"){ el("search").value=""; renderResults(); }
});
el("results").addEventListener("click", function(e){
  var b = e.target.closest("button[data-k]");
  if(b){ addWeapon(b.dataset.k); el("search").value=""; renderResults(); el("search").focus(); }
});
document.addEventListener("click", function(e){
  if(!e.target.closest(".search-wrap")) { el("results").hidden = true; }
});
el("roster").addEventListener("click", function(e){
  var b = e.target.closest("button[data-i]"); if(b) removeAt(+b.dataset.i);
});
el("recs").addEventListener("click", function(e){
  var b = e.target.closest("button[data-k]"); if(b) addWeapon(b.dataset.k);
});
el("clearBtn").addEventListener("click", function(){ state.party=[]; render(); });
el("shareBtn").addEventListener("click", function(){
  saveHash();
  var url = location.href;
  if(navigator.clipboard && navigator.clipboard.writeText){
    navigator.clipboard.writeText(url).then(function(){
      el("shareBtn").textContent = "Copied";
      setTimeout(function(){ el("shareBtn").textContent = "Copy share link"; }, 1400);
    });
  }
});
el("sizeMinus").addEventListener("click", function(){ if(state.size>2){ state.size--; render(); } });
el("sizePlus").addEventListener("click", function(){ if(state.size<60){ state.size++; render(); } });

// ---- init ----
loadHash();
if(state.size===null) state.size = tpl(state.content).base_size;
el("foot").innerHTML = FOOT;
setContent(state.content, true);
})();
"""


def slim_weapons(weapons):
    return {k: {"display_name": w["display_name"],
                "role_hint": w.get("role_hint"),
                "capabilities": w["capabilities"]}
            for k, w in weapons.items()}


def build(dataset, scoring_js):
    meta = dataset["_meta"]
    data = {
        "weapons": slim_weapons(dataset["weapons"]),
        "templates": dataset["templates"],
        "scoring": {k: dataset["scoring"].get(k) for k in
                    ("weights", "capability_synergies", "meta_prior")},
    }
    foot = (f"dataset v{meta['version']} &middot; {meta['weapons_curated']} weapons curated "
            f"&middot; release_clean: {str(meta['release_clean']).lower()} "
            f"&middot; built {datetime.date.today().isoformat()} &middot; "
            "game data from ao-bin-dumps &copy; Sandbox Interactive GmbH &mdash; "
            "unofficial, not affiliated with or endorsed by Sandbox Interactive.")
    payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
    scripts = ("<script>\n" + scoring_js + "\n</script>\n"
               "<script>\nvar DATA = " + payload + ";\n"
               "var CONTENT_ORDER = " + json.dumps(CONTENT_ORDER) + ";\n"
               "var FOOT = " + json.dumps(foot) + ";\n"
               + UI_JS + "\n</script>")
    head_inner = ("<meta charset=\"utf-8\">\n"
                  "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">\n"
                  "<title>Warband Planner</title>\n"
                  "<style>" + CSS + "</style>")
    full = ("<!doctype html>\n<html lang=\"en\">\n<head>\n" + head_inner +
            "\n</head>\n<body>\n" + BODY + scripts + "\n</body>\n</html>\n")
    artifact = ("<title>Warband Planner</title>\n<style>" + CSS + "</style>\n"
                + BODY + scripts + "\n")
    return full, artifact


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifact-out", default=None)
    args = ap.parse_args()

    with open(os.path.join(HERE, "out", "dataset-latest.json"), encoding="utf-8") as f:
        dataset = json.load(f)
    with open(os.path.join(HERE, "app_scoring.js"), encoding="utf-8") as f:
        scoring_js = f.read()

    full, artifact = build(dataset, scoring_js)
    os.makedirs(os.path.dirname(OUT_HTML), exist_ok=True)
    with open(OUT_HTML, "w", encoding="utf-8") as f:
        f.write(full)
    print(f"wrote {os.path.relpath(OUT_HTML, ROOT)} "
          f"({len(full)//1024} KB, {len(dataset['templates'])} contents)")
    if args.artifact_out:
        with open(args.artifact_out, "w", encoding="utf-8") as f:
            f.write(artifact)
        print(f"wrote artifact variant: {args.artifact_out}")


if __name__ == "__main__":
    main()

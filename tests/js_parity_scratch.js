// Node-side half of the scratch pass in tests/test_js_parity.py: the latent
// splits the shipped dataset never reaches, read on a scratch copy of it.
// Usage: node js_parity_scratch.js <app_scoring.js> <scratch.json> <spec.json>
"use strict";
const fs = require("fs");
const CompEngine = require(process.argv[2]);
const data = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const spec = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const names = (rows) => rows.map((r) => r.weapon);
const kitGears = (ko) => {
  const out = {};
  for (const s of Object.keys(ko.options)) out[s] = ko.options[s].map((o) => o.gear);
  return out;
};

const e7 = new CompEngine(data, "castle_outpost", 7, "balanced");
const gang = new CompEngine(data, "castle_outpost", 7, spec.style);
const cell = new CompEngine(data, "blackzone_roam", 20, spec.style);
const party = spec.party;
const out = {
  // a floored capability a kit zeroes keeps its floor lift (F44)
  floor: spec.floor.map(([_cap, cand]) => {
    const pr = e7.pickReport([], cand, null, null);
    return {
      score: pr.score, d_fitness: pr.d_fitness, combo: pr.combo, kit: pr.kit,
      rows: pr.caps.map((r) => [r.cap, r.gain, r.floor_lift, r.delta]),
      actual: e7.compScore([cand], [pr.combo], [pr.kit]) - e7.compScore([]),
    };
  }),
  // an empty `always` with no slots reads the flat sheet
  raw: e7._rawMemberCaps(spec.flat_weapon, null),
  // an empty gang band, an empty style cell and an empty kit_build read
  // as absent
  seat_gang: gang._seatKit(gang.rolesBook[spec.seat_gang]),
  seat_cell: cell._seatKit(cell.rolesBook[spec.seat_cell]),
  // an explicit null top_n reads as each list's default (F45)
  top_null: {
    recommend: names(e7.recommend(party, null)),
    weaknesses: e7.weaknesses(party, null).map((g) => g.cap),
    swap: e7.swapReview(party, null).map((m) => names(m.options)),
    replace: names(e7.replaceOptions(party, 0, null, null, null)),
    kit: kitGears(e7.kitOptions(party[0], null, null, null)),
  },
};
process.stdout.write(JSON.stringify(out));

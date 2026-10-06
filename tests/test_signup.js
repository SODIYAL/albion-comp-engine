/* Sign-up tests - dashboard/_signup.js.
 *
 * The account modules run together in a vm context with no document, as
 * the page loads them: the helpers and the pure functions load, and each
 * UI block returns before touching the DOM. The helpers run against a
 * stub client that records every call, so what the page sends to
 * Supabase is pinned without a network; tests/test_supabase_rls.mjs pins
 * what the database does with it.
 *
 * Pinned: the link and the code in it, the claim token's form and key,
 * the board (claimants per slot, reserves, free slots, counts),
 * validation on the database's bounds, the payload, a profile's lists as
 * the first declaration, database errors as sentences, and what each
 * helper sends.
 *
 * Run:  node tests/test_signup.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail !== undefined ? "\n      " + JSON.stringify(detail) : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

const CALLS = [];
const REPLY = {};
const CHANNELS = [];
const REMOVED = [];
const DB = {
  auth: {
    getSession: async () => ({ data: { session: null }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from() { throw new Error("the sign-up module reaches tables through its functions alone"); },
  channel(topic) {
    const ch = { topic, handlers: [], status: null,
      on(kind, filter, fn) { ch.handlers.push({ kind, filter, fn }); return ch; },
      subscribe(fn) { ch.status = fn; CHANNELS.push(ch); return ch; } };
    return ch;
  },
  removeChannel(ch) { REMOVED.push(ch); },
  rpc(fn, args) {
    CALLS.push({ rpc: fn, args });
    return Promise.resolve(REPLY[`rpc:${fn}`] || { data: null, error: null });
  },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, Date, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js", "_signup.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

(async () => {

/* 1 - the link, the code, the token */
{
  const fromSearch = run("codeFromSearch"), link = run("signupLink");
  check("the code rides the page address as ?cta=", fromSearch("?cta=A1B2C3D4E5") === "A1B2C3D4E5" && fromSearch("?x=1&cta=a1b2c3d4e5") === "A1B2C3D4E5");
  check("no code, a malformed code or another parameter is no sheet",
        fromSearch("") === null && fromSearch("?cta=short") === null && fromSearch("?comp=A1B2C3D4E5") === null && fromSearch(null) === null);
  check("the link is this page with the code as its one parameter, whatever hash or search the page had",
        link("A1B2C3D4E5", "https://x.test/albion/index.html#c=castle&p=A") === "https://x.test/albion/index.html?cta=A1B2C3D4E5"
        && link(" a1b2c3d4e5 ", "https://x.test/?cta=OLD#h") === "https://x.test/?cta=A1B2C3D4E5");
  check("a link's code reads back", fromSearch(new URL(link("A1B2C3D4E5", "https://x.test/index.html")).search) === "A1B2C3D4E5");
  const planner = run("plannerLink");
  check("the planner's link is this page without the sheet parameter, the comp as the share hash",
        planner("https://x.test/albion/index.html?cta=A1B2C3D4E5", "c=castle&n=20&p=A,B") === "https://x.test/albion/index.html#c=castle&n=20&p=A,B"
        && planner("https://x.test/?cta=A1B2C3D4E5#old", "") === "https://x.test/#");
  const token = run("newClaimToken")(new Uint8Array([0, 1, 15, 16, 255, 128, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]));
  check("a claim token is 16 bytes as 32 hex characters", token === "00010f10ff80070809 0a0b0c0d0e0f10".replace(" ", "") && run("CLAIM_TOKEN_RE").test(token));
  check("the token is kept per CTA", run("claimTokenKey")("a1b2c3d4e5") === "cta-claim:A1B2C3D4E5");
}

/* 2 - the board */
{
  const board = run("sheetBoard");
  const slots = [{ position: 2, weapon_id: "MAIN_MACE_HELL", role: "engage" }, { position: 1, weapon_id: "2H_LONGBOW" }, { position: 3, weapon_id: null }];
  const signups = [
    { id: "s1", position: 1, player_name: "Gus", created_at: "2026-10-01T10:00:00Z" },
    { id: "s2", position: null, player_name: "Gil", created_at: "2026-10-01T09:00:00Z" },
    { id: "s3", position: 3, player_name: "Eff", created_at: "2026-10-01T11:00:00Z" },
    { id: "s4", position: null, player_name: "Ann", created_at: "2026-10-01T08:00:00Z" },
  ];
  const b = board(slots, signups);
  check("each slot in position order with its claimant; the free slots listed",
        same(b.rows.map(r => `${r.position}:${r.claimant ? r.claimant.player_name : "-"}`), ["1:Gus", "2:-", "3:Eff"]) && same(b.free, [2]), b.rows);
  check("reserves are the sign-ups without a slot, first come first",
        same(b.reserves.map(r => r.player_name), ["Ann", "Gil"]));
  check("the counts", same(b.counts, { slots: 3, claimed: 2, free: 1, reserves: 2 }), b.counts);
  check("an empty CTA is an empty board", same(board([], []), { rows: [], reserves: [], free: [], counts: { slots: 0, claimed: 0, free: 0, reserves: 0 } }));

  /* the tally: held of planned per role, the open slots to fill next */
  const tally = run("sheetTally");
  const CAT = { "2H_LONGBOW": { name: "Longbow", role: "dps", item: "" }, MAIN_MACE_HELL: { name: "Incubus Mace", role: "frontline", item: "" },
                "2H_HOLYSTAFF": { name: "Great Holy Staff", role: "healer", item: "" }, MYSTERY: { name: "Mystery", role: null, item: "" } };
  const t = tally(board(
    [{ position: 1, weapon_id: "MAIN_MACE_HELL" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: "2H_LONGBOW" },
     { position: 4, weapon_id: "2H_HOLYSTAFF" }, { position: 5, weapon_id: null }, { position: 6, weapon_id: null }],
    [{ id: "s1", position: 1, player_name: "Gus", weapons: ["2H_LONGBOW"] }, { id: "s2", position: 5, player_name: "Eff", weapons: ["2H_HOLYSTAFF"] },
     { id: "s3", position: null, player_name: "Gil", weapons: ["MAIN_MACE_HELL"] }]), CAT);
  check("a held slot counts for its weapon's role whatever the player declared; a slot with no weapon is planned as any and held by the first declared weapon's role",
        same(t.roles.map(r => `${r.role}:${r.held}/${r.planned}`), ["frontline:1/2", "support:0/0", "dps:0/1", "healer:1/1", "any:0/2"]), t.roles);
  check("the open slots to fill next, grouped by role in the comp's order, with their weapons; reserves fill nothing",
        same(t.next.map(g => `${g.role}:${g.slots.map(s => `${s.position} ${s.name}`).join(",")}`),
             ["frontline:2 Incubus Mace", "dps:3 Longbow", "healer:4 Great Holy Staff", "any:6 any weapon"]), t.next);
  const full = tally(board([{ position: 1, weapon_id: "2H_LONGBOW" }], [{ id: "s1", position: 1, player_name: "Gus", weapons: [] }]), CAT);
  check("a full roster of named weapons lists no any row and nothing to fill",
        same(full.roles.map(r => r.role), ["frontline", "support", "dps", "healer"]) && same(full.next, []));
  const odd = tally(board([{ position: 1, weapon_id: "MYSTERY" }, { position: 2, weapon_id: null }], [{ id: "s1", position: 2, player_name: "Gus", weapons: [] }]), CAT);
  check("a roleless weapon and a held slot with nothing declared count under any",
        same(odd.roles.map(r => `${r.role}:${r.held}/${r.planned}`), ["frontline:0/0", "support:0/0", "dps:0/0", "healer:0/0", "any:1/2"])
        && same(odd.next.map(g => `${g.role}:${g.slots.map(s => s.position).join(",")}`), ["any:1"]), odd);
  check("an empty board tallies nothing", same(tally(board([], []), CAT), { roles: [{ role: "frontline", name: "Tank", held: 0, planned: 0 }, { role: "support", name: "Support", held: 0, planned: 0 }, { role: "dps", name: "DPS", held: 0, planned: 0 }, { role: "healer", name: "Healer", held: 0, planned: 0 }], next: [] }));

  /* the bands: the slots grouped by role in the comp's order */
  const bands = run("sheetBands");
  const bb = bands(board(
    [{ position: 1, weapon_id: "2H_LONGBOW" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: null },
     { position: 4, weapon_id: "MAIN_MACE_HELL" }, { position: 5, weapon_id: "MYSTERY" }],
    [{ id: "s1", position: 2, player_name: "Gus", weapons: [] }, { id: "s2", position: 3, player_name: "Eff", weapons: ["2H_HOLYSTAFF"] }]), CAT);
  check("a band per role with a slot, Tanks before DPS, the weaponless and the roleless under Any weapon, each slot in position order",
        same(bb.map(b => `${b.role}:${b.name}:${b.rows.map(r => r.position).join(",")}`), ["frontline:Tanks:2,4", "dps:DPS:1", "any:Any weapon:3,5"]), bb);
  check("a band counts its slots held of planned", same(bb.map(b => `${b.held}/${b.planned}`), ["1/2", "0/1", "1/2"]));
  check("an empty board has no band", same(bands(board([], []), CAT), []));
}

/* 3 - validation and the payload */
{
  const v = run("validateSignup");
  const allowed = new Set([2, 3]);
  const ok = { playerName: "Gus", position: "2", itemPower: "1450", weapons: ["2H_LONGBOW"], note: "late" };
  check("a good guest sign-up passes", same(v(ok, { guest: true, allowed }), {}), v(ok, { guest: true, allowed }));
  check("a guest needs a name within the account name bound; an account does not",
        !!v(Object.assign({}, ok, { playerName: " " }), { guest: true, allowed }).playerName
        && !!v(Object.assign({}, ok, { playerName: "x".repeat(run("ACCOUNT_NAME_MAX") + 1) }), { guest: true, allowed }).playerName
        && same(v(Object.assign({}, ok, { playerName: "" }), { guest: false, allowed }), {}));
  check("the slot is one of the allowed positions, or none (a reserve)",
        !!v(Object.assign({}, ok, { position: "1" }), { guest: true, allowed }).position
        && same(v(Object.assign({}, ok, { position: "" }), { guest: true, allowed }), {})
        && same(v(Object.assign({}, ok, { position: null }), { guest: true, allowed }), {}));
  check("item power is optional, a whole number within the bound",
        same(v(Object.assign({}, ok, { itemPower: "" }), { guest: true, allowed }), {})
        && !!v(Object.assign({}, ok, { itemPower: "3001" }), { guest: true, allowed }).itemPower
        && !!v(Object.assign({}, ok, { itemPower: "12.5" }), { guest: true, allowed }).itemPower
        && !!v(Object.assign({}, ok, { itemPower: "-1" }), { guest: true, allowed }).itemPower);
  check("weapons are dataset keys, each once, at most the bound",
        !!v(Object.assign({}, ok, { weapons: ["not a key"] }), { guest: true, allowed }).weapons
        && !!v(Object.assign({}, ok, { weapons: ["2H_BOW", "2H_BOW"] }), { guest: true, allowed }).weapons
        && !!v(Object.assign({}, ok, { weapons: Array.from({ length: run("SIGNUP_WEAPONS_MAX") + 1 }, (_, i) => `W${i}`) }), { guest: true, allowed }).weapons
        && same(v(Object.assign({}, ok, { weapons: [] }), { guest: true, allowed }), {}));
  check("the note is bounded", !!v(Object.assign({}, ok, { note: "n".repeat(run("SIGNUP_NOTE_MAX") + 1) }), { guest: true, allowed }).note);

  const payload = run("signupPayload");
  check("the payload: a numeric slot or null, trimmed name, numeric item power or null, the flag, the weapons, the note",
        same(payload({ position: "2", playerName: " Gus ", itemPower: "1450", canSwap: 1, weapons: ["A", "B"], note: " late " }),
             { position: 2, player_name: "Gus", item_power: 1450, can_swap: true, weapons: ["A", "B"], note: "late" })
        && same(payload({ position: "", playerName: "", itemPower: "", canSwap: false, weapons: null, note: "" }),
                { position: null, player_name: "", item_power: null, can_swap: false, weapons: [], note: "" }));
  check("a profile's lists become the first declaration: main first, then can also play, each once, at most the bound",
        same(run("weaponsFromLists")({ main: ["A", "B"], secondary: ["B", "C"] }), ["A", "B", "C"])
        && run("weaponsFromLists")({ main: Array.from({ length: 12 }, (_, i) => `W${i}`), secondary: [] }).length === run("SIGNUP_WEAPONS_MAX")
        && same(run("weaponsFromLists")(null), []));
  const S = run("SHEET_STATUS_MSG");
  check("every status but open has a sentence for the sheet", S.open === "" && S.draft && S.locked && S.completed);
}

/* 4 - error wording */
{
  const msg = run("signupErrorMessage"), M = run("SIGNUP_MSG");
  const cases = [
    ["network", new TypeError("Failed to fetch"), M.network],
    ["function missing", { code: "PGRST202", message: "Could not find the function" }, M.missing],
    ["no CTA", { code: "P0002", message: "no CTA has this code" }, M.noEvent],
    ["not open", { code: "55000", message: "sign-up is not open for this CTA" }, M.closed],
    ["slot taken", { code: "23505", message: "duplicate key value violates unique constraint signups_one_per_slot" }, M.taken],
    ["slot gone", { code: "23503", message: "violates foreign key constraint signups_slot" }, M.noSlot],
    ["a guest without a name", { code: "23502", message: "a guest sign-up needs a name" }, M.needsName],
    ["an account without a character", { code: "23502", message: "name your character in the profile first" }, M.needsCharacter],
    ["no token", { code: "42501", message: "a guest sign-up needs a claim token" }, M.needsToken],
    ["full", { code: "23514", message: "a CTA takes at most 120 sign-ups" }, M.full],
    ["a bad weapon", { code: "23514", message: "a declared weapon is not a weapon key" }, M.badWeapon],
    ["refused", { code: "42501", message: "new row violates row-level security policy" }, M.refused],
    ["a value the checks refuse", { code: "23514", message: "violates check constraint" }, M.invalid],
  ];
  for (const [name, err, want] of cases) {
    const got = msg(err);
    check(`error wording: ${name}`, got === want, got);
  }
  check("error wording: the bound in the sentence is the bound in force", M.full.includes(String(run("SIGNUPS_MAX"))));
}

/* 5 - what the helpers send */
{
  CALLS.length = 0;
  REPLY["rpc:event_by_code"] = { data: { event: { id: "e1" } }, error: null };
  const s = await run("loadSheet")("A1B2C3D4E5", "tok");
  check("loadSheet asks event_by_code with the code and the token", same(CALLS[0], { rpc: "event_by_code", args: { code: "A1B2C3D4E5", token: "tok" } }) && s.event.id === "e1");
  CALLS.length = 0;
  await run("loadSheet")("A1B2C3D4E5", null);
  check("without a token, null rides along", CALLS[0].args.token === null);

  CALLS.length = 0;
  REPLY["rpc:sign_up"] = { data: { id: "s1", position: 2 }, error: null };
  const r = await run("submitSignUp")("A1B2C3D4E5", "tok", { position: "2", playerName: " Gus ", itemPower: "1450", canSwap: true, weapons: ["A"], note: "" });
  check("submitSignUp sends sign_up with the code, the token and the payload",
        CALLS[0].rpc === "sign_up" && CALLS[0].args.code === "A1B2C3D4E5" && CALLS[0].args.token === "tok"
        && same(CALLS[0].args.signup, { position: 2, player_name: "Gus", item_power: 1450, can_swap: true, weapons: ["A"], note: "" }) && r.position === 2, CALLS[0]);

  CALLS.length = 0;
  REPLY["rpc:cancel_sign_up"] = { data: true, error: null };
  const gone = await run("cancelSignUp")("A1B2C3D4E5", "tok");
  check("cancelSignUp sends cancel_sign_up and reads the answer", same(CALLS[0], { rpc: "cancel_sign_up", args: { code: "A1B2C3D4E5", token: "tok" } }) && gone === true);
  REPLY["rpc:cancel_sign_up"] = { data: false, error: null };
  check("no sign-up to cancel is false", (await run("cancelSignUp")("A1B2C3D4E5", null)) === false);

  const src = fs.readFileSync(path.join(DASH, "_signup.js"), "utf8");
  check("the player's path reaches the database through its three functions alone; the caller's touches sign-ups and slots",
        same([...new Set(src.match(/\.from\("(\w+)"/g))].sort(), ['.from("event_slots"', '.from("signups"'])
        && /rpc\("event_by_code"/.test(src) && /rpc\("sign_up"/.test(src) && /rpc\("cancel_sign_up"/.test(src)
        && /rpc\("move_signup"/.test(src) && /rpc\("add_player"/.test(src)
        && /rpc\("confirm_sign_up"/.test(src) && /rpc\("mark_attendance"/.test(src) && /rpc\("mark_all_attended"/.test(src));
  check("the module touches the planner through the address bar alone: a page load of the planner's link",
        /location\.assign\(plannerLink\(/.test(src) && !/location\.hash/.test(src) && !/\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash|syncEngine/.test(src));
  check("the claim token lives in localStorage and leaves the browser only inside a statement",
        /localStorage\.(getItem|setItem|removeItem)\(claimTokenKey\(/.test(src) && !/console\.log\(.*token/.test(src));
}


/* 6 - the caller (phase 6) */
{
  const powers = run("callerPowers");
  check("a caller, officer or admin manages the sheet until the CTA is completed; a member or a guest does not",
        powers("caller", "open").manage && powers("officer", "locked").manage && powers("admin", "draft").manage
        && !powers("admin", "completed").manage && !powers("member", "open").manage && !powers(null, "open").manage && !powers("caller", null).manage);
  check("the caller's status moves are the guard's", same(powers("caller", "open").moves, ["draft", "locked"]) && same(powers("member", "open").moves, []));

  const CAT = { "2H_LONGBOW": { name: "Longbow", role: "dps", item: "" }, MAIN_MACE_HELL: { name: "Incubus Mace", role: "frontline", item: "" },
                OLD_THING: { name: "Old", role: "dps", item: "", removed: true }, MYSTERY: { name: "Mystery", role: null, item: "" } };
  const board = run("sheetBoard")([{ position: 1, weapon_id: "2H_LONGBOW" }, { position: 2, weapon_id: "MAIN_MACE_HELL" }, { position: 3, weapon_id: null }],
                                  [{ id: "s1", position: 1, player_name: "Gus" }, { id: "s2", position: null, player_name: "Gil" }]);
  const targets = run("moveTargets");
  check("a held player's targets: the reserves and every other slot, a held one as a swap",
        same(targets(board, board.rows[0].claimant, CAT).map(t => `${t.value}:${t.label}`),
             [":To the reserves", "2:2 · Incubus Mace", "3:3 · any weapon"]));
  check("a reserve's targets: every slot, the held one as a swap with its holder",
        same(targets(board, board.reserves[0], CAT).map(t => `${t.value}:${t.label}`),
             [":Reserve (here)", "1:1 · Longbow · swap with Gus", "2:2 · Incubus Mace", "3:3 · any weapon"]));
  const groups = run("weaponOptions")(CAT);
  check("the slot's weapon list groups the catalog by role, removed lines out, a roleless line under Other",
        same(groups.map(g => `${g.role}:${g.weapons.map(w => w.key).join(",")}`), ["frontline:MAIN_MACE_HELL", "dps:2H_LONGBOW", "other:MYSTERY"]), groups);

  CALLS.length = 0;
  REPLY["rpc:move_signup"] = { data: { id: "s1", position: 2, swapped: null }, error: null };
  await run("moveSignup")("s1", "2");
  await run("moveSignup")("s1", "");
  check("moveSignup sends move_signup with a numeric target, or null for the reserves",
        same(CALLS[0], { rpc: "move_signup", args: { signup_id: "s1", target: 2 } }) && CALLS[1].args.target === null, CALLS);
  CALLS.length = 0;
  REPLY["rpc:add_player"] = { data: { id: "s9", position: 3, player_name: "Disc" }, error: null };
  await run("addPlayer")("e1", { playerName: " Disc ", position: "3", weapons: [] });
  check("addPlayer sends add_player with the event and the player's payload",
        CALLS[0].rpc === "add_player" && CALLS[0].args.event_id === "e1" && CALLS[0].args.player.player_name === "Disc" && CALLS[0].args.player.position === 3, CALLS[0]);
}


/* 7 - the live sheet (phase 7) */
{
  check("the CTA's topic is cta:<code>, the code cleaned", run("sheetTopic")(" a1b2c3d4e5 ") === "cta:A1B2C3D4E5");
  const M = run("LIVE_STATE_MSG");
  check("the channel's states read as words: live, not live, or nothing once closed",
        M.SUBSCRIBED === "live" && /refresh/i.test(M.CHANNEL_ERROR) && /refresh/i.test(M.TIMED_OUT) && M.CLOSED === "");
  check("the sheet settles before re-reading (a swap is several messages)", run("LIVE_SETTLE_MS") >= 100 && run("LIVE_SETTLE_MS") <= 1000);

  CHANNELS.length = 0;
  REMOVED.length = 0;
  const seen = [];
  const states = [];
  const leave = run("watchSheet")("A1B2C3D4E5", p => seen.push(p), s => states.push(s));
  const ch = CHANNELS[0];
  check("watchSheet joins the CTA's channel and listens for 'changed' broadcasts",
        CHANNELS.length === 1 && ch.topic === "cta:A1B2C3D4E5" && ch.handlers.length === 1
        && ch.handlers[0].kind === "broadcast" && same(ch.handlers[0].filter, { event: "changed" }));
  ch.handlers[0].fn({ payload: { table: "signups", op: "INSERT" } });
  ch.handlers[0].fn({});
  ch.status("SUBSCRIBED");
  check("a message reaches the listener with its payload (or an empty one); the state reaches the state listener",
        same(seen, [{ table: "signups", op: "INSERT" }, {}]) && same(states, ["SUBSCRIBED"]));
  leave();
  check("leaving removes the channel", REMOVED.length === 1 && REMOVED[0] === ch);
  const src = fs.readFileSync(path.join(DASH, "_signup.js"), "utf8");
  check("the sheet joins the channel once the sheet is read and leaves it when the page goes or another CTA opens",
        /if \(sheet\) startWatching\(\);/.test(src) && /window\.addEventListener\("pagehide", stopWatching\)/.test(src) && /stopWatching\(\);\s+clearMessages\(\);\s+showPage\(\);/.test(src));
  check("a live change re-reads the sheet without refilling the player's form", /reload\(true, true\)/.test(src) && /if \(!live && \(!keepForm \|\| sheet\.mine\)\) fillForm\(\);/.test(src));
}


/* 8 - the record (phase 8) */
{
  const S = run("ATTENDANCE_STATUSES"), N = run("ATTENDANCE_NAMES"), K = run("ATTENDANCE_MARKS");
  check("the six statuses, each named; the caller's list offers four (cancelled and reserve are findings)",
        same(S, ["signed_up", "confirmed", "attended", "no_show", "cancelled", "reserve"]) && S.every(s => N[s])
        && same(K, ["signed_up", "confirmed", "attended", "no_show"]));
  const summary = run("attendanceSummary")([{ status: "confirmed" }, { status: "attended" }, { status: "attended" }, { status: "no_show" }, { status: "reserve" }, { status: "odd" }]);
  check("the summary counts each status, an unknown one aside",
        summary.confirmed === 1 && summary.attended === 2 && summary.no_show === 1 && summary.reserve === 1 && summary.signed_up === 0 && summary.total === 5, summary);
  check("an empty record counts nothing", run("attendanceSummary")(null).total === 0);
  const history = run("historyRows")([
    { id: "a", signup_id: "s1", player_name: "Live", status: "signed_up" },
    { id: "b", signup_id: null, player_name: "Gone", status: "cancelled", marked_at: null },
    { id: "c", signup_id: null, player_name: "Away", status: "no_show", marked_at: "2026-10-03T20:00:00Z" },
    { id: "d", signup_id: null, player_name: "Bench", status: "reserve", marked_at: null },
  ]);
  check("the history is the records with no claim behind them, the marked ones first, then by name",
        same(history.map(r => r.id), ["c", "d", "b"]), history.map(r => r.id));
  const powers = run("markPowers");
  check("a caller marks any time, marks everyone once completed; a player confirms their own sign-up before completion",
        powers("caller", "open", { id: "m" }).mark && !powers("caller", "open", { id: "m" }).all && powers("caller", "completed", null).all
        && powers("member", "open", { id: "m" }).confirm && !powers("member", "completed", { id: "m" }).confirm
        && !powers("member", "open", null).confirm && !powers("member", "open", { id: "m" }).mark && !powers(null, "open", null).mark);

  CALLS.length = 0;
  REPLY["rpc:confirm_sign_up"] = { data: { id: "a1", status: "confirmed" }, error: null };
  const c = await run("confirmSignUp")("A1B2C3D4E5", "tok", true);
  check("confirmSignUp sends confirm_sign_up with the code, the token and the answer",
        same(CALLS[0], { rpc: "confirm_sign_up", args: { code: "A1B2C3D4E5", token: "tok", confirmed: true } }) && c.status === "confirmed", CALLS[0]);
  CALLS.length = 0;
  await run("confirmSignUp")("A1B2C3D4E5", null, false);
  check("withdrawing sends false and a null token for an account", CALLS[0].args.confirmed === false && CALLS[0].args.token === null);
  CALLS.length = 0;
  REPLY["rpc:mark_attendance"] = { data: { id: "a1", status: "attended", marked_at: "x" }, error: null };
  await run("markAttendance")("a1", "attended");
  check("markAttendance sends mark_attendance with the record and the mark", same(CALLS[0], { rpc: "mark_attendance", args: { attendance_id: "a1", mark: "attended" } }));
  CALLS.length = 0;
  REPLY["rpc:mark_all_attended"] = { data: 7, error: null };
  const n = await run("markAllAttended")("e1");
  check("markAllAttended sends mark_all_attended with the CTA and reads the count", same(CALLS[0], { rpc: "mark_all_attended", args: { event_id: "e1" } }) && n === 7);
}

console.log(`\n${pass}/${pass + fail} sign-up tests passed`);
process.exit(fail ? 1 : 0);
})();

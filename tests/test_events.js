/* CTA tests - dashboard/_events.js.
 *
 * _auth.js, _profile.js, _guild.js, _comps.js and _events.js run together
 * in a vm context with no document, as the page loads them: the helpers
 * and the pure functions load, and each UI block returns before touching
 * the DOM. The helpers run against a stub client that records every
 * query, so what the page sends to Supabase is pinned without a network;
 * tests/test_supabase_rls.mjs pins what the database does with it.
 *
 * Pinned: the statuses and the moves the guard allows, the times both
 * ways (a datetime-local field, the ISO instant, the label with its UTC
 * time), a guild's calendar split into ahead and past, an event made
 * from a template or the planner's hash, validation on top of the comp's
 * rules, the payload (no slots once completed), what a role may do,
 * database errors as sentences, and each helper writing exactly what its
 * policy admits.
 *
 * Run:  node tests/test_events.js
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
const SESSION = { user: { id: "u-me", email: "me@example.com" } };
function chain(record, answer) {
  const proxy = new Proxy(function () {}, {
    get(_t, prop) {
      if (prop === "then") return (res, rej) => Promise.resolve(answer()).then(res, rej);
      return (...args) => { record.push([prop, ...args]); return proxy; };
    },
  });
  return proxy;
}
const DB = {
  auth: {
    getSession: async () => ({ data: { session: SESSION }, error: null }),
    onAuthStateChange: () => ({ data: { subscription: { unsubscribe() {} } } }),
  },
  from(table) {
    const ops = [];
    CALLS.push({ table, ops });
    return chain(ops, () => REPLY[table] || { data: null, error: null });
  },
  rpc(fn, args) {
    CALLS.push({ rpc: fn, args });
    return Promise.resolve(REPLY[`rpc:${fn}`] || { data: null, error: null });
  },
};

const ctx = { console, URLSearchParams, setTimeout, Promise, Proxy, Date, decodeURIComponent, encodeURIComponent };
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
for (const f of ["_auth.js", "_profile.js", "_guild.js", "_comps.js", "_events.js"]) {
  vm.runInContext(fs.readFileSync(path.join(DASH, f), "utf8"), ctx, { filename: f });
}
const run = expr => vm.runInContext(expr, ctx);

const CONTENTS = { territory_defense: "Territory Defense", ancient_lands: "Dragon Portal" };
const STYLES = { brawl: "Brawl", clap: "Clap" };

(async () => {

/* 1 - statuses and moves */
{
  const S = run("EVENT_STATUSES"), M = run("EVENT_MOVES"), N = run("EVENT_STATUS_NAMES"), L = run("EVENT_MOVE_LABELS");
  check("the four statuses, each named", same(S, ["draft", "open", "locked", "completed"]) && S.every(s => N[s]));
  check("the moves: draft to open, open to draft or locked, locked to open or completed, completed final",
        same(M.draft, ["open"]) && same(M.open, ["draft", "locked"]) && same(M.locked, ["open", "completed"]) && same(M.completed, []));
  check("every move has a button label", Object.values(M).flat().every(to => L[to]));
  const powers = run("eventPowers");
  check("callers, officers and admins write and move; a member reads; nobody edits a completed event's slots",
        powers("caller", { status: "open" }).write && same(powers("caller", { status: "open" }).moves, ["draft", "locked"])
        && powers("caller", { status: "open" }).editSlots
        && !powers("member", { status: "open" }).write && same(powers("member", { status: "open" }).moves, [])
        && !powers("admin", { status: "completed" }).editSlots && same(powers("admin", { status: "completed" }).moves, [])
        && !powers(null, null).write && same(powers("admin", null).moves, []));
}

/* 2 - times */
{
  const toInput = run("toLocalInput"), fromInput = run("fromLocalInput"), label = run("eventTimeLabel");
  const iso = "2026-10-03T17:30:00.000Z";
  const field = toInput(iso);
  check("an ISO instant shows in the field as a local minute", /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/.test(field), field);
  check("the field's value goes back to the same instant", fromInput(field) === iso, fromInput(field));
  check("an empty field is no time; junk is null", fromInput("") === "" && fromInput("   ") === "" && fromInput("soon") === null);
  check("no time shows an empty field; junk shows an empty field", toInput("") === "" && toInput(null) === "" && toInput("soon") === "");
  check("the label carries the UTC time the game runs on", label(iso).endsWith("(17:30 UTC)") && label(iso).length > 12, label(iso));
  check("no start, no label", label("") === "" && label(null) === "" && label("soon") === "");
  check("the zoned label still ends in the UTC time and names the reader's zone beside the local time",
        label(iso, true).endsWith("(17:30 UTC)") && label(iso, true).length > label(iso).length, label(iso, true));

  const toZone = run("toZoneInput"), fromZone = run("fromZoneInput"), echo = run("zoneEcho"), until = run("eventCountdown");
  check("a UTC field shows the instant's UTC minute and goes back to the same instant, whatever the machine's zone",
        toZone(iso, "utc") === "2026-10-03T17:30" && fromZone("2026-10-03T17:30", "utc") === iso
        && fromZone("2026-10-03T17:30:00", "utc") === iso, toZone(iso, "utc"));
  check("the local zone is the local field: the same functions",
        toZone(iso, "local") === toInput(iso) && fromZone(toInput(iso), "local") === iso);
  check("an empty UTC field is no time; junk and a half-typed value are null",
        fromZone("", "utc") === "" && fromZone("soon", "utc") === null && fromZone("2026-10-03", "utc") === null
        && toZone("", "utc") === "" && toZone("soon", "utc") === "");
  check("the zones are UTC first (the default) and the caller's own", same(run("EVENT_ZONES"), ["utc", "local"]));
  check("under a UTC field the echo is the caller's own time; under a local field it is the UTC time; no time, no echo",
        echo("2026-10-03T17:30", "utc").startsWith("your time: ") && echo(toInput(iso), "local").endsWith("17:30 UTC")
        && echo(toInput(iso), "local").startsWith("game time: ") && echo("", "utc") === "" && echo("soon", "local") === "");
  const now = "2026-10-03T12:00:00.000Z";
  check("the countdown reads to the minute: days and hours, hours and minutes, minutes, now, and since the start",
        until("2026-10-05T15:00:00Z", now) === "in 2d 3h" && until("2026-10-03T15:12:00Z", now) === "in 3h 12m"
        && until("2026-10-03T12:12:00Z", now) === "in 12m" && until(now, now) === "starting now"
        && until("2026-10-03T11:35:00Z", now) === "started 25m ago",
        [until("2026-10-05T15:00:00Z", now), until("2026-10-03T15:12:00Z", now), until("2026-10-03T11:35:00Z", now)]);
  check("no start has no countdown, and a start half a day gone has none",
        until("", now) === "" && until("soon", now) === "" && until("2026-10-02T20:00:00Z", now) === "");
}

/* 3 - the calendar */
{
  const groups = run("eventGroups");
  const now = new Date("2026-10-03T12:00:00Z");
  const list = [
    { id: "a", starts_at: "2026-10-05T18:00:00Z", status: "draft" },
    { id: "b", starts_at: "2026-10-03T10:00:00Z", status: "open" },
    { id: "c", starts_at: "2026-10-01T18:00:00Z", status: "locked" },
    { id: "d", starts_at: "2026-10-04T18:00:00Z", status: "completed" },
    { id: "e", starts_at: "2026-10-03T23:00:00Z", status: "open" },
  ];
  const g = groups(list, now);
  check("ahead: soonest first; a start two hours gone is still ahead",
        same(g.upcoming.map(e => e.id), ["b", "e", "a"]), g.upcoming.map(e => e.id));
  check("past: latest first; a completed event is past whatever its start; a start more than twelve hours gone is past",
        same(g.past.map(e => e.id), ["d", "c"]), g.past.map(e => e.id));
  check("an empty list makes two empty groups", same(groups([], now), { upcoming: [], past: [] }) && same(groups(null, now), { upcoming: [], past: [] }));
  check("the split is at twelve hours", run("EVENT_PAST_AFTER_MS") === 12 * 60 * 60 * 1000);
}

/* 4 - a new event from a template or the planner */
{
  const fromT = run("eventFromTemplate"), fromH = run("eventFromHash");
  const t = { id: "t1", name: "Castle A", content: "territory_defense", style: "clap", planned_size: 20,
              share_hash: "c=territory_defense&n=20&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL&g=abc",
              slots: [{ position: 2, weapon_id: "MAIN_MACE_HELL", role: "engage" }, { position: 1, weapon_id: "2H_LONGBOW" }] };
  const e = fromT(t, "g1");
  check("from a template: the name, content, style, size, share hash and slots are copied; the template is remembered; a draft with no time yet",
        e.id === null && e.guild_id === "g1" && e.template_id === "t1" && e.name === "Castle A" && e.content === "territory_defense"
        && e.style === "clap" && e.planned_size === 20 && e.share_hash === t.share_hash && e.status === "draft" && e.starts_at === ""
        && same(e.slots.map(s => `${s.position}:${s.weapon_id}:${s.role}`), ["1:2H_LONGBOW:null", "2:MAIN_MACE_HELL:engage"]), e);
  check("the template's slots are copied, not shared", e.slots !== t.slots && e.slots[0] !== t.slots[1]);
  const h = fromH("#c=ancient_lands&n=7&st=clap&p=2H_LONGBOW,MAIN_MACE_HELL&g=abc", "g1", CONTENTS, STYLES);
  check("from the planner: the hash's content, size, style and weapons, the hash kept whole, no template",
        h && h.template_id === null && h.content === "ancient_lands" && h.planned_size === 7 && h.style === "clap"
        && h.share_hash.startsWith("c=ancient_lands") && h.slots.length === 2 && h.slots[1].weapon_id === "MAIN_MACE_HELL", h);
  check("a content or style the build does not know is left for the caller to choose",
        fromH("c=narnia&st=yolo&p=A", "g1", CONTENTS, STYLES).content === "" && fromH("c=narnia&st=yolo&p=A", "g1", CONTENTS, STYLES).style === "");
  check("a planner with no weapons makes no event", fromH("c=castle&n=20", "g1", CONTENTS, STYLES) === null && fromH("", "g1", CONTENTS, STYLES) === null);
}

/* 5 - validation and the payload */
{
  const v = run("validateEvent");
  const ok = { name: "Friday CTA", content: "territory_defense", style: "", plannedSize: 20, startsAt: "2026-10-03T18:00:00Z", massAt: "2026-10-03T17:30:00Z" };
  check("a good event passes", same(v(ok, CONTENTS, STYLES), {}), v(ok, CONTENTS, STYLES));
  check("the comp's rules still hold: a name, a listed content, a size in range, a listed style",
        v(Object.assign({}, ok, { name: " " }), CONTENTS, STYLES).name === "Name the CTA."
        && !!v(Object.assign({}, ok, { content: "narnia" }), CONTENTS, STYLES).content
        && !!v(Object.assign({}, ok, { plannedSize: 61 }), CONTENTS, STYLES).plannedSize
        && !!v(Object.assign({}, ok, { style: "yolo" }), CONTENTS, STYLES).style);
  check("a start is required and must be a time",
        !!v(Object.assign({}, ok, { startsAt: "" }), CONTENTS, STYLES).startsAt
        && !!v(Object.assign({}, ok, { startsAt: "soon" }), CONTENTS, STYLES).startsAt);
  check("the mass time is optional, must be a time, and never after the start",
        same(v(Object.assign({}, ok, { massAt: "" }), CONTENTS, STYLES), {})
        && !!v(Object.assign({}, ok, { massAt: "soon" }), CONTENTS, STYLES).massAt
        && !!v(Object.assign({}, ok, { massAt: "2026-10-03T18:00:01Z" }), CONTENTS, STYLES).massAt
        && same(v(Object.assign({}, ok, { massAt: "2026-10-03T18:00:00Z" }), CONTENTS, STYLES), {}));

  const payload = run("eventPayload");
  const p = payload({ id: "e1", guild_id: "g1", template_id: "t1", name: " Friday ", content: "castle", style: "", planned_size: "20",
                      starts_at: "2026-10-03T18:00:00.000Z", mass_at: "", notes: " n ", status: "open", share_hash: "c=castle&p=A",
                      slots: [{ position: 2, weapon_id: "B" }, { position: 1, weapon_id: "A", role: " r " }] });
  check("the payload: trimmed texts, a numeric size, the times as given, normalized slots",
        same(p, { id: "e1", guild_id: "g1", template_id: "t1", name: "Friday", content: "castle", style: "", planned_size: 20,
                  starts_at: "2026-10-03T18:00:00.000Z", mass_at: "", notes: "n", status: "open", share_hash: "c=castle&p=A",
                  slots: [{ position: 1, weapon_id: "A", role: "r", note: null }, { position: 2, weapon_id: "B", role: null, note: null }] }), p);
  const done = payload({ id: "e1", guild_id: "g1", name: "F", content: "castle", planned_size: 20, starts_at: "x", status: "completed", slots: [{ position: 1 }] });
  check("a completed event's payload carries no slots (they are frozen)", !("slots" in done) && done.status === "completed", done);
  check("a new event's payload defaults to draft with no template", payload({ guild_id: "g1", name: "F", content: "castle", planned_size: 20, starts_at: "x" }).status === "draft"
        && payload({ guild_id: "g1", name: "F", content: "castle", planned_size: 20, starts_at: "x" }).template_id === null
        && payload({ guild_id: "g1", name: "F", content: "castle", planned_size: 20, starts_at: "x" }).id === null);
}

/* 6 - error wording */
{
  const msg = run("eventErrorMessage"), M = run("EVENT_MSG");
  const cases = [
    ["network", new TypeError("Failed to fetch"), M.network],
    ["not signed in", { code: "42501", message: "sign in to save a CTA" }, M.signedOut],
    ["table missing", { code: "PGRST205", message: "Could not find the table" }, M.missing],
    ["too many events", { code: "23514", message: "a guild keeps at most 200 events" }, M.tooManyEvents],
    ["too many slots", { code: "23514", message: "a CTA holds at most 60 slots" }, M.tooManySlots],
    ["a move the guard refuses", { code: "23514", message: "a CTA moves from draft to open, open to locked and back, locked to completed" }, M.move],
    ["a completed event's slots", { code: "23514", message: "a completed CTA keeps its slots" }, M.frozen],
    ["the comp is gone", { code: "P0002", message: "the comp was not found" }, M.templateGone],
    ["a share code collision", { code: "23505", message: "duplicate key value violates unique constraint" }, M.collision],
    ["a position twice", { code: "21000", message: "ON CONFLICT DO UPDATE command cannot affect row a second time" }, M.duplicate],
    ["refused by the policy", { code: "42501", message: "the CTA was not found, or your role does not edit it" }, M.refused],
    ["no row came back", { code: "refused", message: "the server refused the change" }, M.refused],
    ["a value the checks refuse", { code: "23514", message: "violates check constraint" }, M.invalid],
    ["a bad time", { code: "22007", message: "invalid input syntax for type timestamp with time zone" }, M.invalid],
  ];
  for (const [name, err, want] of cases) {
    const got = msg(err);
    check(`error wording: ${name}`, got === want, got);
  }
  check("error wording: the bounds in the sentences are the bounds in force",
        M.tooManyEvents.includes(String(run("EVENTS_MAX"))) && M.tooManySlots.includes(String(run("COMP_SLOTS_MAX"))));
}

/* 7 - what the helpers send */
{
  const find = table => CALLS.find(c => c.table === table);
  const has = (ops, ...want) => ops.some(o => want.every((w, i) => same(o[i], w)));

  CALLS.length = 0;
  REPLY.events = { data: [], error: null };
  await run("loadGuildEvents")("g1");
  let q = find("events");
  check("loadGuildEvents reads one guild's events, latest start first, with the caller and the slot count",
        has(q.ops, "eq", "guild_id", "g1") && has(q.ops, "order", "starts_at", { ascending: false })
        && q.ops.some(o => o[0] === "select" && /caller:profiles!events_created_by_fkey/.test(o[1]) && /slots:event_slots\(count\)/.test(o[1])
                      && /signups:signups\(count\)/.test(o[1]) && /share_code/.test(o[1])), q.ops);

  CALLS.length = 0;
  REPLY.events = { data: { id: "e1", slots: [{ position: 2, weapon_id: "B" }, { position: 1, weapon_id: "A" }] }, error: null };
  const e = await run("loadEvent")("e1");
  q = find("events");
  check("loadEvent reads one event with its slots, and orders the slots",
        has(q.ops, "eq", "id", "e1") && q.ops.some(o => o[0] === "maybeSingle") && same(e.slots.map(s => s.position), [1, 2]), q.ops);

  CALLS.length = 0;
  REPLY["rpc:save_event"] = { data: { id: "e1" }, error: null };
  await run("saveEvent")({ id: null, guild_id: "g1", template_id: "t1", name: " Friday ", content: "castle", planned_size: 20,
                           starts_at: "2026-10-03T18:00:00.000Z", slots: [{ position: 1, weapon_id: "A" }] });
  const r = CALLS.find(c => c.rpc);
  check("saveEvent sends one save_event payload",
        r.rpc === "save_event" && r.args.event.name === "Friday" && r.args.event.template_id === "t1" && r.args.event.status === "draft"
        && same(r.args.event.slots, [{ position: 1, weapon_id: "A", role: null, note: null }]), r.args);

  CALLS.length = 0;
  REPLY.events = { data: [{ id: "e1", status: "open", updated_at: "x" }], error: null };
  const moved = await run("setEventStatus")("e1", "open");
  q = find("events");
  check("setEventStatus updates the status alone and reads the row back",
        has(q.ops, "update", { status: "open" }) && has(q.ops, "eq", "id", "e1") && q.ops.some(o => o[0] === "select") && moved.status === "open", q.ops);
  CALLS.length = 0;
  REPLY.events = { data: [], error: null };
  let refused = null;
  try { await run("setEventStatus")("e1", "open"); } catch (x) { refused = x; }
  check("a move the policy refused (no row back) is reported", refused && refused.code === "refused");

  CALLS.length = 0;
  REPLY.events = { data: [{ id: "e1" }], error: null };
  await run("deleteEvent")("e1");
  q = find("events");
  check("deleteEvent deletes one event and reads the row back",
        q.ops.some(o => o[0] === "delete") && has(q.ops, "eq", "id", "e1") && q.ops.some(o => o[0] === "select"), q.ops);
  CALLS.length = 0;
  REPLY.events = { data: [], error: null };
  refused = null;
  try { await run("deleteEvent")("e1"); } catch (x) { refused = x; }
  check("a deletion the policy refused (no row back) is reported", refused && refused.code === "refused");

  const src = fs.readFileSync(path.join(DASH, "_events.js"), "utf8");
  check("the module touches the planner through the address bar alone",
        /location\.hash/.test(src) && !/\bENG\b|CompEngine|DATASET|\brender\(|saveHash|loadHash|syncEngine/.test(src));
  check("the module never writes a template (an event is a copy)",
        !/from\("comp_template|save_comp_template|saveTemplate\(|deleteTemplate\(/.test(src));
}

console.log(`\n${pass}/${pass + fail} CTA tests passed`);
process.exit(fail ? 1 : 0);
})();

/* Account-layer tests - dashboard/_auth.js and the <head> script in
 * dashboard/_shell.html that sets an email link's return aside.
 *
 * _auth.js is inlined into the page as its own <script>, not a module. The
 * whole file runs here in a vm context with no document: the helpers and the
 * pure functions load, and the UI block returns before touching the DOM. The
 * helpers run against a stub client that records every call, so what the page
 * sends to Supabase is pinned without a network.
 *
 * Pinned: sign-up / log-in validation (a whitespace-only Albion name is
 * empty, the display name is optional, passwords are never trimmed), the
 * error wording for every failure the dialog explains, the duplicate-account
 * signal, the account name fallback, email-link parsing, the head script
 * that keeps an email link's tokens away from the planner's hash rewrite,
 * and the client's fetch (_supabase.js), which fails a request the service
 * has not answered in time.
 *
 * Run:  node tests/test_auth_ui.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const DASH = path.join(__dirname, "..", "dashboard");
const AUTH = fs.readFileSync(path.join(DASH, "_auth.js"), "utf8");
const SHELL = fs.readFileSync(path.join(DASH, "_shell.html"), "utf8");

let pass = 0, fail = 0;
function check(name, cond, detail) {
  if (cond) { pass++; console.log(`PASS  ${name}`); }
  else { fail++; console.log(`FAIL  ${name}${detail ? "\n      " + detail : ""}`); }
}
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

/* the stub client: every auth call is recorded and answered from REPLY */
const CALLS = [];
const REPLY = {};
const answer = (name, args) => { CALLS.push([name, args]); return Promise.resolve(REPLY[name] || {data: {}, error: null}); };
const DB = {
  auth: {
    signUp: a => answer("signUp", a),
    signInWithPassword: a => answer("signInWithPassword", a),
    signOut: () => answer("signOut"),
    getSession: () => answer("getSession"),
    resend: a => answer("resend", a),
    setSession: a => answer("setSession", a),
    onAuthStateChange: () => ({data: {subscription: {unsubscribe() {}}}}),
  },
};

const ctx = {
  console, URLSearchParams, setTimeout, Promise,
  location: {protocol: "https:", origin: "https://sodiyal.github.io", pathname: "/albion-comp-engine/"},
};
ctx.window = ctx;
ctx.window.DB = DB;
vm.createContext(ctx);
vm.runInContext(AUTH, ctx, {filename: "_auth.js"});
const run = expr => vm.runInContext(expr, ctx);

(async () => {

/* 1 - validation */
{
  const login = run("validateLogIn");
  check("log in: an empty email and password are both flagged",
        same(Object.keys(login({email: "", password: ""})).sort(), ["email", "password"]));
  check("log in: an email of spaces alone is empty",
        /enter your email/i.test(login({email: "   ", password: "x"}).email || ""));
  check("log in: a malformed email is flagged",
        /valid email/i.test(login({email: "player@", password: "x"}).email || ""));
  check("log in: a well-formed pair passes (surrounding spaces on the email are tolerated)",
        same(login({email: "  player@example.com ", password: "x"}), {}));
  check("log in: no length rule on a log-in password (an older account keeps working)",
        same(login({email: "player@example.com", password: "1"}), {}));

  const signup = run("validateSignUp");
  const ok = {email: "player@example.com", password: "hunter22", albionName: "Zaddy",
              albionServer: "europe", displayName: ""};
  check("sign up: a complete form without a display name passes (display name is optional)",
        same(signup(ok), {}));
  check("sign up: the Albion name is required",
        /albion/i.test(signup({...ok, albionName: ""}).albionName || ""));
  check("sign up: an Albion name of whitespace alone is empty",
        !!signup({...ok, albionName: " \t  "}).albionName);
  check("sign up: email and password are required",
        same(Object.keys(signup({...ok, email: "", password: ""})).sort(), ["email", "password"]));
  const min = run("AUTH_PASSWORD_MIN");
  check(`sign up: a password under ${min} characters is flagged with the number`,
        new RegExp(`\\b${min}\\b`).test(signup({...ok, password: "x".repeat(min - 1)}).password || ""));
  check("sign up: a password of exactly the minimum passes",
        same(signup({...ok, password: "x".repeat(min)}), {}));
  check("sign up: the minimum is Supabase's floor (6), never above what the server asks",
        min === 6, `AUTH_PASSWORD_MIN = ${min}`);
  const identity = run("validateIdentity"), MAX = run("ACCOUNT_NAME_MAX");
  const eu = {albionServer: "europe"};
  const names = fields => identity({...eu, ...fields});
  check("names: an Albion name at the bound passes, one character over is flagged",
        same(names({albionName: "a".repeat(MAX)}), {})
        && new RegExp(`\\b${MAX}\\b`).test(names({albionName: "a".repeat(MAX + 1)}).albionName || ""));
  check("names: a display name over the bound is flagged; an empty one passes",
        !!names({albionName: "Z", displayName: "d".repeat(MAX + 1)}).displayName
        && same(names({albionName: "Z", displayName: ""}), {}));
  check("names: the bound counts characters as the database does, not UTF-16 units",
        same(names({albionName: "\u{1F600}".repeat(MAX)}), {})
        && !!names({albionName: "\u{1F600}".repeat(MAX + 1)}).albionName);
  check("names: surrounding spaces do not count toward the bound",
        same(names({albionName: `  ${"a".repeat(MAX)}  `}), {}));
  check("sign up: an oversized display name is flagged before sending",
        !!signup({...ok, displayName: "d".repeat(MAX + 1)}).displayName);

  const SERVERS = run("ALBION_SERVERS");
  check("servers: the game's three, in the words a player reads",
        same(SERVERS, {americas: "Americas", asia: "Asia", europe: "Europe"}), SERVERS);
  check("servers: every one of the three passes",
        Object.keys(SERVERS).every(s => same(identity({albionName: "Z", albionServer: s}), {})));
  check("servers: a character without a server is flagged (names are unique per server)",
        /server/i.test(identity({albionName: "Z"}).albionServer || "")
        && !!identity({albionName: "Z", albionServer: ""}).albionServer);
  check("servers: a value off the list is flagged, an inherited property included",
        !!identity({albionName: "Z", albionServer: "narnia"}).albionServer
        && !!identity({albionName: "Z", albionServer: "toString"}).albionServer);
  check("sign up: the server is required",
        !!signup({...ok, albionServer: ""}).albionServer);
  const opts = [...SHELL.matchAll(/<select id="(signup|profile)-server"[\s\S]*?<\/select>/g)]
    .map(m => [...m[0].matchAll(/<option value="([^"]*)">([^<]*)</g)].filter(o => o[1]).map(o => [o[1], o[2]]));
  check("servers: both server fields offer exactly the list, in its order and words",
        opts.length === 2 && opts.every(o => same(Object.fromEntries(o), SERVERS)
                                             && same(o.map(x => x[0]), Object.keys(SERVERS))), opts);
  const hint = SHELL.match(/id="signup-password-hint">([^<]*)</);
  check("sign up: the password hint states the same minimum as the check",
        !!hint && new RegExp(`\\b${min}\\b`).test(hint[1]), hint ? hint[1] : "hint missing");
}

/* 2 - error wording: every failure the dialog explains */
{
  const msg = run("authErrorMessage"), M = run("AUTH_MSG");
  const cases = [
    ["wrong password (code)", {code: "invalid_credentials", message: "Invalid login credentials"}, M.credentials],
    ["wrong password (message only)", {message: "Invalid login credentials"}, M.credentials],
    ["account not verified (code)", {code: "email_not_confirmed", message: "Email not confirmed"}, M.unverified],
    ["account not verified (message only)", {message: "Email not confirmed"}, M.unverified],
    ["duplicate account (code)", {code: "user_already_exists", message: "User already registered"}, M.exists],
    ["duplicate account (message only)", {message: "User already registered"}, M.exists],
    ["invalid email (code)", {code: "email_address_invalid", message: 'Email address "x@y" is invalid'}, M.email],
    ["invalid email (message only)", {message: "Unable to validate email address: invalid format"}, M.email],
    ["network: retryable fetch error", {name: "AuthRetryableFetchError", status: 0, message: "Failed to fetch"}, M.network],
    ["network: raw fetch TypeError", new TypeError("Failed to fetch"), M.network],
    ["network: Safari wording", new TypeError("Load failed"), M.network],
    ["email rate limit", {code: "over_email_send_rate_limit", message: "email rate limit exceeded"}, M.emailRate],
    ["request rate limit", {code: "over_request_rate_limit", message: "Request rate limit reached"}, M.rate],
    ["sign-ups closed", {code: "signup_disabled", message: "Signups not allowed for this instance"}, M.closed],
    ["expired email link", {code: "otp_expired", message: "Email link is invalid or has expired"}, M.link],
  ];
  for (const [name, err, want] of cases) {
    const got = msg(err);
    check(`error wording: ${name}`, got === want, `got "${got}"`);
  }
  const weak = {code: "weak_password", message: "Password should be at least 8 characters."};
  check("error wording: a weak password shows the server's own rule (it names a raised minimum)",
        msg(weak) === weak.message, `got "${msg(weak)}"`);
  check("error wording: a weak password without a message still explains itself",
        msg({code: "weak_password"}) === M.weak);
  check("error wording: an unknown failure carries the server's message",
        /Something went wrong: .*boom/.test(msg({message: "boom"})));
  check("error wording: an empty error still says something",
        msg(null) === M.unknown && msg({}) === M.unknown);
  check("error kind: the dialog offers a resend exactly on an unverified account",
        run("authErrorKind")({code: "email_not_confirmed"}) === "unverified"
        && run("authErrorKind")({code: "invalid_credentials"}) !== "unverified");
}

/* 3 - the duplicate-account signal (email verification on) */
{
  const dup = run("isExistingAccount");
  check("duplicate: a user with no identities is an existing account",
        dup({user: {id: "u", identities: []}, session: null}) === true);
  check("duplicate: a fresh user with an identity is not",
        dup({user: {id: "u", identities: [{id: "i"}]}, session: null}) === false);
  check("duplicate: no user, or no identities field, is not",
        dup({}) === false && dup(null) === false && dup({user: {id: "u"}}) === false);
}

/* 4 - the account's name on the masthead */
{
  const label = run("accountLabel"), names = run("accountNames");
  const user = {user_metadata: {display_name: "Meta Display", albion_name: "MetaAlbion"}};
  check("name: the profile's display name first",
        label({display_name: "Zaddy", albion_name: "ZaddyAO"}, user) === "Zaddy");
  check("name: a blank display name falls back to the Albion name",
        label({display_name: "  ", albion_name: "ZaddyAO"}, user) === "ZaddyAO"
        && label({display_name: null, albion_name: "ZaddyAO"}, user) === "ZaddyAO");
  check("name: a profile with neither reads Account (the row decides, not the metadata)",
        label({display_name: null, albion_name: null}, user) === "Account");
  check("name: an unreadable profile row falls back to the sign-up metadata",
        label(null, user) === "Meta Display"
        && label(null, {user_metadata: {albion_name: "MetaAlbion"}}) === "MetaAlbion");
  check("name: nothing at all reads Account",
        label(null, null) === "Account" && label(null, {}) === "Account");
  check("name: names are trimmed and split for the menu",
        same(names({display_name: " Zaddy ", albion_name: " ZaddyAO ", albion_server: "europe"}, null),
             {label: "Zaddy", display: "Zaddy", albion: "ZaddyAO", server: "europe"}));
  check("name: a server off the list reads as none recorded",
        names({albion_name: "Z", albion_server: "narnia"}, null).server === ""
        && names({albion_name: "Z"}, null).server === "");
  check("name: the sign-up metadata's server stands in while the row is unreadable",
        names(null, {user_metadata: {albion_name: "Z", albion_server: "asia"}}).server === "asia");
}

/* 5 - email-link parsing */
{
  const parse = run("parseAuthLink");
  const ok = parse("#access_token=AT&expires_in=3600&refresh_token=RT&token_type=bearer&type=signup");
  check("link: a verification return yields both tokens and the type",
        same(ok, {accessToken: "AT", refreshToken: "RT", type: "signup"}), JSON.stringify(ok));
  const bad = parse("#error=access_denied&error_code=otp_expired&error_description=Email+link+is+invalid+or+has+expired");
  check("link: an expired link yields its code and a decoded message",
        same(bad, {error: {code: "otp_expired", message: "Email link is invalid or has expired"}}), JSON.stringify(bad));
  check("link: an error in the query string parses the same way",
        same(parse("?error=access_denied&error_code=otp_expired&error_description=x"),
             {error: {code: "otp_expired", message: "x"}}));
  check("link: a share-link hash is not an email link",
        parse("#c=castle_outpost&n=7&p=2H_LONGBOW") === null);
  check("link: a token without its refresh token is not a session",
        parse("#access_token=AT") === null);
  check("link: empty is nothing", parse("") === null && parse(null) === null);
}

/* 6 - what the helpers send to Supabase */
{
  CALLS.length = 0;
  REPLY.signUp = {data: {user: {id: "u", identities: [{}]}, session: null}, error: null};
  const data = await run("signUpUser")({email: "p@example.com", password: "hunter22",
                                        albionName: "ZaddyAO", albionServer: "europe", displayName: "Zaddy"});
  const [name, args] = CALLS[0] || [];
  check("signUpUser sends email, password, both names and the server as profile metadata",
        name === "signUp" && args.email === "p@example.com" && args.password === "hunter22"
        && same(args.options.data, {albion_name: "ZaddyAO", albion_server: "europe", display_name: "Zaddy"}),
        JSON.stringify(CALLS[0]));
  check("signUpUser asks the email link to return to this page",
        args && args.options.emailRedirectTo === "https://sodiyal.github.io/albion-comp-engine/",
        args && String(args.options.emailRedirectTo));
  check("signUpUser returns the data (the dialog reads session and identities from it)",
        data === REPLY.signUp.data);

  ctx.location = {protocol: "file:", origin: "null", pathname: "/C:/dashboard/index.html"};
  CALLS.length = 0;
  await run("signUpUser")({email: "p@example.com", password: "hunter22", albionName: "Z", displayName: null});
  check("signUpUser from file:// leaves the return to the project's Site URL",
        CALLS[0] && CALLS[0][1].options.emailRedirectTo === undefined);
  ctx.location = {protocol: "https:", origin: "https://sodiyal.github.io", pathname: "/albion-comp-engine/"};

  REPLY.signInWithPassword = {data: {}, error: {code: "invalid_credentials", message: "Invalid login credentials"}};
  let thrown = null;
  try { await run("signInUser")("p@example.com", "nope"); } catch (e) { thrown = e; }
  check("signInUser throws the server's error object (the dialog words it)",
        thrown && thrown.code === "invalid_credentials");
  REPLY.signInWithPassword = {data: {user: {id: "u"}}, error: null};

  CALLS.length = 0;
  await run("resendVerificationEmail")("p@example.com");
  check("resendVerificationEmail asks for a sign-up email to the same address and return",
        CALLS[0] && CALLS[0][0] === "resend" && CALLS[0][1].type === "signup"
        && CALLS[0][1].email === "p@example.com"
        && CALLS[0][1].options.emailRedirectTo === "https://sodiyal.github.io/albion-comp-engine/");

  CALLS.length = 0;
  await run("adoptEmailLinkSession")({accessToken: "AT", refreshToken: "RT"});
  check("adoptEmailLinkSession stores the link's tokens as the session",
        CALLS[0] && CALLS[0][0] === "setSession"
        && same(CALLS[0][1], {access_token: "AT", refresh_token: "RT"}));

  check("authServiceReady reads the client; without it the account UI explains the outage",
        run("authServiceReady()") === true);
  ctx.window.DB = undefined;
  check("authServiceReady is false when the library did not load", run("authServiceReady()") === false);
  ctx.window.DB = DB;
}

/* 7 - the <head> script: an email link's return is set aside before the
   planner boots and rewrites the hash */
{
  const head = SHELL.slice(0, SHELL.indexOf("</head>"));
  const m = head.match(/<script>\s*([\s\S]*?window\.AUTH_LINK[\s\S]*?)<\/script>/);
  check("head: the email-link script sits in <head>", !!m);
  const runHead = (hash, search) => {
    const replaced = [];
    const hctx = {
      location: {hash, search, pathname: "/albion-comp-engine/"},
      history: {replaceState: (s, t, url) => replaced.push(url)},
    };
    hctx.window = hctx;
    vm.createContext(hctx);
    vm.runInContext(m ? m[1] : "", hctx);
    return {link: hctx.AUTH_LINK, replaced};
  };
  if (m) {
    const tok = runHead("#access_token=AT&refresh_token=RT&type=signup", "");
    check("head: a verification return is set aside and its tokens leave the address",
          tok.link === "#access_token=AT&refresh_token=RT&type=signup"
          && same(tok.replaced, ["/albion-comp-engine/"]), JSON.stringify(tok));
    const err = runHead("", "?error=access_denied&error_code=otp_expired&error_description=x");
    check("head: a link error in the query is set aside too",
          err.link.startsWith("?error=") && same(err.replaced, ["/albion-comp-engine/"]), JSON.stringify(err));
    const share = runHead("#c=castle_outpost&n=7&p=2H_LONGBOW", "");
    check("head: a share link is left alone for the planner",
          share.link === "" && share.replaced.length === 0, JSON.stringify(share));
    const kept = runHead("#c=castle_outpost", "?error_description=x");
    check("head: stripping a query error keeps the planner's hash",
          same(kept.replaced, ["/albion-comp-engine/#c=castle_outpost"]), JSON.stringify(kept));
    const plain = runHead("", "");
    check("head: a plain visit sets nothing aside", plain.link === "" && plain.replaced.length === 0);
  }
}

/* 8 - the export kit: CSV text, a file name, the download */
{
  const csv = run("acctCsvText"), name = run("acctFilename");
  check("CSV: a plain cell as is; a comma, a quote, a line break or an outer space quoted with quotes doubled; CRLF line ends",
        csv([["#", "Weapon", "Note"], [1, "Longbow", 'engage, then "kite"'], [2, "", " x\ny"]]) === '#,Weapon,Note\r\n1,Longbow,"engage, then ""kite"""\r\n2,," x\ny"\r\n');
  check("CSV: null and undefined are empty cells; no rows is an empty sheet", csv([[null, undefined]]) === ",\r\n" && csv([]) === "\r\n" && csv(null) === "\r\n");
  check("a file name keeps letters, digits, spaces, dashes and underscores, cut at 60, the extension appended; nothing becomes export",
        name("Castle A: tanks/heals (v2)", "csv") === "Castle A tanks heals v2.csv" && name("Zaddy é", "csv") === "Zaddy e.csv"
        && name("", "csv") === "export.csv" && name("x".repeat(80), "txt").length === 64);
  check("the download does nothing without a document", run("acctDownloadText")("a.csv", "x", "text/csv") === false);
}

/* 9 - the client's fetch (_supabase.js): no account request waits forever.
   A request that never settled held the CTA dialog's New CTA until the
   page was reloaded. */
{
  const SUPA = fs.readFileSync(path.join(DASH, "_supabase.js"), "utf8");
  let created = null;
  const sctx = { console: { log() {} }, setTimeout, clearTimeout, Promise, AbortController };
  sctx.window = sctx;
  sctx.supabase = { createClient: (url, key, opts) => { created = { url, key, opts }; return {}; } };
  vm.createContext(sctx);
  vm.runInContext(SUPA, sctx, { filename: "_supabase.js" });
  check("the client is created with the timed fetch",
        !!(created && created.opts && created.opts.global && typeof created.opts.global.fetch === "function"));
  check("the timeout is 20 s", vm.runInContext("ACCOUNT_FETCH_TIMEOUT_MS", sctx) === 20000);
  const accountFetch = vm.runInContext("accountFetch", sctx);

  let err = null;
  const t0 = Date.now();
  await accountFetch(() => new Promise(() => {}), 40)("https://x/rest/v1/events", { method: "GET" }).catch(e => { err = e; });
  const message = err ? err.message : "";
  check("a request that never answers fails once its time is up",
        /failed to fetch/i.test(message) && Date.now() - t0 < 1000, message);
  check("every dialog words that failure as the network one, raw or as postgrest-js wraps it (name: message)",
        run(`authErrorKind({ message: ${JSON.stringify(message)} })`) === "network"
        && run(`authErrorKind({ message: ${JSON.stringify("TypeError: " + message)} })`) === "network");

  let seen = null;
  const res = await accountFetch((input, init) => { seen = { input, init }; return Promise.resolve("ok"); }, 1000)(
    "u", { method: "POST", headers: { a: "1" } });
  check("an answer in time passes through with the caller's options and an abort signal",
        res === "ok" && seen.input === "u" && seen.init.method === "POST" && seen.init.headers.a === "1"
        && !!seen.init.signal && seen.init.signal.aborted === false);

  const outer = new AbortController();
  let inner = null, abortErr = null;
  const pending = accountFetch((input, init) => {
    inner = init.signal;
    /* as fetch does: an aborted signal rejects at once, a later abort when it comes */
    if (init.signal.aborted) return Promise.reject(new Error("aborted"));
    return new Promise((_, reject) => init.signal.addEventListener("abort", () => reject(new Error("aborted"))));
  }, 1000)("u", { signal: outer.signal });
  outer.abort();
  await pending.catch(e => { abortErr = e; });
  check("the caller's own abort still aborts the request",
        !!inner && inner.aborted && !!abortErr && abortErr.message === "aborted");
}

console.log(`\n${pass}/${pass + fail} account-layer tests passed`);
process.exit(fail ? 1 : 0);

})().catch(e => { console.error(e); process.exit(1); });

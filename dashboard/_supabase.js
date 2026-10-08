"use strict";

/*
 * Supabase client layer.
 *
 * Authentication and persistent application data live in Supabase.
 * Albion composition/scoring logic remains inside CompEngine.
 */

const SUPABASE_URL = "https://wfhsyagkagtzzledesmg.supabase.co";
const SUPABASE_PUBLISHABLE_KEY = "sb_publishable_NxnsTEV0y59bvCmpY1KL4A_cY6U23tR";

/* No account request waits forever: one the service has not answered in
   ACCOUNT_FETCH_TIMEOUT_MS fails as a network error, which every dialog
   words as "Could not reach the account service", so a dialog's busy state
   always ends. A request that never settled held a dialog's buttons until
   the page was reloaded (the CTA dialog's New CTA). */
const ACCOUNT_FETCH_TIMEOUT_MS = 20000;

function accountFetch(fetchImpl, ms) {
  return (input, init) => new Promise((resolve, reject) => {
    const opts = Object.assign({}, init);
    const ctrl = typeof AbortController === "function" ? new AbortController() : null;
    const outer = opts.signal;
    if (ctrl) {
      if (outer && outer.aborted) ctrl.abort();
      else if (outer) outer.addEventListener("abort", () => ctrl.abort(), { once: true });
      opts.signal = ctrl.signal;
    }
    const timer = setTimeout(() => {
      if (ctrl) ctrl.abort();
      reject(new TypeError(`Failed to fetch: the account service did not answer in ${Math.round(ms / 1000)} s`));
    }, ms);
    let pending;
    try {
      pending = Promise.resolve(fetchImpl(input, opts));
    } catch (err) {
      pending = Promise.reject(err);
    }
    pending.then(resolve, reject).finally(() => clearTimeout(timer));
  });
}

if (!window.supabase) {
  throw new Error("Supabase JS library did not load.");
}

window.DB = window.supabase.createClient(
  SUPABASE_URL,
  SUPABASE_PUBLISHABLE_KEY,
  { global: { fetch: accountFetch((input, init) => window.fetch(input, init), ACCOUNT_FETCH_TIMEOUT_MS) } }
);

console.log("Supabase client initialized");

"use strict";

/*
 * Accounts: the Supabase auth helpers and the account UI.
 *
 * build.py inlines this file as its own <script>, after the planner's
 * scripts and after _supabase.js (the one client, window.DB). The account
 * layer never reads or writes planner state, and a sign-in service that
 * fails to load leaves the planner running: the account button then
 * explains the outage instead of signing anyone in.
 *
 * Four parts:
 *   helpers - the only code that talks to window.DB
 *   pure    - validation, error wording, names (tests/test_auth_ui.js)
 *   UI kit  - busy buttons, field flags, messages and dialog wiring, shared
 *             with every account dialog (_profile.js)
 *   UI      - the masthead button, the account menu, the sign-in dialog,
 *             and window.Account: the identity store feature modules
 *             subscribe to. It calls the helpers, never window.DB directly.
 */


/* ------------------------------------------------------------ helpers */

/* false when the Supabase library did not load (_supabase.js threw) */
function authServiceReady() {
  return !!(typeof window !== "undefined" && window.DB && window.DB.auth);
}


/* Where an email link returns: this page, when it is served over http(s).
   Supabase honours the address only when it is on the project's Redirect
   URLs list; otherwise the link returns to the project's Site URL. */
function authReturnAddress() {
  if (typeof location === "undefined" || !/^https?:$/.test(location.protocol)) {
    return undefined;
  }

  return location.origin + location.pathname;
}


async function signUpUser({
  email,
  password,
  albionName,
  albionServer,
  displayName,
  emailRedirectTo = authReturnAddress()
}) {
  const { data, error } = await window.DB.auth.signUp({
    email,
    password,
    options: {
      emailRedirectTo,
      data: {
        albion_name: albionName,
        albion_server: albionServer,
        display_name: displayName
      }
    }
  });

  if (error) {
    throw error;
  }

  return data;
}


async function signInUser(email, password) {
  const { data, error } = await window.DB.auth.signInWithPassword({
    email,
    password
  });

  if (error) {
    throw error;
  }

  return data;
}


async function signOutUser() {
  const { error } = await window.DB.auth.signOut();

  if (error) {
    throw error;
  }
}


async function getCurrentUser() {
  const {
    data: { session },
    error
  } = await window.DB.auth.getSession();

  if (error) {
    console.error("Unable to get auth session:", error);
    return null;
  }

  return session?.user || null;
}


async function getCurrentProfile() {
  const user = await getCurrentUser();

  if (!user) {
    return null;
  }

  const { data, error } = await window.DB
    .from("profiles")
    .select("*")
    .eq("id", user.id)
    .single();

  if (error) {
    console.error("Unable to load profile:", error);
    return null;
  }

  return data;
}


/* A new verification email for an account that has not confirmed yet. */
async function resendVerificationEmail(email) {
  const { error } = await window.DB.auth.resend({
    type: "signup",
    email,
    options: { emailRedirectTo: authReturnAddress() }
  });

  if (error) {
    throw error;
  }
}


/* An email link's tokens (parseAuthLink) become the stored session. */
async function adoptEmailLinkSession({ accessToken, refreshToken }) {
  const { data, error } = await window.DB.auth.setSession({
    access_token: accessToken,
    refresh_token: refreshToken
  });

  if (error) {
    throw error;
  }

  return data;
}


/* Every sign-in, sign-out and token refresh, in this tab or another
   (supabase-js relays other tabs' changes). Returns the unsubscribe. */
function onAuthChange(callback) {
  const { data } = window.DB.auth.onAuthStateChange(callback);
  return () => data.subscription.unsubscribe();
}


/* --------------------------------------------------------------- pure */

const AUTH_EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/* Supabase Auth's lowest allowed minimum password length. A project
   setting can only raise it, and the server's weak_password message names
   the raised length, so the client never asks for more than the server. */
const AUTH_PASSWORD_MIN = 6;

const AUTH_MSG = {
  network: "Could not reach the account service. Check your connection and try again.",
  credentials: "Wrong email or password.",
  unverified: "This email is not verified yet. Open the link in the verification email, then log in.",
  exists: "An account with this email already exists. Log in instead.",
  email: "That email address is not valid.",
  weak: "That password is too weak. Use a longer one.",
  emailRate: "Too many emails were sent to this address. Wait a few minutes, then try again.",
  rate: "Too many attempts. Wait a minute, then try again.",
  closed: "New accounts cannot be created right now.",
  link: "This email link is invalid or has expired. If your account is verified, log in; otherwise log in to request a new link.",
  unavailable: "Accounts are unavailable: the sign-in service did not load. Check your connection or content blocker, then reload the page.",
  unknown: "Something went wrong. Try again."
};

const AUTH_CODE_KIND = {
  invalid_credentials: "credentials",
  email_not_confirmed: "unverified",
  user_already_exists: "exists",
  email_exists: "exists",
  email_address_invalid: "email",
  weak_password: "weak",
  over_email_send_rate_limit: "emailRate",
  over_request_rate_limit: "rate",
  signup_disabled: "closed",
  email_provider_disabled: "closed",
  otp_expired: "link",
  access_denied: "link"
};


function validateLogIn({ email, password }) {
  const errors = {};
  const address = String(email || "").trim();

  if (!address) {
    errors.email = "Enter your email.";
  } else if (!AUTH_EMAIL_RE.test(address)) {
    errors.email = "Enter a valid email address.";
  }

  if (!password) {
    errors.password = "Enter your password.";
  }

  return errors;
}


/* The database's bound on both names (the profiles_*_clean checks in
   supabase/migrations; tests/test_supabase_schema.py pins that the two
   agree): a storage bound against abuse, not a game rule. */
const ACCOUNT_NAME_MAX = 64;

/* the length the database counts: characters, not UTF-16 units */
const nameLength = value => Array.from(String(value || "").trim()).length;


/* The game's servers, as the database stores them (the
   profiles_albion_server_known check; tests/test_supabase_schema.py pins
   that the two agree) and as a player reads them. A character name is
   unique per server, not across the game. */
const ALBION_SERVERS = { americas: "Americas", asia: "Asia", europe: "Europe" };


/* A character is its name and its server, both required; a name of spaces
   alone counts as empty. The display name is optional. Shared by sign-up
   and the profile form. */
function validateIdentity({ albionName, albionServer, displayName }) {
  const errors = {};

  if (!String(albionName || "").trim()) {
    errors.albionName = "Enter your Albion character name.";
  } else if (nameLength(albionName) > ACCOUNT_NAME_MAX) {
    errors.albionName = `Use at most ${ACCOUNT_NAME_MAX} characters.`;
  }

  if (!Object.prototype.hasOwnProperty.call(ALBION_SERVERS, albionServer || "")) {
    errors.albionServer = "Choose the server your character plays on.";
  }

  if (nameLength(displayName) > ACCOUNT_NAME_MAX) {
    errors.displayName = `Use at most ${ACCOUNT_NAME_MAX} characters.`;
  }

  return errors;
}


/* Passwords are never trimmed. */
function validateSignUp({ email, password, albionName, albionServer, displayName }) {
  const errors = validateLogIn({ email, password });

  if (password && password.length < AUTH_PASSWORD_MIN) {
    errors.password = `Use at least ${AUTH_PASSWORD_MIN} characters.`;
  }

  return Object.assign(errors, validateIdentity({ albionName, albionServer, displayName }));
}


/* With email verification on, signUp answers an address that already has
   an account with a user holding no identities instead of an error, so an
   address cannot be probed through the error channel. */
function isExistingAccount(data) {
  const user = data && data.user;
  return !!(user && Array.isArray(user.identities) && user.identities.length === 0);
}


function authErrorKind(err) {
  const code = String((err && (err.code || err.error_code)) || "");
  const message = String((err && err.message) || "");
  const name = String((err && err.name) || "");

  if (name === "AuthRetryableFetchError" || (err && err.status === 0)
      || /failed to fetch|networkerror|network request failed|load failed/i.test(message)
      || (typeof navigator !== "undefined" && navigator.onLine === false)) {
    return "network";
  }

  if (AUTH_CODE_KIND[code]) {
    return AUTH_CODE_KIND[code];
  }

  /* servers older than error codes answer with the message alone */
  if (/invalid login credentials/i.test(message)) return "credentials";
  if (/email not confirmed/i.test(message)) return "unverified";
  if (/already (?:been )?registered|already exists/i.test(message)) return "exists";
  if (/password/i.test(message) && /weak|at least|should (?:be|contain)/i.test(message)) return "weak";
  if (/email/i.test(message) && /invalid|unable to validate/i.test(message)) return "email";
  if (/rate limit/i.test(message)) return /email/i.test(message) ? "emailRate" : "rate";
  if (/signups? not allowed|signups? (?:are |is )?disabled/i.test(message)) return "closed";
  if (/link is invalid|has expired/i.test(message)) return "link";

  return "unknown";
}


function authErrorMessage(err) {
  const kind = authErrorKind(err);
  const message = String((err && err.message) || "").trim();

  /* the server's weak_password message names the rule the password broke
     (its length, its character classes, a known leaked password) */
  if (kind === "weak" && message) {
    return message;
  }

  if (kind === "unknown" && message) {
    return `Something went wrong: ${message}`;
  }

  return AUTH_MSG[kind];
}


/* The account's names and server. The profile row decides; the sign-up
   metadata stands in while the row is unreadable. label: display name,
   else Albion name, else "Account". server: a key of ALBION_SERVERS, or ""
   when none is recorded. */
function accountNames(profile, user) {
  const source = profile || (user && user.user_metadata) || {};
  const clean = value => (typeof value === "string" ? value.trim() : "");
  const display = clean(source.display_name);
  const albion = clean(source.albion_name);
  const server = Object.prototype.hasOwnProperty.call(ALBION_SERVERS, clean(source.albion_server))
    ? clean(source.albion_server) : "";

  return { label: display || albion || "Account", display, albion, server };
}


function accountLabel(profile, user) {
  return accountNames(profile, user).label;
}


/* An email link's return: the new session's tokens, or the link's error.
   Anything else (a share-link hash, junk) is null. */
function parseAuthLink(link) {
  if (!link) {
    return null;
  }

  const params = new URLSearchParams(String(link).replace(/^[#?]/, ""));

  if (params.get("error_description") || params.get("error")) {
    return {
      error: {
        code: params.get("error_code") || params.get("error") || "",
        message: params.get("error_description") || ""
      }
    };
  }

  const accessToken = params.get("access_token");
  const refreshToken = params.get("refresh_token");

  if (!accessToken || !refreshToken) {
    return null;
  }

  return { accessToken, refreshToken, type: params.get("type") || "" };
}


/* ------------------------------------------------------------- UI kit */
/* Shared by every account dialog: the sign-in dialog below and the profile
   dialog (_profile.js). */

/* aria-disabled, not disabled: a disabled button drops keyboard focus to
   the page behind the dialog. The caller's busy flag is what refuses a
   second submit. */
function acctBusy(button, text) {
  button.dataset.idle = button.textContent;
  button.textContent = text;
  button.setAttribute("aria-busy", "true");
  button.setAttribute("aria-disabled", "true");
}


function acctIdle(button) {
  if (button.dataset.idle === undefined) return;
  button.textContent = button.dataset.idle;
  delete button.dataset.idle;
  button.removeAttribute("aria-busy");
  button.removeAttribute("aria-disabled");
}


/* inputs: {key: input}; errors: {key: message}. Writes each message into
   the input's #<id>-err, flags the input, and returns the first flagged
   input (null when none). An empty errors object clears every flag. */
function acctFlagFields(inputs, errors) {
  let first = null;

  for (const [key, input] of Object.entries(inputs)) {
    const message = errors[key] || "";
    const out = document.getElementById(`${input.id}-err`);
    if (out) out.textContent = message;

    if (message) {
      input.setAttribute("aria-invalid", "true");
      first = first || input;
    } else {
      input.removeAttribute("aria-invalid");
    }
  }

  return first;
}


/* one message at a time: kind "error", "notice", or null for neither */
function acctMessage(errorEl, noticeEl, kind, text) {
  errorEl.hidden = kind !== "error";
  errorEl.textContent = kind === "error" ? text : "";
  noticeEl.hidden = kind !== "notice";
  noticeEl.textContent = kind === "notice" ? text : "";
}


/* A native <dialog> opened with showModal() gets: Escape closes it (the
   cancel event); the planner's document-level shortcuts never see keys
   typed in it; a click on the backdrop closes it when canClose() allows,
   and a text selection dragged out of a field and released on the
   backdrop never does; editing a flagged field clears its flag; closing
   returns focus to the account button (the element that opened the
   dialog may be a menu item that is hidden by now). */
function acctWireDialog(dialog, { canClose = () => true } = {}) {
  dialog.addEventListener("keydown", e => e.stopPropagation());

  let downOutside = false;
  const outside = e => {
    const r = dialog.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  };
  dialog.addEventListener("pointerdown", e => { downOutside = e.target === dialog && outside(e); });
  dialog.addEventListener("click", e => {
    if (downOutside && e.target === dialog && outside(e) && canClose()) dialog.close();
    downOutside = false;
  });

  dialog.addEventListener("input", e => {
    const input = e.target;
    if (input.getAttribute("aria-invalid") !== "true") return;
    input.removeAttribute("aria-invalid");
    const out = document.getElementById(`${input.id}-err`);
    if (out) out.textContent = "";
  });

  dialog.addEventListener("close", () => {
    const btn = document.getElementById("acct-btn");
    if (btn) btn.focus();
  });
}


/* ----------------------------------------------------------------- UI */

(function accountUI() {
  if (typeof document === "undefined") {
    return;
  }

  const $id = id => document.getElementById(id);
  const btn = $id("acct-btn");
  const menu = $id("acct-menu");
  const dialog = $id("auth-dialog");

  if (!btn || !menu || !dialog || typeof dialog.showModal !== "function") {
    return;
  }

  const SERVICE = authServiceReady();

  const el = {
    btnName: btn.querySelector(".acct-name"),
    btnInit: btn.querySelector(".acct-init"),
    menuName: $id("acct-menu-name"),
    menuAlbion: $id("acct-menu-albion"),
    menuEmail: $id("acct-menu-email"),
    menuErr: $id("acct-menu-err"),
    profileItem: $id("acct-profile"),
    logoutItem: $id("acct-logout"),
    title: $id("auth-title"),
    error: $id("auth-error"),
    notice: $id("auth-notice"),
    login: $id("auth-login"),
    signup: $id("auth-signup"),
    info: $id("auth-info"),
    infoBody: $id("auth-info-body"),
    infoPrimary: $id("auth-info-primary"),
    infoSecondary: $id("auth-info-secondary"),
    loginSubmit: $id("login-submit"),
    signupSubmit: $id("signup-submit"),
    resend: $id("login-resend")
  };

  const FIELDS = {
    login: {
      email: $id("login-email"),
      password: $id("login-password")
    },
    signup: {
      email: $id("signup-email"),
      password: $id("signup-password"),
      albionName: $id("signup-albion"),
      albionServer: $id("signup-server"),
      displayName: $id("signup-display")
    }
  };

  const TITLES = {
    login: "Log in",
    signup: "Create account",
    sent: "Check your email",
    verified: "Email verified"
  };

  /* one identity at a time: id is undefined until the stored session has
     been read, then a user id or null. A profile read that returns after
     the identity changed is dropped (seq). */
  const state = { ready: false, id: undefined, user: null, profile: null, seq: 0 };


  /* ---- the account store ----
     Feature modules (_profile.js; guilds and events after it) read the
     identity here instead of asking Supabase again, hear every change, and
     offer views the account menu opens. Each module is its own <script>
     after this one (build.py). */

  const listeners = new Set();
  const views = {};
  const snapshot = () => ({ ready: state.ready, user: state.user, profile: state.profile });

  function notify() {
    const now = snapshot();
    for (const fn of listeners) {
      try { fn(now); } catch (err) { console.error("account listener failed:", err); }
    }
  }

  window.Account = Object.freeze({
    current: snapshot,

    /* fn(state) at once and on every identity or profile change;
       returns the unsubscribe */
    subscribe(fn) {
      listeners.add(fn);
      fn(snapshot());
      return () => listeners.delete(fn);
    },

    /* a module saved this account's profile row: the masthead and every
       listener follow it */
    updateProfile(profile) {
      if (!state.user || !profile || profile.id !== state.user.id) return;
      state.profile = profile;
      paint();
    },

    /* open(): a view the account menu offers by name ("profile") */
    registerView(name, open) {
      views[name] = open;
      paint();
    }
  });

  /* one auth request at a time, from any button in the dialog; while it
     is in flight the dialog's controls wait (Close and Escape still work) */
  let busy = false;
  /* bumped by every view change, the dialog's reopening included: a
     request's message lands only on the view that sent it */
  let viewSeq = 0;
  let sentTo = "";
  let infoActions = { primary: null, secondary: null };


  /* ---- account state -> the masthead button and the menu ---- */

  function adopt(user, force) {
    const id = user ? user.id : null;
    state.ready = true;

    if (!force && id === state.id) {
      if (user) state.user = user;
      paint();
      return;
    }

    state.id = id;
    state.user = user || null;
    state.profile = null;
    const seq = ++state.seq;
    paint();

    /* a login form the new identity made stale closes (another tab logged
       in); feature dialogs close themselves on the change (subscribe) */
    const view = dialog.open ? dialog.dataset.view : "";
    if (user && (view === "login" || view === "signup")) {
      closeDialog();
    }

    if (!user) return;

    getCurrentProfile()
      .then(profile => {
        if (seq !== state.seq) return;
        state.profile = profile;
        paint();
      })
      .catch(() => { /* the metadata names stay */ });
  }

  function paint() {
    const signedIn = !!state.user;
    const names = accountNames(state.profile, state.user);

    btn.dataset.state = !state.ready ? "pending" : signedIn ? "in" : "out";
    el.btnName.textContent = signedIn ? names.label : "Log in";
    el.btnInit.textContent = signedIn ? Array.from(names.label)[0].toUpperCase() : "";

    if (signedIn) {
      /* a disclosure: the menu is plain buttons, not an ARIA menu */
      btn.removeAttribute("aria-haspopup");
      btn.setAttribute("aria-controls", "acct-menu");
      btn.setAttribute("aria-expanded", String(!menu.hidden));
      btn.setAttribute("aria-label", `${names.label}: account menu`);
      btn.title = `logged in as ${names.label}`;
    } else {
      closeMenu(false);
      btn.setAttribute("aria-haspopup", "dialog");
      btn.removeAttribute("aria-controls");
      btn.removeAttribute("aria-expanded");
      btn.removeAttribute("aria-label");
      btn.title = "log in or create an account";
    }

    el.menuName.textContent = names.label;
    const character = [names.albion !== names.label ? names.albion : "",
                       ALBION_SERVERS[names.server] || ""].filter(Boolean).join(" · ");
    el.menuAlbion.textContent = character ? `Albion: ${character}` : "";
    el.menuEmail.textContent = (state.user && state.user.email) || "";
    el.profileItem.hidden = !views.profile;

    notify();
  }


  /* ---- the account menu ---- */

  function placeMenu() {
    const r = btn.getBoundingClientRect();

    /* the phone masthead scrolls its top rows away: a menu whose button
       left the screen closes instead of floating free */
    if (r.bottom < 0 || r.top > window.innerHeight) {
      closeMenu(false);
      return;
    }

    menu.style.top = `${Math.round(r.bottom + 8)}px`;
    menu.style.right = `${Math.max(16, Math.round(document.documentElement.clientWidth - r.right))}px`;
  }

  function openMenu() {
    el.menuErr.textContent = "";
    menu.hidden = false;
    placeMenu();
    btn.setAttribute("aria-expanded", "true");
    menuItems()[0].focus();
  }

  /* the items on offer: Profile shows once a module registered the view */
  const menuItems = () => [el.profileItem, el.logoutItem].filter(item => !item.hidden);

  function closeMenu(returnFocus) {
    if (menu.hidden) return;
    menu.hidden = true;
    if (btn.hasAttribute("aria-expanded")) btn.setAttribute("aria-expanded", "false");
    if (returnFocus) btn.focus();
  }

  btn.addEventListener("click", () => {
    if (!state.user) {
      openDialog("login");
    } else if (menu.hidden) {
      openMenu();
    } else {
      closeMenu(true);
    }
  });

  document.addEventListener("pointerdown", e => {
    if (!menu.hidden && !menu.contains(e.target) && !btn.contains(e.target)) {
      closeMenu(false);
    }
  }, true);

  window.addEventListener("scroll", () => { if (!menu.hidden) placeMenu(); },
                          { passive: true, capture: true });
  window.addEventListener("resize", () => { if (!menu.hidden) placeMenu(); });

  menu.addEventListener("keydown", e => {
    /* the planner's own shortcuts ("/", Escape) stay out of the menu */
    e.stopPropagation();
    const items = menuItems();

    if (e.key === "Escape") {
      e.preventDefault();
      closeMenu(true);
    } else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const at = items.indexOf(document.activeElement);
      const step = e.key === "ArrowDown" ? 1 : -1;
      const next = at < 0 ? 0 : (at + step + items.length) % items.length;
      items[next].focus();
    } else if (e.key === "Tab") {
      /* the menu sits at the end of the document: Tab returns to the
         button instead of falling off the page */
      e.preventDefault();
      closeMenu(true);
    }
  });

  el.profileItem.addEventListener("click", () => {
    closeMenu(false);
    if (views.profile) views.profile();
  });

  el.logoutItem.addEventListener("click", async () => {
    if (el.logoutItem.getAttribute("aria-busy") === "true") return;
    el.menuErr.textContent = "";
    acctBusy(el.logoutItem, "Logging out…");

    try {
      await signOutUser();
      /* SIGNED_OUT follows through onAuthChange; the button changes now */
      adopt(null);
      btn.focus();
    } catch (err) {
      el.menuErr.textContent = authErrorMessage(err);
    } finally {
      acctIdle(el.logoutItem);
    }
  });


  /* ---- the dialog ---- */

  function showView(view) {
    viewSeq++;
    dialog.dataset.view = view;
    el.title.textContent = TITLES[view];
    el.login.hidden = view !== "login";
    el.signup.hidden = view !== "signup";
    el.info.hidden = !(view === "sent" || view === "verified");
    clearMessages();

    if ((view === "login" || view === "signup") && !SERVICE) {
      showError(AUTH_MSG.unavailable);
    }

    if (view === "sent") fillSent();
    if (view === "verified") fillVerified();
  }

  function focusView(view) {
    const fields = FIELDS[view];

    if (fields) {
      const first = view === "login" && fields.email.value.trim() ? fields.password : fields.email;
      first.focus();
      return;
    }

    el.infoPrimary.focus();
  }

  function openDialog(view) {
    closeMenu(false);
    showView(view);
    if (!dialog.open) dialog.showModal();
    focusView(view);
  }

  function closeDialog() {
    if (dialog.open) dialog.close();
  }

  acctWireDialog(dialog);

  $id("auth-close").addEventListener("click", closeDialog);

  dialog.addEventListener("click", e => {
    const to = e.target.closest("[data-auth-view]");
    if (!to || busy) return;
    const view = to.dataset.authView;

    /* the address typed in one form follows to the other */
    const from = FIELDS[dialog.dataset.view];
    if (from && FIELDS[view] && from.email.value.trim() && !FIELDS[view].email.value.trim()) {
      FIELDS[view].email.value = from.email.value.trim();
    }

    showView(view);
    focusView(view);
  });


  /* ---- messages, field errors, busy buttons ---- */

  const showError = message => acctMessage(el.error, el.notice, "error", message);
  const showNotice = message => acctMessage(el.error, el.notice, "notice", message);

  function clearMessages() {
    acctMessage(el.error, el.notice, null, "");
    el.resend.hidden = true;
    for (const fields of Object.values(FIELDS)) acctFlagFields(fields, {});
  }

  /* flags the view's fields and focuses the first flagged one; true when
     any field was flagged */
  function showFieldErrors(view, errors) {
    const first = acctFlagFields(FIELDS[view], errors);
    if (first) first.focus();
    return !!first;
  }

  /* work(live): live() is false once the dialog was closed or moved to
     another view, so a late answer never writes over what is on screen */
  async function request(button, text, work) {
    if (busy) return;

    if (!SERVICE) {
      showError(AUTH_MSG.unavailable);
      return;
    }

    busy = true;
    acctBusy(button, text);
    const asked = viewSeq;
    const live = () => dialog.open && viewSeq === asked;

    try {
      await work(live);
    } finally {
      busy = false;
      acctIdle(button);
    }
  }


  /* ---- log in ---- */

  el.login.addEventListener("submit", e => {
    e.preventDefault();
    if (busy) return;

    const fields = FIELDS.login;
    const email = fields.email.value.trim();
    const password = fields.password.value;

    clearMessages();
    if (showFieldErrors("login", validateLogIn({ email, password }))) return;

    request(el.loginSubmit, "Logging in…", async live => {
      try {
        const data = await signInUser(email, password);
        fields.password.value = "";
        adopt(data.user || (data.session && data.session.user) || null);
        closeDialog();
      } catch (err) {
        if (!live()) return;
        showError(authErrorMessage(err));
        const kind = authErrorKind(err);

        if (kind === "unverified") {
          el.resend.hidden = false;
        } else if (kind === "credentials") {
          fields.password.select();
          fields.password.focus();
        }
      }
    });
  });

  el.resend.addEventListener("click", () => {
    const email = FIELDS.login.email.value.trim();
    const errors = validateLogIn({ email, password: "-" });
    if (showFieldErrors("login", errors)) return;
    resend(el.resend, email);
  });


  /* ---- create account ---- */

  el.signup.addEventListener("submit", e => {
    e.preventDefault();
    if (busy) return;

    const fields = FIELDS.signup;
    const input = {
      email: fields.email.value.trim(),
      password: fields.password.value,
      albionName: fields.albionName.value.trim(),
      albionServer: fields.albionServer.value,
      displayName: fields.displayName.value.trim()
    };

    clearMessages();
    if (showFieldErrors("signup", validateSignUp(input))) return;

    request(el.signupSubmit, "Creating account…", async live => {
      try {
        const data = await signUpUser({
          email: input.email,
          password: input.password,
          albionName: input.albionName,
          albionServer: input.albionServer,
          /* an empty display name is stored as none, so the masthead
             falls back to the Albion name */
          displayName: input.displayName || null
        });

        if (isExistingAccount(data)) {
          if (live()) showError(AUTH_MSG.exists);
          return;
        }

        fields.password.value = "";

        /* a project without email verification signs the account in */
        if (data.session) {
          adopt(data.session.user);
          closeDialog();
          return;
        }

        /* the account exists now: its next step is shown even when the
           dialog was closed while the request ran */
        sentTo = input.email;
        FIELDS.login.email.value = input.email;
        openDialog("sent");
      } catch (err) {
        if (live()) showError(authErrorMessage(err));
      }
    });
  });


  /* ---- information views: sent, verified ---- */

  function paragraph(text, strong) {
    const p = document.createElement("p");

    if (strong) {
      const b = document.createElement("strong");
      b.textContent = strong;
      p.append(text[0], b, text[1]);
    } else {
      p.textContent = text;
    }

    return p;
  }

  function setInfoActions(primary, secondary) {
    el.infoPrimary.textContent = primary.label;
    infoActions.primary = primary.run;
    el.infoSecondary.hidden = !secondary;

    if (secondary) {
      el.infoSecondary.textContent = secondary.label;
      infoActions.secondary = secondary.run;
    } else {
      infoActions.secondary = null;
    }
  }

  function fillSent() {
    el.infoBody.replaceChildren(
      paragraph("Account created. Check your email to verify your account."),
      paragraph(["The verification link went to ", ". After you open it, log in here."], sentTo)
    );
    setInfoActions(
      { label: "Back to login", run: () => { showView("login"); focusView("login"); } },
      { label: "Resend email", run: () => resend(el.infoSecondary, sentTo) }
    );
  }

  function fillVerified() {
    el.infoBody.replaceChildren(
      paragraph("Your email is verified and you are logged in.")
    );
    setInfoActions({ label: "Continue", run: closeDialog });
  }

  el.infoPrimary.addEventListener("click", () => {
    if (!busy && infoActions.primary) infoActions.primary();
  });

  el.infoSecondary.addEventListener("click", () => {
    if (!busy && infoActions.secondary) infoActions.secondary();
  });

  function resend(button, email) {
    request(button, "Sending…", async live => {
      try {
        await resendVerificationEmail(email);
        if (live()) showNotice(`A new verification email is on its way to ${email}.`);
      } catch (err) {
        if (live()) showError(authErrorMessage(err));
      }
    });
  }


  /* ---- an email link's return (the <head> script set it aside) ---- */

  function adoptEmailLink() {
    const parsed = parseAuthLink(window.AUTH_LINK || "");
    window.AUTH_LINK = "";

    if (!parsed) return;

    if (!SERVICE || parsed.error) {
      openDialog("login");
      if (parsed.error) showError(authErrorMessage(parsed.error));
      return;
    }

    adoptEmailLinkSession(parsed)
      .then(data => {
        adopt(data.user || (data.session && data.session.user) || null);
        if (parsed.type === "signup") openDialog("verified");
      })
      .catch(err => {
        openDialog("login");
        showError(authErrorMessage(err));
      });
  }


  /* ---- boot ---- */

  paint();

  if (!SERVICE) {
    state.ready = true;
    paint();
    adoptEmailLink();
    return;
  }

  onAuthChange((event, session) => {
    /* supabase-js runs this callback while it holds its auth lock: a
       Supabase call awaited inside would wait on that lock forever, so the
       work runs after it */
    setTimeout(() => {
      if (event === "SIGNED_OUT") {
        adopt(null);
      } else {
        adopt(session ? session.user : null, event === "USER_UPDATED");
      }
    }, 0);
  });

  /* a persisted session (localStorage) survives the reload */
  getCurrentUser()
    .then(user => adopt(user))
    .catch(() => adopt(null));

  adoptEmailLink();
})();

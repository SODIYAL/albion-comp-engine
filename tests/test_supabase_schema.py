"""Schema rules for supabase/migrations/ (supabase/README.md).

Script-style (NOT pytest): runs at import, exits 0 on pass. Reads the
migration files as text; tests/test_supabase_rls.mjs runs them against a
real Postgres. This file pins the rules a behaviour test cannot see: a
function that runs with its definer's rights behaves exactly like one that runs as the
caller until its own WHERE clause has a bug, so SECURITY DEFINER is a
listed exception, never a default.

    py -3 tests/test_supabase_schema.py
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MIGRATIONS = os.path.join(ROOT, "supabase", "migrations")

FAILURES = []

# The functions allowed to run with their definer's rights, each with the
# reason a caller's rights cannot do the job (supabase/README.md rule 8).
# Keyed by schema: a helper that policies call lives in `private`, which
# the API does not expose (Supabase lint 0029); the API schema keeps the
# sign-up trigger alone, which no API role can execute.
DEFINER_ALLOWED = {
    # the sign-up trigger writes the new user's profile row before any
    # session exists to write it
    "public.handle_new_user": "trigger",
    # a policy on guild_members that read guild_members under its own
    # policy would recurse; the helper answers for the caller alone
    "private.guild_role_of": "policy helper",
    # the insert policy checks a join code against a guild the joiner
    # cannot yet read
    "private.guild_id_for_code": "policy helper",
    # the member bound counts rows the joiner cannot yet read
    "private.guild_member_count": "guard helper",
    # the broadcast trigger writes realtime.messages, which row-level
    # security keeps from the API roles (no policy for them: a send as
    # the caller lands nothing); the message names a table and an
    # operation, and no API role can call the function
    "public.sheet_changed": "trigger",
    # the attendance record is the guild's: no API role holds an insert
    # or delete grant on it, so the mirror from sign-ups and the
    # settlement at completion write it with the definer's rights; no
    # API role can call the function
    "public.attendance_record": "trigger",
}

# A guest's reach (supabase/README.md rule 13): the tables `anon` reads
# through policies that check the CTA's share code carried by the
# statement, and the functions a guest calls (each running as the
# caller). Nothing else is granted to anon, and no anon policy stands
# without the code.
GUEST_TABLES = {"events", "event_slots", "guilds", "signups", "attendance"}
GUEST_FUNCTIONS = {"public.claim_hash", "public.event_by_code", "public.sign_up", "public.cancel_sign_up", "public.confirm_sign_up"}


def check(cond, label, detail=""):
    if cond:
        print("  ok   %s" % label)
    else:
        print("  FAIL %s%s" % (label, (" - " + detail) if detail else ""))
        FAILURES.append(label)


def read(path):
    with open(path, "rb") as f:
        raw = f.read()
    return raw, raw.decode("utf-8")


def strip_comments(sql):
    """Line comments out; string literals in these files carry no '--'."""
    return re.sub(r"--[^\n]*", "", sql)


print("DB1 - migration files")
names = sorted(f for f in os.listdir(MIGRATIONS) if f.endswith(".sql"))
check(bool(names), "DB1a supabase/migrations holds the schema")
SQL = {}
for name in names:
    raw, text = read(os.path.join(MIGRATIONS, name))
    check(re.fullmatch(r"\d{14}_[a-z0-9_]+\.sql", name) is not None,
          "DB1b %s is named <14-digit version>_<snake_case>.sql" % name)
    check(b"\r" not in raw, "DB1c %s uses LF line endings" % name)
    SQL[name] = strip_comments(text)
versions = [n[:14] for n in names]
check(len(set(versions)) == len(versions), "DB1d every migration version is unique")
ALL = "\n".join(SQL[n] for n in names)

print("DB2 - every table: RLS on, anon revoked, policies for signed-in users")
tables = sorted(set(re.findall(r"create table (?:if not exists )?public\.(\w+)", ALL)))
check(bool(tables), "DB2a the migrations create tables")
for t in tables:
    check(re.search(r"alter table public\.%s enable row level security" % t, ALL) is not None,
          "DB2b %s enables row level security" % t)
    revokes = re.findall(r"revoke all on table public\.%s from ([^;]+);" % t, ALL)
    check(any("anon" in r for r in revokes),
          "DB2c %s revokes the project's default grants from anon" % t,
          "default privileges grant every new public table to anon")
    policies = re.findall(r"create policy \"[^\"]+\" on public\.%s\s+for (\w+) to ([\w, ]+)" % t, ALL)
    check(bool(policies), "DB2d %s has policies" % t)
    check(all(roles.strip() == "authenticated" or (roles.strip() == "anon" and t in GUEST_TABLES)
              for _op, roles in policies),
          "DB2e every policy on %s is for signed-in users, or for guests on a table a share code opens" % t,
          str(policies))
    anon_policies = re.findall(r"create policy \"[^\"]+\" on public\.%s\s+for \w+ to anon\s+(.*?);" % t, ALL, re.S)
    check(all(re.search(r"app\.share_code|app\.claim_token|from public\.events", body) for body in anon_policies),
          "DB2e2 every guest policy on %s reads the share code (or the CTA it names) from the statement" % t)
    if re.search(r"create table (?:if not exists )?public\.%s \([^;]*\bupdated_at\b" % t, ALL):
        check(re.search(r"before update on public\.%s\s+for each row execute function public\.set_updated_at\(\)" % t, ALL)
              is not None, "DB2f %s keeps updated_at through set_updated_at()" % t)
anon_grants = [g for g in re.findall(r"grant [^;]*\bto\b[^;]*\banon\b[^;]*;", ALL)]
check(all(re.search(r"on table public\.(%s)\b" % "|".join(sorted(GUEST_TABLES)), g)
          or re.search(r"on function (%s)\(" % "|".join(re.escape(f) for f in sorted(GUEST_FUNCTIONS)), g)
          for g in anon_grants),
      "DB2g nothing is granted to anon beyond the guest tables and the guest functions", str(anon_grants))
check(not any(re.search(r"grant (all|insert|update|delete)[^;]*on table public\.(events|event_slots|guilds)\b[^;]*\banon\b", g)
              for g in anon_grants),
      "DB2g2 a guest reads the CTA, its slots and its guild, and writes only sign-ups and their own record's status")

print("DB3 - policies read auth.uid() and current_setting() once per statement")
# the definition in force: the last create or alter of each policy, in
# file order (an earlier form a later migration replaced is history)
policy_stmts = {}
for stmt in re.findall(r"(?:create|alter) policy [^;]+;", ALL):
    policy_stmts[re.search(r"\"([^\"]+)\"", stmt).group(1)] = stmt
for name, stmt in policy_stmts.items():
    bare = re.findall(r"(?<!select )(?:auth\.uid\(\)|current_setting\()", stmt)
    check(not bare, "DB3a %s uses (select auth.uid()) and (select current_setting(...))" % name,
          "a bare call re-evaluates per row (Supabase lint 0003)")

print("DB4 - functions (the definition in force: the last one in file order, dropped ones gone)")
FUNC = re.compile(r"create or replace function (public|private)\.(\w+)\(([^)]*)\)\s+returns\s+([\w.]+(?: [\w.]+)?)(.*?)\$\$(.*?)\$\$;",
                  re.S)
DROP = re.compile(r"drop function if exists (public|private)\.(\w+)\(([^)]*)\);")
funcs = {}
for name in names:
    text = SQL[name]
    events = sorted([(m.start(), "def", m) for m in FUNC.finditer(text)]
                    + [(m.start(), "drop", m) for m in DROP.finditer(text)])
    for _at, kind, m in events:
        schema, fname = m.group(1), m.group(2)
        arg_types = ", ".join(a.split(" default ")[0].split()[-1] for a in m.group(3).split(",") if a.strip())
        key = "%s.%s(%s)" % (schema, fname, arg_types)
        if kind == "drop":
            funcs.pop(key, None)
        else:
            funcs[key] = m
check(bool(funcs), "DB4a the migrations define functions")
for key, m in funcs.items():
    schema, fname, args, returns, header, body = m.groups()
    sig = "%s.%s(%s)" % (schema, fname, args.strip())
    listed = "%s.%s" % (schema, fname)
    check("set search_path = ''" in header, "DB4b %s pins an empty search_path" % sig,
          "Supabase lint 0011")
    arg_types = ", ".join(a.split(" default ")[0].split()[-1] for a in args.split(",") if a.strip())
    revokes = re.findall(r"revoke execute on function %s\.%s\(%s\) from ([^;]+);"
                         % (schema, fname, re.escape(arg_types)), ALL)
    revoked = {r.strip() for line in revokes for r in line.split(",")}
    definer = "security definer" in header
    if returns == "trigger":
        check({"public", "anon", "authenticated"} <= revoked,
              "DB4c trigger function %s is revoked from public, anon and authenticated" % sig,
              "revoked from: %s" % sorted(revoked))
        check(not definer or listed in DEFINER_ALLOWED,
              "DB4d trigger function %s runs as the caller unless listed" % sig)
    else:
        check(("security invoker" in header and not definer) or listed in DEFINER_ALLOWED,
              "DB4e function %s is SECURITY INVOKER (policies bound it) unless listed" % sig)
        check(not definer or schema == "private",
              "DB4e2 definer helper %s lives in the private schema, out of the API's reach (lint 0029)" % sig)
        guest = listed in GUEST_FUNCTIONS
        check("public" in revoked and (guest or "anon" in revoked),
              "DB4f function %s is revoked from public and anon (a guest function keeps anon)" % sig,
              "revoked from: %s" % sorted(revoked))
        check(re.search(r"grant execute on function %s\.%s\(%s\) to %s;"
                        % (schema, fname, re.escape(arg_types), "anon, authenticated" if guest else "authenticated"), ALL) is not None,
              "DB4g function %s is granted to %s" % (sig, "guests and signed-in users" if guest else "authenticated"))
        check(not guest or "security invoker" in header,
              "DB4g2 guest function %s runs as the caller: the policies bound a guest exactly" % sig)
check(re.search(r"grant usage on schema private to authenticated", ALL) is not None
      and re.search(r"revoke all on schema private from public", ALL) is not None,
      "DB4h the private schema is usable by signed-in users and no one else")
in_force = {k.split("(")[0] for k in funcs}
check(all(k in in_force for k in DEFINER_ALLOWED if k != "public.handle_new_user")
      and "public.handle_new_user" in in_force, "DB4i every listed definer is defined", str(sorted(in_force)))

print("DB5 - the client's bounds are the database's")
with open(os.path.join(ROOT, "dashboard", "_profile.js"), encoding="utf-8") as f:
    PROFILE_JS = f.read()
with open(os.path.join(ROOT, "dashboard", "_auth.js"), encoding="utf-8") as f:
    AUTH_JS = f.read()
with open(os.path.join(ROOT, "dashboard", "_shell.html"), encoding="utf-8") as f:
    SHELL = f.read()


def js_const(src, name):
    m = re.search(r"const %s = (\d+);" % name, src)
    return int(m.group(1)) if m else None


name_max = js_const(AUTH_JS, "ACCOUNT_NAME_MAX")
sql_name_bounds = set(re.findall(r"char_length\((?:albion|display)_name\) between 1 and (\d+)", ALL))
check(name_max is not None and sql_name_bounds == {str(name_max)},
      "DB5a ACCOUNT_NAME_MAX (_auth.js) is the profiles name bound",
      "js %s, sql %s" % (name_max, sorted(sql_name_bounds)))
trigger_cut = set(re.findall(r"left\(btrim\(new\.raw_user_meta_data ->> '\w+'\), (\d+)\)", ALL))
check(trigger_cut == {str(name_max)}, "DB5b the sign-up trigger cuts names at the same bound",
      str(sorted(trigger_cut)))
for field in ("signup-albion", "signup-display", "profile-albion", "profile-display"):
    tag = re.search(r'<input[^>]*\bid="%s"[^>]*>' % field, SHELL)
    length = tag and re.search(r'\bmaxlength="(\d+)"', tag.group(0))
    check(length is not None and int(length.group(1)) == name_max,
          "DB5c the %s field's maxlength is the bound" % field,
          tag.group(0) if tag else "field missing")
weapons_max = js_const(PROFILE_JS, "WEAPONS_MAX")
sql_weapon_bounds = set(re.findall(r"(?:count\(\*\) from public\.player_weapons where user_id = new\.user_id\) >= |jsonb_array_length\(weapons\) > )(\d+)", ALL))
check(weapons_max is not None and sql_weapon_bounds == {str(weapons_max)},
      "DB5d WEAPONS_MAX (_profile.js) is the player_weapons bound",
      "js %s, sql %s" % (weapons_max, sorted(sql_weapon_bounds)))
js_key = re.search(r"const WEAPON_KEY_RE = /(.+?)/;", PROFILE_JS)
sql_key = re.search(r"weapon_id ~ '(.+?)'", ALL)
check(js_key is not None and sql_key is not None and js_key.group(1) == sql_key.group(1),
      "DB5e the client's weapon key form is the database's",
      "js %s, sql %s" % (js_key and js_key.group(1), sql_key and sql_key.group(1)))
prefs_js = re.search(r"const WEAPON_PREFERENCES = \[([^\]]+)\];", PROFILE_JS)
prefs_sql = re.search(r"preference in \(([^)]+)\)", ALL)
norm = lambda s: sorted(x.strip().strip("'\"") for x in s.split(","))
check(prefs_js is not None and prefs_sql is not None and norm(prefs_js.group(1)) == norm(prefs_sql.group(1)),
      "DB5f the client's preferences are the database's",
      "js %s, sql %s" % (prefs_js and prefs_js.group(1), prefs_sql and prefs_sql.group(1)))
servers_js = re.search(r"const ALBION_SERVERS = \{([^}]+)\};", AUTH_JS)
js_servers = sorted(re.findall(r"(\w+): \"", servers_js.group(1))) if servers_js else []
sql_servers = [norm(m) for m in re.findall(r"albion_server'? in \(([^)]+)\)", ALL)]
check(bool(js_servers) and len(sql_servers) >= 3 and all(l == js_servers for l in sql_servers),
      "DB5g the client's servers are the database's: the profile check, the sign-up trigger, the guild check",
      "js %s, sql %s" % (js_servers, sql_servers))

print("DB6 - guilds: the client's bounds are the database's")
with open(os.path.join(ROOT, "dashboard", "_guild.js"), encoding="utf-8") as f:
    GUILD_JS = f.read()
roles_js = re.search(r"const GUILD_ROLES = \[([^\]]+)\];", GUILD_JS)
roles_sql = re.search(r"role in \(([^)]+)\)\)", ALL)
check(roles_js is not None and roles_sql is not None and norm(roles_js.group(1)) == norm(roles_sql.group(1)),
      "DB6a the client's guild roles are the database's",
      "js %s, sql %s" % (roles_js and roles_js.group(1), roles_sql and roles_sql.group(1)))
guild_name_sql = set(re.findall(r"char_length\(name\) between 1 and (\d+)", ALL))
check(guild_name_sql == {str(name_max)}, "DB6b a guild name shares the account name bound (ACCOUNT_NAME_MAX)",
      str(sorted(guild_name_sql)))
tag = re.search(r'<input[^>]*\bid="guild-new-name"[^>]*>', SHELL)
length = tag and re.search(r'\bmaxlength="(\d+)"', tag.group(0))
check(length is not None and int(length.group(1)) == name_max,
      "DB6c the guild name field's maxlength is the bound", tag.group(0) if tag else "field missing")
for js_name, sql_pat in (("GUILD_MEMBERS_MAX", r"private\.guild_member_count\(new\.guild_id\) >= (\d+)"),
                         ("GUILDS_MAX", r"from public\.guild_members where user_id = new\.user_id\) >= (\d+)")):
    js_val = js_const(GUILD_JS, js_name)
    sql_val = set(re.findall(sql_pat, ALL))
    check(js_val is not None and sql_val == {str(js_val)},
          "DB6d %s (_guild.js) is the guild_members bound" % js_name, "js %s, sql %s" % (js_val, sorted(sql_val)))
js_code = re.search(r"const JOIN_CODE_RE = /(.+?)/;", GUILD_JS)
sql_code = re.search(r"join_code ~ '(.+?)'", ALL)
check(js_code is not None and sql_code is not None and js_code.group(1) == sql_code.group(1),
      "DB6e the client's join code form is the database's",
      "js %s, sql %s" % (js_code and js_code.group(1), sql_code and sql_code.group(1)))

print("DB7 - saved comps: the client's bounds are the database's and the planner's")
with open(os.path.join(ROOT, "dashboard", "_comps.js"), encoding="utf-8") as f:
    COMPS_JS = f.read()
with open(os.path.join(ROOT, "dashboard", "_app.js"), encoding="utf-8") as f:
    APP_JS = f.read()
slots_max = js_const(COMPS_JS, "COMP_SLOTS_MAX")
hard_cap = js_const(APP_JS, "HARD_CAP")
sql_slots = set(re.findall(r"position between 1 and (\d+)", ALL)) | set(re.findall(r"jsonb_array_length\(slots\) > (\d+)", ALL))
sql_size = re.search(r"planned_size between (\d+) and (\d+)", ALL)
check(slots_max is not None and hard_cap == slots_max and sql_slots == {str(slots_max)},
      "DB7a COMP_SLOTS_MAX (_comps.js) is the planner's HARD_CAP and the slot bound",
      "js %s, planner %s, sql %s" % (slots_max, hard_cap, sorted(sql_slots)))
check(sql_size is not None and int(sql_size.group(1)) == js_const(COMPS_JS, "COMP_SIZE_MIN")
      and int(sql_size.group(2)) == slots_max,
      "DB7b the planned size runs from COMP_SIZE_MIN to the slot bound", sql_size and sql_size.groups())
for js_name, sql_pat in (("COMP_TEMPLATES_MAX", r"from public\.comp_templates where guild_id = new\.guild_id\) >= (\d+)"),
                         ("COMP_NOTES_MAX", r"char_length\(notes\) <= (\d+)"),
                         ("COMP_ROLE_MAX", r"char_length\(role\) between 1 and (\d+)"),
                         ("COMP_NOTE_MAX", r"char_length\(note\) between 1 and (\d+)")):
    js_val = js_const(COMPS_JS, js_name)
    sql_val = set(re.findall(sql_pat, ALL))
    check(js_val is not None and sql_val == {str(js_val)},
          "DB7c %s (_comps.js) is the database's bound" % js_name, "js %s, sql %s" % (js_val, sorted(sql_val)))
js_key = re.search(r"const COMP_KEY_RE = /(.+?)/;", COMPS_JS)
sql_keys = set(re.findall(r"(?:content|style) ~ '(.+?)'", ALL))
check(js_key is not None and sql_keys == {js_key.group(1)},
      "DB7d the client's content and style key form is the database's",
      "js %s, sql %s" % (js_key and js_key.group(1), sorted(sql_keys)))
roles_js = re.search(r"const COMP_WRITER_ROLES = \[([^\]]+)\];", COMPS_JS)
roles_sql = set(re.findall(r"in \('caller', 'officer', 'admin'\)", ALL))
check(roles_js is not None and norm(roles_js.group(1)) == ["admin", "caller", "officer"] and len(roles_sql) == 1,
      "DB7e the roles that write comps are the policies' caller, officer, admin",
      roles_js and roles_js.group(1))
comp_name_sql = set(re.findall(r"char_length\(name\) between 1 and (\d+)", ALL))
check(comp_name_sql == {str(name_max)}, "DB7f a comp name shares the account name bound", str(sorted(comp_name_sql)))
tag = re.search(r'<input[^>]*\bid="comp-name"[^>]*>', SHELL)
length = tag and re.search(r'\bmaxlength="(\d+)"', tag.group(0))
check(length is not None and int(length.group(1)) == name_max, "DB7g the comp name field's maxlength is the bound")
size_tag = re.search(r'<input[^>]*\bid="comp-size"[^>]*>', SHELL)
check(size_tag is not None and ('min="%d"' % js_const(COMPS_JS, "COMP_SIZE_MIN")) in size_tag.group(0)
      and ('max="%d"' % slots_max) in size_tag.group(0), "DB7h the planned size field's range is the bound")

print("DB8 - CTAs: the client's statuses, moves and bounds are the database's")
with open(os.path.join(ROOT, "dashboard", "_events.js"), encoding="utf-8") as f:
    EVENTS_JS = f.read()
statuses_js = re.search(r"const EVENT_STATUSES = \[([^\]]+)\];", EVENTS_JS)
statuses_sql = re.search(r"status in \(([^)]+)\)", ALL)
check(statuses_js is not None and statuses_sql is not None and norm(statuses_js.group(1)) == norm(statuses_sql.group(1)),
      "DB8a the client's statuses are the database's",
      "js %s, sql %s" % (statuses_js and statuses_js.group(1), statuses_sql and statuses_sql.group(1)))
moves_js = re.search(r"const EVENT_MOVES = \{([^}]+)\};", EVENTS_JS)
js_moves = set()
for frm, tos in re.findall(r"(\w+): \[([^\]]*)\]", moves_js.group(1) if moves_js else ""):
    for to in re.findall(r"\"(\w+)\"", tos):
        js_moves.add((frm, to))
guard_moves = re.search(r"\(old\.status, new\.status\) not in \(((?:\s*\('\w+', '\w+'\),?)+)\s*\)", ALL)
sql_moves = set(re.findall(r"\('(\w+)', '(\w+)'\)", guard_moves.group(1))) if guard_moves else set()
check(bool(js_moves) and js_moves == sql_moves, "DB8b the moves the client offers are the guard's",
      "js %s, sql %s" % (sorted(js_moves), sorted(sql_moves)))
check(all(frm in norm(statuses_js.group(1)) and to in norm(statuses_js.group(1)) for frm, to in js_moves)
      and not any(frm == "completed" for frm, _to in js_moves),
      "DB8c every move joins two listed statuses and none leaves completed")
events_max = js_const(EVENTS_JS, "EVENTS_MAX")
sql_events = set(re.findall(r"from public\.events where guild_id = new\.guild_id\) >= (\d+)", ALL))
check(events_max is not None and sql_events == {str(events_max)},
      "DB8d EVENTS_MAX (_events.js) is the events bound", "js %s, sql %s" % (events_max, sorted(sql_events)))
tag = re.search(r'<input[^>]*\bid="ev-name"[^>]*>', SHELL)
length = tag and re.search(r'\bmaxlength="(\d+)"', tag.group(0))
check(length is not None and int(length.group(1)) == name_max, "DB8e the CTA name field's maxlength is the account name bound")
size_tag = re.search(r'<input[^>]*\bid="ev-size"[^>]*>', SHELL)
check(size_tag is not None and ('min="%d"' % js_const(COMPS_JS, "COMP_SIZE_MIN")) in size_tag.group(0)
      and ('max="%d"' % slots_max) in size_tag.group(0), "DB8f the CTA's planned size field's range is the bound")
check("mass_at is null or mass_at <= starts_at" in ALL and "Mass time comes before the start." in EVENTS_JS,
      "DB8g the mass time never follows the start: the check and the client's sentence")
check("if (event.status !== \"completed\")" in EVENTS_JS and re.search(r"= 'completed' then\s+raise exception 'a completed CTA keeps its slots'", ALL) is not None,
      "DB8h a completed CTA's slots are frozen by the guard and the client sends none")

print("DB9 - sign-up: the client's bounds are the database's; the code and the token ride the statement")
with open(os.path.join(ROOT, "dashboard", "_signup.js"), encoding="utf-8") as f:
    SIGNUP_JS = f.read()
for js_name, sql_pat in (("SIGNUP_WEAPONS_MAX", r"array_length\(weapons, 1\), 0\) <= (\d+)"),
                         ("SIGNUP_IP_MAX", r"item_power between 0 and (\d+)"),
                         ("SIGNUPS_MAX", r"from public\.signups where event_id = new\.event_id\) >= (\d+)")):
    js_val = js_const(SIGNUP_JS, js_name)
    sql_val = set(re.findall(sql_pat, ALL))
    check(js_val is not None and sql_val == {str(js_val)},
          "DB9a %s (_signup.js) is the database's bound" % js_name, "js %s, sql %s" % (js_val, sorted(sql_val)))
check(js_const(SIGNUP_JS, "SIGNUP_NOTE_MAX") == js_const(COMPS_JS, "COMP_NOTE_MAX"),
      "DB9b a sign-up note shares the slot note bound (char_length(note) between 1 and N, one value across the migrations)")
declared_form = set(re.findall(r"unnest\(new\.weapons\) as w where w !~ '(.+?)'", ALL))
weapon_form = re.search(r"const WEAPON_KEY_RE = /(.+?)/;", PROFILE_JS)
check(weapon_form is not None and declared_form == {weapon_form.group(1)},
      "DB9c a declared weapon has the weapon key form (WEAPON_KEY_RE)", str(sorted(declared_form)))
code_forms = set(re.findall(r"clean !~ '(.+?)'", ALL))
check(js_code is not None and code_forms == {js_code.group(1)},
      "DB9d the guest functions check the share code's form, the join code's (JOIN_CODE_RE)", str(sorted(code_forms)))
check("WEAPON_KEY_RE.test" in SIGNUP_JS and "JOIN_CODE_RE.test" in SIGNUP_JS,
      "DB9e the client checks weapons and the code against the same forms")
token_hash = re.search(r"guest_token_hash ~ '(.+?)'", ALL)
check(token_hash is not None and token_hash.group(1) == "^[a-f0-9]{64}$"
      and re.search(r"const CLAIM_TOKEN_RE = /\^\[a-f0-9\]\{32\}\$/;", SIGNUP_JS) is not None,
      "DB9f the row keeps a SHA-256 (64 hex) of a 32-hex claim token, never the token")
check(re.search(r"char_length\(coalesce\(token, ''\)\) < 16", ALL) is not None
      and "player_name = btrim(player_name) and char_length(player_name) between 1 and %d" % name_max in ALL,
      "DB9g a short token is no token; a player's name shares the account name bound")
tag = re.search(r'<input[^>]*\bid="su-name"[^>]*>', SHELL)
length = tag and re.search(r'\bmaxlength="(\d+)"', tag.group(0))
check(length is not None and int(length.group(1)) == name_max, "DB9h the guest name field's maxlength is the bound")
ip_tag = re.search(r'<input[^>]*\bid="su-ip"[^>]*>', SHELL)
check(ip_tag is not None and ('min="%d"' % js_const(SIGNUP_JS, "SIGNUP_IP_MIN")) in ip_tag.group(0)
      and ('max="%d"' % js_const(SIGNUP_JS, "SIGNUP_IP_MAX")) in ip_tag.group(0), "DB9i the item power field's range is the bound")
check(re.search(r"set_config\('app\.share_code', clean, true\)", ALL) is not None
      and re.search(r"set_config\('app\.claim_token', coalesce\(token, ''\), true\)", ALL) is not None
      and re.search(r"where status = 'open'|e\.status = 'open'", ALL) is not None,
      "DB9j the code and the token ride the statement; a sign-up is written only while the CTA is open")

print("DB10 - caller management: the caller branch, the player kept, the functions")
check(ALL.count("private.guild_role_of((select e.guild_id from public.events e where e.id = event_id))") >= 4,
      "DB10a the sheet's insert, update and delete policies carry the caller branch")
check(re.search(r"new\.user_id is distinct from old\.user_id or new\.guest_token_hash is distinct from old\.guest_token_hash", ALL) is not None
      and "raise exception 'a sign-up keeps its player'" in ALL,
      "DB10b the guard keeps every sign-up's player: the identity columns change only for the adoption")
check("callerPowers" in SIGNUP_JS and "compPowers(myRole).write" in SIGNUP_JS and 'status !== "completed"' in SIGNUP_JS,
      "DB10c the client offers the caller's controls to the policies' roles, until completed")
check(re.search(r"function public\.move_signup\(signup_id uuid, target smallint\)", ALL) is not None
      and re.search(r"function public\.add_player\(event_id uuid, player jsonb\)", ALL) is not None,
      "DB10d the caller's functions: move_signup (a swap in one transaction) and add_player")
check("public.claim_hash(gen_random_uuid()::text)" in ALL, "DB10e a player the caller adds is a guest row nobody holds a token for")

print("DB11 - live updates: the broadcast names the table and the operation, on the CTA's topic, and nothing else")
FUNC_BODY = re.search(r"create or replace function public\.sheet_changed\(\)(.*?)\$\$;", ALL, re.S)
body = FUNC_BODY.group(1) if FUNC_BODY else ""
check("jsonb_build_object('table', tg_table_name, 'op', tg_op)" in body, "DB11a the payload is the table name and the operation")
check("'cta:' || code" in body and "false);" in body, "DB11b the topic is cta:<share code>; the channel is public (the code is the key)")
cols = set(re.findall(r"\b(?:new|old)\.(\w+)", body))
check(cols <= {"share_code", "event_id"}, "DB11c the trigger reads the code and the event id of the row, no other column", str(sorted(cols)))
check("to_regprocedure('realtime.send(jsonb, text, text, boolean)') is null" in body, "DB11d without Realtime the trigger does nothing (the sheet keeps its Refresh)")
check(all(re.search(r"create trigger \w+_changed\s+after [\w ]+ on public\.%s\s+for each row execute function public\.sheet_changed\(\)" % t, ALL) for t in ("signups", "event_slots", "events", "attendance")),
      "DB11e sign-ups, slots, the CTA itself and the record each carry the trigger, after the write")
check("function sheetTopic" in SIGNUP_JS and 'on("broadcast", { event: "changed" }' in SIGNUP_JS and "rpc(\"event_by_code\"" in SIGNUP_JS,
      "DB11f the client listens on the topic and re-reads through event_by_code: the channel only reports")

print("DB12 - history: the record's statuses are the client's; the record is written by its trigger, marked by the caller, confirmed by the player")
att_sql = re.search(r"constraint attendance_status_known check \(\s*status in \(([^)]+)\)", ALL)
att_js = re.search(r"const ATTENDANCE_STATUSES = \[([^\]]+)\];", SIGNUP_JS)
check(att_sql is not None and att_js is not None and norm(att_sql.group(1)) == norm(att_js.group(1)),
      "DB12a the client's attendance statuses are the database's", "js %s, sql %s" % (att_js and att_js.group(1), att_sql and att_sql.group(1)))
marks_js = re.search(r"const ATTENDANCE_MARKS = \[([^\]]+)\];", SIGNUP_JS)
check(marks_js is not None and set(norm(marks_js.group(1))) <= set(norm(att_js.group(1))) and "cancelled" not in marks_js.group(1) and "reserve" not in marks_js.group(1),
      "DB12b the marks a caller's list offers are listed statuses; cancelled and reserve are the record's own findings")
check(re.search(r"grant (all|insert|delete)[^;]*on table public\.attendance\b", ALL) is None
      and re.search(r"grant update \(status\) on table public\.attendance to anon, authenticated;", ALL) is not None,
      "DB12c no API role inserts or deletes a record; the status is the one column the API writes")
guard = re.search(r"create or replace function public\.attendance_guard\(\)(.*?)\$\$;", ALL, re.S)
gbody = guard.group(1) if guard else ""
check("pg_trigger_depth() >= 2" in gbody and "a player confirms or unconfirms; the caller marks attendance" in gbody
      and "new.marked_by := me" in gbody and "= 'completed' then" in gbody,
      "DB12d the guard: the record's own triggers write freely, a caller's mark carries who and when, a player moves between signed_up and confirmed before completion")
check(all(re.search(r"create trigger \w+_attendance\s+after [\w ]+ on public\.%s\s+for each row execute function public\.attendance_record\(\)" % t, ALL) for t in ("signups", "events")),
      "DB12e the record follows the sign-up (made, moved, gone) and the CTA's completion")
check("function markPowers" in SIGNUP_JS and 'status !== "completed"' in SIGNUP_JS and "compPowers(myRole).write" in SIGNUP_JS,
      "DB12f the client offers marks to the caller roles and confirmation to the player before completion")

print("DB13 - analytics: facts over completed CTAs, computed on read as the caller, each measure defined, no rating")
with open(os.path.join(ROOT, "dashboard", "_history.js"), encoding="utf-8") as f:
    HISTORY_JS = f.read()
GH = re.search(r"create or replace function public\.guild_history\(guild_id uuid\)(.*?)\$\$;", ALL, re.S)
gh_header, gh_body = (GH.group(1).split("$$", 1) + [""])[:2] if GH else ("", "")
check(GH is not None and "security invoker" in gh_header and "stable" in gh_header, "DB13a guild_history runs as the caller and only reads")
check("and e.status = 'completed'" in gh_body, "DB13b the facts are over completed CTAs alone")
check("round(sum(p.attended)::numeric / nullif(sum(p.attended) + sum(p.no_show), 0), 3)" in gh_body
      and "round(p.attended::numeric / nullif(p.attended + p.no_show, 0), 3)" in gh_body
      and "in ('signed_up', 'confirmed')))::int as unmarked" in gh_body,
      "DB13c show rate is attended over attended plus no-show, the unmarked counted apart, for the guild and per player")
check("const a = Number(attended) || 0;" in HISTORY_JS and "return n ? a / n : null;" in HISTORY_JS,
      "DB13d the client's show rate is the same definition (a helper for facts the database did not round)")
check("'account:' || a.user_id::text" in gh_body and "'guest:' || lower(a.player_name)" in gh_body,
      "DB13e a player is an account by id, a guest by name whatever its case")
check("where r.status = 'attended' and r.weapon_id is not null" in gh_body, "DB13f played is the settled slot weapon over attended records alone")
check(not re.search(r"skill|rating", gh_body, re.I), "DB13g no skill rating in the facts")
check(js_const(HISTORY_JS, "REGULAR_MIN_ATTENDED") is not None and re.search(r"const REGULAR_MIN_RATE = 0\.\d+;", HISTORY_JS) is not None
      and "None of this is a skill rating" in HISTORY_JS,
      "DB13h the client's regular is defined by two stated constants and the definitions are shown beside the list")

if FAILURES:
    print("\n%d schema rule(s) failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nall schema rules hold")
sys.exit(0)

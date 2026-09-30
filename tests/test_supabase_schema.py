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
}


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
    check(all(roles.strip() == "authenticated" for _op, roles in policies),
          "DB2e every policy on %s is for signed-in users only" % t,
          str(policies))
    if re.search(r"create table (?:if not exists )?public\.%s \([^;]*\bupdated_at\b" % t, ALL):
        check(re.search(r"before update on public\.%s\s+for each row execute function public\.set_updated_at\(\)" % t, ALL)
              is not None, "DB2f %s keeps updated_at through set_updated_at()" % t)
check(re.search(r"grant [^;]*\bto\b[^;]*\banon\b", ALL) is None, "DB2g nothing is granted to anon")

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
        arg_types = ", ".join(a.split()[-1] for a in m.group(3).split(",") if a.strip())
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
    arg_types = ", ".join(a.split()[-1] for a in args.split(",") if a.strip())
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
        check({"public", "anon"} <= revoked,
              "DB4f function %s is revoked from public and anon" % sig,
              "revoked from: %s" % sorted(revoked))
        check(re.search(r"grant execute on function %s\.%s\(%s\) to authenticated;"
                        % (schema, fname, re.escape(arg_types)), ALL) is not None,
              "DB4g function %s is granted to authenticated" % sig)
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

if FAILURES:
    print("\n%d schema rule(s) failed: %s" % (len(FAILURES), ", ".join(FAILURES)))
    sys.exit(1)
print("\nall schema rules hold")
sys.exit(0)

"""Shared serializer for committed JSON artifacts.

Same semantics as json.dump(obj, f, indent=1, sort_keys=True), except
scalar-only lists render on one line — audit boards stay diffable
without a line per citation/id. dump() also enforces the repo-wide
newline="\n" discipline (CLAUDE.md: CRLF copies churn the tree and
invalidate recorded hashes).
"""
import json


def dumps(obj):
    def key(k):
        # json.dump's key coercion for non-string keys
        if isinstance(k, str):
            return json.dumps(k)
        if k is True or k is False or k is None:
            return json.dumps({True: "true", False: "false", None: "null"}[k])
        return json.dumps(json.dumps(k))  # int/float

    def enc(o, lvl):
        pad, pad2 = " " * lvl, " " * (lvl + 1)
        if isinstance(o, dict):
            if not o:
                return "{}"
            return ("{\n" + ",\n".join(
                f"{pad2}{key(k)}: {enc(v, lvl + 1)}"
                for k, v in sorted(o.items())) + "\n" + pad + "}")
        if isinstance(o, list):
            if not o:
                return "[]"
            if all(not isinstance(v, (dict, list)) for v in o):
                return "[" + ", ".join(json.dumps(v) for v in o) + "]"
            return ("[\n" + ",\n".join(
                pad2 + enc(v, lvl + 1) for v in o) + "\n" + pad + "]")
        return json.dumps(o)
    return enc(obj, 0)


def dump(obj, path):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(dumps(obj))

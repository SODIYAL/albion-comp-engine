using StatisticsAnalysisTool.PhotonPackageParser;

namespace CompForgeCompanion;

/// <summary>
/// Photon -> Albion event dispatch, SHAPE-BASED (self-calibrating).
///
/// Albion's event-code NUMBERS shift with game patches, so we do NOT hardcode
/// them. Instead each event is identified by the SHAPE of its parameters — a
/// NewCharacter is "a name string + a 10-slot equipment array + a 14-slot
/// spell array", whatever code number it carries this patch. The important
/// payload arrays are read by SEARCHING for the right-length array, so the
/// handlers also survive per-event parameter-index shifts. Fingerprints were
/// verified unique against a live /schema capture (2026-08-14); the detected
/// code<->role bindings are exposed at /status so a patch that renumbers
/// events shows up as new numbers there instead of a silent breakage.
///
/// Albion's real code still travels in parameter 252 (operations: 253); we
/// keep it only for the histogram/schema diagnostics, never for dispatch.
/// </summary>
public sealed class AlbionEventParser : PhotonParser
{
    private readonly PartyState _state;
    private readonly ItemDb _items;
    private readonly bool _debug;
    private readonly Dictionary<Guid, string> _guidToName = new();

    public long EventsSeen, EventsHandled, RequestsSeen, ResponsesSeen;
    public DateTime LastEventUtc = DateTime.MinValue;
    public readonly Dictionary<short, long> EventCodeHist = new();
    private readonly Dictionary<short, Dictionary<byte, string>> _eventSchema = new();
    private readonly Dictionary<short, Dictionary<byte, string>> _reqSchema = new();
    private readonly Dictionary<short, Dictionary<byte, string>> _resSchema = new();
    // role -> the code number currently carrying it (self-calibrated), for
    // /status. If this ever shows a different number after a patch, the
    // shape-detection re-bound automatically — no code change needed.
    private readonly Dictionary<string, short> _bindings = new();

    public AlbionEventParser(PartyState state, ItemDb items, bool debug)
    {
        _state = state; _items = items; _debug = debug;
    }

    protected override void OnEvent(byte code, Dictionary<byte, object> p)
    {
        EventsSeen++; LastEventUtc = DateTime.UtcNow;
        if (!TryGetShort(p, 252, out var evCode)) return;
        lock (EventCodeHist)
            EventCodeHist[evCode] = EventCodeHist.GetValueOrDefault(evCode) + 1;
        SampleSchema(_eventSchema, evCode, p);

        // Dispatch by shape, not by code number. Order matters: NewCharacter
        // (has a name) is tested before EquipmentChanged (same arrays, no name).
        string? role =
            LooksLikeNewCharacter(p) ? (HandleNewCharacter(p) ? "NewCharacter" : null)
          : LooksLikeEquipmentChanged(p) ? (HandleEquipmentChanged(p) ? "EquipmentChanged" : null)
          : LooksLikePartyRoster(p) ? (HandlePartyRoster(p) ? "PartyRoster" : null)
          : null;
        if (role != null) Bind(role, evCode);
    }

    protected override void OnRequest(byte operationCode, Dictionary<byte, object> p)
    {
        RequestsSeen++;
        if (TryGetShort(p, 253, out var reqOp)) SampleSchema(_reqSchema, reqOp, p);
    }

    protected override void OnResponse(byte operationCode, short returnCode,
        string debugMessage, Dictionary<byte, object> p)
    {
        ResponsesSeen++;
        if (TryGetShort(p, 253, out var op)) SampleSchema(_resSchema, op, p);
        // Self-join response: a numeric objectId at 0 + a name string at 2.
        if (IsNum(p, 0) && p.TryGetValue(2, out var v) && v is string && HandleSelfJoin(p))
            Bind("SelfJoin", TryGetShort(p, 253, out var o) ? o : (short)0);
    }

    // ---------------------------------------------------- shape fingerprints
    // Each verified UNIQUE against a live /schema capture (2026-08-14).

    // name at 1, objectId at 0, a 10-slot equipment array, a 14-slot spell array
    private static bool LooksLikeNewCharacter(Dictionary<byte, object> p) =>
        IsNum(p, 0) && p.TryGetValue(1, out var n) && n is string
        && HasNumArray(p, 10) && HasNumArray(p, 14);

    // same arrays as NewCharacter but NO name at 1 (it's a numeric objectId)
    private static bool LooksLikeEquipmentChanged(Dictionary<byte, object> p) =>
        IsNum(p, 0) && !(p.TryGetValue(1, out var n) && n is string)
        && HasNumArray(p, 10) && HasNumArray(p, 14);

    // OUR party roster. This is the fussy one: guild vault/bank tab listings
    // ALSO carry a numeric id + a string[] + a guid list, so the naive shape
    // matched them and flip-flopped the binding (live bug, 2026-08-14).
    // Distinguish the real party by three things a bank listing never satisfies:
    //   1. exactly ONE string[] — bank tabs carry names AND icon-name arrays (two)
    //   2. one guid per name
    //   3. when we know who we are, the roster CONTAINS self — bank tabs don't
    private bool LooksLikePartyRoster(Dictionary<byte, object> p)
    {
        if (!IsNum(p, 0)) return false;
        var strArrays = 0;
        foreach (var v in p.Values) if (v is string[] { Length: > 0 }) strArrays++;
        if (strArrays != 1) return false;
        var names = FindStringArray(p);
        var guids = FindGuidList(p);
        if (names == null || guids == null || guids.Count != names.Length) return false;
        var self = _state.SelfName;
        return self == null
            || names.Any(n => n.Equals(self, StringComparison.OrdinalIgnoreCase));
    }

    // ------------------------------------------------------------- handlers
    // Return true when the event was genuinely handled (used to confirm the
    // shape binding). Payload arrays are found by size, robust to index shifts.

    private bool HandleNewCharacter(Dictionary<byte, object> p)
    {
        if (!TryGetLong(p, 0, out var objectId)) return false;
        var name = GetString(p, 1);
        if (name == null) return false;
        var guild = SecondString(p, name);
        _state.SeeCharacter(objectId, name, guild);
        // Equipment (10-slot, geared) and spells (14-slot) arrive right here on
        // visibility; naked players send zeros, which UpdateLoadout skips.
        var equipment = FindNumArray(p, 10);
        var spells = FindNumArray(p, 14);
        _state.UpdateLoadout(name, _items, equipment, spells, null, "NewCharacter");
        Log($"NewCharacter {name} guild={guild} eq={equipment?.Length} sp={spells?.Length}");
        EventsHandled++;
        return true;
    }

    private bool HandleEquipmentChanged(Dictionary<byte, object> p)
    {
        if (!TryGetLong(p, 0, out var objectId)) return false;
        var name = _state.NameForObject(objectId);
        if (name == null) return false;         // an object we haven't named yet
        var equipment = FindNumArray(p, 10);
        var spells = FindNumArray(p, 14);
        if (!_state.UpdateLoadout(name, _items, equipment, spells, null, "EquipmentChanged"))
            return false;
        Log($"Equip {name} eq={equipment?.Length} sp={spells?.Length}");
        EventsHandled++;
        return true;
    }

    private bool HandlePartyRoster(Dictionary<byte, object> p)
    {
        var names = FindStringArray(p);
        if (names is not { Length: > 0 }) return false;
        var guids = FindGuidList(p, names.Length) ?? new List<Guid>();
        var members = new List<(Guid, string)>();
        for (var i = 0; i < names.Length; i++)
            members.Add((i < guids.Count ? guids[i] : Guid.Empty, names[i]));
        _guidToName.Clear();
        foreach (var (g, n) in members) if (g != Guid.Empty) _guidToName[g] = n;
        _state.SetParty(members);
        Log($"Party [{string.Join(", ", names)}]");
        EventsHandled++;
        return true;
    }

    private bool HandleSelfJoin(Dictionary<byte, object> p)
    {
        // Registers self name + objectId so YOUR EquipmentChanged maps. We do
        // NOT read gear here: the join response's 10-slot int array is item
        // INSTANCE ids (consecutive per-world-item), not item TYPE ids. Self
        // gear arrives via EquipmentChanged like every other player.
        if (!TryGetLong(p, 0, out var objectId)) return false;
        var name = GetString(p, 2);
        if (name == null) return false;
        _state.SetSelf(name);
        _state.SeeCharacter(objectId, name, null);
        _state.UpdateLoadout(name, _items, null, null, null, "Self");
        Log($"SelfJoin {name} (self registered)");
        EventsHandled++;
        return true;
    }

    private void Bind(string role, short code)
    {
        lock (_bindings)
        {
            if (_bindings.TryGetValue(role, out var prev) && prev != code)
                Console.WriteLine($"[calibrate] {role} rebound: code {prev} -> {code} (patch shift)");
            _bindings[role] = code;
        }
    }

    public Dictionary<string, short> Bindings()
    {
        lock (_bindings) return new Dictionary<string, short>(_bindings);
    }

    // ------------------------------------------------------- param helpers

    private static bool TryGetShort(Dictionary<byte, object> p, byte k, out short v)
    {
        v = 0;
        if (!p.TryGetValue(k, out var o)) return false;
        try { v = Convert.ToInt16(o); return true; } catch { return false; }
    }

    private static bool TryGetLong(Dictionary<byte, object> p, byte k, out long v)
    {
        v = 0;
        if (!p.TryGetValue(k, out var o)) return false;
        try { v = Convert.ToInt64(o); return true; } catch { return false; }
    }

    private static string? GetString(Dictionary<byte, object> p, byte k) =>
        p.TryGetValue(k, out var o) ? o as string : null;

    /// <summary>The first non-empty string in parameter order that isn't the
    /// name — used for the guild, robust to its exact parameter index.</summary>
    private static string? SecondString(Dictionary<byte, object> p, string notThis)
    {
        foreach (var kv in p.OrderBy(x => x.Key))
            if (kv.Value is string s && s.Length > 0 && s != notThis) return s;
        return null;
    }

    private static bool IsNum(Dictionary<byte, object> p, byte k) =>
        p.TryGetValue(k, out var o)
        && o is byte or sbyte or short or ushort or int or uint or long or ulong;

    private static int ArrayLen(object? o) => o switch
    {
        byte[] a => a.Length, short[] a => a.Length,
        int[] a => a.Length, long[] a => a.Length, _ => -1,
    };

    /// <summary>Does any parameter hold a numeric array of exactly this length?
    /// (Equipment is 10, spells are 14 — the shape fingerprints.)</summary>
    private static bool HasNumArray(Dictionary<byte, object> p, int len)
    {
        foreach (var v in p.Values) if (ArrayLen(v) == len) return true;
        return false;
    }

    /// <summary>The first numeric array of exactly `len`, normalized to int[].
    /// Found by SIZE, not fixed index, so it survives parameter-index shifts.</summary>
    private static int[]? FindNumArray(Dictionary<byte, object> p, int len)
    {
        foreach (var kv in p.OrderBy(x => x.Key))
        {
            if (ArrayLen(kv.Value) != len) continue;
            return kv.Value switch
            {
                byte[] b => Array.ConvertAll(b, x => (int)x),
                short[] s => Array.ConvertAll(s, x => (int)x),
                int[] i => i,
                long[] l => Array.ConvertAll(l, x => (int)x),
                _ => null,
            };
        }
        return null;
    }

    private static string[]? FindStringArray(Dictionary<byte, object> p)
    {
        foreach (var kv in p.OrderBy(x => x.Key))
            if (kv.Value is string[] { Length: > 0 } sa) return sa;
        return null;
    }

    /// <summary>The party guid list: a byte[] of 16-byte chunks (>=2) or
    /// byte[][]. Prefers the list whose count matches the roster size, else the
    /// largest — so a single leader guid never wins over the full roster.</summary>
    private static List<Guid>? FindGuidList(Dictionary<byte, object> p, int preferCount = 0)
    {
        List<Guid>? best = null;
        foreach (var v in p.Values)
        {
            var g = AsGuidList(v);
            if (g == null) continue;
            if (preferCount > 0 && g.Count == preferCount) return g;
            if (best == null || g.Count > best.Count) best = g;
        }
        return best;
    }

    private static List<Guid>? AsGuidList(object? v)
    {
        // guid lists arrive either as byte[][] or as one flat byte[] of 16-byte
        // chunks; require >=2 (>=32 bytes) so a single guid isn't a "list"
        switch (v)
        {
            case byte[][] arr when arr.Length >= 2 && arr.All(x => x.Length == 16):
                return arr.Select(x => new Guid(x)).ToList();
            case byte[] flat when flat.Length >= 32 && flat.Length % 16 == 0:
                return Enumerable.Range(0, flat.Length / 16)
                    .Select(i => new Guid(flat.AsSpan(i * 16, 16).ToArray())).ToList();
            default:
                return null;
        }
    }

    private void Log(string msg)
    {
        if (_debug) Console.WriteLine($"[{DateTime.Now:HH:mm:ss}] {msg}");
    }

    /// <summary>The N most-common raw event codes seen, for /status — this is
    /// how a live run reveals which codes are actually flowing.</summary>
    public Dictionary<string, long> TopEventCodes(int n)
    {
        lock (EventCodeHist)
            return EventCodeHist.OrderByDescending(kv => kv.Value).Take(n)
                .ToDictionary(kv => kv.Key.ToString(), kv => kv.Value);
    }

    /// <summary>Record the parameter SHAPE for a code the first time we see it
    /// (enriching if a later occurrence has more params). Cheap, bounded.</summary>
    private static void SampleSchema(Dictionary<short, Dictionary<byte, string>> into,
        short code, Dictionary<byte, object> parameters)
    {
        lock (into)
        {
            if (!into.TryGetValue(code, out var shape))
                into[code] = shape = new Dictionary<byte, string>();
            foreach (var (k, v) in parameters)
            {
                if (k is 252 or 253) continue;   // the code itself
                if (!shape.ContainsKey(k)) shape[k] = Describe(v);
            }
        }
    }

    private static string Describe(object? v) => v switch
    {
        null => "null",
        string s => "\"" + (s.Length > 24 ? s[..24] + "…" : s) + "\"",
        byte[] b => b.Length == 16 ? "guid(byte[16])" : $"byte[{b.Length}]",
        short[] a => $"short[{a.Length}]",
        int[] a => $"int[{a.Length}]",
        long[] a => $"long[{a.Length}]",
        float[] a => $"float[{a.Length}]",
        string[] a => $"string[{a.Length}]" + (a.Length > 0 ? " e.g. \"" + (a[0].Length > 16 ? a[0][..16] + "…" : a[0]) + "\"" : ""),
        byte[][] a => $"guidList(byte[{a.Length}][])",
        bool bo => $"bool:{bo}",
        byte or sbyte or short or ushort or int or uint or long or ulong => $"num:{v}",
        _ => v.GetType().Name,
    };

    /// <summary>Full parameter-shape map for /schema — the key that lets us map
    /// event codes to party/equipment handlers without hardcoded numbers.</summary>
    public object SchemaDump()
    {
        Dictionary<string, Dictionary<string, string>> Freeze(
            Dictionary<short, Dictionary<byte, string>> src)
        {
            lock (src)
                return src.OrderBy(kv => kv.Key).ToDictionary(
                    kv => kv.Key.ToString(),
                    kv => kv.Value.OrderBy(p => p.Key)
                        .ToDictionary(p => p.Key.ToString(), p => p.Value));
        }
        return new { events = Freeze(_eventSchema), requests = Freeze(_reqSchema),
                     responses = Freeze(_resSchema) };
    }
}

using StatisticsAnalysisTool.PhotonPackageParser;

namespace CompForgeCompanion;

/// <summary>
/// Photon -> Albion event dispatch. Albion's REAL event code travels in
/// parameter 252 (operations: 253), not the Photon-level code byte
/// (COMPANION_SCOPE.md, verified from SAT's AlbionParser). Event codes are
/// positional per game version — when the numbers below stop matching,
/// sync them against SAT's EventCodes.cs (see README, "patch ritual").
/// </summary>
public sealed class AlbionEventParser : PhotonParser
{
    // Event/op codes IDENTIFIED FROM LIVE /schema (2026-08-13, Realm Divided
    // era). These shift per game patch: if handled_events stalls at 0 after an
    // update, re-run the /schema discovery (README) and re-map — the param
    // SHAPES (name string, equipment short[10], guid list) are the fingerprints.
    private const short EvNewCharacter = 29;            // 0=objId 1=name 8=guild 40=equip short[10] 43=spells short[14]
    private const short EvEquipmentChanged = 90;        // 0=objId 2=equip short[10] 7=spells short[14]
    private const short EvPartyRoster = 231;            // 9=names string[] 8=guids byte[16*n]
    private const short OpSelfJoin = 2;                 // response: 0=objId 2=name 58=guild (52 is INSTANCE ids, not item types)

    private readonly PartyState _state;
    private readonly ItemDb _items;
    private readonly bool _debug;
    private readonly Dictionary<Guid, string> _guidToName = new();

    public long EventsSeen, EventsHandled, RequestsSeen, ResponsesSeen;
    public DateTime LastEventUtc = DateTime.MinValue;
    // diagnostic: histogram of the raw Albion event codes (param 252) we see,
    // so a live run tells us which codes are actually flowing vs the constants
    public readonly Dictionary<short, long> EventCodeHist = new();
    // diagnostic: per event/op code, the SHAPE of its parameters (index -> a
    // short type/value description). Event codes shift per patch, so this is
    // how we IDENTIFY which code carries names+equipment (NewCharacter) or a
    // name+guid list (party) without trusting hardcoded numbers.
    private readonly Dictionary<short, Dictionary<byte, string>> _eventSchema = new();
    private readonly Dictionary<short, Dictionary<byte, string>> _reqSchema = new();
    private readonly Dictionary<short, Dictionary<byte, string>> _resSchema = new();

    public AlbionEventParser(PartyState state, ItemDb items, bool debug)
    {
        _state = state; _items = items; _debug = debug;
    }

    protected override void OnEvent(byte code, Dictionary<byte, object> parameters)
    {
        EventsSeen++; LastEventUtc = DateTime.UtcNow;
        if (!TryGetShort(parameters, 252, out var evCode)) return;
        lock (EventCodeHist)
            EventCodeHist[evCode] = EventCodeHist.GetValueOrDefault(evCode) + 1;
        SampleSchema(_eventSchema, evCode, parameters);
        switch (evCode)
        {
            case EvNewCharacter: HandleNewCharacter(parameters); break;
            case EvEquipmentChanged: HandleEquipmentChanged(parameters); break;
            case EvPartyRoster: HandlePartyRoster(parameters); break;
        }
    }

    protected override void OnRequest(byte operationCode, Dictionary<byte, object> parameters)
    {
        RequestsSeen++;
        if (TryGetShort(parameters, 253, out var reqOp)) SampleSchema(_reqSchema, reqOp, parameters);
    }

    protected override void OnResponse(byte operationCode, short returnCode,
        string debugMessage, Dictionary<byte, object> parameters)
    {
        ResponsesSeen++;
        if (!TryGetShort(parameters, 253, out var op)) return;
        SampleSchema(_resSchema, op, parameters);
        if (op == OpSelfJoin) HandleSelfJoin(parameters);
    }

    // ------------------------------------------------------------- handlers

    private void HandleNewCharacter(Dictionary<byte, object> p)
    {
        if (!TryGetLong(p, 0, out var objectId)) return;
        var name = GetString(p, 1);
        if (name == null) return;
        var guild = GetString(p, 8);
        _state.SeeCharacter(objectId, name, guild);
        // Equipment (40, short[10] geared / byte[10] of zeros when naked) and
        // selected spells (43, short[14]) both arrive right here on visibility —
        // no need to wait for an EquipmentChanged. Empty slots are 0 and get
        // skipped in UpdateLoadout, so a naked byte[10] harmlessly yields nothing.
        var equipment = GetIntArray(p, 40);
        var spells = GetIntArray(p, 43);
        _state.UpdateLoadout(name, _items, equipment, spells, null, "NewCharacter");
        Log($"NewCharacter[29] {name} guild={guild} eq={equipment?.Length} sp={spells?.Length}");
        EventsHandled++;
    }

    private void HandleEquipmentChanged(Dictionary<byte, object> p)
    {
        if (!TryGetLong(p, 0, out var objectId)) return;
        var name = _state.NameForObject(objectId);
        if (name == null) return;               // an object we haven't named yet
        var equipment = GetIntArray(p, 2);      // short[10]
        var spells = GetIntArray(p, 7);         // short[14]
        if (_state.UpdateLoadout(name, _items, equipment, spells, null, "EquipmentChanged"))
        {
            Log($"Equip[90] {name} eq={equipment?.Length} sp={spells?.Length}");
            EventsHandled++;
        }
    }

    private void HandlePartyRoster(Dictionary<byte, object> p)
    {
        var names = GetStringArray(p, 9);
        if (names is not { Length: > 0 })
        {
            Log("Party[231] no names — RAW " + Shapes(p));
            return;
        }
        p.TryGetValue(8, out var guidRaw);
        var guids = AsGuidList(guidRaw) ?? new List<Guid>();
        var members = new List<(Guid, string)>();
        for (var i = 0; i < names.Length; i++)
            members.Add((i < guids.Count ? guids[i] : Guid.Empty, names[i]));
        _guidToName.Clear();
        foreach (var (g, n) in members) if (g != Guid.Empty) _guidToName[g] = n;
        _state.SetParty(members);
        Log($"Party[231] [{string.Join(", ", names)}]");
        EventsHandled++;
    }

    private void HandleSelfJoin(Dictionary<byte, object> p)
    {
        // Establishes self name + objectId so YOUR EquipmentChanged (90) maps.
        // We deliberately do NOT read gear here: the join response's 10-slot
        // int array is item INSTANCE ids (consecutive per-world-item), not
        // item TYPE ids — it won't map to weapon names. Self gear arrives via
        // event 90 like every other player.
        if (!TryGetLong(p, 0, out var objectId)) return;
        var name = GetString(p, 2);
        if (name == null) return;
        _state.SetSelf(name);
        _state.SeeCharacter(objectId, name, GetString(p, 58));
        _state.UpdateLoadout(name, _items, null, null, null, "Self");   // put self on the roster; gear fills from event 90
        Log($"SelfJoin[resp2] {name} (self registered)");
        EventsHandled++;
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

    private static bool TryGetDouble(Dictionary<byte, object> p, byte k, out double v)
    {
        v = 0;
        if (!p.TryGetValue(k, out var o)) return false;
        try { v = Convert.ToDouble(o); return true; } catch { return false; }
    }

    private static string? GetString(Dictionary<byte, object> p, byte k) =>
        p.TryGetValue(k, out var o) ? o as string : null;

    /// <summary>Equipment/spell arrays arrive as byte[]/short[]/int[] depending
    /// on the values involved — normalize to int[].</summary>
    private static int[]? GetIntArray(Dictionary<byte, object> p, byte k)
    {
        if (!p.TryGetValue(k, out var o)) return null;
        return o switch
        {
            byte[] b => b.Select(x => (int)x).ToArray(),
            short[] s => s.Select(x => (int)x).ToArray(),
            int[] i => i,
            long[] l => l.Select(x => (int)x).ToArray(),
            float[] f => f.Select(x => (int)x).ToArray(),
            _ => null,
        };
    }

    private static string[]? GetStringArray(Dictionary<byte, object> p, byte k) =>
        p.TryGetValue(k, out var o) ? o as string[] : null;

    private static List<Guid>? AsGuidList(object? v)
    {
        // guid lists arrive either as byte[][] or as one flat byte[] of 16-byte chunks
        switch (v)
        {
            case byte[][] arr when arr.Length > 0 && arr.All(x => x.Length == 16):
                return arr.Select(x => new Guid(x)).ToList();
            case byte[] flat when flat.Length >= 32 && flat.Length % 16 == 0:
                return Enumerable.Range(0, flat.Length / 16)
                    .Select(i => new Guid(flat.AsSpan(i * 16, 16).ToArray())).ToList();
            default:
                return null;
        }
    }

    private static string Shapes(Dictionary<byte, object> p) =>
        "{" + string.Join(", ", p.Select(kv =>
            $"{kv.Key}:{kv.Value?.GetType().Name ?? "null"}")) + "}";

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

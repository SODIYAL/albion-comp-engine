using System.Text.Json;
using System.Text.Json.Serialization;

namespace CompForgeCompanion;

/// <summary>
/// The companion's whole world-model: who is in the party and what we have
/// seen them wearing/casting. Thread-safe via a single lock — event rates
/// are tiny (human-scale), contention is irrelevant.
///
/// Members are keyed by lower-cased character NAME: party events carry
/// Guid+Name, visibility events (NewCharacter/EquipmentChanged) carry
/// ObjectId+Name — the name is the only key present on both sides.
/// </summary>
public sealed class PartyState
{
    /// <summary>Shared serializer options — a fresh instance per call
    /// discards System.Text.Json's cached type metadata (Program.cs's
    /// endpoints reuse this too).</summary>
    internal static readonly JsonSerializerOptions Indented = new() { WriteIndented = true };

    private readonly object _lock = new();
    private readonly Dictionary<string, Member> _members = new();   // key: name.ToLowerInvariant()
    private readonly Dictionary<long, string> _objectIdToName = new();
    private string? _selfName;
    private string? _cachePath;
    private SpellDb? _spells;
    private ItemDb? _items;

    public void SetSpellDb(SpellDb spells) => _spells = spells;
    public void SetItemDb(ItemDb items) => _items = items;

    /// <summary>Our own character name, once the self-join is seen.</summary>
    public string? SelfName { get { lock (_lock) return _selfName; } }

    // Party composition changes often, so a cache older than this is more
    // likely to MISLEAD (show a stale party) than to help. Beyond it we start
    // empty and wait for a live roster event.
    private static readonly TimeSpan CacheMaxAge = TimeSpan.FromHours(2);

    /// <summary>Roster persistence: the party event only fires on zone/party
    /// change, so a fresh launch may not see it immediately. We save the roster
    /// (names+guids, no gear) whenever it updates and reload it on startup IF
    /// it is recent — gear then fills back in from visibility events by name.
    /// A fresh roster event always replaces the cache. An old cache is ignored
    /// so it can't show a party you left days ago.</summary>
    public void EnablePersistence(string path)
    {
        _cachePath = path;
        if (!File.Exists(path)) return;
        var age = DateTime.UtcNow - File.GetLastWriteTimeUtc(path);
        if (age > CacheMaxAge)
        {
            Console.WriteLine($"[party] cached roster is {age.TotalHours:F1}h old — ignoring "
                              + "(zone once to capture the current party)");
            return;
        }
        try
        {
            var roster = JsonSerializer.Deserialize<List<RosterEntry>>(File.ReadAllText(path));
            if (roster == null) return;
            lock (_lock)
                foreach (var r in roster)
                {
                    if (string.IsNullOrEmpty(r.Name)) continue;
                    _members[r.Name.ToLowerInvariant()] =
                        new Member { Name = r.Name, Guid = r.Guid, Source = "cache" };
                }
            Console.WriteLine($"[party] restored {_members.Count} cached members "
                              + $"({age.TotalMinutes:F0}m old) — a live roster event will refresh them");
        }
        catch { /* corrupt cache — ignore, a live roster event rebuilds it */ }
    }

    private void SaveRoster()
    {
        if (_cachePath == null) return;
        try
        {
            var roster = _members.Values
                .Select(m => new RosterEntry { Name = m.Name, Guid = m.Guid }).ToList();
            File.WriteAllText(_cachePath, JsonSerializer.Serialize(roster));
        }
        catch { /* best-effort */ }
    }

    private sealed class RosterEntry
    {
        public string Name { get; set; } = "";
        public string? Guid { get; set; }
    }

    public sealed class Member
    {
        [JsonPropertyName("name")] public string Name { get; set; } = "";
        [JsonPropertyName("guid")] public string? Guid { get; set; }
        [JsonPropertyName("guild")] public string? Guild { get; set; }
        [JsonPropertyName("weapon")] public string? Weapon { get; set; }          // engine unique_name, e.g. 2H_MACE
        [JsonPropertyName("weapon_item")] public string? WeaponItem { get; set; } // full item, e.g. T8_2H_MACE@3
        [JsonPropertyName("item_power")] public double? ItemPower { get; set; }
        [JsonPropertyName("equipment")] public Dictionary<string, string>? Equipment { get; set; }
        // spell slot -> UniqueName (matches the engine's sheet evidence IDs);
        // resolved from the packet index via SpellDb
        [JsonPropertyName("spells")] public Dictionary<string, string>? Spells { get; set; }
        [JsonPropertyName("updated_utc")] public string? UpdatedUtc { get; set; }
        [JsonPropertyName("source")] public string? Source { get; set; }          // which event last touched this
    }

    public void SetSelf(string name)
    {
        lock (_lock) _selfName = name;
    }

    public void SetParty(IEnumerable<(Guid guid, string name)> members)
    {
        lock (_lock)
        {
            var incoming = members.ToList();
            var keep = incoming.Select(m => m.name.ToLowerInvariant()).ToHashSet();
            foreach (var k in _members.Keys.Where(k => !keep.Contains(k)).ToList())
                _members.Remove(k);
            foreach (var (guid, name) in incoming)
                Upsert(name, m => { m.Guid = guid.ToString(); }, "PartyRoster");
            SaveRoster();
        }
    }

    // Object ids are per-zone and the game offers no clean zone-change signal
    // here, so the id->name map cannot be invalidated precisely; bound it so a
    // long session can't grow it forever (KNOWN LIMITATION: a reused id can
    // briefly attribute a stranger's gear to a party member until their next
    // NewCharacter — see companion/README.md).
    private const int MaxObjectIds = 4096;
    private readonly Queue<long> _objectIdOrder = new();

    public void SeeCharacter(long objectId, string name, string? guild)
    {
        lock (_lock)
        {
            if (!_objectIdToName.ContainsKey(objectId))
            {
                _objectIdOrder.Enqueue(objectId);
                while (_objectIdOrder.Count > MaxObjectIds)
                    _objectIdToName.Remove(_objectIdOrder.Dequeue());
            }
            _objectIdToName[objectId] = name;
            if (_members.ContainsKey(name.ToLowerInvariant()) && guild != null)
                Upsert(name, m => m.Guild = guild, "NewCharacter");
        }
    }

    public string? NameForObject(long objectId)
    {
        lock (_lock) return _objectIdToName.GetValueOrDefault(objectId);
    }

    /// <summary>Party member by guid — the inspect response's only identity.
    /// Guids come from the roster event alone, so this is party-scoped by
    /// construction (a stranger you inspect resolves to nothing).</summary>
    /// <summary>A decoded equipment array is a kit only if every resolved
    /// slot carries an item of that slot's kind: main hand a MAIN_/2H_ weapon,
    /// off-hand OFF_, head HEAD_, chest ARMOR_, shoes SHOES_, cape CAPEITEM_,
    /// potion POTION, food MEAL. An index missing from the item table counts
    /// as wrong (a patch shift or a non-item number). At least the main hand
    /// or the chest must resolve, or there is nothing to accept.</summary>
    public static bool PlausibleEquipment(int[] eq, ItemDb items, out string why)
    {
        string[][] prefixes =
        {
            new[] { "MAIN_", "2H_" }, new[] { "OFF_" }, new[] { "HEAD_" },
            new[] { "ARMOR_" }, new[] { "SHOES_" }, new[] { "BAG" },
            new[] { "CAPEITEM_", "CAPE" }, new[] { "MOUNT_", "UNIQUE_MOUNT" },
            new[] { "POTION", "T1_POTION", "UNIQUE_POTION" },
            new[] { "MEAL", "UNIQUE_MEAL" },
        };
        var resolved = 0;
        for (var i = 0; i < eq.Length && i < prefixes.Length; i++)
        {
            if (eq[i] <= 0) continue;
            var full = items.FullName(eq[i]);
            if (full.StartsWith("ITEM_")) { why = $"slot {i} index {eq[i]} not in the item table"; return false; }
            var bare = System.Text.RegularExpressions.Regex.Replace(full, @"^T\d+_", "");
            var ok = false;
            foreach (var pre in prefixes[i]) if (bare.StartsWith(pre)) { ok = true; break; }
            if (!ok) { why = $"slot {i} holds {full}"; return false; }
            if (i == 0 || i == 3) resolved++;
        }
        if (resolved == 0) { why = "neither main hand nor chest resolved"; return false; }
        why = "";
        return true;
    }

    public string? NameForGuid(Guid guid)
    {
        var key = guid.ToString();
        lock (_lock)
            return _members.Values.FirstOrDefault(m => m.Guid == key)?.Name;
    }

    /// <summary>Equipment update for a player we may or may not track.
    /// Only party members (or self) are recorded — party scope only.</summary>
    public bool UpdateLoadout(string name,
        int[]? equipment, int[]? spells, double? itemPower, string source)
    {
        lock (_lock)
        {
            var key = name.ToLowerInvariant();
            var isSelf = _selfName != null && key == _selfName.ToLowerInvariant();
            if (!_members.ContainsKey(key) && !isSelf) return false;
            // SLOT-MEANING GUARD (2026-09-10): the handlers find equipment by
            // SHAPE (the first 10-long numeric array), and after the September
            // patch that shape also matched the batched entity-update event and
            // the unverified inspect response — boots as a main hand, a glaive
            // as a helmet, eight consecutive entity ids as a kit. A real kit
            // always satisfies the slot prefixes below; anything else is
            // rejected here, the member keeps its last good state, and the
            // caller does not bind the event code to this role.
            if (equipment is { Length: > 0 } && _items is ItemDb chk
                && !PlausibleEquipment(equipment, chk, out var why))
            {
                Console.WriteLine($"[guard] {source} for {name} rejected: {why}");
                return false;
            }
            Upsert(name, m =>
            {
                if (equipment is { Length: > 0 } && _items is ItemDb items)
                {
                    var eq = new Dictionary<string, string>();
                    string[] slots = { "mainhand", "offhand", "head", "chest", "shoes",
                                       "bag", "cape", "mount", "potion", "food" };
                    for (var i = 0; i < equipment.Length && i < slots.Length; i++)
                    {
                        if (equipment[i] <= 0) continue;
                        eq[slots[i]] = items.FullName(equipment[i]);
                    }
                    m.Equipment = eq;
                    if (eq.TryGetValue("mainhand", out var mh))
                    {
                        m.WeaponItem = mh;
                        m.Weapon = ItemDb.ToEngineKey(mh);
                    }
                }
                if (spells is { Length: > 0 })
                {
                    // indices per COMPANION_SCOPE.md: 0,1,2 = Q,W,E; 3=D; 4=R; 5=F.
                    // Resolve to UniqueNames so they match the engine's evidence IDs.
                    var sp = new Dictionary<string, string>();
                    string[] slotNames = { "q", "w", "e", "d", "r", "f" };
                    for (var i = 0; i < spells.Length && i < slotNames.Length; i++)
                    {
                        if (spells[i] < 0) continue;
                        var nm = _spells?.Name(spells[i]);
                        if (!string.IsNullOrEmpty(nm)) sp[slotNames[i]] = nm;
                    }
                    if (sp.Count > 0) m.Spells = sp;
                }
                if (itemPower is > 0) m.ItemPower = itemPower;
            }, source);
            return true;
        }
    }

    private void Upsert(string name, Action<Member> mutate, string source)
    {
        // caller must hold _lock — every caller (SetParty, SeeCharacter,
        // UpdateLoadout) provably does; re-locking here only obscured who
        // owns the lock
        var key = name.ToLowerInvariant();
        if (!_members.TryGetValue(key, out var m))
            _members[key] = m = new Member { Name = name };
        mutate(m);
        m.UpdatedUtc = DateTime.UtcNow.ToString("o");
        m.Source = source;
    }

    public string ToJson()
    {
        lock (_lock)
        {
            var doc = new
            {
                ts = DateTime.UtcNow.ToString("o"),
                self = _selfName,
                members = _members.Values.OrderBy(m => m.Name).ToList(),
            };
            return JsonSerializer.Serialize(doc, Indented);
        }
    }

    public int Count { get { lock (_lock) return _members.Count; } }
}

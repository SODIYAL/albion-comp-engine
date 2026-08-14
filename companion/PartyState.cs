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
    private readonly object _lock = new();
    private readonly Dictionary<string, Member> _members = new();   // key: name.ToLowerInvariant()
    private readonly Dictionary<long, string> _objectIdToName = new();
    private string? _selfName;
    private string? _cachePath;

    /// <summary>Roster persistence: the party event (231) only fires on zone/
    /// party change, so a fresh launch may not see it. We save the roster
    /// (names+guids, no gear) whenever it updates and reload it on startup, so
    /// the party survives restarts — gear then fills back in from visibility
    /// events by name. A fresh 231 always replaces the cached roster.</summary>
    public void EnablePersistence(string path)
    {
        _cachePath = path;
        if (!File.Exists(path)) return;
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
        }
        catch { /* corrupt cache — ignore, a live 231 rebuilds it */ }
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
        [JsonPropertyName("spells")] public Dictionary<string, int>? SpellsRaw { get; set; }
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

    public void AddMember(Guid guid, string name) =>
        Upsert(name, m => m.Guid = guid.ToString(), "PartyPlayerJoined");

    public void RemoveMember(string name)
    {
        lock (_lock) _members.Remove(name.ToLowerInvariant());
    }

    public void Disband()
    {
        lock (_lock)
        {
            _members.Clear();
            _objectIdToName.Clear();
        }
    }

    public void SeeCharacter(long objectId, string name, string? guild)
    {
        lock (_lock)
        {
            _objectIdToName[objectId] = name;
            if (_members.ContainsKey(name.ToLowerInvariant()) && guild != null)
                Upsert(name, m => m.Guild = guild, "NewCharacter");
        }
    }

    public string? NameForObject(long objectId)
    {
        lock (_lock) return _objectIdToName.GetValueOrDefault(objectId);
    }

    /// <summary>Equipment update for a player we may or may not track.
    /// Only party members (or self) are recorded — party scope only.</summary>
    public bool UpdateLoadout(string name, ItemDb items,
        int[]? equipment, int[]? spells, double? itemPower, string source)
    {
        lock (_lock)
        {
            var key = name.ToLowerInvariant();
            var isSelf = _selfName != null && key == _selfName.ToLowerInvariant();
            if (!_members.ContainsKey(key) && !isSelf) return false;
            Upsert(name, m =>
            {
                if (equipment is { Length: > 0 })
                {
                    var eq = new Dictionary<string, string>();
                    string?[] slots = { "mainhand", "offhand", "head", "chest", "shoes",
                                        "bag", "cape", "mount", "potion", "food" };
                    for (var i = 0; i < equipment.Length && i < slots.Length; i++)
                    {
                        if (equipment[i] <= 0 || slots[i] == null) continue;
                        eq[slots[i]!] = items.FullName(equipment[i]);
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
                    // indices per COMPANION_SCOPE.md: 0,1,2 = Q,W,E; 3=D; 4=R; 5=F
                    var sp = new Dictionary<string, int>();
                    string[] slotNames = { "q", "w", "e", "d", "r", "f" };
                    for (var i = 0; i < spells.Length && i < slotNames.Length; i++)
                        if (spells[i] >= 0) sp[slotNames[i]] = spells[i];
                    m.SpellsRaw = sp;
                }
                if (itemPower is > 0) m.ItemPower = itemPower;
            }, source);
            return true;
        }
    }

    private void Upsert(string name, Action<Member> mutate, string source)
    {
        lock (_lock)
        {
            var key = name.ToLowerInvariant();
            if (!_members.TryGetValue(key, out var m))
                _members[key] = m = new Member { Name = name };
            mutate(m);
            m.UpdatedUtc = DateTime.UtcNow.ToString("o");
            m.Source = source;
        }
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
            return JsonSerializer.Serialize(doc, new JsonSerializerOptions { WriteIndented = true });
        }
    }

    public int Count { get { lock (_lock) return _members.Count; } }
}

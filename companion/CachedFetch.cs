namespace CompForgeCompanion;

/// <summary>
/// Download-with-cache shared by the item and spell tables: use the cached
/// file when younger than 7 days, otherwise re-download — falling back to a
/// stale cache, then to nothing, loudly. One home for the policy: ItemDb and
/// SpellDb carried drifted copies of this exact block (the timeout was the
/// only real difference, and it stays a parameter).
/// </summary>
public static class CachedFetch
{
    private static readonly TimeSpan MaxAge = TimeSpan.FromDays(7);

    public static async Task<string?> GetAsync(string url, string cachePath,
        string logTag, TimeSpan timeout)
    {
        var fresh = File.Exists(cachePath)
            && DateTime.UtcNow - File.GetLastWriteTimeUtc(cachePath) < MaxAge;
        if (fresh)
            return await File.ReadAllTextAsync(cachePath);
        try
        {
            using var http = new HttpClient { Timeout = timeout };
            http.DefaultRequestHeaders.UserAgent.ParseAdd("compforge-companion/0.1");
            var text = await http.GetStringAsync(url);
            await File.WriteAllTextAsync(cachePath, text);
            Console.WriteLine($"[{logTag}] refreshed from ao-bin-dumps ({text.Length / 1024} KB)");
            return text;
        }
        catch (Exception e) when (File.Exists(cachePath))
        {
            Console.WriteLine($"[{logTag}] refresh failed ({e.Message}) — using stale cache");
            return await File.ReadAllTextAsync(cachePath);
        }
        catch (Exception e)
        {
            Console.WriteLine($"[{logTag}] WARNING: no {logTag} table ({e.Message}) — raw indices only");
            return null;
        }
    }
}

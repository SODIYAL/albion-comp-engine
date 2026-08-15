using System.Net;
using System.Text;
using CompForgeCompanion;

/* Comp Forge Party Companion — read-only local Photon reader.
 *
 * Extracts party roster + per-member equipment and selected spells from the
 * data the game client already renders (party UI, inspect window) and
 * serves it as JSON on localhost for Comp Forge's "connect companion"
 * button. Scope, event map and legality reasoning: ../COMPANION_SCOPE.md.
 *
 *   usage: compforge-companion [--port 53321] [--debug]
 *   endpoints: GET /party  GET /status
 *
 * Read-only by construction: the capture socket never sends; the HTTP
 * server binds loopback only.
 */

var port = 53321;
var debug = false;
for (var i = 0; i < args.Length; i++)
{
    if (args[i] == "--port" && i + 1 < args.Length && int.TryParse(args[i + 1], out var p)) port = p;
    if (args[i] == "--debug") debug = true;
}

Console.WriteLine("Comp Forge Party Companion v0.1 (calibration build)");
Console.WriteLine("read-only Photon reader — party roster, equipment, spell picks");
Console.WriteLine();

var exeDir = AppContext.BaseDirectory;
var items = await ItemDb.LoadAsync(exeDir);
var spells = await SpellDb.LoadAsync(exeDir);
var state = new PartyState();
state.SetSpellDb(spells);
state.EnablePersistence(Path.Combine(exeDir, "party-cache.json"));
var parser = new AlbionEventParser(state, items, debug);
var capture = new RawSocketCapture(parser);
capture.Start();

var listener = new HttpListener();
listener.Prefixes.Add($"http://127.0.0.1:{port}/");
listener.Prefixes.Add($"http://localhost:{port}/");
listener.Start();
Console.WriteLine($"[http] serving http://localhost:{port}/party  (and /status)");
Console.WriteLine("[http] CORS allowlist: Comp Forge Pages origin, localhost, file://");
if (!debug) Console.WriteLine("tip: --debug prints every handled event — use it for the first live run");

// CORS: echo the request Origin only when it is Comp Forge's own page —
// the public Pages site, a localhost dev copy, or the file:// build (which
// sends the literal Origin "null"). Loopback binding already keeps LAN
// peers out; this keeps arbitrary WEBSITES the user has open from silently
// polling character/party data (COMPANION_SCOPE.md specifies the Pages
// origin, not a wildcard).
static string? AllowedOrigin(string? origin) =>
    origin != null
    && (origin == "https://sodiyal.github.io"
        || origin == "null"                                  // file:// page
        || origin.StartsWith("http://localhost:")
        || origin == "http://localhost"
        || origin.StartsWith("http://127.0.0.1:")
        || origin == "http://127.0.0.1")
    ? origin : null;

var started = DateTime.UtcNow;
while (listener.IsListening)
{
    HttpListenerContext ctx;
    try { ctx = await listener.GetContextAsync(); }
    catch (ObjectDisposedException) { break; }
    catch (HttpListenerException) { break; }        // listener stopped
    catch (Exception) { continue; }                 // transient accept error

    // One flaky client must never take the server (and with it the whole
    // process, capture threads included) down: everything per-request is
    // contained. HttpListener throws from the response stream on a client
    // abort mid-write — the most common failure with a polling page.
    try
    {
    var res = ctx.Response;
    var allowed = AllowedOrigin(ctx.Request.Headers["Origin"]);
    if (allowed != null) res.Headers["Access-Control-Allow-Origin"] = allowed;
    res.Headers["Cache-Control"] = "no-store";

    // Chrome's Private Network Access gates public-HTTPS -> localhost
    // fetches behind an OPTIONS preflight that must be acknowledged —
    // without this the Pages site can never reach the companion once PNA
    // enforcement is on, and the page shows "companion not found" forever.
    if (ctx.Request.HttpMethod == "OPTIONS")
    {
        if (allowed != null)
        {
            res.Headers["Access-Control-Allow-Methods"] = "GET";
            res.Headers["Access-Control-Allow-Headers"] = "*";
            res.Headers["Access-Control-Allow-Private-Network"] = "true";
        }
        res.StatusCode = 204;
        res.Close();
        continue;
    }

    string body;
    switch (ctx.Request.Url?.AbsolutePath)
    {
        case "/party":
            body = state.ToJson();
            res.ContentType = "application/json";
            break;
        case "/schema":
            // parameter-shape map per event/op code — used to identify which
            // codes carry party/equipment data on the current game version
            body = System.Text.Json.JsonSerializer.Serialize(parser.SchemaDump(),
                new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
            res.ContentType = "application/json";
            break;
        case "/status":
            body = System.Text.Json.JsonSerializer.Serialize(new
            {
                ok = true,
                version = "0.1",
                uptime_s = (int)(DateTime.UtcNow - started).TotalSeconds,
                packets_seen = capture.PacketsSeen,
                albion_packets = capture.AlbionPackets,
                fragmented_packets = capture.Fragments,
                reassembled_datagrams = capture.Reassembled,
                parse_errors = capture.ParseErrors,
                last_parse_error = capture.LastParseError,
                photon_events = parser.EventsSeen,
                photon_requests = parser.RequestsSeen,
                photon_responses = parser.ResponsesSeen,
                handled_events = parser.EventsHandled,
                detected_codes = parser.Bindings(),   // role -> code, self-calibrated this session
                event_code_histogram = parser.TopEventCodes(15),
                last_event_utc = parser.LastEventUtc == DateTime.MinValue ? null : parser.LastEventUtc.ToString("o"),
                party_members = state.Count,
                item_indices = items.Count,
                spell_indices = spells.Count,
            }, new System.Text.Json.JsonSerializerOptions { WriteIndented = true });
            res.ContentType = "application/json";
            break;
        default:
            body = "compforge-companion: GET /party, /status, or /schema\n";
            res.ContentType = "text/plain";
            break;
    }

    var bytes = Encoding.UTF8.GetBytes(body);
    res.ContentLength64 = bytes.Length;
    await res.OutputStream.WriteAsync(bytes);
    res.Close();
    }
    catch (Exception e)
    {
        try { ctx.Response.Abort(); } catch { /* already gone */ }
        if (debug) Console.WriteLine($"[http] request aborted: {e.Message}");
    }
}

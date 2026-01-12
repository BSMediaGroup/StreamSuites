using System;
using System.Collections.Generic;
using System.Net;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace StreamSuites.DesktopAdmin.Bridge
{
    public sealed class BridgeServer
    {
        private static readonly HashSet<string> AllowedOrigins = new(StringComparer.OrdinalIgnoreCase)
        {
            "https://bsmediagroup.github.io"
        };

        private readonly BridgeState _state;
        private readonly RuntimeLifecycleController _runtimeController;
        private readonly Action<string> _log;
        private readonly int _port;
        private readonly object _sync = new();
        private HttpListener _listener;
        private CancellationTokenSource _cts;
        private Task _listenTask;
        private string _lastLoggedRuntimeStatus;

        public BridgeServer(
            BridgeState state,
            RuntimeLifecycleController runtimeController,
            int port,
            Action<string> log)
        {
            _state = state ?? throw new ArgumentNullException(nameof(state));
            _runtimeController = runtimeController ?? throw new ArgumentNullException(nameof(runtimeController));
            _log = log ?? throw new ArgumentNullException(nameof(log));
            _port = port <= 0 ? 8787 : port;
        }

        public int Port => _port;

        public Task StartAsync()
        {
            lock (_sync)
            {
                if (_listener != null)
                    return Task.CompletedTask;

                var prefix = $"http://127.0.0.1:{_port}/";
                _listener = new HttpListener();
                _listener.Prefixes.Add(prefix);

                try
                {
                    _listener.Start();
                }
                catch (Exception ex)
                {
                    _listener.Close();
                    _listener = null;
                    _state.SetError(ex.Message, _port);
                    _log($"[Bridge] Failed to start on {prefix}: {ex.Message}");
                    return Task.CompletedTask;
                }

                _cts = new CancellationTokenSource();
                _listenTask = Task.Run(() => ListenLoopAsync(_listener, _cts.Token));
                _state.SetRunning(_port);
                _log($"[Bridge] Started on {prefix}");
            }

            return Task.CompletedTask;
        }

        public async Task StopAsync()
        {
            Task listenTask = null;

            lock (_sync)
            {
                if (_listener == null)
                    return;

                _cts?.Cancel();
                _listener.Stop();
                _listener.Close();
                _listener = null;

                listenTask = _listenTask;
                _listenTask = null;
                _cts = null;
            }

            if (listenTask != null)
            {
                try
                {
                    await listenTask.ConfigureAwait(false);
                }
                catch
                {
                    // Ignore listener shutdown exceptions.
                }
            }

            _state.SetStopped();
            _log("[Bridge] Stopped.");
        }

        private async Task ListenLoopAsync(HttpListener listener, CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                HttpListenerContext context = null;

                try
                {
                    context = await listener.GetContextAsync().ConfigureAwait(false);
                }
                catch (HttpListenerException)
                {
                    if (token.IsCancellationRequested)
                        break;
                }
                catch (ObjectDisposedException)
                {
                    break;
                }

                if (context == null)
                    continue;

                _ = Task.Run(() => HandleRequestAsync(context, token));
            }
        }

        private async Task HandleRequestAsync(HttpListenerContext context, CancellationToken token)
        {
            try
            {
                var request = context.Request;
                var response = context.Response;
                var origin = request.Headers["Origin"];

                if (!IsOriginAllowed(origin))
                {
                    response.StatusCode = (int)HttpStatusCode.Forbidden;
                    response.Close();
                    return;
                }

                ApplyCorsHeaders(response, origin);

                if (string.Equals(request.HttpMethod, "OPTIONS", StringComparison.OrdinalIgnoreCase))
                {
                    response.StatusCode = (int)HttpStatusCode.NoContent;
                    response.Close();
                    return;
                }

                if (!string.Equals(request.HttpMethod, "GET", StringComparison.OrdinalIgnoreCase) &&
                    !string.Equals(request.HttpMethod, "POST", StringComparison.OrdinalIgnoreCase))
                {
                    response.StatusCode = (int)HttpStatusCode.MethodNotAllowed;
                    response.Close();
                    return;
                }

                var path = request.Url?.AbsolutePath ?? string.Empty;
                var snapshot = _state.GetSnapshot();

                if (string.Equals(path, "/health", StringComparison.OrdinalIgnoreCase) &&
                    string.Equals(request.HttpMethod, "GET", StringComparison.OrdinalIgnoreCase))
                {
                    _log("[Bridge] GET /health");
                    await WriteJsonAsync(response, new
                    {
                        status = "ok",
                        bridge = snapshot.Status
                    }, token).ConfigureAwait(false);
                    return;
                }

                if (string.Equals(path, "/status", StringComparison.OrdinalIgnoreCase) &&
                    string.Equals(request.HttpMethod, "GET", StringComparison.OrdinalIgnoreCase))
                {
                    var runtimeSnapshot = _runtimeController.GetSnapshot();
                    _log("[Bridge] GET /status");
                    LogRuntimeStatusChange(runtimeSnapshot.Status);
                    await WriteJsonAsync(response, new
                    {
                        bridge = snapshot.Status,
                        runtime = runtimeSnapshot.Status,
                        runtimePid = runtimeSnapshot.RuntimePid,
                        runtimeUptime = runtimeSnapshot.RuntimeUptimeSeconds,
                        version = runtimeSnapshot.Version
                    }, token).ConfigureAwait(false);
                    return;
                }

                if (string.Equals(path, "/commands/runtime/start", StringComparison.OrdinalIgnoreCase) &&
                    string.Equals(request.HttpMethod, "POST", StringComparison.OrdinalIgnoreCase))
                {
                    _log("[Bridge] POST /commands/runtime/start");
                    var runtimeSnapshot = _runtimeController.StartInBackground();
                    LogRuntimeStatusChange(runtimeSnapshot.Status);
                    await WriteJsonAsync(response, new
                    {
                        command = "runtime.start",
                        accepted = true,
                        runtimeState = runtimeSnapshot.Status,
                        bridge = snapshot.Status,
                        runtime = runtimeSnapshot.Status,
                        runtimePid = runtimeSnapshot.RuntimePid,
                        runtimeUptime = runtimeSnapshot.RuntimeUptimeSeconds,
                        version = runtimeSnapshot.Version
                    }, token).ConfigureAwait(false);
                    return;
                }

                if (string.Equals(path, "/commands/runtime/stop", StringComparison.OrdinalIgnoreCase) &&
                    string.Equals(request.HttpMethod, "POST", StringComparison.OrdinalIgnoreCase))
                {
                    _log("[Bridge] POST /commands/runtime/stop (runtime only)");
                    var runtimeSnapshot = _runtimeController.StopRuntimeInBackground();
                    LogRuntimeStatusChange(runtimeSnapshot.Status);
                    await WriteJsonAsync(response, new
                    {
                        command = "runtime.stop",
                        accepted = true,
                        runtimeState = runtimeSnapshot.Status,
                        bridge = snapshot.Status,
                        runtime = runtimeSnapshot.Status,
                        runtimePid = runtimeSnapshot.RuntimePid,
                        runtimeUptime = runtimeSnapshot.RuntimeUptimeSeconds,
                        version = runtimeSnapshot.Version
                    }, token).ConfigureAwait(false);
                    return;
                }

                response.StatusCode = (int)HttpStatusCode.NotFound;
                response.Close();
            }
            catch
            {
                try
                {
                    context.Response.StatusCode = (int)HttpStatusCode.InternalServerError;
                    context.Response.Close();
                }
                catch
                {
                    // Ignore.
                }
            }
        }

        private static void ApplyCorsHeaders(HttpListenerResponse response, string origin)
        {
            if (string.IsNullOrWhiteSpace(origin))
                return;

            response.Headers["Access-Control-Allow-Origin"] = origin;
            response.Headers["Vary"] = "Origin";
            response.Headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS";
            response.Headers["Access-Control-Allow-Headers"] = "Content-Type";
        }

        private static bool IsOriginAllowed(string origin)
        {
            if (string.IsNullOrWhiteSpace(origin))
                return true;

            if (AllowedOrigins.Contains(origin))
                return true;

            return origin.StartsWith("http://localhost", StringComparison.OrdinalIgnoreCase);
        }

        private static async Task WriteJsonAsync(
            HttpListenerResponse response,
            object payload,
            CancellationToken token)
        {
            var json = JsonSerializer.Serialize(payload);
            var bytes = Encoding.UTF8.GetBytes(json);

            response.ContentType = "application/json";
            response.ContentEncoding = Encoding.UTF8;
            response.ContentLength64 = bytes.Length;
            response.StatusCode = (int)HttpStatusCode.OK;

            await response.OutputStream.WriteAsync(bytes, 0, bytes.Length, token)
                .ConfigureAwait(false);
            response.Close();
        }

        private void LogRuntimeStatusChange(string status)
        {
            if (string.Equals(_lastLoggedRuntimeStatus, status, StringComparison.OrdinalIgnoreCase))
                return;

            _lastLoggedRuntimeStatus = status;
            _log($"[Bridge] Runtime status: {status}");
        }
    }
}

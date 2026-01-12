using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using StreamSuites.DesktopAdmin.Core;
using StreamSuites.DesktopAdmin.Models;
using StreamSuites.DesktopAdmin.RuntimeBridge;

namespace StreamSuites.DesktopAdmin.Bridge
{
    public sealed class RuntimeLifecycleController
    {
        private readonly object _lock = new();
        private readonly BridgeState _bridgeState;
        private readonly AppState _appState;
        private readonly AdminCommandDispatcher _commandDispatcher;
        private string _runtimeVersion = "unknown";
        private int? _runtimePid;
        private double? _runtimeUptimeSeconds;
        private RuntimeTransition _pendingTransition = RuntimeTransition.None;
        private bool? _lastKnownRuntimeRunning;

        public RuntimeLifecycleController(
            BridgeState bridgeState,
            AppState appState,
            AdminCommandDispatcher commandDispatcher)
        {
            _bridgeState = bridgeState ?? throw new ArgumentNullException(nameof(bridgeState));
            _appState = appState ?? throw new ArgumentNullException(nameof(appState));
            _commandDispatcher = commandDispatcher ?? throw new ArgumentNullException(nameof(commandDispatcher));
        }

        public RuntimeLifecycleSnapshot GetSnapshot()
        {
            lock (_lock)
            {
                return BuildSnapshot(null);
            }
        }

        public void UpdateFromSnapshot(RuntimeSnapshot snapshot)
        {
            lock (_lock)
            {
                var runtimeRunning = snapshot?.IsTimestampValid == true;
                _lastKnownRuntimeRunning = runtimeRunning;
                var updated = BuildSnapshot(runtimeRunning);
                PublishSnapshot(updated);
            }
        }

        public void SetRuntimeVersion(string version)
        {
            lock (_lock)
            {
                _runtimeVersion = string.IsNullOrWhiteSpace(version) ? "unknown" : version;
                PublishSnapshot(BuildSnapshot(null));
            }
        }

        public async Task<RuntimeLifecycleSnapshot> StartAsync(
            CancellationToken cancellationToken = default)
        {
            var canDispatch = TryBeginTransition(RuntimeTransition.Starting, out var snapshot);
            if (!canDispatch)
                return snapshot;

            await DispatchCommandAsync(
                "runtime.launch",
                cancellationToken).ConfigureAwait(false);

            lock (_lock)
            {
                snapshot = BuildSnapshot(null);
                PublishSnapshot(snapshot);
                return snapshot;
            }
        }

        public RuntimeLifecycleSnapshot StartInBackground()
        {
            var canDispatch = TryBeginTransition(RuntimeTransition.Starting, out var snapshot);
            if (!canDispatch)
                return snapshot;

            _ = Task.Run(async () =>
            {
                await DispatchCommandAsync(
                    "runtime.launch",
                    CancellationToken.None).ConfigureAwait(false);

                lock (_lock)
                {
                    var updated = BuildSnapshot(null);
                    PublishSnapshot(updated);
                }
            });

            return snapshot;
        }

        public async Task<RuntimeLifecycleSnapshot> StopAsync(
            CancellationToken cancellationToken = default)
        {
            var canDispatch = TryBeginTransition(RuntimeTransition.Stopping, out var snapshot);
            if (!canDispatch)
                return snapshot;

            await DispatchCommandAsync(
                "runtime.terminate",
                cancellationToken).ConfigureAwait(false);

            lock (_lock)
            {
                snapshot = BuildSnapshot(null);
                PublishSnapshot(snapshot);
                return snapshot;
            }
        }

        public Task<RuntimeLifecycleSnapshot> StopRuntimeAsync(
            CancellationToken cancellationToken = default)
        {
            return StopAsync(cancellationToken);
        }

        public RuntimeLifecycleSnapshot StopInBackground()
        {
            var canDispatch = TryBeginTransition(RuntimeTransition.Stopping, out var snapshot);
            if (!canDispatch)
                return snapshot;

            _ = Task.Run(async () =>
            {
                await DispatchCommandAsync(
                    "runtime.terminate",
                    CancellationToken.None).ConfigureAwait(false);

                lock (_lock)
                {
                    var updated = BuildSnapshot(null);
                    PublishSnapshot(updated);
                }
            });

            return snapshot;
        }

        public RuntimeLifecycleSnapshot StopRuntimeInBackground()
        {
            return StopInBackground();
        }

        private bool TryBeginTransition(RuntimeTransition transition, out RuntimeLifecycleSnapshot snapshot)
        {
            lock (_lock)
            {
                snapshot = BuildSnapshot(null);

                if (transition == RuntimeTransition.Starting &&
                    (snapshot.Status == "running" || snapshot.Status == "starting"))
                    return false;

                if (transition == RuntimeTransition.Stopping &&
                    (snapshot.Status == "stopped" || snapshot.Status == "stopping"))
                    return false;

                _pendingTransition = transition;
                snapshot = BuildSnapshot(null);
                PublishSnapshot(snapshot);
                return true;
            }
        }

        private Task DispatchCommandAsync(string command, CancellationToken cancellationToken)
        {
            return _commandDispatcher.QueueCommandAsync(
                command,
                new Dictionary<string, string>(),
                cancellationToken);
        }

        private RuntimeLifecycleSnapshot BuildSnapshot(bool? runtimeRunningOverride)
        {
            var runtimeRunning = runtimeRunningOverride ??
                                 _lastKnownRuntimeRunning ??
                                 (_appState.LastSnapshot?.IsTimestampValid == true);

            var status = runtimeRunning ? "running" : "stopped";

            if (_pendingTransition == RuntimeTransition.Starting && !runtimeRunning)
                status = "starting";

            if (_pendingTransition == RuntimeTransition.Stopping && runtimeRunning)
                status = "stopping";

            if (_pendingTransition == RuntimeTransition.Starting && runtimeRunning)
                _pendingTransition = RuntimeTransition.None;

            if (_pendingTransition == RuntimeTransition.Stopping && !runtimeRunning)
                _pendingTransition = RuntimeTransition.None;

            return new RuntimeLifecycleSnapshot(
                status,
                _runtimePid,
                _runtimeUptimeSeconds,
                _runtimeVersion);
        }

        private void PublishSnapshot(RuntimeLifecycleSnapshot snapshot)
        {
            _bridgeState.SetRuntimeDetails(
                snapshot.Status,
                snapshot.RuntimePid,
                snapshot.RuntimeUptimeSeconds,
                snapshot.Version);
        }

        private enum RuntimeTransition
        {
            None,
            Starting,
            Stopping
        }
    }

    public readonly struct RuntimeLifecycleSnapshot
    {
        public RuntimeLifecycleSnapshot(
            string status,
            int? runtimePid,
            double? runtimeUptimeSeconds,
            string version)
        {
            Status = status;
            RuntimePid = runtimePid;
            RuntimeUptimeSeconds = runtimeUptimeSeconds;
            Version = version;
        }

        public string Status { get; }
        public int? RuntimePid { get; }
        public double? RuntimeUptimeSeconds { get; }
        public string Version { get; }
    }
}

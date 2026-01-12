using System;

namespace StreamSuites.DesktopAdmin.Bridge
{
    public sealed class BridgeState
    {
        private readonly object _lock = new();
        private string _status = "stopped";
        private string _lastError = string.Empty;
        private int _boundPort;
        private string _runtimeStatus = "unknown";
        private string _runtimeVersion = "unknown";

        public event EventHandler StateChanged;

        public BridgeStateSnapshot GetSnapshot()
        {
            lock (_lock)
            {
                return new BridgeStateSnapshot(
                    _status,
                    _lastError,
                    _boundPort,
                    _runtimeStatus,
                    _runtimeVersion);
            }
        }

        public void SetRunning(int port)
        {
            lock (_lock)
            {
                _status = "running";
                _lastError = string.Empty;
                _boundPort = port;
            }

            OnStateChanged();
        }

        public void SetStopped()
        {
            lock (_lock)
            {
                _status = "stopped";
                _lastError = string.Empty;
                _boundPort = 0;
            }

            OnStateChanged();
        }

        public void SetError(string message, int port)
        {
            lock (_lock)
            {
                _status = "error";
                _lastError = message ?? string.Empty;
                _boundPort = port;
            }

            OnStateChanged();
        }

        public void SetRuntimeStatus(string status)
        {
            lock (_lock)
            {
                _runtimeStatus = string.IsNullOrWhiteSpace(status) ? "unknown" : status;
            }

            OnStateChanged();
        }

        public void SetRuntimeVersion(string version)
        {
            lock (_lock)
            {
                _runtimeVersion = string.IsNullOrWhiteSpace(version) ? "unknown" : version;
            }

            OnStateChanged();
        }

        private void OnStateChanged()
        {
            StateChanged?.Invoke(this, EventArgs.Empty);
        }
    }

    public readonly struct BridgeStateSnapshot
    {
        public BridgeStateSnapshot(
            string status,
            string lastError,
            int boundPort,
            string runtimeStatus,
            string runtimeVersion)
        {
            Status = status;
            LastError = lastError;
            BoundPort = boundPort;
            RuntimeStatus = runtimeStatus;
            RuntimeVersion = runtimeVersion;
        }

        public string Status { get; }
        public string LastError { get; }
        public int BoundPort { get; }
        public string RuntimeStatus { get; }
        public string RuntimeVersion { get; }
    }
}

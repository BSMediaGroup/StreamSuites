using System.Collections.Generic;

namespace StreamSuites.DesktopAdmin.Models
{
    /// <summary>
    /// Represents the operational status of a single platform
    /// as reported by the StreamSuites runtime snapshot.
    /// Mirrors platform entries in runtime_snapshot.json.
    /// </summary>
    public class PlatformStatus
    {
        /// <summary>
        /// Internal platform name (e.g. "youtube", "rumble").
        /// </summary>
        public string Name { get; set; } = string.Empty;

        /// <summary>
        /// Platform identifier (usually same as Name).
        /// Preserved separately for schema parity.
        /// </summary>
        public string Platform { get; set; } = string.Empty;

        /// <summary>
        /// Whether the platform is enabled at the system level.
        /// </summary>
        public bool Enabled { get; set; }

        /// <summary>
        /// Whether the platform is currently paused.
        /// </summary>
        public bool Paused { get; set; }

        /// <summary>
        /// Whether telemetry collection is enabled.
        /// </summary>
        public bool Telemetry_Enabled { get; set; }

        /// <summary>
        /// High-level runtime state (active, paused, disabled).
        /// </summary>
        public string State { get; set; } = string.Empty;

        /// <summary>
        /// Reported status string (active, inactive, paused).
        /// </summary>
        public string Status { get; set; } = string.Empty;

        /// <summary>
        /// Optional pause reason supplied by runtime.
        /// </summary>
        public string? Paused_Reason { get; set; }

        /// <summary>
        /// Timestamp of last heartbeat from the platform worker.
        /// </summary>
        public string? Last_Heartbeat { get; set; }

        /// <summary>
        /// Timestamp of last successful event.
        /// </summary>
        public string? Last_Success_Ts { get; set; }

        /// <summary>
        /// Timestamp of last processed event.
        /// </summary>
        public string? Last_Event_Ts { get; set; }

        /// <summary>
        /// Optional error string reported by the platform.
        /// </summary>
        public string? Error { get; set; }

        /// <summary>
        /// Platform-level counters (messages, triggers, actions).
        /// </summary>
        public PlatformCounters Counters { get; set; }
            = new PlatformCounters();

        /// <summary>
        /// Whether chat replay is supported for this platform.
        /// </summary>
        public bool Replay_Supported { get; set; }

        /// <summary>
        /// Whether overlay rendering is supported for this platform.
        /// </summary>
        public bool Overlay_Supported { get; set; }

        // -----------------------------------------------------------------
        // Derived / UI-safe helpers (NOT part of runtime JSON contract)
        // -----------------------------------------------------------------

        /// <summary>
        /// Effective display state taking Enabled / Paused into account.
        /// </summary>
        public string Display_State
        {
            get
            {
                if (!Enabled)
                    return "Disabled";

                if (Paused)
                    return "Paused";

                if (!string.IsNullOrWhiteSpace(State))
                    return State;

                return "Unknown";
            }
        }

        /// <summary>
        /// Human-readable telemetry status.
        /// </summary>
        public string Telemetry_Display
        {
            get => Telemetry_Enabled ? "On" : "Off";
        }

        /// <summary>
        /// Indicates whether the platform currently reports an error.
        /// </summary>
        public bool Has_Error
        {
            get => !string.IsNullOrWhiteSpace(Error);
        }

        /// <summary>
        /// Short capability summary string for UI usage.
        /// </summary>
        public string Capabilities
        {
            get
            {
                var caps = new List<string>();

                if (Replay_Supported)
                    caps.Add("Replay");

                if (Overlay_Supported)
                    caps.Add("Overlay");

                return caps.Count == 0
                    ? "None"
                    : string.Join(", ", caps);
            }
        }
    }

    // ---------------------------------------------------------------------

    /// <summary>
    /// Counter block embedded in platform status.
    /// </summary>
    public class PlatformCounters
    {
        public int Messages { get; set; }
        public int Triggers { get; set; }
        public int Actions { get; set; }
        public int Actions_Failed { get; set; }
    }
}

using System;
using System.Collections.Generic;
using System.Globalization;

namespace StreamSuites.DesktopAdmin.Models
{
    /// <summary>
    /// Represents a complete snapshot of runtime state exported
    /// by the StreamSuites runtime engine.
    /// Mirrors runtime_snapshot.json exactly.
    /// </summary>
    public class RuntimeSnapshot
    {
        public string Schema_Version { get; set; } = string.Empty;

        public string Generated_At { get; set; } = string.Empty;

        public string Heartbeat { get; set; } = string.Empty;

        public RuntimeInfo Runtime { get; set; } = new RuntimeInfo();

        public SystemInfo System { get; set; } = new SystemInfo();

        public IList<JobStatus> Jobs { get; set; } = new List<JobStatus>();

        public IList<PlatformStatus> Platforms { get; set; }
            = new List<PlatformStatus>();

        public IList<CreatorStatus> Creators { get; set; }
            = new List<CreatorStatus>();

        public ReplayStatus Replay { get; set; } = new ReplayStatus();

        public RestartIntent Restart_Intent { get; set; } = new RestartIntent();

        // =============================================================
        // Derived / UI-safe helpers (NOT part of runtime JSON contract)
        // =============================================================

        public DateTime? ParsedGeneratedAt =>
            ParseUtcTimestamp(Generated_At);

        public DateTime? ParsedHeartbeat =>
            ParseUtcTimestamp(Heartbeat);

        /// <summary>
        /// Best available timestamp representing snapshot freshness.
        /// Prefers heartbeat, falls back to generated_at.
        /// </summary>
        public DateTime? EffectiveTimestamp =>
            ParsedHeartbeat ?? ParsedGeneratedAt;

        public bool IsTimestampValid =>
            EffectiveTimestamp.HasValue;

        /// <summary>
        /// Snapshot age in seconds (UTC).
        /// Returns null if timestamp invalid.
        /// </summary>
        public double? AgeSeconds
        {
            get
            {
                if (!EffectiveTimestamp.HasValue)
                    return null;

                return (DateTime.UtcNow - EffectiveTimestamp.Value)
                    .TotalSeconds;
            }
        }

        /// <summary>
        /// Determines whether snapshot is stale based on threshold.
        /// </summary>
        public bool IsStale(int staleAfterSeconds)
        {
            if (!AgeSeconds.HasValue)
                return true;

            return AgeSeconds.Value > staleAfterSeconds;
        }

        /// <summary>
        /// High-level snapshot health classification.
        /// </summary>
        public SnapshotHealthState HealthState(int staleAfterSeconds)
        {
            if (!IsTimestampValid)
                return SnapshotHealthState.Invalid;

            if (IsStale(staleAfterSeconds))
                return SnapshotHealthState.Stale;

            return SnapshotHealthState.Healthy;
        }

        private static DateTime? ParseUtcTimestamp(string raw)
        {
            if (string.IsNullOrWhiteSpace(raw))
                return null;

            if (DateTime.TryParse(
                raw,
                CultureInfo.InvariantCulture,
                DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal,
                out var parsed))
            {
                return parsed;
            }

            return null;
        }
    }

    // ================================================================
    // Supporting models (unchanged)
    // ================================================================

    public enum SnapshotHealthState
    {
        Healthy,
        Stale,
        Invalid
    }

    // ---------------------------------------------------------------------

    public class RuntimeInfo
    {
        public string Project { get; set; } = string.Empty;
        public string Version { get; set; } = string.Empty;
        public string Build { get; set; } = string.Empty;
    }

    // ---------------------------------------------------------------------

    public class SystemInfo
    {
        public PlatformPolling Platform_Polling_Enabled { get; set; }
            = new PlatformPolling();

        public Dictionary<string, bool> Platforms { get; set; }
            = new Dictionary<string, bool>();

        public HotReloadInfo Hot_Reload { get; set; }
            = new HotReloadInfo();
    }

    public class PlatformPolling
    {
        public bool Enabled { get; set; }
    }

    public class HotReloadInfo
    {
        public bool Enabled { get; set; }
        public string Watch_Path { get; set; } = string.Empty;
        public double Interval_Seconds { get; set; }
    }

    // ---------------------------------------------------------------------

    public class JobStatus
    {
        public string Name { get; set; } = string.Empty;
        public bool Enabled { get; set; }
        public bool Applied { get; set; }
        public string? Reason { get; set; }
    }

    // ---------------------------------------------------------------------

    public class CreatorStatus
    {
        public string Creator_Id { get; set; } = string.Empty;
        public string Display_Name { get; set; } = string.Empty;

        public bool Enabled { get; set; }

        public Dictionary<string, bool> Platforms { get; set; }
            = new Dictionary<string, bool>();

        public string? Last_Heartbeat { get; set; }
        public string? Error { get; set; }
    }

    // ---------------------------------------------------------------------

    public class ReplayStatus
    {
        public bool Available { get; set; }

        public IList<string> Platforms { get; set; }
            = new List<string>();

        public int Event_Count { get; set; }

        public string? Last_Event_Timestamp { get; set; }

        public bool Overlay_Safe { get; set; }
    }

    // ---------------------------------------------------------------------

    public class RestartIntent
    {
        public bool Required { get; set; }

        public RestartPending Pending { get; set; }
            = new RestartPending();
    }

    public class RestartPending
    {
        public bool System { get; set; }
        public bool Creators { get; set; }
        public bool Triggers { get; set; }
        public bool Platforms { get; set; }
    }
}

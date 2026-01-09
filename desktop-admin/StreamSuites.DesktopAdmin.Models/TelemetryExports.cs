using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Models
{
    public class TelemetryEventsExport
    {
        [JsonPropertyName("schema_version")]
        public string Schema_Version { get; set; } = string.Empty;

        [JsonPropertyName("generated_at")]
        public string Generated_At { get; set; } = string.Empty;

        [JsonPropertyName("events")]
        public List<TelemetryEventItem> Events { get; set; } = new();
    }

    public class TelemetryErrorsExport
    {
        [JsonPropertyName("schema_version")]
        public string Schema_Version { get; set; } = string.Empty;

        [JsonPropertyName("generated_at")]
        public string Generated_At { get; set; } = string.Empty;

        [JsonPropertyName("errors")]
        public List<TelemetryErrorItem> Errors { get; set; } = new();
    }

    public class TelemetryRatesExport
    {
        [JsonPropertyName("schema_version")]
        public string Schema_Version { get; set; } = string.Empty;

        [JsonPropertyName("generated_at")]
        public string Generated_At { get; set; } = string.Empty;

        [JsonPropertyName("windows")]
        public List<TelemetryRateWindow> Windows { get; set; } = new();
    }

    public class TelemetryEventItem
    {
        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = string.Empty;

        [JsonPropertyName("source")]
        public string Source { get; set; } = string.Empty;

        [JsonPropertyName("severity")]
        public string Severity { get; set; } = string.Empty;

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;
    }

    public class TelemetryErrorItem
    {
        [JsonPropertyName("timestamp")]
        public string Timestamp { get; set; } = string.Empty;

        [JsonPropertyName("subsystem")]
        public string Subsystem { get; set; } = string.Empty;

        [JsonPropertyName("error_type")]
        public string Error_Type { get; set; } = string.Empty;

        [JsonPropertyName("source")]
        public string? Source { get; set; }

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;
    }

    public class TelemetryRateWindow
    {
        [JsonPropertyName("window")]
        public string Window { get; set; } = string.Empty;

        [JsonPropertyName("metrics")]
        public TelemetryRateMetrics Metrics { get; set; } = new();
    }

    public class TelemetryRateMetrics
    {
        [JsonPropertyName("messages")]
        public Dictionary<string, int> Messages { get; set; } = new();

        [JsonPropertyName("triggers")]
        public Dictionary<string, int> Triggers { get; set; } = new();

        [JsonPropertyName("actions")]
        public Dictionary<string, int> Actions { get; set; } = new();

        [JsonPropertyName("actions_failed")]
        public Dictionary<string, int> Actions_Failed { get; set; } = new();
    }
}

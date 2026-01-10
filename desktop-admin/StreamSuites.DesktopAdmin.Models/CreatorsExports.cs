using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Models
{
    public class CreatorConfigExport
    {
        [JsonPropertyName("creators")]
        public List<CreatorConfigEntry> Creators { get; set; } = new();
    }

    public class CreatorConfigEntry
    {
        [JsonPropertyName("creator_id")]
        public string Creator_Id { get; set; } = string.Empty;

        [JsonPropertyName("display_name")]
        public string Display_Name { get; set; } = string.Empty;

        [JsonPropertyName("enabled")]
        public bool Enabled { get; set; }

        [JsonPropertyName("platforms")]
        public Dictionary<string, bool> Platforms { get; set; } = new();

        [JsonPropertyName("notes")]
        public string? Notes { get; set; }
    }

    public class AdminCreatorsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("creators")]
        public List<AdminCreatorEntry> Creators { get; set; } = new();
    }

    public class AdminExportMeta
    {
        [JsonPropertyName("generated_at")]
        public string Generated_At { get; set; } = string.Empty;

        [JsonPropertyName("captured_at")]
        public string Captured_At { get; set; } = string.Empty;

        [JsonPropertyName("source")]
        public string Source { get; set; } = string.Empty;

        [JsonPropertyName("visibility")]
        public string Visibility { get; set; } = string.Empty;

        [JsonPropertyName("scope")]
        public string Scope { get; set; } = string.Empty;
    }

    public class AdminCreatorEntry
    {
        [JsonPropertyName("creator_id")]
        public string Creator_Id { get; set; } = string.Empty;

        [JsonPropertyName("display_name")]
        public string Display_Name { get; set; } = string.Empty;

        [JsonPropertyName("platforms")]
        public Dictionary<string, AdminPlatformState> Platforms { get; set; } = new();

        [JsonPropertyName("created_at")]
        public string? Created_At { get; set; }

        [JsonPropertyName("updated_at")]
        public string? Updated_At { get; set; }

        [JsonPropertyName("notes")]
        public string? Notes { get; set; }
    }

    public class AdminPlatformState
    {
        [JsonPropertyName("enabled")]
        public bool Enabled { get; set; }
    }
}

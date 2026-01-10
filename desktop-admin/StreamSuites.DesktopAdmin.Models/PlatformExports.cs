using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Models
{
    public class PlatformsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("platforms")]
        public List<PlatformModuleExport> Platforms { get; set; } = new();
    }

    public class PlatformModuleExport
    {
        [JsonPropertyName("name")]
        public string Name { get; set; } = string.Empty;

        [JsonPropertyName("status")]
        public string Status { get; set; } = string.Empty;

        [JsonPropertyName("mode")]
        public string Mode { get; set; } = string.Empty;

        [JsonPropertyName("notes")]
        public string? Notes { get; set; }

        [JsonPropertyName("replay_supported")]
        public bool Replay_Supported { get; set; }

        [JsonPropertyName("overlay_supported")]
        public bool Overlay_Supported { get; set; }
    }
}

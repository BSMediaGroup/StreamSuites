using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Models
{
    public class AboutExport
    {
        [JsonPropertyName("scope")]
        public string Scope { get; set; } = string.Empty;

        [JsonPropertyName("surface")]
        public string Surface { get; set; } = string.Empty;

        [JsonPropertyName("version")]
        public string Version { get; set; } = string.Empty;

        [JsonPropertyName("build")]
        public string Build { get; set; } = string.Empty;

        [JsonPropertyName("last_updated")]
        public string Last_Updated { get; set; } = string.Empty;

        [JsonPropertyName("owner")]
        public string Owner { get; set; } = string.Empty;

        [JsonPropertyName("copyright")]
        public string Copyright { get; set; } = string.Empty;

        [JsonPropertyName("notice")]
        public string Notice { get; set; } = string.Empty;
    }
}

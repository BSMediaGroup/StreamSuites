using System;
using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Runtime.Processes
{
    public sealed class RuntimeProcessDefinition
    {
        [JsonPropertyName("id")]
        public string Id { get; set; } = string.Empty;

        [JsonPropertyName("display_name")]
        public string DisplayName { get; set; } = string.Empty;

        [JsonPropertyName("working_dir")]
        public string WorkingDirectory { get; set; } = string.Empty;

        [JsonPropertyName("exe")]
        public string Executable { get; set; } = string.Empty;

        [JsonPropertyName("args")]
        public RuntimeProcessArgs Args { get; set; } = new RuntimeProcessArgs();

        [JsonPropertyName("env")]
        public Dictionary<string, string> EnvironmentVariables { get; set; }
            = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);

        [JsonPropertyName("auto_start")]
        public bool AutoStart { get; set; }

        [JsonPropertyName("show_in_ui")]
        public bool ShowInUi { get; set; } = true;

        [JsonPropertyName("start_in_external_terminal_by_default")]
        public bool StartInExternalTerminalByDefault { get; set; }

        public string DisplayLabel =>
            string.IsNullOrWhiteSpace(DisplayName) ? Id : DisplayName;
    }
}

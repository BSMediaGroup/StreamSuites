using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Runtime.Processes
{
    public sealed class RuntimeProcessConfig
    {
        [JsonPropertyName("stop_all_on_exit")]
        public bool StopAllOnExit { get; set; }

        [JsonPropertyName("processes")]
        public List<RuntimeProcessDefinition> Processes { get; set; }
            = new List<RuntimeProcessDefinition>();
    }
}

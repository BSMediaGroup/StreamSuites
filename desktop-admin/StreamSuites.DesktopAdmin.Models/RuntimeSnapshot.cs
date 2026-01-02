using System.Collections.Generic;

namespace StreamSuites.DesktopAdmin.Models;

public class RuntimeSnapshot
{
    public string Version { get; set; } = string.Empty;

    public string CapturedAt { get; set; } = string.Empty;

    public IList<PlatformStatus> Platforms { get; set; } = new List<PlatformStatus>();

    public TelemetrySnapshot? Telemetry { get; set; }
        = new TelemetrySnapshot();

    public IList<TriggerCounter> TriggerCounters { get; set; } = new List<TriggerCounter>();
}

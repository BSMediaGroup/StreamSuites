namespace StreamSuites.DesktopAdmin.Models;

public class TelemetrySnapshot
{
    public int ErrorCount { get; set; }
        = 0;

    public int EventRatePerMinute { get; set; }
        = 0;

    public int ActiveJobs { get; set; }
        = 0;
}

namespace StreamSuites.DesktopAdmin.Models;

public class PlatformStatus
{
    public string Platform { get; set; } = string.Empty;

    public string Health { get; set; } = "unknown";

    public string LastUpdated { get; set; } = string.Empty;
}

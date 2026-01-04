namespace StreamSuites.DesktopAdmin.Models
{
    /// <summary>
    /// Represents telemetry metrics captured from the runtime
    /// at the time a snapshot is generated.
    /// </summary>
    public class TelemetrySnapshot
    {
        /// <summary>
        /// Total number of runtime errors recorded.
        /// </summary>
        public int ErrorCount { get; set; } = 0;

        /// <summary>
        /// Aggregate event rate per minute across all platforms.
        /// </summary>
        public int EventRatePerMinute { get; set; } = 0;

        /// <summary>
        /// Number of currently active jobs.
        /// </summary>
        public int ActiveJobs { get; set; } = 0;
    }
}

namespace StreamSuites.DesktopAdmin.Models
{
    /// <summary>
    /// Represents a counter for a specific trigger or action
    /// recorded by the StreamSuites runtime.
    /// </summary>
    public class TriggerCounter
    {
        /// <summary>
        /// Trigger identifier or name.
        /// </summary>
        public string Name { get; set; } = string.Empty;

        /// <summary>
        /// Total number of times the trigger has fired.
        /// </summary>
        public int Count { get; set; } = 0;
    }
}

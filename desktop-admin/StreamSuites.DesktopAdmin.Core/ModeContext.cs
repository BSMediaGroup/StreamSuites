namespace StreamSuites.DesktopAdmin.Core
{
    /// <summary>
    /// Represents the current operational mode of the admin UI.
    /// This mirrors high-level routing / mode state in the web dashboard.
    /// </summary>
    public class ModeContext
    {
        public ModeContext(string currentMode)
        {
            CurrentMode = string.IsNullOrWhiteSpace(currentMode)
                ? "Unknown"
                : currentMode;
        }

        /// <summary>
        /// The active mode identifier (e.g. Dashboard, Telemetry, Config).
        /// </summary>
        public string CurrentMode { get; private set; }

        /// <summary>
        /// Switches the current mode if a valid value is provided.
        /// </summary>
        public void SetMode(string mode)
        {
            if (!string.IsNullOrWhiteSpace(mode))
            {
                CurrentMode = mode;
            }
        }
    }
}

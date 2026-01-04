using StreamSuites.DesktopAdmin.Models;

namespace StreamSuites.DesktopAdmin.Core
{
    /// <summary>
    /// Central application state container for the desktop admin UI.
    /// Mirrors the role of the global app state in the web dashboard.
    /// </summary>
    public class AppState
    {
        public AppState(ModeContext modeContext)
        {
            ModeContext = modeContext;
        }

        /// <summary>
        /// Current UI mode / view context.
        /// </summary>
        public ModeContext ModeContext { get; }

        /// <summary>
        /// Most recently ingested runtime snapshot.
        /// Null until the first successful load.
        /// </summary>
        public RuntimeSnapshot LastSnapshot { get; set; }
    }
}

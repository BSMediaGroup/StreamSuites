using StreamSuites.DesktopAdmin.Models;

namespace StreamSuites.DesktopAdmin.Core;

public class AppState
{
    public AppState(ModeContext modeContext)
    {
        ModeContext = modeContext;
    }

    public ModeContext ModeContext { get; }

    public RuntimeSnapshot? LastSnapshot { get; set; }
}

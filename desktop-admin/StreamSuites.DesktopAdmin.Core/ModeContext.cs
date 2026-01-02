namespace StreamSuites.DesktopAdmin.Core;

public class ModeContext
{
    public ModeContext(string currentMode)
    {
        CurrentMode = string.IsNullOrWhiteSpace(currentMode) ? "Unknown" : currentMode;
    }

    public string CurrentMode { get; private set; }

    public void SetMode(string mode)
    {
        CurrentMode = string.IsNullOrWhiteSpace(mode) ? CurrentMode : mode;
    }
}

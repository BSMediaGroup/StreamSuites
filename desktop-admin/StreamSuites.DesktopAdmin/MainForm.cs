using System.Windows.Forms;
using StreamSuites.DesktopAdmin.Core;

namespace StreamSuites.DesktopAdmin;

public partial class MainForm : Form
{
    private readonly AppState _appState;

    public MainForm(AppState appState)
    {
        _appState = appState;
        InitializeComponent();
        UpdateModeStatus();
    }

    private void UpdateModeStatus()
    {
        modeStatusLabel.Text = $"Mode: {_appState.ModeContext.CurrentMode}";
    }
}

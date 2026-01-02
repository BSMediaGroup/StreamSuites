using System;
using System.Windows.Forms;
using StreamSuites.DesktopAdmin.Core;

namespace StreamSuites.DesktopAdmin;

internal static class Program
{
    [STAThread]
    private static void Main()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);

        var appState = new AppState(new ModeContext("Static"));
        var mainForm = new MainForm(appState);

        Application.Run(mainForm);
    }
}

using StreamSuites.DesktopAdmin.Core;
using StreamSuites.DesktopAdmin.Models;

namespace StreamSuites.DesktopAdmin.RuntimeBridge;

public class RuntimeConnector
{
    private readonly FileSnapshotReader _snapshotReader;
    private readonly AppState _appState;

    public RuntimeConnector(FileSnapshotReader snapshotReader, AppState appState)
    {
        _snapshotReader = snapshotReader;
        _appState = appState;
    }

    public async Task<RuntimeSnapshot?> RefreshSnapshotAsync(string snapshotPath, CancellationToken cancellationToken = default)
    {
        var snapshot = await _snapshotReader.TryReadSnapshotAsync(snapshotPath, cancellationToken).ConfigureAwait(false);
        _appState.LastSnapshot = snapshot;
        return snapshot;
    }
}

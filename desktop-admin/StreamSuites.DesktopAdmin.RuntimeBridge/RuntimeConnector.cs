using System.Threading;
using System.Threading.Tasks;
using StreamSuites.DesktopAdmin.Core;
using StreamSuites.DesktopAdmin.Models;

namespace StreamSuites.DesktopAdmin.RuntimeBridge
{
    /// <summary>
    /// Coordinates ingestion of runtime snapshot data into application state.
    /// Acts as the bridge between exported runtime files and the admin UI.
    /// </summary>
    public class RuntimeConnector
    {
        private readonly FileSnapshotReader _snapshotReader;
        private readonly AppState _appState;

        public RuntimeConnector(
            FileSnapshotReader snapshotReader,
            AppState appState)
        {
            _snapshotReader = snapshotReader;
            _appState = appState;
        }

        /// <summary>
        /// Attempts to refresh the runtime snapshot from disk and
        /// apply it to the central application state.
        /// </summary>
        public async Task<RuntimeSnapshot> RefreshSnapshotAsync(
            string snapshotPath,
            CancellationToken cancellationToken = default)
        {
            var snapshot = await _snapshotReader
                .TryReadSnapshotAsync(snapshotPath, cancellationToken)
                .ConfigureAwait(false);

            if (snapshot != null)
            {
                _appState.LastSnapshot = snapshot;
            }

            return snapshot;
        }
    }
}

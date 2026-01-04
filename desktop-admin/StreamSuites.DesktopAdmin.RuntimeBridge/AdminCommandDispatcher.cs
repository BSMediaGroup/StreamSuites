using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using StreamSuites.DesktopAdmin.Core;

namespace StreamSuites.DesktopAdmin.RuntimeBridge
{
    /// <summary>
    /// Dispatches administrative commands intended for the runtime.
    /// In the current alpha phase, this is intentionally a no-op to
    /// preserve a strictly read-only control surface.
    /// </summary>
    public class AdminCommandDispatcher
    {
        private readonly AppState _appState;

        public AdminCommandDispatcher(AppState appState)
        {
            _appState = appState;
        }

        /// <summary>
        /// Queues an administrative command for execution.
        /// Currently unimplemented by design.
        /// </summary>
        public Task QueueCommandAsync(
            string commandName,
            IDictionary<string, string> arguments,
            CancellationToken cancellationToken = default)
        {
            // Future hook for sending control-plane instructions to the runtime.
            // Alpha scope intentionally prevents runtime mutation.
            return Task.CompletedTask;
        }
    }
}

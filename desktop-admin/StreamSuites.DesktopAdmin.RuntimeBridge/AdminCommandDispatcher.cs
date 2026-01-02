using System.Collections.Generic;
using StreamSuites.DesktopAdmin.Core;

namespace StreamSuites.DesktopAdmin.RuntimeBridge;

public class AdminCommandDispatcher
{
    private readonly AppState _appState;

    public AdminCommandDispatcher(AppState appState)
    {
        _appState = appState;
    }

    public Task QueueCommandAsync(string commandName, IDictionary<string, string>? arguments = null, CancellationToken cancellationToken = default)
    {
        // Future hook for sending control-plane instructions to the runtime.
        // Alpha scope keeps this as a no-op to avoid runtime mutation.
        return Task.CompletedTask;
    }
}

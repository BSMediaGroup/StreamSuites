using System.Text.Json;
using StreamSuites.DesktopAdmin.Models;

namespace StreamSuites.DesktopAdmin.RuntimeBridge;

public interface IFileAccessor
{
    Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default);

    Task<string?> ReadAllTextAsync(string path, CancellationToken cancellationToken = default);
}

public class DefaultFileAccessor : IFileAccessor
{
    public Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default)
    {
        return Task.FromResult(File.Exists(path));
    }

    public async Task<string?> ReadAllTextAsync(string path, CancellationToken cancellationToken = default)
    {
        if (!File.Exists(path))
        {
            return null;
        }

        return await File.ReadAllTextAsync(path, cancellationToken).ConfigureAwait(false);
    }
}

public class FileSnapshotReader
{
    private readonly IFileAccessor _fileAccessor;
    private readonly JsonSerializerOptions _serializerOptions;

    public FileSnapshotReader(IFileAccessor fileAccessor)
    {
        _fileAccessor = fileAccessor;
        _serializerOptions = new JsonSerializerOptions
        {
            PropertyNameCaseInsensitive = true,
            WriteIndented = false
        };
    }

    public async Task<RuntimeSnapshot?> TryReadSnapshotAsync(string path, CancellationToken cancellationToken = default)
    {
        if (string.IsNullOrWhiteSpace(path))
        {
            return null;
        }

        if (!await _fileAccessor.ExistsAsync(path, cancellationToken).ConfigureAwait(false))
        {
            return null;
        }

        var content = await _fileAccessor.ReadAllTextAsync(path, cancellationToken).ConfigureAwait(false);
        if (string.IsNullOrWhiteSpace(content))
        {
            return null;
        }

        try
        {
            return JsonSerializer.Deserialize<RuntimeSnapshot>(content, _serializerOptions);
        }
        catch (JsonException)
        {
            return null;
        }
    }
}

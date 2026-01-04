using System.IO;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using StreamSuites.DesktopAdmin.Models;

namespace StreamSuites.DesktopAdmin.RuntimeBridge
{
    /// <summary>
    /// Abstraction for filesystem access to allow testing and isolation.
    /// </summary>
    public interface IFileAccessor
    {
        Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default);
        Task<string> ReadAllTextAsync(string path, CancellationToken cancellationToken = default);
    }

    /// <summary>
    /// Default filesystem-backed implementation of IFileAccessor.
    /// </summary>
    public class DefaultFileAccessor : IFileAccessor
    {
        public Task<bool> ExistsAsync(string path, CancellationToken cancellationToken = default)
        {
            return Task.FromResult(File.Exists(path));
        }

        public async Task<string> ReadAllTextAsync(string path, CancellationToken cancellationToken = default)
        {
            if (!File.Exists(path))
            {
                return string.Empty;
            }

            return await File.ReadAllTextAsync(path, cancellationToken)
                .ConfigureAwait(false);
        }
    }

    /// <summary>
    /// Reads and deserializes runtime snapshot files exported by the StreamSuites runtime.
    /// </summary>
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

        /// <summary>
        /// Attempts to read and deserialize a runtime snapshot from disk.
        /// Returns an empty RuntimeSnapshot if the operation fails.
        /// </summary>
        public async Task<RuntimeSnapshot> TryReadSnapshotAsync(
            string path,
            CancellationToken cancellationToken = default)
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return new RuntimeSnapshot();
            }

            if (!await _fileAccessor.ExistsAsync(path, cancellationToken)
                    .ConfigureAwait(false))
            {
                return new RuntimeSnapshot();
            }

            var content = await _fileAccessor
                .ReadAllTextAsync(path, cancellationToken)
                .ConfigureAwait(false);

            if (string.IsNullOrWhiteSpace(content))
            {
                return new RuntimeSnapshot();
            }

            try
            {
                var snapshot = JsonSerializer.Deserialize<RuntimeSnapshot>(
                    content,
                    _serializerOptions);

                return snapshot ?? new RuntimeSnapshot();
            }
            catch (JsonException)
            {
                return new RuntimeSnapshot();
            }
        }
    }
}

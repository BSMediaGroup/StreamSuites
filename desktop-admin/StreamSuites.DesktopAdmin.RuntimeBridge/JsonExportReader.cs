using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace StreamSuites.DesktopAdmin.RuntimeBridge
{
    /// <summary>
    /// Generic JSON reader for runtime export files.
    /// </summary>
    public class JsonExportReader
    {
        private readonly IFileAccessor _fileAccessor;
        private readonly JsonSerializerOptions _serializerOptions;

        public JsonExportReader(IFileAccessor fileAccessor)
        {
            _fileAccessor = fileAccessor;

            _serializerOptions = new JsonSerializerOptions
            {
                PropertyNameCaseInsensitive = true,
                WriteIndented = false
            };
        }

        public async Task<T?> TryReadAsync<T>(
            string path,
            CancellationToken cancellationToken = default)
            where T : class
        {
            if (string.IsNullOrWhiteSpace(path))
            {
                return null;
            }

            if (!await _fileAccessor.ExistsAsync(path, cancellationToken)
                    .ConfigureAwait(false))
            {
                return null;
            }

            var content = await _fileAccessor
                .ReadAllTextAsync(path, cancellationToken)
                .ConfigureAwait(false);

            if (string.IsNullOrWhiteSpace(content))
            {
                return null;
            }

            try
            {
                return JsonSerializer.Deserialize<T>(
                    content,
                    _serializerOptions);
            }
            catch (JsonException)
            {
                return null;
            }
        }
    }
}

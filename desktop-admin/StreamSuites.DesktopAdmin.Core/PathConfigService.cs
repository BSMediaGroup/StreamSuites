using System;
using System.Collections.Generic;
using System.Configuration;
using System.IO;
using System.Text.Json;
using System.Text.Json.Serialization;
using System.Text.RegularExpressions;

namespace StreamSuites.DesktopAdmin.Core
{
    public class PathConfiguration
    {
        [JsonPropertyName("runtime_snapshot_root")]
        public string RuntimeSnapshotRoot { get; set; } = string.Empty;

        [JsonPropertyName("last_updated_utc")]
        public DateTime LastUpdatedUtc { get; set; }
    }

    public enum SnapshotPathState
    {
        NotConfigured,
        DirectoryMissing,
        FileMissing,
        PermissionDenied,
        InvalidFormat,
        InvalidPath,
        Valid
    }

    public class SnapshotPathStatus
    {
        public SnapshotPathState State { get; set; }

        public string Message { get; set; } = string.Empty;

        public string SnapshotRoot { get; set; } = string.Empty;

        public string SnapshotFilePath { get; set; } = string.Empty;

        public DateTime? LastModifiedUtc { get; set; }

        public string SnapshotFileName { get; set; } = string.Empty;

        public TimeSpan? Age
        {
            get
            {
                if (LastModifiedUtc == null)
                    return null;

                return DateTime.UtcNow - LastModifiedUtc.Value;
            }
        }

        public bool IsValid => State == SnapshotPathState.Valid;
    }

    public class PathConfigService
    {
        private const string ConfigFileName = "desktop-admin.json";
        private const string ConfigDirectory = "StreamSuites";

        private readonly string _configPath;
        private readonly string _snapshotFileName;
        private readonly string _importedAppConfigRoot;

        public PathConfigService()
        {
            var localAppData =
                Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);

            _configPath = Path.Combine(localAppData, ConfigDirectory, ConfigFileName);
            _snapshotFileName = ConfigurationManager.AppSettings["SnapshotFileName"] ??
                "runtime_snapshot.json";
            _importedAppConfigRoot =
                ConfigurationManager.AppSettings["SnapshotDirectory"] ?? string.Empty;
        }

        public string SnapshotFileName => _snapshotFileName;

        public PathConfiguration Load()
        {
            var existing = ReadConfigFromDisk();
            if (!string.IsNullOrWhiteSpace(existing.RuntimeSnapshotRoot))
            {
                return existing;
            }

            var imported = ImportFromAppConfig();
            if (!string.IsNullOrWhiteSpace(imported.RuntimeSnapshotRoot))
            {
                SaveSnapshotRoot(imported.RuntimeSnapshotRoot);
                return imported;
            }

            return existing;
        }

        public void SaveSnapshotRoot(string? snapshotRoot)
        {
            var normalized = NormalizeRoot(snapshotRoot);

            var payload = new PathConfiguration
            {
                RuntimeSnapshotRoot = normalized,
                LastUpdatedUtc = DateTime.UtcNow
            };

            try
            {
                var directory = Path.GetDirectoryName(_configPath);
                if (!string.IsNullOrWhiteSpace(directory))
                {
                    Directory.CreateDirectory(directory);
                }

                var json = JsonSerializer.Serialize(payload, new JsonSerializerOptions
                {
                    WriteIndented = true
                });

                File.WriteAllText(_configPath, json);
            }
            catch
            {
                // Swallow exceptions to avoid crashing the dashboard when persistence fails.
            }
        }

        public SnapshotPathStatus ValidateSnapshotRoot(string? snapshotRoot)
        {
            var normalized = NormalizeRoot(snapshotRoot);
            var status = new SnapshotPathStatus
            {
                SnapshotRoot = normalized,
                SnapshotFileName = _snapshotFileName,
                State = SnapshotPathState.NotConfigured,
                Message = "Snapshot path not configured"
            };

            if (string.IsNullOrWhiteSpace(normalized))
            {
                return status;
            }

            if (!Path.IsPathRooted(normalized))
            {
                status.State = SnapshotPathState.InvalidPath;
                status.Message = "Path must be absolute";
                return status;
            }

            if (!Directory.Exists(normalized))
            {
                status.State = SnapshotPathState.DirectoryMissing;
                status.Message = "Directory missing";
                return status;
            }

            var snapshotPath = Path.Combine(normalized, _snapshotFileName);
            status.SnapshotFilePath = snapshotPath;

            try
            {
                var fileInfo = new FileInfo(snapshotPath);
                if (!fileInfo.Exists)
                {
                    status.State = SnapshotPathState.FileMissing;
                    status.Message = $"{_snapshotFileName} missing";
                    return status;
                }

                status.LastModifiedUtc = fileInfo.LastWriteTimeUtc;

                string content;
                using (var stream = new FileStream(snapshotPath, FileMode.Open, FileAccess.Read, FileShare.ReadWrite))
                using (var reader = new StreamReader(stream))
                {
                    content = reader.ReadToEnd();
                }

                if (string.IsNullOrWhiteSpace(content))
                {
                    status.State = SnapshotPathState.InvalidFormat;
                    status.Message = "Snapshot file is empty";
                    return status;
                }

                try
                {
                    using var doc = JsonDocument.Parse(content);
                    if (!doc.RootElement.TryGetProperty("runtime", out _))
                    {
                        status.State = SnapshotPathState.InvalidFormat;
                        status.Message = "Invalid snapshot format";
                        return status;
                    }
                }
                catch (JsonException)
                {
                    status.State = SnapshotPathState.InvalidFormat;
                    status.Message = "Invalid snapshot format";
                    return status;
                }

                status.State = SnapshotPathState.Valid;
                status.Message = "Snapshot path valid";
                return status;
            }
            catch (UnauthorizedAccessException)
            {
                status.State = SnapshotPathState.PermissionDenied;
                status.Message = "Permission denied";
                return status;
            }
            catch (IOException)
            {
                status.State = SnapshotPathState.PermissionDenied;
                status.Message = "Permission denied";
                return status;
            }
        }

        private PathConfiguration ReadConfigFromDisk()
        {
            try
            {
                if (!File.Exists(_configPath))
                {
                    return new PathConfiguration();
                }

                var json = File.ReadAllText(_configPath);
                if (string.IsNullOrWhiteSpace(json))
                {
                    return new PathConfiguration();
                }

                var payload = JsonSerializer.Deserialize<PathConfiguration>(
                    json,
                    new JsonSerializerOptions
                    {
                        PropertyNameCaseInsensitive = true
                    });
                if (payload == null)
                {
                    return new PathConfiguration();
                }

                return new PathConfiguration
                {
                    RuntimeSnapshotRoot = NormalizeRoot(payload.RuntimeSnapshotRoot),
                    LastUpdatedUtc = payload.LastUpdatedUtc
                };
            }
            catch
            {
                return new PathConfiguration();
            }
        }

        private PathConfiguration ImportFromAppConfig()
        {
            if (string.IsNullOrWhiteSpace(_importedAppConfigRoot))
            {
                return new PathConfiguration();
            }

            return new PathConfiguration
            {
                RuntimeSnapshotRoot = NormalizeRoot(_importedAppConfigRoot),
                LastUpdatedUtc = DateTime.UtcNow
            };
        }

        private static string NormalizeRoot(string? snapshotRoot)
        {
            if (string.IsNullOrWhiteSpace(snapshotRoot))
            {
                return string.Empty;
            }

            var trimmed = snapshotRoot.Trim();

            try
            {
                if (Path.IsPathRooted(trimmed))
                {
                    return Path.GetFullPath(trimmed);
                }

                return trimmed;
            }
            catch
            {
                return trimmed;
            }
        }

    }

    public sealed class RuntimeVersionInfo
    {
        public RuntimeVersionInfo(string version, string build, string sourcePath)
        {
            Version = version;
            Build = build;
            SourcePath = sourcePath;
        }

        public string Version { get; }

        public string Build { get; }

        public string SourcePath { get; }

        public bool IsVersionAvailable =>
            !string.Equals(Version, RuntimeVersionProvider.VersionUnavailable, StringComparison.Ordinal);

        public bool IsBuildAvailable =>
            !string.Equals(Build, RuntimeVersionProvider.BuildUnavailable, StringComparison.Ordinal);

        public string ToDisplayVersion()
        {
            return IsVersionAvailable
                ? $"v{Version}"
                : Version;
        }

        public string ToDisplayBuild()
        {
            return IsBuildAvailable
                ? $"Build {Build}"
                : Build;
        }

        public static RuntimeVersionInfo Unavailable(string? sourcePath = null)
        {
            return new RuntimeVersionInfo(
                RuntimeVersionProvider.VersionUnavailable,
                RuntimeVersionProvider.BuildUnavailable,
                sourcePath ?? string.Empty);
        }
    }

    public static class RuntimeVersionProvider
    {
        public const string VersionUnavailable = "Version unavailable";
        public const string BuildUnavailable = "Build unavailable";

        private static readonly Regex VersionRegex = new(
            @"^\s*VERSION\s*=\s*[""'](?<value>[^""']+)[""']\s*$",
            RegexOptions.Multiline);

        private static readonly Regex BuildRegex = new(
            @"^\s*BUILD\s*=\s*[""'](?<value>[^""']+)[""']\s*$",
            RegexOptions.Multiline);

        public static RuntimeVersionInfo Load(string? snapshotRoot)
        {
            var path = ResolveVersionPath();
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
            {
                return RuntimeVersionInfo.Unavailable(path);
            }

            try
            {
                var content = File.ReadAllText(path);
                return ParseContent(content, path);
            }
            catch
            {
                return RuntimeVersionInfo.Unavailable(path);
            }
        }

        private static RuntimeVersionInfo ParseContent(string content, string sourcePath)
        {
            var version = ExtractValue(VersionRegex, content, VersionUnavailable);
            var build = ExtractValue(BuildRegex, content, BuildUnavailable);

            return new RuntimeVersionInfo(version, build, sourcePath);
        }

        private static string ExtractValue(Regex regex, string content, string fallback)
        {
            var match = regex.Match(content);
            if (!match.Success)
            {
                return fallback;
            }

            var value = match.Groups["value"].Value.Trim();
            return string.IsNullOrWhiteSpace(value) ? fallback : value;
        }

        private static string? ResolveVersionPath()
        {
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            if (!string.IsNullOrWhiteSpace(baseDir))
            {
                var directory = new DirectoryInfo(baseDir);
                while (directory != null)
                {
                    if (IsRuntimeRepoRoot(directory.FullName))
                    {
                        return Path.Combine(directory.FullName, "runtime", "version.py");
                    }

                    directory = directory.Parent;
                }
            }

            return null;
        }

        private static bool IsRuntimeRepoRoot(string candidateRoot)
        {
            var runtimeVersion = Path.Combine(candidateRoot, "runtime", "version.py");
            var desktopAdmin = Path.Combine(candidateRoot, "desktop-admin");
            return File.Exists(runtimeVersion) && Directory.Exists(desktopAdmin);
        }
    }
}

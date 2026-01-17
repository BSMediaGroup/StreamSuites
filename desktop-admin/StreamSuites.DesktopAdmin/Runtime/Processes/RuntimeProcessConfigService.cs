using System;
using System.IO;
using System.Text.Json;

namespace StreamSuites.DesktopAdmin.Runtime.Processes
{
    public sealed class RuntimeProcessConfigService
    {
        private const string ConfigFileName = "runtime-processes.json";
        private const string ConfigDirectory = "StreamSuites";

        public string AppDataConfigPath
        {
            get
            {
                var localAppData =
                    Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
                return Path.Combine(localAppData, ConfigDirectory, ConfigFileName);
            }
        }

        public string AppBaseConfigPath =>
            Path.Combine(AppDomain.CurrentDomain.BaseDirectory, ConfigFileName);

        public RuntimeProcessConfig Load()
        {
            var payload = TryLoadFromDisk(AppDataConfigPath)
                ?? TryLoadFromDisk(AppBaseConfigPath)
                ?? new RuntimeProcessConfig();

            return payload;
        }

        public string DescribeConfigLocation()
        {
            if (File.Exists(AppDataConfigPath))
                return AppDataConfigPath;

            if (File.Exists(AppBaseConfigPath))
                return AppBaseConfigPath;

            return AppDataConfigPath;
        }

        private static RuntimeProcessConfig? TryLoadFromDisk(string path)
        {
            if (string.IsNullOrWhiteSpace(path) || !File.Exists(path))
                return null;

            try
            {
                var json = File.ReadAllText(path);
                if (string.IsNullOrWhiteSpace(json))
                    return null;

                var options = new JsonSerializerOptions
                {
                    PropertyNameCaseInsensitive = true
                };
                options.Converters.Add(new RuntimeProcessArgsConverter());

                return JsonSerializer.Deserialize<RuntimeProcessConfig>(json, options);
            }
            catch
            {
                return null;
            }
        }
    }
}

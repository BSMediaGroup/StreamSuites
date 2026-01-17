using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Runtime.Processes
{
    [JsonConverter(typeof(RuntimeProcessArgsConverter))]
    public sealed class RuntimeProcessArgs
    {
        public string Raw { get; private set; } = string.Empty;
        public IReadOnlyList<string> Arguments { get; private set; }
            = Array.Empty<string>();

        public bool HasList => Arguments.Count > 0;

        public void SetRaw(string raw)
        {
            Raw = raw ?? string.Empty;
            Arguments = Array.Empty<string>();
        }

        public void SetArguments(IEnumerable<string> args)
        {
            Arguments = args?.Where(arg => !string.IsNullOrWhiteSpace(arg)).ToArray()
                ?? Array.Empty<string>();
            Raw = string.Empty;
        }
    }

    internal sealed class RuntimeProcessArgsConverter : JsonConverter<RuntimeProcessArgs>
    {
        public override RuntimeProcessArgs Read(
            ref Utf8JsonReader reader,
            Type typeToConvert,
            JsonSerializerOptions options)
        {
            var args = new RuntimeProcessArgs();

            if (reader.TokenType == JsonTokenType.String)
            {
                args.SetRaw(reader.GetString() ?? string.Empty);
                return args;
            }

            if (reader.TokenType == JsonTokenType.StartArray)
            {
                var list = new List<string>();
                while (reader.Read())
                {
                    if (reader.TokenType == JsonTokenType.EndArray)
                        break;
                    if (reader.TokenType == JsonTokenType.String)
                    {
                        list.Add(reader.GetString() ?? string.Empty);
                    }
                }

                args.SetArguments(list);
                return args;
            }

            if (reader.TokenType == JsonTokenType.Null)
                return args;

            throw new JsonException("Invalid args format in runtime-processes.json");
        }

        public override void Write(
            Utf8JsonWriter writer,
            RuntimeProcessArgs value,
            JsonSerializerOptions options)
        {
            if (value == null || (!value.HasList && string.IsNullOrWhiteSpace(value.Raw)))
            {
                writer.WriteStringValue(string.Empty);
                return;
            }

            if (value.HasList)
            {
                writer.WriteStartArray();
                foreach (var arg in value.Arguments)
                {
                    writer.WriteStringValue(arg ?? string.Empty);
                }
                writer.WriteEndArray();
                return;
            }

            writer.WriteStringValue(value.Raw ?? string.Empty);
        }
    }
}

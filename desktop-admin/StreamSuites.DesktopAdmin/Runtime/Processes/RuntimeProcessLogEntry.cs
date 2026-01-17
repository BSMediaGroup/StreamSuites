using System;

namespace StreamSuites.DesktopAdmin.Runtime.Processes
{
    public sealed class RuntimeProcessLogEntry
    {
        public RuntimeProcessLogEntry(
            DateTime timestampUtc,
            string stream,
            string message)
        {
            TimestampUtc = timestampUtc;
            Stream = stream;
            Message = message;
        }

        public DateTime TimestampUtc { get; }
        public string Stream { get; }
        public string Message { get; }

        public override string ToString()
        {
            return $"[{TimestampUtc:HH:mm:ss}] [{Stream}] {Message}";
        }
    }
}

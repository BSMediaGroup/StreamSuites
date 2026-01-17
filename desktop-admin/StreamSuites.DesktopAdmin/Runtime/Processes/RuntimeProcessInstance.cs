using System;
using System.Collections.Generic;
using System.Diagnostics;

namespace StreamSuites.DesktopAdmin.Runtime.Processes
{
    public sealed class RuntimeProcessInstance
    {
        private readonly List<RuntimeProcessLogEntry> _logEntries = new List<RuntimeProcessLogEntry>();
        private readonly object _logSync = new object();
        private int _logCap;

        public RuntimeProcessInstance(RuntimeProcessDefinition definition, int logCap)
        {
            Definition = definition ?? throw new ArgumentNullException(nameof(definition));
            _logCap = logCap;
        }

        public RuntimeProcessDefinition Definition { get; }
        public Process? Process { get; set; }
        public RuntimeProcessStatus Status { get; set; }
        public DateTime? StartTimeUtc { get; set; }
        public int? LastExitCode { get; set; }
        public string? LastError { get; set; }
        public int LogCap => _logCap;
        internal JobObject? Job { get; set; }

        public void AddLogEntry(RuntimeProcessLogEntry entry)
        {
            lock (_logSync)
            {
                _logEntries.Add(entry);
                TrimLogBuffer();
            }
        }

        public IReadOnlyList<RuntimeProcessLogEntry> GetLogSnapshot()
        {
            lock (_logSync)
            {
                return new List<RuntimeProcessLogEntry>(_logEntries);
            }
        }

        public void SetLogCap(int logCap)
        {
            if (logCap <= 0)
                return;

            lock (_logSync)
            {
                _logCap = logCap;
                TrimLogBuffer();
            }
        }

        public void ClearLogs()
        {
            lock (_logSync)
            {
                _logEntries.Clear();
            }
        }

        private void TrimLogBuffer()
        {
            if (_logEntries.Count <= _logCap)
                return;

            var removeCount = _logEntries.Count - _logCap;
            _logEntries.RemoveRange(0, removeCount);
        }
    }
}

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Threading.Tasks;

namespace StreamSuites.DesktopAdmin.Runtime.Processes
{
    public sealed class RuntimeProcessManager
    {
        private readonly Dictionary<string, RuntimeProcessInstance> _instances
            = new Dictionary<string, RuntimeProcessInstance>(StringComparer.OrdinalIgnoreCase);
        private readonly object _sync = new object();
        private readonly int _defaultLogCap;

        public RuntimeProcessManager(int defaultLogCap)
        {
            _defaultLogCap = defaultLogCap;
        }

        public event Action<string, RuntimeProcessStatus>? StatusChanged;
        public event Action<string, RuntimeProcessLogEntry>? LogLine;

        public IReadOnlyCollection<RuntimeProcessInstance> Instances
        {
            get
            {
                lock (_sync)
                {
                    return _instances.Values.ToList();
                }
            }
        }

        public void LoadDefinitions(IEnumerable<RuntimeProcessDefinition> definitions)
        {
            if (definitions == null)
                return;

            lock (_sync)
            {
                _instances.Clear();
                foreach (var definition in definitions)
                {
                    if (definition == null || string.IsNullOrWhiteSpace(definition.Id))
                        continue;

                    _instances[definition.Id] = new RuntimeProcessInstance(definition, _defaultLogCap)
                    {
                        Status = RuntimeProcessStatus.Stopped
                    };
                }
            }
        }

        public RuntimeProcessInstance? GetInstance(string id)
        {
            if (string.IsNullOrWhiteSpace(id))
                return null;

            lock (_sync)
            {
                return _instances.TryGetValue(id, out var instance) ? instance : null;
            }
        }

        public Task<bool> StartAsync(string id)
        {
            var instance = GetInstance(id);
            if (instance == null)
                return Task.FromResult(false);

            if (instance.Process != null && !instance.Process.HasExited)
                return Task.FromResult(false);

            SetStatus(instance, RuntimeProcessStatus.Starting, null);

            try
            {
                var definition = instance.Definition;
                var startInfo = BuildStartInfo(definition);
                var process = new Process
                {
                    StartInfo = startInfo,
                    EnableRaisingEvents = true
                };

                process.OutputDataReceived += (_, args) =>
                    CaptureOutput(instance, "stdout", args.Data);
                process.ErrorDataReceived += (_, args) =>
                    CaptureOutput(instance, "stderr", args.Data);
                process.Exited += (_, __) =>
                    HandleProcessExited(instance);

                if (!process.Start())
                {
                    SetStatus(instance, RuntimeProcessStatus.Error, "Failed to start process.");
                    return Task.FromResult(false);
                }

                instance.Process = process;
                instance.StartTimeUtc = DateTime.UtcNow;
                instance.LastExitCode = null;
                instance.LastError = null;

                instance.Job = JobObject.CreateAndAssign(process);

                process.BeginOutputReadLine();
                process.BeginErrorReadLine();

                SetStatus(instance, RuntimeProcessStatus.Running, null);
                return Task.FromResult(true);
            }
            catch (Exception ex)
            {
                instance.LastError = ex.Message;
                SetStatus(instance, RuntimeProcessStatus.Error, ex.Message);
                return Task.FromResult(false);
            }
        }

        public async Task<bool> StopAsync(string id)
        {
            var instance = GetInstance(id);
            if (instance == null)
                return false;

            var process = instance.Process;
            if (process == null || process.HasExited)
            {
                SetStatus(instance, RuntimeProcessStatus.Stopped, null);
                return false;
            }

            try
            {
                var exited = await TryCloseMainWindowAsync(process).ConfigureAwait(false);
                if (!exited)
                {
                    exited = await TryTerminateJobAsync(instance).ConfigureAwait(false);
                }

                if (!exited)
                {
                    exited = await TryTaskKillAsync(process.Id).ConfigureAwait(false);
                }

                if (!exited)
                {
                    try
                    {
                        process.Kill(entireProcessTree: true);
                        process.WaitForExit(2000);
                        exited = process.HasExited;
                    }
                    catch
                    {
                        exited = process.HasExited;
                    }
                }

                if (exited)
                {
                    SetStatus(instance, RuntimeProcessStatus.Stopped, null);
                }
            }
            catch (Exception ex)
            {
                instance.LastError = ex.Message;
                SetStatus(instance, RuntimeProcessStatus.Error, ex.Message);
            }

            return true;
        }

        public async Task<bool> RestartAsync(string id)
        {
            var instance = GetInstance(id);
            if (instance == null)
                return false;

            await StopAsync(id).ConfigureAwait(false);
            return await StartAsync(id).ConfigureAwait(false);
        }

        public async Task StopAllAsync()
        {
            var instances = Instances.ToList();
            foreach (var instance in instances)
            {
                await StopAsync(instance.Definition.Id).ConfigureAwait(false);
            }
        }

        public void UpdateLogCap(string id, int logCap)
        {
            var instance = GetInstance(id);
            instance?.SetLogCap(logCap);
        }

        public void ClearLogs(string id)
        {
            var instance = GetInstance(id);
            instance?.ClearLogs();
        }

        public IReadOnlyList<RuntimeProcessLogEntry> GetLogSnapshot(string id)
        {
            var instance = GetInstance(id);
            return instance?.GetLogSnapshot() ?? Array.Empty<RuntimeProcessLogEntry>();
        }

        private static ProcessStartInfo BuildStartInfo(RuntimeProcessDefinition definition)
        {
            var workingDir = definition.WorkingDirectory;
            if (!string.IsNullOrWhiteSpace(workingDir) && !Path.IsPathRooted(workingDir))
            {
                workingDir = Path.GetFullPath(
                    Path.Combine(AppDomain.CurrentDomain.BaseDirectory, workingDir));
            }

            var startInfo = new ProcessStartInfo
            {
                FileName = definition.Executable,
                WorkingDirectory = string.IsNullOrWhiteSpace(workingDir)
                    ? AppDomain.CurrentDomain.BaseDirectory
                    : workingDir,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true
            };

            if (definition.Args != null)
            {
                if (definition.Args.HasList)
                {
                    foreach (var arg in definition.Args.Arguments)
                    {
                        startInfo.ArgumentList.Add(arg);
                    }
                }
                else if (!string.IsNullOrWhiteSpace(definition.Args.Raw))
                {
                    startInfo.Arguments = definition.Args.Raw;
                }
            }

            if (definition.EnvironmentVariables != null)
            {
                foreach (var entry in definition.EnvironmentVariables)
                {
                    startInfo.Environment[entry.Key] = entry.Value;
                }
            }

            return startInfo;
        }

        private void CaptureOutput(RuntimeProcessInstance instance, string stream, string? data)
        {
            if (string.IsNullOrEmpty(data))
                return;

            var entry = new RuntimeProcessLogEntry(DateTime.UtcNow, stream, data);
            instance.AddLogEntry(entry);
            LogLine?.Invoke(instance.Definition.Id, entry);
        }

        private void HandleProcessExited(RuntimeProcessInstance instance)
        {
            var process = instance.Process;
            if (process == null)
                return;

            try
            {
                instance.LastExitCode = process.ExitCode;
                instance.Job?.Dispose();
                instance.Job = null;
            }
            catch
            {
                // ignore
            }

            if (instance.Status != RuntimeProcessStatus.Stopped)
            {
                SetStatus(instance, RuntimeProcessStatus.Exited, null);
            }
        }

        private void SetStatus(RuntimeProcessInstance instance, RuntimeProcessStatus status, string? error)
        {
            instance.Status = status;
            if (!string.IsNullOrWhiteSpace(error))
            {
                instance.LastError = error;
            }

            StatusChanged?.Invoke(instance.Definition.Id, status);
        }

        private static Task<bool> TryCloseMainWindowAsync(Process process)
        {
            return Task.Run(() =>
            {
                try
                {
                    if (process.HasExited)
                        return true;

                    if (process.MainWindowHandle != IntPtr.Zero)
                    {
                        process.CloseMainWindow();
                        if (process.WaitForExit(1500))
                            return true;
                    }
                }
                catch
                {
                    // ignore
                }

                return process.HasExited;
            });
        }

        private static Task<bool> TryTerminateJobAsync(RuntimeProcessInstance instance)
        {
            return Task.Run(() =>
            {
                try
                {
                    if (instance.Job != null)
                    {
                        instance.Job.Terminate();
                        instance.Process?.WaitForExit(2000);
                        return instance.Process?.HasExited ?? true;
                    }
                }
                catch
                {
                    // ignore
                }

                return instance.Process?.HasExited ?? true;
            });
        }

        private static Task<bool> TryTaskKillAsync(int pid)
        {
            return Task.Run(() =>
            {
                try
                {
                    var startInfo = new ProcessStartInfo
                    {
                        FileName = "taskkill",
                        Arguments = $"/PID {pid} /T /F",
                        UseShellExecute = false,
                        CreateNoWindow = true
                    };

                    using var taskKill = Process.Start(startInfo);
                    taskKill?.WaitForExit(2000);
                    return true;
                }
                catch
                {
                    return false;
                }
            });
        }

        private sealed class JobObject : IDisposable
        {
            private IntPtr _handle;

            private JobObject(IntPtr handle)
            {
                _handle = handle;
            }

            public static JobObject? CreateAndAssign(Process process)
            {
                try
                {
                    var handle = CreateJobObject(IntPtr.Zero, null);
                    if (handle == IntPtr.Zero)
                        return null;

                    var info = new JOBOBJECT_EXTENDED_LIMIT_INFORMATION
                    {
                        BasicLimitInformation = new JOBOBJECT_BASIC_LIMIT_INFORMATION
                        {
                            LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
                        }
                    };

                    var length = Marshal.SizeOf(typeof(JOBOBJECT_EXTENDED_LIMIT_INFORMATION));
                    var infoPtr = Marshal.AllocHGlobal(length);
                    try
                    {
                        Marshal.StructureToPtr(info, infoPtr, false);
                        if (!SetInformationJobObject(handle, JobObjectInfoType.ExtendedLimitInformation, infoPtr, (uint)length))
                        {
                            CloseHandle(handle);
                            return null;
                        }
                    }
                    finally
                    {
                        Marshal.FreeHGlobal(infoPtr);
                    }

                    if (!AssignProcessToJobObject(handle, process.Handle))
                    {
                        CloseHandle(handle);
                        return null;
                    }

                    return new JobObject(handle);
                }
                catch
                {
                    return null;
                }
            }

            public void Terminate()
            {
                if (_handle == IntPtr.Zero)
                    return;

                TerminateJobObject(_handle, 1);
            }

            public void Dispose()
            {
                if (_handle == IntPtr.Zero)
                    return;

                CloseHandle(_handle);
                _handle = IntPtr.Zero;
            }

            private const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;

            [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
            private static extern IntPtr CreateJobObject(IntPtr lpJobAttributes, string? lpName);

            [DllImport("kernel32.dll")]
            private static extern bool SetInformationJobObject(
                IntPtr hJob,
                JobObjectInfoType infoType,
                IntPtr lpJobObjectInfo,
                uint cbJobObjectInfoLength);

            [DllImport("kernel32.dll", SetLastError = true)]
            private static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

            [DllImport("kernel32.dll")]
            private static extern bool TerminateJobObject(IntPtr hJob, uint exitCode);

            [DllImport("kernel32.dll", SetLastError = true)]
            private static extern bool CloseHandle(IntPtr hObject);

            private enum JobObjectInfoType
            {
                ExtendedLimitInformation = 9
            }

            [StructLayout(LayoutKind.Sequential)]
            private struct IO_COUNTERS
            {
                public ulong ReadOperationCount;
                public ulong WriteOperationCount;
                public ulong OtherOperationCount;
                public ulong ReadTransferCount;
                public ulong WriteTransferCount;
                public ulong OtherTransferCount;
            }

            [StructLayout(LayoutKind.Sequential)]
            private struct JOBOBJECT_BASIC_LIMIT_INFORMATION
            {
                public long PerProcessUserTimeLimit;
                public long PerJobUserTimeLimit;
                public uint LimitFlags;
                public UIntPtr MinimumWorkingSetSize;
                public UIntPtr MaximumWorkingSetSize;
                public uint ActiveProcessLimit;
                public long Affinity;
                public uint PriorityClass;
                public uint SchedulingClass;
            }

            [StructLayout(LayoutKind.Sequential)]
            private struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
            {
                public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
                public IO_COUNTERS IoInfo;
                public UIntPtr ProcessMemoryLimit;
                public UIntPtr JobMemoryLimit;
                public UIntPtr PeakProcessMemoryUsed;
                public UIntPtr PeakJobMemoryUsed;
            }
        }
    }
}

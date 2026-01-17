using System;
using System.Diagnostics;

namespace StreamSuites.DesktopAdmin.Runtime.Services
{
    public abstract class RuntimeServiceController : IDisposable
    {
        private readonly object _syncRoot = new object();
        private Process _process;
        private bool _disposed;

        public string Name { get; }
        public string Command { get; }
        public string Arguments { get; }

        public bool IsRunning
        {
            get
            {
                lock (_syncRoot)
                {
                    return _process != null && !_process.HasExited;
                }
            }
        }

        public event Action<string> StdOutReceived;
        public event Action<string> StdErrReceived;
        public event Action<int> ProcessExited;

        protected RuntimeServiceController(string name, string command, string arguments)
        {
            Name = name ?? throw new ArgumentNullException(nameof(name));
            Command = command ?? throw new ArgumentNullException(nameof(command));
            Arguments = arguments ?? string.Empty;
        }

        public bool Start()
        {
            lock (_syncRoot)
            {
                ThrowIfDisposed();

                if (_process != null && !_process.HasExited)
                {
                    return false;
                }

                CleanupProcess();

                _process = BuildProcess();
                _process.Start();
                _process.BeginOutputReadLine();
                _process.BeginErrorReadLine();
                return true;
            }
        }

        public bool Stop(TimeSpan? timeout = null)
        {
            Process process;

            lock (_syncRoot)
            {
                ThrowIfDisposed();

                if (_process == null)
                {
                    return false;
                }

                process = _process;
            }

            if (process.HasExited)
            {
                CleanupProcess();
                return false;
            }

            var waitTimeout = timeout ?? TimeSpan.FromSeconds(5);
            var exited = false;

            if (process.MainWindowHandle != IntPtr.Zero)
            {
                process.CloseMainWindow();
                exited = process.WaitForExit((int)waitTimeout.TotalMilliseconds);
            }

            if (!exited)
            {
                process.Kill(entireProcessTree: true);
                process.WaitForExit((int)waitTimeout.TotalMilliseconds);
            }

            CleanupProcess();
            return true;
        }

        public bool Restart(TimeSpan? timeout = null)
        {
            Stop(timeout);
            return Start();
        }

        public void Dispose()
        {
            lock (_syncRoot)
            {
                if (_disposed)
                {
                    return;
                }

                _disposed = true;
            }

            Stop();
        }

        private Process BuildProcess()
        {
            var startInfo = new ProcessStartInfo
            {
                FileName = Command,
                Arguments = Arguments,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true
            };

            var process = new Process
            {
                StartInfo = startInfo,
                EnableRaisingEvents = true
            };

            process.OutputDataReceived += OnOutputDataReceived;
            process.ErrorDataReceived += OnErrorDataReceived;
            process.Exited += OnProcessExited;

            return process;
        }

        private void OnOutputDataReceived(object sender, DataReceivedEventArgs e)
        {
            if (e.Data == null)
            {
                return;
            }

            StdOutReceived?.Invoke(e.Data);
        }

        private void OnErrorDataReceived(object sender, DataReceivedEventArgs e)
        {
            if (e.Data == null)
            {
                return;
            }

            StdErrReceived?.Invoke(e.Data);
        }

        private void OnProcessExited(object sender, EventArgs e)
        {
            int exitCode;

            lock (_syncRoot)
            {
                exitCode = _process != null ? _process.ExitCode : -1;
            }

            ProcessExited?.Invoke(exitCode);
        }

        private void CleanupProcess()
        {
            if (_process == null)
            {
                return;
            }

            _process.OutputDataReceived -= OnOutputDataReceived;
            _process.ErrorDataReceived -= OnErrorDataReceived;
            _process.Exited -= OnProcessExited;
            _process.Dispose();
            _process = null;
        }

        private void ThrowIfDisposed()
        {
            if (_disposed)
            {
                throw new ObjectDisposedException(GetType().Name);
            }
        }
    }
}

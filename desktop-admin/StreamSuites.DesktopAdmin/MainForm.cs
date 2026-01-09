using StreamSuites.DesktopAdmin.Core;
using StreamSuites.DesktopAdmin.RuntimeBridge;
using StreamSuites.DesktopAdmin.Models;
using System.Collections.Generic;
using System;
using System.ComponentModel;
using System.Configuration;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace StreamSuites.DesktopAdmin
{
    public partial class MainForm : Form
    {
        private readonly AppState _appState;
        private readonly RuntimeConnector _runtimeConnector;
        private readonly AdminCommandDispatcher _commandDispatcher;
        private readonly JsonExportReader _exportReader;

        private readonly PathConfigService _pathConfigService;
        private PathConfiguration _pathConfiguration;
        private SnapshotPathStatus _currentPathStatus;

        private readonly System.Windows.Forms.Timer _refreshTimer;
        private bool _refreshInProgress;

        private readonly BindingSource _platformBindingSource;
        private readonly BindingSource _jobsBindingSource;
        private readonly BindingSource _telemetryEventsBindingSource;
        private readonly BindingSource _telemetryErrorsBindingSource;
        private readonly BindingSource _telemetryRatesBindingSource;
        private readonly ToolTip _snapshotToolTip;

        // STEP K - last refresh live counter
        private readonly System.Windows.Forms.Timer _sinceRefreshTimer;
        private DateTime? _lastSuccessfulRefreshUtc;

        // Inspector UI (STEP G)
        private Panel _inspectorPanel;
        private Label _inspectorTitle;
        private Label _inspectorBody;

        private const int SnapshotStaleThresholdSeconds = 20;

        // Tray menu (STEP L)
        private ContextMenuStrip _trayMenu;
        private ToolStripMenuItem _trayStatusItem;

        private ToolStripStatusLabel _statusHealthDot;

        private MenuStrip _menuMain;

        private DataGridView _jobsGrid;
        private Label _jobsSummary;

        private DataGridView _telemetryEventsGrid;
        private DataGridView _telemetryErrorsGrid;
        private DataGridView _telemetryRatesGrid;
        private Label _telemetrySummary;

        public MainForm()
        {
            InitializeComponent();

            // Reduce first-paint artefacts / flicker
            SetStyle(
                ControlStyles.AllPaintingInWmPaint |
                ControlStyles.OptimizedDoubleBuffer,
                true
            );
            UpdateStyles();

            StartPosition = FormStartPosition.CenterScreen;
            FormBorderStyle = FormBorderStyle.Sizable;
            MaximizeBox = true;
            MinimizeBox = true;
            MinimumSize = new Size(900, 650);
            AutoScaleMode = AutoScaleMode.Dpi;
            Text = "StreamSuites Administrator Dashboard";

            try
            {
                Icon = new Icon(
                    Path.Combine(
                        AppDomain.CurrentDomain.BaseDirectory,
                        "assets",
                        "streamsuites.ico"
                    )
                );
            }
            catch { }

            // IMPORTANT: re-apply tray icon AFTER we set the form icon
            InitializeTrayIcon();

            _snapshotToolTip = new ToolTip
            {
                AutoPopDelay = 15000,
                InitialDelay = 300,
                ReshowDelay = 100,
                ShowAlways = true
            };

            _statusHealthDot = new ToolStripStatusLabel
            {
                Text = "●",
                ForeColor = Color.Gray
            };
            statusBar.Items.Insert(0, _statusHealthDot);

            var modeContext = new ModeContext("Dashboard");
            _appState = new AppState(modeContext);

            var fileAccessor = new DefaultFileAccessor();
            var snapshotReader = new FileSnapshotReader(fileAccessor);
            _runtimeConnector = new RuntimeConnector(snapshotReader, _appState);
            _commandDispatcher = new AdminCommandDispatcher(_appState);
            _exportReader = new JsonExportReader(fileAccessor);

            _pathConfigService = new PathConfigService();
            _pathConfiguration = _pathConfigService.Load();
            _currentPathStatus = new SnapshotPathStatus();

            _platformBindingSource = new BindingSource();
            _jobsBindingSource = new BindingSource();
            _telemetryEventsBindingSource = new BindingSource();
            _telemetryErrorsBindingSource = new BindingSource();
            _telemetryRatesBindingSource = new BindingSource();
            gridPlatforms.DataSource = _platformBindingSource;

            InitializePlatformGrid();
            InitializeInspectorPanel();
            InitializeMenu();
            InitializeJobsTab();
            InitializeTelemetryTab();
            InitializePlatformTabs();
            UpdatePlatformActionButtons(null);

            txtSnapshotPath.Text = _pathConfiguration.RuntimeSnapshotRoot;
            txtSnapshotPath.ReadOnly = false;

            btnBrowseSnapshotPath.Click += BtnBrowseSnapshotPath_Click;
            btnSaveSnapshotPath.Click += BtnSaveSnapshotPath_Click;
            txtSnapshotPath.TextChanged += (_, __) => RefreshSnapshotPathStatus();

            gridPlatforms.SelectionChanged += GridPlatforms_SelectionChanged;
            tabMain.SelectedIndexChanged += TabMain_SelectedIndexChanged;
            btnRefresh.Click += async (_, __) => await RefreshSnapshotAsync();

            _refreshTimer = new System.Windows.Forms.Timer
            {
                Interval = GetRefreshIntervalMs()
            };
            _refreshTimer.Tick += async (_, __) =>
                await RefreshSnapshotAsync();

            _sinceRefreshTimer = new System.Windows.Forms.Timer
            {
                Interval = 1000
            };
            _sinceRefreshTimer.Tick += (_, __) =>
                UpdateLastRefreshCounter();

            RefreshSnapshotPathStatus();

            Shown += async (_, __) =>
            {
                await RefreshSnapshotAsync();
                _refreshTimer.Start();
                _sinceRefreshTimer.Start();
            };
        }

        private void InitializeMenu()
        {
            _menuMain = new MenuStrip
            {
                Dock = DockStyle.Top
            };

            var menuFile = new ToolStripMenuItem("File");
            var itemOpenDashboard = new ToolStripMenuItem("Open Dashboard");
            itemOpenDashboard.Click += (_, __) => ShowDashboard();
            var itemExit = new ToolStripMenuItem("Exit");
            itemExit.Click += (_, __) => Close();
            menuFile.DropDownItems.Add(itemOpenDashboard);
            menuFile.DropDownItems.Add(new ToolStripSeparator());
            menuFile.DropDownItems.Add(itemExit);

            var menuOptions = new ToolStripMenuItem("Options");
            var itemStatus = new ToolStripMenuItem("Status (placeholder)")
            {
                Enabled = false
            };
            var itemPlatforms = new ToolStripMenuItem("Platforms");
            foreach (var platform in GetPlatformNames())
            {
                itemPlatforms.DropDownItems.Add(
                    new ToolStripMenuItem(platform) { Enabled = false });
            }

            var itemSettings = new ToolStripMenuItem("Settings (placeholder)");
            itemSettings.DropDownItems.Add(
                new ToolStripMenuItem("General (placeholder)") { Enabled = false });

            menuOptions.DropDownItems.Add(itemStatus);
            menuOptions.DropDownItems.Add(itemPlatforms);
            menuOptions.DropDownItems.Add(itemSettings);

            var menuHelp = new ToolStripMenuItem("Help");
            var itemAbout = new ToolStripMenuItem("About");
            itemAbout.Click += async (_, __) => await ShowAboutDialogAsync();
            menuHelp.DropDownItems.Add(itemAbout);

            _menuMain.Items.Add(menuFile);
            _menuMain.Items.Add(menuOptions);
            _menuMain.Items.Add(menuHelp);

            Controls.Add(_menuMain);
            MainMenuStrip = _menuMain;
            Controls.SetChildIndex(_menuMain, 0);
        }

        private void InitializeJobsTab()
        {
            tabJobs.Padding = new Padding(8);

            _jobsGrid = new DataGridView
            {
                Dock = DockStyle.Fill,
                ReadOnly = true,
                AllowUserToAddRows = false,
                AllowUserToDeleteRows = false,
                AllowUserToResizeRows = false,
                AllowUserToResizeColumns = true,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                RowHeadersVisible = false,
                AutoGenerateColumns = false,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill
            };

            _jobsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(JobStatus.Name),
                HeaderText = "Job",
                MinimumWidth = 160
            });

            _jobsGrid.Columns.Add(new DataGridViewCheckBoxColumn
            {
                DataPropertyName = nameof(JobStatus.Enabled),
                HeaderText = "Enabled",
                Width = 80
            });

            _jobsGrid.Columns.Add(new DataGridViewCheckBoxColumn
            {
                DataPropertyName = nameof(JobStatus.Applied),
                HeaderText = "Applied",
                Width = 80
            });

            _jobsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(JobStatus.Reason),
                HeaderText = "Reason",
                MinimumWidth = 220
            });

            _jobsGrid.DataSource = _jobsBindingSource;
            EnableDoubleBuffering(_jobsGrid);

            _jobsSummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Jobs: —"
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 2,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

            layout.Controls.Add(_jobsSummary, 0, 0);
            layout.Controls.Add(_jobsGrid, 0, 1);

            tabJobs.Controls.Clear();
            tabJobs.Controls.Add(layout);
        }

        private void InitializeTelemetryTab()
        {
            tabTelemetry.Padding = new Padding(8);

            _telemetryEventsGrid = BuildTelemetryGrid();
            _telemetryEventsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryEventItem.Timestamp),
                HeaderText = "Timestamp",
                MinimumWidth = 150
            });
            _telemetryEventsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryEventItem.Source),
                HeaderText = "Source",
                MinimumWidth = 120
            });
            _telemetryEventsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryEventItem.Severity),
                HeaderText = "Severity",
                MinimumWidth = 80
            });
            _telemetryEventsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryEventItem.Message),
                HeaderText = "Message",
                MinimumWidth = 240
            });
            _telemetryEventsGrid.DataSource = _telemetryEventsBindingSource;

            _telemetryErrorsGrid = BuildTelemetryGrid();
            _telemetryErrorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryErrorItem.Timestamp),
                HeaderText = "Timestamp",
                MinimumWidth = 150
            });
            _telemetryErrorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryErrorItem.Subsystem),
                HeaderText = "Subsystem",
                MinimumWidth = 120
            });
            _telemetryErrorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryErrorItem.Error_Type),
                HeaderText = "Type",
                MinimumWidth = 100
            });
            _telemetryErrorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryErrorItem.Source),
                HeaderText = "Source",
                MinimumWidth = 120
            });
            _telemetryErrorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryErrorItem.Message),
                HeaderText = "Message",
                MinimumWidth = 240
            });
            _telemetryErrorsGrid.DataSource = _telemetryErrorsBindingSource;

            _telemetryRatesGrid = BuildTelemetryGrid();
            _telemetryRatesGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Window),
                HeaderText = "Window",
                MinimumWidth = 80
            });
            _telemetryRatesGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Metric),
                HeaderText = "Metric",
                MinimumWidth = 100
            });
            _telemetryRatesGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Platform),
                HeaderText = "Platform",
                MinimumWidth = 120
            });
            _telemetryRatesGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Value),
                HeaderText = "Value",
                MinimumWidth = 80
            });
            _telemetryRatesGrid.DataSource = _telemetryRatesBindingSource;

            _telemetrySummary = new Label
            {
                AutoSize = true,
                Dock = DockStyle.Fill,
                Text = "Telemetry: —"
            };

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Top,
                ColumnCount = 1,
                RowCount = 4,
                AutoSize = true,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            layout.Controls.Add(_telemetrySummary, 0, 0);
            layout.Controls.Add(BuildTelemetryGroup("Events", _telemetryEventsGrid), 0, 1);
            layout.Controls.Add(BuildTelemetryGroup("Errors", _telemetryErrorsGrid), 0, 2);
            layout.Controls.Add(BuildTelemetryGroup("Rates", _telemetryRatesGrid), 0, 3);

            panel.Controls.Add(layout);

            tabTelemetry.Controls.Clear();
            tabTelemetry.Controls.Add(panel);
        }

        private DataGridView BuildTelemetryGrid()
        {
            var grid = new DataGridView
            {
                Dock = DockStyle.Fill,
                ReadOnly = true,
                AllowUserToAddRows = false,
                AllowUserToDeleteRows = false,
                AllowUserToResizeRows = false,
                AllowUserToResizeColumns = true,
                SelectionMode = DataGridViewSelectionMode.FullRowSelect,
                RowHeadersVisible = false,
                AutoGenerateColumns = false,
                AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill,
                Height = 180
            };

            EnableDoubleBuffering(grid);
            return grid;
        }

        private static GroupBox BuildTelemetryGroup(string title, Control content)
        {
            var group = new GroupBox
            {
                Text = title,
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            content.Dock = DockStyle.Fill;
            group.Controls.Add(content);
            return group;
        }

        private void InitializePlatformTabs()
        {
            foreach (var platform in GetPlatformNames())
            {
                if (tabMain.TabPages.Cast<TabPage>()
                    .Any(tab => string.Equals(tab.Text, platform, StringComparison.OrdinalIgnoreCase)))
                {
                    continue;
                }

                var tab = new TabPage
                {
                    Text = platform,
                    Padding = new Padding(12)
                };

                var label = new Label
                {
                    AutoSize = true,
                    Text = $"{platform} configuration will appear here."
                };

                tab.Controls.Add(label);
                tabMain.TabPages.Add(tab);
            }
        }

        private static string[] GetPlatformNames()
        {
            return new[]
            {
                "Discord",
                "Kick",
                "Pilled",
                "Rumble",
                "Twitch",
                "Twitter",
                "YouTube"
            };
        }

        private void ShowDashboard()
        {
            Show();
            WindowState = FormWindowState.Normal;
            Activate();
            ForceControlRefresh(tabMain);
        }

        private async Task ShowAboutDialogAsync()
        {
            var aboutPath = ResolveExportPath("about.admin.json");
            if (string.IsNullOrWhiteSpace(aboutPath))
            {
                MessageBox.Show(
                    this,
                    "Unable to resolve about metadata. Check snapshot path configuration.",
                    "About",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                return;
            }

            var about = await _exportReader
                .TryReadAsync<AboutExport>(aboutPath);

            if (about == null)
            {
                MessageBox.Show(
                    this,
                    "About metadata could not be loaded from exports.",
                    "About",
                    MessageBoxButtons.OK,
                    MessageBoxIcon.Warning);
                return;
            }

            var appName = BuildAboutApplicationName(about);
            using var dialog = new AboutDialog(appName, about);
            dialog.ShowDialog(this);
        }

        private static string BuildAboutApplicationName(AboutExport about)
        {
            if (string.Equals(about.Scope, "admin", StringComparison.OrdinalIgnoreCase))
            {
                return "StreamSuites Administrator Dashboard";
            }

            return "StreamSuites";
        }

        private void TabMain_SelectedIndexChanged(object? sender, EventArgs e)
        {
            ForceControlRefresh(tabMain.SelectedTab);
        }

        private void ForceControlRefresh(Control? control)
        {
            if (control == null)
                return;

            control.SuspendLayout();
            control.ResumeLayout(true);
            control.Invalidate(true);
            control.Update();
        }

        // -----------------------------------------------------------------
        // Snapshot refresh
        // -----------------------------------------------------------------

        private async Task RefreshSnapshotAsync()
        {
            if (_refreshInProgress)
                return;

            var pathStatus = RefreshSnapshotPathStatus();
            if (!pathStatus.IsValid)
            {
                HandleInvalidSnapshotPath(pathStatus);
                return;
            }

            var snapshotPath = pathStatus.SnapshotFilePath;
            if (string.IsNullOrWhiteSpace(snapshotPath))
            {
                HandleInvalidSnapshotPath(pathStatus);
                return;
            }

            try
            {
                _refreshInProgress = true;

                var snapshot = await _runtimeConnector
                    .RefreshSnapshotAsync(snapshotPath)
                    .ConfigureAwait(true);

                if (snapshot?.Runtime == null)
                {
                    UpdateSnapshotStatus("Snapshot: invalid");
                    ApplySnapshotHealthStyle(SnapshotHealthState.Invalid);
                    UpdateTrayIconHealth(SnapshotHealthState.Invalid);
                    UpdateSnapshotHealthIndicators(SnapshotHealthState.Invalid);
                    SetSnapshotTooltip(null, "Snapshot missing runtime block.");
                    UpdatePlatformCount("Platforms: invalid");
                    UpdateStatusRuntime("Runtime: invalid snapshot");
                    _platformBindingSource.DataSource = null;
                    ClearJobData();
                    ClearTelemetryData();
                    UpdatePlatformActionButtons(null);
                    return;
                }

                var health =
                    snapshot.HealthState(SnapshotStaleThresholdSeconds);
                var label =
                    health.ToString().ToUpperInvariant();

                UpdateSnapshotStatus(
                    $"Snapshot: {snapshot.Runtime.Version} @ {snapshot.Generated_At} [{label}]"
                );

                ApplySnapshotHealthStyle(health);
                UpdateTrayIconHealth(health);
                UpdateSnapshotHealthIndicators(health);
                SetSnapshotTooltip(snapshot, null);
                UpdateStatusRuntime("Runtime: snapshot bound");

                UpdatePlatformCount(
                    $"Platforms: {snapshot.Platforms?.Count ?? 0}"
                );
                _platformBindingSource.DataSource =
                    snapshot.Platforms;
                SelectFirstPlatformRow();
                UpdateJobData(snapshot);
                await RefreshTelemetryAsync(_currentPathStatus.SnapshotRoot)
                    .ConfigureAwait(true);

                if (!string.IsNullOrWhiteSpace(_currentSortProperty))
                    ApplyGridSort(_currentSortProperty, _currentSortDirection);

                _lastSuccessfulRefreshUtc = DateTime.UtcNow;
                UpdateLastRefreshCounter();
                RefreshRuntimePanels();
            }
            catch
            {
                UpdateSnapshotStatus("Snapshot: error reading");
                ApplySnapshotHealthStyle(SnapshotHealthState.Invalid);
                UpdateTrayIconHealth(SnapshotHealthState.Invalid);
                UpdateSnapshotHealthIndicators(SnapshotHealthState.Invalid);
                SetSnapshotTooltip(null, "Exception reading snapshot.");
                UpdatePlatformCount("Platforms: error");
                UpdateStatusRuntime("Runtime: disconnected");
                ClearJobData();
                ClearTelemetryData();
                UpdatePlatformActionButtons(null);
            }
            finally
            {
                _refreshInProgress = false;
            }
        }

        private void HandleInvalidSnapshotPath(SnapshotPathStatus pathStatus)
        {
            var label = string.IsNullOrWhiteSpace(pathStatus?.Message)
                ? "Snapshot: path not configured"
                : $"Snapshot: {pathStatus.Message}";

            UpdateSnapshotStatus(label);
            ApplySnapshotHealthStyle(SnapshotHealthState.Invalid);
            UpdateTrayIconHealth(SnapshotHealthState.Invalid);
            UpdateSnapshotHealthIndicators(SnapshotHealthState.Invalid);
            SetSnapshotTooltip(null, pathStatus?.Message);
            UpdatePlatformCount("Platforms: unknown");
            _platformBindingSource.DataSource = null;
            UpdateStatusRuntime("Runtime: disconnected");
            _lastSuccessfulRefreshUtc = null;
            lblLastRefresh.Text = "Last refresh: —";
            ClearJobData();
            ClearTelemetryData();
            UpdatePlatformActionButtons(null);
        }

        private SnapshotPathStatus RefreshSnapshotPathStatus()
        {
            _currentPathStatus = _pathConfigService
                .ValidateSnapshotRoot(txtSnapshotPath.Text);

            UpdatePathTabStatus(_currentPathStatus);
            return _currentPathStatus;
        }

        private void BtnBrowseSnapshotPath_Click(object? sender, EventArgs e)
        {
            using var dialog = new FolderBrowserDialog
            {
                Description = "Select the runtime snapshot export directory",
                ShowNewFolderButton = false
            };

            if (!string.IsNullOrWhiteSpace(txtSnapshotPath.Text) &&
                Directory.Exists(txtSnapshotPath.Text))
            {
                dialog.SelectedPath = txtSnapshotPath.Text;
            }

            if (dialog.ShowDialog() == DialogResult.OK)
            {
                txtSnapshotPath.Text = dialog.SelectedPath;
            }
        }

        private async void BtnSaveSnapshotPath_Click(object? sender, EventArgs e)
        {
            _pathConfigService.SaveSnapshotRoot(txtSnapshotPath.Text);
            _pathConfiguration = _pathConfigService.Load();
            txtSnapshotPath.Text = _pathConfiguration.RuntimeSnapshotRoot;

            var status = RefreshSnapshotPathStatus();

            if (status.IsValid)
            {
                await RefreshSnapshotAsync();
            }
            else
            {
                HandleInvalidSnapshotPath(status);
            }
        }

        private void UpdatePathTabStatus(SnapshotPathStatus status)
        {
            if (status == null)
                return;

            var color = status.State switch
            {
                SnapshotPathState.Valid => Color.DarkGreen,
                SnapshotPathState.NotConfigured => Color.Gray,
                _ => Color.DarkRed
            };

            var prefix = status.State == SnapshotPathState.Valid ? "✔" : "✖";
            lblSnapshotPathStatus.ForeColor = color;
            lblSnapshotPathStatus.Text =
                $"Status: {prefix} {status.Message}";

            lblSnapshotDetected.Text = BuildSnapshotDetectionText(status);
        }

        private string BuildSnapshotDetectionText(SnapshotPathStatus status)
        {
            var details = new List<string>();

            if (!string.IsNullOrWhiteSpace(status.SnapshotRoot))
            {
                details.Add($"Root: {status.SnapshotRoot}");
            }

            if (!string.IsNullOrWhiteSpace(status.SnapshotFilePath))
            {
                var suffix = status.State switch
                {
                    SnapshotPathState.FileMissing => "missing",
                    SnapshotPathState.DirectoryMissing => "directory missing",
                    SnapshotPathState.InvalidPath => "invalid path",
                    _ when status.LastModifiedUtc != null =>
                        $"updated {FormatSnapshotAge(status.Age)}",
                    _ => "unreadable"
                };

                details.Add(
                    $"{status.SnapshotFileName}: {suffix}");
            }

            if (status.LastModifiedUtc != null)
            {
                details.Add(
                    $"Last modified (UTC): {status.LastModifiedUtc:yyyy-MM-dd HH:mm:ss}");
            }

            if (details.Count == 0)
                return string.Empty;

            return "Detected:\n- " + string.Join("\n- ", details);
        }

        private static string FormatSnapshotAge(TimeSpan? age)
        {
            if (age == null)
                return "unknown";

            var seconds = Math.Max(0, (int)Math.Round(age.Value.TotalSeconds));
            return seconds == 1 ? "1s ago" : $"{seconds}s ago";
        }

        // -----------------------------------------------------------------
        // STEP K - last refresh counter
        // -----------------------------------------------------------------

        private void UpdateLastRefreshCounter()
        {
            if (_lastSuccessfulRefreshUtc == null)
                return;

            var seconds =
                (int)(DateTime.UtcNow -
                _lastSuccessfulRefreshUtc.Value).TotalSeconds;

            var text = $"Last refresh: {seconds}s ago";

            if (InvokeRequired)
                Invoke(new Action(() =>
                    lblLastRefresh.Text = text));
            else
                lblLastRefresh.Text = text;
        }

        // -----------------------------------------------------------------
        // Jobs + telemetry
        // -----------------------------------------------------------------

        private void UpdateJobData(RuntimeSnapshot snapshot)
        {
            var jobs = snapshot.Jobs ?? new List<JobStatus>();
            _jobsBindingSource.DataSource = jobs.ToList();
            _jobsSummary.Text = $"Jobs: {jobs.Count}";
            ForceControlRefresh(tabJobs);
        }

        private void ClearJobData()
        {
            _jobsBindingSource.DataSource = null;
            if (_jobsSummary != null)
            {
                _jobsSummary.Text = "Jobs: —";
            }

            ForceControlRefresh(tabJobs);
        }

        private async Task RefreshTelemetryAsync(string? snapshotRoot)
        {
            if (string.IsNullOrWhiteSpace(snapshotRoot) ||
                !Directory.Exists(snapshotRoot))
            {
                ClearTelemetryData();
                return;
            }

            var telemetryRoot = Path.Combine(snapshotRoot, "telemetry");
            if (!Directory.Exists(telemetryRoot))
            {
                ClearTelemetryData();
                return;
            }

            var eventsPath = Path.Combine(telemetryRoot, "events.json");
            var errorsPath = Path.Combine(telemetryRoot, "errors.json");
            var ratesPath = Path.Combine(telemetryRoot, "rates.json");

            var eventsExport = await _exportReader
                .TryReadAsync<TelemetryEventsExport>(eventsPath)
                .ConfigureAwait(true);
            var errorsExport = await _exportReader
                .TryReadAsync<TelemetryErrorsExport>(errorsPath)
                .ConfigureAwait(true);
            var ratesExport = await _exportReader
                .TryReadAsync<TelemetryRatesExport>(ratesPath)
                .ConfigureAwait(true);

            _telemetryEventsBindingSource.DataSource =
                eventsExport?.Events?.ToList();
            _telemetryErrorsBindingSource.DataSource =
                errorsExport?.Errors?.ToList();
            _telemetryRatesBindingSource.DataSource =
                BuildRateRows(ratesExport);

            UpdateTelemetrySummary(eventsExport, errorsExport, ratesExport);
            ForceControlRefresh(tabTelemetry);
        }

        private void ClearTelemetryData()
        {
            _telemetryEventsBindingSource.DataSource = null;
            _telemetryErrorsBindingSource.DataSource = null;
            _telemetryRatesBindingSource.DataSource = null;

            if (_telemetrySummary != null)
            {
                _telemetrySummary.Text = "Telemetry: —";
            }

            ForceControlRefresh(tabTelemetry);
        }

        private void UpdateTelemetrySummary(
            TelemetryEventsExport? eventsExport,
            TelemetryErrorsExport? errorsExport,
            TelemetryRatesExport? ratesExport)
        {
            var eventsCount = eventsExport?.Events?.Count ?? 0;
            var errorsCount = errorsExport?.Errors?.Count ?? 0;
            var generated = eventsExport?.Generated_At
                ?? errorsExport?.Generated_At
                ?? ratesExport?.Generated_At
                ?? "—";

            if (_telemetrySummary != null)
            {
                _telemetrySummary.Text =
                    $"Telemetry: {eventsCount} events • {errorsCount} errors • Updated {generated}";
            }
        }

        private static List<TelemetryRateRow> BuildRateRows(
            TelemetryRatesExport? ratesExport)
        {
            var rows = new List<TelemetryRateRow>();
            if (ratesExport?.Windows == null)
                return rows;

            foreach (var window in ratesExport.Windows)
            {
                if (window?.Metrics == null)
                    continue;

                AddRateRows(rows, window.Window, "Messages", window.Metrics.Messages);
                AddRateRows(rows, window.Window, "Triggers", window.Metrics.Triggers);
                AddRateRows(rows, window.Window, "Actions", window.Metrics.Actions);
                AddRateRows(rows, window.Window, "Actions Failed", window.Metrics.Actions_Failed);
            }

            return rows;
        }

        private static void AddRateRows(
            List<TelemetryRateRow> rows,
            string window,
            string metric,
            Dictionary<string, int> values)
        {
            if (values == null)
                return;

            foreach (var entry in values.OrderBy(v => v.Key))
            {
                rows.Add(new TelemetryRateRow
                {
                    Window = window,
                    Metric = metric,
                    Platform = ToTitleCase(entry.Key),
                    Value = entry.Value
                });
            }
        }

        private void SelectFirstPlatformRow()
        {
            if (gridPlatforms.Rows.Count == 0)
                return;

            gridPlatforms.ClearSelection();
            gridPlatforms.CurrentCell = gridPlatforms.Rows[0].Cells[0];
            gridPlatforms.Rows[0].Selected = true;
        }

        private void RefreshRuntimePanels()
        {
            gridPlatforms.Refresh();
            panelRuntimeTable.Refresh();
            panelRuntimeRight.Refresh();
            splitRuntime.Refresh();
            tabRuntime.Refresh();
        }

        private string? ResolveExportPath(string fileName)
        {
            var root = _currentPathStatus?.SnapshotRoot;
            if (string.IsNullOrWhiteSpace(root))
                return null;

            var path = Path.Combine(root, fileName);
            return File.Exists(path) ? path : null;
        }

        // -----------------------------------------------------------------
        // STEP L - tray icon health mapping
        // -----------------------------------------------------------------

        private void InitializeTrayIcon()
        {
            if (trayIcon == null)
                return;

            try
            {
                trayIcon.Icon =
                    Icon ?? SystemIcons.Application;
            }
            catch
            {
                trayIcon.Icon =
                    SystemIcons.Application;
            }

            trayIcon.Visible = true;
            trayIcon.Text = "StreamSuites Administrator";

            _trayMenu = new ContextMenuStrip();

            var itemOpen =
                new ToolStripMenuItem("Open Dashboard");
            itemOpen.Click += (_, __) =>
            {
                ShowDashboard();
            };

            _trayStatusItem =
                new ToolStripMenuItem("🟡 Status: Unknown")
                {
                    Enabled = false
                };

            var itemSettings =
                new ToolStripMenuItem("Settings (placeholder)");
            var itemSettingsGeneral =
                new ToolStripMenuItem("General (placeholder)");

            itemSettings.DropDownItems.Add(
                itemSettingsGeneral
            );

            var itemPlatforms =
                new ToolStripMenuItem("Platforms");

            itemPlatforms.DropDownItems.Add(
                BuildPlatformTraySubmenu("Discord"));
            itemPlatforms.DropDownItems.Add(
                BuildPlatformTraySubmenu("Kick"));
            itemPlatforms.DropDownItems.Add(
                BuildPlatformTraySubmenu("Pilled"));
            itemPlatforms.DropDownItems.Add(
                BuildPlatformTraySubmenu("Rumble"));
            itemPlatforms.DropDownItems.Add(
                BuildPlatformTraySubmenu("Twitch"));
            itemPlatforms.DropDownItems.Add(
                BuildPlatformTraySubmenu("Twitter"));
            itemPlatforms.DropDownItems.Add(
                BuildPlatformTraySubmenu("YouTube"));

            var itemExit =
                new ToolStripMenuItem("Exit");
            itemExit.Click += (_, __) =>
            {
                trayIcon.Visible = false;
                Application.Exit();
            };

            _trayMenu.Items.Add(itemOpen);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(_trayStatusItem);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemPlatforms);
            _trayMenu.Items.Add(itemSettings);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemExit);

            trayIcon.ContextMenuStrip = _trayMenu;

            trayIcon.DoubleClick += (_, __) =>
            {
                ShowDashboard();
            };
        }

        private ToolStripMenuItem BuildPlatformTraySubmenu(
            string platformDisplayName)
        {
            var root =
                new ToolStripMenuItem(platformDisplayName);

            var itemToggle =
                new ToolStripMenuItem(
                    "Enable / Disable Client (placeholder)");
            var itemConfigure =
                new ToolStripMenuItem(
                    "Configure Client (placeholder)");

            root.DropDownItems.Add(itemToggle);
            root.DropDownItems.Add(itemConfigure);

            return root;
        }

        private void UpdateTrayIconHealth(
            SnapshotHealthState health)
        {
            if (trayIcon == null)
                return;

            var (dot, label) = GetHealthLabel(health);
            trayIcon.Text =
                $"{dot} StreamSuites - {label}";
            trayIcon.BalloonTipTitle =
                "StreamSuites Snapshot Status";
            if (_trayStatusItem != null)
            {
                _trayStatusItem.Text = $"{dot} Status: {label}";
            }

            switch (health)
            {
                case SnapshotHealthState.Healthy:
                    trayIcon.BalloonTipText =
                        "Snapshot healthy and up to date.";
                    trayIcon.BalloonTipIcon =
                        ToolTipIcon.Info;
                    break;

                case SnapshotHealthState.Stale:
                    trayIcon.BalloonTipText =
                        "Snapshot stale - refresh delayed.";
                    trayIcon.BalloonTipIcon =
                        ToolTipIcon.Warning;
                    break;

                default:
                    trayIcon.BalloonTipText =
                        "Snapshot invalid or unavailable.";
                    trayIcon.BalloonTipIcon =
                        ToolTipIcon.Error;
                    break;
            }
        }

        // -----------------------------------------------------------------
        // Grid
        // -----------------------------------------------------------------

        private void InitializePlatformGrid()
        {
            gridPlatforms.AutoGenerateColumns = false;
            gridPlatforms.Columns.Clear();

            gridPlatforms.AutoSizeColumnsMode =
                DataGridViewAutoSizeColumnsMode.None;
            gridPlatforms.AllowUserToOrderColumns = true;
            gridPlatforms.AllowUserToResizeColumns = true;
            gridPlatforms.ColumnHeadersHeightSizeMode =
                DataGridViewColumnHeadersHeightSizeMode.EnableResizing;

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Platform),
                    HeaderText = "Platform",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.None,
                    SortMode = DataGridViewColumnSortMode.Programmatic,
                    Resizable = DataGridViewTriState.True,
                    Width = 140,
                    MinimumWidth = 100
                });

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Display_State),
                    HeaderText = "State",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.None,
                    SortMode = DataGridViewColumnSortMode.Programmatic,
                    Resizable = DataGridViewTriState.True,
                    Width = 140,
                    MinimumWidth = 100
                });

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Telemetry_Display),
                    HeaderText = "Telemetry",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.None,
                    SortMode = DataGridViewColumnSortMode.Programmatic,
                    Resizable = DataGridViewTriState.True,
                    Width = 120,
                    MinimumWidth = 100
                });

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Capabilities),
                    HeaderText = "Capabilities",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.None,
                    MinimumWidth = 140,
                    SortMode = DataGridViewColumnSortMode.Programmatic,
                    Resizable = DataGridViewTriState.True,
                    Width = 220
                });

            EnableDoubleBuffering(gridPlatforms);
            EnableDoubleBuffering(splitRuntime);
            EnableDoubleBuffering(panelRuntimeTable);
            EnableDoubleBuffering(panelRuntimeRight);
            gridPlatforms.ScrollBars = ScrollBars.Both;

            gridPlatforms.ColumnHeaderMouseClick -= GridPlatforms_ColumnHeaderMouseClick;
            gridPlatforms.ColumnHeaderMouseClick += GridPlatforms_ColumnHeaderMouseClick;

            // REQUIRED: cell-level formatting (bold Platform column only)
            gridPlatforms.CellFormatting -= GridPlatforms_CellFormatting;
            gridPlatforms.CellFormatting += GridPlatforms_CellFormatting;
        }

        private void GridPlatforms_SelectionChanged(
            object? sender, EventArgs e)
        {
            if (gridPlatforms.CurrentRow?.DataBoundItem
                is not PlatformStatus p)
            {
                ClearInspector();
                UpdatePlatformActionButtons(null);
                RefreshRuntimePanels();
                return;
            }

            panelRuntimeRight.SuspendLayout();
            PopulateInspector(p);
            UpdatePlatformActionButtons(p);
            panelRuntimeRight.ResumeLayout(true);
            RefreshRuntimePanels();
        }

        // -----------------------------------------------------------------
        // Inspector (STEP G — FIXED PANEL, NON-COLLAPSIBLE)
        // -----------------------------------------------------------------

        private Button _btnToggleClient;
        private Button _btnConfigureClient;
        private Button _btnLaunchMain;
        private Button _btnLaunchClient;
        private Label _lblClientToggleNote;
        private PictureBox _inspectorIcon;

        private Image? _inspectorIconOwned; // we own/dispose this
        private readonly Dictionary<string, Image> _inspectorIconCache = new(StringComparer.OrdinalIgnoreCase);
        private Panel? _inspectorHeaderPanel;

        private string? _currentSortProperty;
        private ListSortDirection _currentSortDirection = ListSortDirection.Ascending;

        private void InitializeInspectorPanel()
        {
            // Inspector is ALWAYS present
            splitRuntime.Panel2Collapsed = false;

            panelRuntimeRight.SuspendLayout();
            panelRuntimeRight.Controls.Clear();

            // AutoScroll prevents bottom controls from being clipped at DPI/small heights
            panelRuntimeRight.AutoScroll = true;

            // Add a bit more bottom padding so controls never look "under" the footer line visually
            panelRuntimeRight.Padding = new Padding(8, 8, 8, 16);
            panelRuntimeRight.BackColor = SystemColors.ControlLight;

            // -------------------------------------------------------------
            // Header (icon + title)
            // -------------------------------------------------------------

            var headerPanel = new Panel
            {
                Dock = DockStyle.Top,
                Height = 36
            };

            _inspectorHeaderPanel = headerPanel;

            _inspectorIcon = new PictureBox
            {
                Width = 24,
                Height = 24,
                Margin = new Padding(0, 6, 6, 6),
                SizeMode = PictureBoxSizeMode.Zoom,
                Dock = DockStyle.Left
            };

            _inspectorTitle = new Label
            {
                Dock = DockStyle.Fill,
                Font = new Font(Font, FontStyle.Bold),
                TextAlign = ContentAlignment.MiddleLeft,
                Text = "Platform Inspector"
            };

            headerPanel.Controls.Add(_inspectorTitle);
            headerPanel.Controls.Add(_inspectorIcon);

            // -------------------------------------------------------------
            // Action buttons (bottom)
            // -------------------------------------------------------------

            var actionsPanel = new TableLayoutPanel
            {
                Dock = DockStyle.Bottom,
                Padding = new Padding(8),
                ColumnCount = 1,
                RowCount = 5,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink
            };

            actionsPanel.ColumnStyles.Add(
                new ColumnStyle(SizeType.Percent, 100f));

            _btnToggleClient = new Button
            {
                Text = "Enable / Disable Client",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Margin = new Padding(0, 0, 0, 8)
            };

            _btnConfigureClient = new Button
            {
                Text = "Configure Client",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Margin = new Padding(0, 0, 0, 8)
            };

            _btnLaunchMain = new Button
            {
                Text = "Launch Runtime",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Margin = new Padding(0, 0, 0, 8)
            };

            _btnLaunchClient = new Button
            {
                Text = "Launch Client",
                Dock = DockStyle.Fill,
                AutoSize = true,
                AutoSizeMode = AutoSizeMode.GrowAndShrink,
                Margin = new Padding(0, 0, 0, 8)
            };

            _lblClientToggleNote = new Label
            {
                Text = "Service toggles require a runtime restart to take effect.",
                Dock = DockStyle.Fill,
                AutoSize = true,
                Font = new Font(Font.FontFamily, 8f, FontStyle.Regular),
                ForeColor = SystemColors.GrayText,
                Margin = new Padding(0, 0, 0, 8)
            };

            actionsPanel.RowStyles.Add(new RowStyle());
            actionsPanel.Controls.Add(_lblClientToggleNote, 0, actionsPanel.RowStyles.Count - 1);

            actionsPanel.RowStyles.Add(new RowStyle());
            actionsPanel.Controls.Add(_btnToggleClient, 0, actionsPanel.RowStyles.Count - 1);

            actionsPanel.RowStyles.Add(new RowStyle());
            actionsPanel.Controls.Add(_btnConfigureClient, 0, actionsPanel.RowStyles.Count - 1);

            actionsPanel.RowStyles.Add(new RowStyle());
            actionsPanel.Controls.Add(_btnLaunchMain, 0, actionsPanel.RowStyles.Count - 1);

            actionsPanel.RowStyles.Add(new RowStyle());
            actionsPanel.Controls.Add(_btnLaunchClient, 0, actionsPanel.RowStyles.Count - 1);

            // -------------------------------------------------------------
            // Inspector body (fills between header + buttons)
            // -------------------------------------------------------------

            _inspectorBody = new Label
            {
                Dock = DockStyle.Fill,
                Padding = new Padding(12),
                Text = "No platform selected."
            };

            // -------------------------------------------------------------
            // Compose inspector
            // -------------------------------------------------------------

            panelRuntimeRight.Controls.Add(_inspectorBody);
            panelRuntimeRight.Controls.Add(actionsPanel);
            panelRuntimeRight.Controls.Add(headerPanel);

            panelRuntimeRight.ResumeLayout(true);
            panelRuntimeRight.Invalidate(true);

            _btnToggleClient.Click += async (_, __) => await ToggleClientAsync();
            _btnConfigureClient.Click += async (_, __) => await ConfigureClientAsync();
            _btnLaunchMain.Click += async (_, __) => await ToggleRuntimeAsync();
            _btnLaunchClient.Click += async (_, __) => await TogglePlatformClientAsync();

            // -------------------------------------------------------------
            // SAFE splitter setup AFTER layout is real
            // -------------------------------------------------------------

            Shown -= ApplyInspectorSplitterAfterShown;
            Shown += ApplyInspectorSplitterAfterShown;

            splitRuntime.SizeChanged -= ClampInspectorSplitter;
            splitRuntime.SizeChanged += ClampInspectorSplitter;
            splitRuntime.SplitterMoved -= ClampInspectorSplitter;
            splitRuntime.SplitterMoved += ClampInspectorSplitter;
        }

        private void ApplyInspectorSplitterAfterShown(object? sender, EventArgs e)
        {
            Shown -= ApplyInspectorSplitterAfterShown;

            // Only now set min sizes (avoids InvalidOperationException)
            splitRuntime.Panel2MinSize = 260;
            splitRuntime.Panel1MinSize = 420;

            ClampInspectorSplitter(null, EventArgs.Empty, true);
        }

        private void ClampInspectorSplitter(object? sender, EventArgs e)
        {
            ClampInspectorSplitter(sender, e, false);
        }

        private void ClampInspectorSplitter(object? sender, EventArgs e, bool applyDefault)
        {
            var total = splitRuntime.ClientSize.Width;
            if (total <= 0)
                return;

            const int desiredInspectorWidth = 320;
            const int maxInspectorWidth = 520;

            var min1 = splitRuntime.Panel1MinSize;
            var min2 = splitRuntime.Panel2MinSize;
            var max = total - min2;

            if (max < min1)
            {
                splitRuntime.SplitterDistance = Math.Max(0, max);
                return;
            }

            var inspectorWidth = total - splitRuntime.SplitterDistance;

            if (applyDefault)
            {
                var desired = total - desiredInspectorWidth;

                if (desired < min1)
                    desired = min1;
                if (desired > max)
                    desired = max;

                splitRuntime.SplitterDistance = desired;
                return;
            }

            if (inspectorWidth < min2)
            {
                splitRuntime.SplitterDistance = total - min2;
                return;
            }

            var maxAllowedInspector = Math.Min(maxInspectorWidth, total - min1);

            if (inspectorWidth > maxAllowedInspector)
            {
                splitRuntime.SplitterDistance = total - maxAllowedInspector;
            }
        }

        private void PopulateInspector(PlatformStatus p)
        {
            _inspectorTitle.Text = ToTitleCase(p.Platform);

            SetInspectorIconForPlatform(p.Platform);

            _inspectorBody.Text =
                $"State: {p.Display_State}\n" +
                $"Telemetry: {p.Telemetry_Display}\n" +
                $"Enabled: {p.Enabled}\n" +
                $"Paused: {p.Paused}\n" +
                $"Capabilities: {p.Capabilities}\n\n" +
                $"Last Heartbeat:\n{p.Last_Heartbeat ?? "—"}\n\n" +
                $"Error:\n{p.Error ?? "None"}";
        }

        private void SetInspectorIconForPlatform(string platform)
        {
            _inspectorIcon.Image = null;

            // Try multiple common locations/names
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            var assetsDir = Path.Combine(baseDir, "assets");

            var key = (platform ?? string.Empty).Trim();
            var lower = key.ToLowerInvariant();

            if (string.IsNullOrWhiteSpace(key))
            {
                _inspectorIconOwned = null;
                InvalidateInspectorHeader();
                return;
            }

            if (_inspectorIconCache.TryGetValue(key, out var cached))
            {
                _inspectorIconOwned = cached;
                _inspectorIcon.Image = _inspectorIconOwned;
                InvalidateInspectorHeader();
                return;
            }

            var candidates = new[]
            {
                Path.Combine(assetsDir, $"{lower}.png"),
                Path.Combine(assetsDir, $"{lower}.ico"),
                Path.Combine(baseDir, $"{lower}.png"),
                Path.Combine(baseDir, $"{lower}.ico"),
                Path.Combine(baseDir, "..", "..", "..", "assets", $"{lower}.png"),
                Path.Combine(baseDir, "..", "..", "..", "assets", $"{lower}.ico"),
            };

            foreach (var path in candidates)
            {
                try
                {
                    if (!File.Exists(path))
                        continue;

                    // Load into memory so the file isn't locked and image doesn't "blank"
                    using var fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.ReadWrite);
                    using var raw = Image.FromStream(fs);

                    _inspectorIconOwned = new Bitmap(raw);
                    _inspectorIconCache[key] = _inspectorIconOwned;
                    _inspectorIcon.Image = _inspectorIconOwned;
                    InvalidateInspectorHeader();
                    return;
                }
                catch
                {
                    // try next candidate
                }
            }

            if (_inspectorIcon.Image == null)
            {
                _inspectorIcon.Image = SystemIcons.Application.ToBitmap();
            }

            InvalidateInspectorHeader();
        }

        private void ClearInspector()
        {
            _inspectorTitle.Text = "Platform Inspector";

            _inspectorIconOwned = null;
            _inspectorIcon.Image = null;
            _inspectorBody.Text = "No platform selected.";

            _lblClientToggleNote.Visible = false;
            _btnLaunchMain.Visible = false;
            _btnLaunchClient.Visible = false;

            InvalidateInspectorHeader();
        }

        private PlatformStatus? GetSelectedPlatform()
        {
            return gridPlatforms.CurrentRow?.DataBoundItem as PlatformStatus;
        }

        private void UpdatePlatformActionButtons(PlatformStatus? platform)
        {
            var runtimeRunning = _appState.LastSnapshot?.IsTimestampValid == true;
            _btnLaunchMain.Text = runtimeRunning ? "Terminate Runtime" : "Launch Runtime";
            _btnLaunchMain.Enabled = _currentPathStatus?.IsValid == true;

            if (platform == null)
            {
                _btnToggleClient.Enabled = false;
                _btnConfigureClient.Enabled = false;
                _btnLaunchClient.Enabled = false;
                _lblClientToggleNote.Visible = false;
                _btnLaunchMain.Visible = true;
                _btnLaunchClient.Visible = false;
                return;
            }

            var clientRunning = IsClientRunning(platform);
            _btnToggleClient.Text = platform.Enabled ? "Disable Client" : "Enable Client";
            _btnLaunchClient.Text = clientRunning ? "Terminate Client" : "Launch Client";

            _lblClientToggleNote.Visible = true;
            _btnLaunchMain.Visible = true;
            _btnLaunchClient.Visible = true;

            var hasSnapshot = _appState.LastSnapshot?.Runtime != null;
            _btnToggleClient.Enabled = hasSnapshot;
            _btnConfigureClient.Enabled = hasSnapshot;
            _btnLaunchClient.Enabled = hasSnapshot;
        }

        private static bool IsClientRunning(PlatformStatus platform)
        {
            if (!platform.Enabled)
                return false;

            if (!string.IsNullOrWhiteSpace(platform.State) &&
                !string.Equals(platform.State, "disabled", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            if (!string.IsNullOrWhiteSpace(platform.Status) &&
                !string.Equals(platform.Status, "disabled", StringComparison.OrdinalIgnoreCase))
            {
                return true;
            }

            return false;
        }

        private async Task ToggleClientAsync()
        {
            var platform = GetSelectedPlatform();
            if (platform == null)
                return;

            var command = platform.Enabled ? "platform.disable" : "platform.enable";
            await _commandDispatcher.QueueCommandAsync(
                command,
                new Dictionary<string, string>
                {
                    ["platform"] = platform.Platform
                },
                CancellationToken.None);
        }

        private async Task ConfigureClientAsync()
        {
            var platform = GetSelectedPlatform();
            if (platform == null)
                return;

            await _commandDispatcher.QueueCommandAsync(
                "platform.configure",
                new Dictionary<string, string>
                {
                    ["platform"] = platform.Platform
                },
                CancellationToken.None);
        }

        private async Task ToggleRuntimeAsync()
        {
            var runtimeRunning = _appState.LastSnapshot?.IsTimestampValid == true;
            var command = runtimeRunning ? "runtime.terminate" : "runtime.launch";

            await _commandDispatcher.QueueCommandAsync(
                command,
                new Dictionary<string, string>(),
                CancellationToken.None);
        }

        private async Task TogglePlatformClientAsync()
        {
            var platform = GetSelectedPlatform();
            if (platform == null)
                return;

            var command = IsClientRunning(platform)
                ? "platform.client.terminate"
                : "platform.client.launch";

            await _commandDispatcher.QueueCommandAsync(
                command,
                new Dictionary<string, string>
                {
                    ["platform"] = platform.Platform
                },
                CancellationToken.None);
        }

        private void InvalidateInspectorHeader()
        {
            _inspectorIcon?.Invalidate();
            _inspectorHeaderPanel?.Invalidate(true);
            _inspectorHeaderPanel?.Update();
        }

        // -----------------------------------------------------------------
        // Visual semantics (GRID)
        // -----------------------------------------------------------------

        private void GridPlatforms_CellFormatting(
            object sender,
            DataGridViewCellFormattingEventArgs e)
        {
            if (e.RowIndex < 0)
                return;

            var row = gridPlatforms.Rows[e.RowIndex];
            if (row.DataBoundItem is not PlatformStatus platform)
                return;

            // Reset row defaults (NOT fonts)
            row.DefaultCellStyle.BackColor = SystemColors.Window;
            row.DefaultCellStyle.ForeColor = SystemColors.ControlText;

            // PLATFORM COLUMN — bold + proper noun (CELL-LEVEL ONLY)
            if (gridPlatforms.Columns[e.ColumnIndex].DataPropertyName ==
                nameof(PlatformStatus.Platform))
            {
                e.Value = ToTitleCase(platform.Platform);
                e.CellStyle.Font = new Font(gridPlatforms.Font, FontStyle.Bold);
                e.FormattingApplied = true;
            }
            else
            {
                // Ensure other columns remain normal weight
                e.CellStyle.Font = gridPlatforms.Font;
            }

            // ROW STATE COLORS
            if (!platform.Enabled)
            {
                row.DefaultCellStyle.BackColor = Color.FromArgb(245, 245, 245);
                row.DefaultCellStyle.ForeColor = Color.Gray;
            }
            else if (platform.Has_Error)
            {
                row.DefaultCellStyle.BackColor = Color.FromArgb(255, 230, 230);
                row.DefaultCellStyle.ForeColor = Color.DarkRed;
            }
            else if (platform.Paused)
            {
                row.DefaultCellStyle.BackColor = Color.FromArgb(255, 248, 220);
                row.DefaultCellStyle.ForeColor = Color.DarkGoldenrod;
            }
            else
            {
                row.DefaultCellStyle.BackColor = Color.FromArgb(232, 245, 233);
                row.DefaultCellStyle.ForeColor = Color.DarkGreen;
            }
        }

        private void ApplySnapshotHealthStyle(SnapshotHealthState health)
        {
            lblSnapshotStatus.ForeColor = health switch
            {
                SnapshotHealthState.Healthy => Color.DarkGreen,
                SnapshotHealthState.Stale => Color.DarkGoldenrod,
                SnapshotHealthState.Invalid => Color.DarkRed,
                _ => SystemColors.ControlText
            };
        }

        private void UpdateSnapshotHealthIndicators(SnapshotHealthState health)
        {
            if (_statusHealthDot == null)
                return;

            var (dot, _) = GetHealthLabel(health);
            _statusHealthDot.Text = dot;
            _statusHealthDot.ForeColor = health switch
            {
                SnapshotHealthState.Healthy => Color.DarkGreen,
                SnapshotHealthState.Stale => Color.DarkGoldenrod,
                SnapshotHealthState.Invalid => Color.DarkRed,
                _ => SystemColors.GrayText
            };
        }

        private static (string dot, string label) GetHealthLabel(SnapshotHealthState health)
        {
            return health switch
            {
                SnapshotHealthState.Healthy => ("🟢", "Healthy"),
                SnapshotHealthState.Stale => ("🟡", "Stale"),
                _ => ("🔴", "Error")
            };
        }

        private void SetSnapshotTooltip(RuntimeSnapshot snapshot, string? fallback)
        {
            if (snapshot == null)
            {
                _snapshotToolTip.SetToolTip(
                    lblSnapshotStatus,
                    fallback ?? "No snapshot data available."
                );
                return;
            }

            if (!DateTime.TryParse(
                snapshot.Generated_At,
                CultureInfo.InvariantCulture,
                DateTimeStyles.AssumeUniversal | DateTimeStyles.AdjustToUniversal,
                out var generatedAt))
            {
                _snapshotToolTip.SetToolTip(
                    lblSnapshotStatus,
                    $"Generated_At parse failure:\n{snapshot.Generated_At}"
                );
                return;
            }

            var ageSeconds = (DateTime.UtcNow - generatedAt).TotalSeconds;

            _snapshotToolTip.SetToolTip(
                lblSnapshotStatus,
                $"Generated at: {generatedAt:yyyy-MM-dd HH:mm:ss} UTC\n" +
                $"Snapshot age: {Math.Round(ageSeconds)} seconds\n" +
                $"Stale threshold: {SnapshotStaleThresholdSeconds} seconds"
            );
        }

        private void UpdateSnapshotStatus(string text)
        {
            void ApplyText()
            {
                lblSnapshotStatus.Text = text;
                statusSnapshot.Text = text;
            }

            if (InvokeRequired)
                Invoke(new Action(ApplyText));
            else
                ApplyText();
        }

        private void UpdatePlatformCount(string text)
        {
            if (InvokeRequired)
                Invoke(new Action(() => lblPlatformCount.Text = text));
            else
                lblPlatformCount.Text = text;
        }

        private void UpdateStatusRuntime(string text)
        {
            if (InvokeRequired)
                Invoke(new Action(() => statusRuntime.Text = text));
            else
                statusRuntime.Text = text;
        }

        private static int GetRefreshIntervalMs()
        {
            var rawValue =
                ConfigurationManager.AppSettings["SnapshotRefreshIntervalMs"];

            if (int.TryParse(rawValue, out var interval) && interval > 0)
                return interval;

            return 5000;
        }

        // -----------------------------------------------------------------
        // Helpers
        // -----------------------------------------------------------------

        private static string ToTitleCase(string value)
        {
            if (string.IsNullOrWhiteSpace(value))
                return value;

            return CultureInfo.InvariantCulture.TextInfo.ToTitleCase(
                value.ToLowerInvariant()
            );
        }

        private static void EnableDoubleBuffering(Control control)
        {
            try
            {
                var prop = control.GetType().GetProperty(
                    "DoubleBuffered",
                    System.Reflection.BindingFlags.Instance |
                    System.Reflection.BindingFlags.NonPublic
                );

                prop?.SetValue(control, true, null);
            }
            catch { }
        }

        private void GridPlatforms_ColumnHeaderMouseClick(object? sender, DataGridViewCellMouseEventArgs e)
        {
            var column = gridPlatforms.Columns[e.ColumnIndex];

            if (string.IsNullOrWhiteSpace(column.DataPropertyName))
                return;

            var desiredDirection =
                _currentSortProperty == column.DataPropertyName &&
                _currentSortDirection == ListSortDirection.Ascending
                ? ListSortDirection.Descending
                : ListSortDirection.Ascending;

            ApplyGridSort(column.DataPropertyName, desiredDirection);

            column.HeaderCell.SortGlyphDirection =
                desiredDirection == ListSortDirection.Ascending
                    ? SortOrder.Ascending
                    : SortOrder.Descending;
        }

        private void ApplyGridSort(string propertyName, ListSortDirection direction)
        {
            _currentSortProperty = propertyName;
            _currentSortDirection = direction;

            if (_platformBindingSource.DataSource is not IEnumerable<PlatformStatus> data)
                return;

            var ordered = (direction == ListSortDirection.Ascending
                ? data.OrderBy(p => GetSortValue(p, propertyName))
                : data.OrderByDescending(p => GetSortValue(p, propertyName)))
                .ToList();

            var current = gridPlatforms.CurrentRow?.DataBoundItem as PlatformStatus;

            _platformBindingSource.DataSource = ordered;

            if (current == null)
                return;

            for (var i = 0; i < ordered.Count; i++)
            {
                if (!ReferenceEquals(ordered[i], current))
                    continue;

                gridPlatforms.ClearSelection();
                gridPlatforms.CurrentCell = gridPlatforms.Rows[i].Cells[0];
                gridPlatforms.Rows[i].Selected = true;
                break;
            }

            var sortedColumn = gridPlatforms.Columns
                .Cast<DataGridViewColumn>()
                .FirstOrDefault(c => c.DataPropertyName == propertyName);

            foreach (DataGridViewColumn col in gridPlatforms.Columns)
            {
                if (col == sortedColumn)
                {
                    col.HeaderCell.SortGlyphDirection =
                        direction == ListSortDirection.Ascending
                            ? SortOrder.Ascending
                            : SortOrder.Descending;
                }
                else
                {
                    col.HeaderCell.SortGlyphDirection = SortOrder.None;
                }
            }
        }

        private static object? GetSortValue(PlatformStatus platform, string propertyName)
        {
            return propertyName switch
            {
                nameof(PlatformStatus.Platform) => platform.Platform,
                nameof(PlatformStatus.Display_State) => platform.Display_State,
                nameof(PlatformStatus.Telemetry_Display) => platform.Telemetry_Display,
                nameof(PlatformStatus.Capabilities) => platform.Capabilities,
                _ => null
            };
        }

        private class TelemetryRateRow
        {
            public string Window { get; set; } = string.Empty;
            public string Metric { get; set; } = string.Empty;
            public string Platform { get; set; } = string.Empty;
            public int Value { get; set; }
        }
    }
}

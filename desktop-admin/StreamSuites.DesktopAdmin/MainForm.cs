using StreamSuites.DesktopAdmin.Core;
using StreamSuites.DesktopAdmin.RuntimeBridge;
using StreamSuites.DesktopAdmin.Models;
using System;
using System.Configuration;
using System.Drawing;
using System.Globalization;
using System.IO;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace StreamSuites.DesktopAdmin
{
    public partial class MainForm : Form
    {
        private readonly AppState _appState;
        private readonly RuntimeConnector _runtimeConnector;

        private readonly Timer _refreshTimer;
        private bool _refreshInProgress;

        private readonly BindingSource _platformBindingSource;
        private readonly ToolTip _snapshotToolTip;

        // STEP K - last refresh live counter
        private readonly Timer _sinceRefreshTimer;
        private DateTime? _lastSuccessfulRefreshUtc;

        // Inspector UI (STEP G)
        private Panel _inspectorPanel;
        private Label _inspectorTitle;
        private Label _inspectorBody;

        private const int SnapshotStaleThresholdSeconds = 20;

        // Tray menu (STEP L)
        private ContextMenuStrip _trayMenu;

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

            var modeContext = new ModeContext("Dashboard");
            _appState = new AppState(modeContext);

            var fileAccessor = new DefaultFileAccessor();
            var snapshotReader = new FileSnapshotReader(fileAccessor);
            _runtimeConnector = new RuntimeConnector(snapshotReader, _appState);

            _platformBindingSource = new BindingSource();
            gridPlatforms.DataSource = _platformBindingSource;

            InitializePlatformGrid();
            InitializeInspectorPanel();

            gridPlatforms.SelectionChanged += GridPlatforms_SelectionChanged;

            _refreshTimer = new Timer
            {
                Interval = GetRefreshIntervalMs()
            };
            _refreshTimer.Tick += async (_, __) =>
                await RefreshSnapshotAsync();

            _sinceRefreshTimer = new Timer
            {
                Interval = 1000
            };
            _sinceRefreshTimer.Tick += (_, __) =>
                UpdateLastRefreshCounter();

            Shown += async (_, __) =>
            {
                await RefreshSnapshotAsync();
                _refreshTimer.Start();
                _sinceRefreshTimer.Start();
            };
        }

        // -----------------------------------------------------------------
        // Snapshot refresh
        // -----------------------------------------------------------------

        private async Task RefreshSnapshotAsync()
        {
            if (_refreshInProgress)
                return;

            var snapshotPath = GetSnapshotPath();
            if (string.IsNullOrWhiteSpace(snapshotPath))
            {
                UpdateSnapshotStatus("Snapshot: path not configured");
                ApplySnapshotHealthStyle(SnapshotHealthState.Invalid);
                UpdateTrayIconHealth(SnapshotHealthState.Invalid);
                SetSnapshotTooltip(null, "Snapshot path not configured.");
                UpdatePlatformCount("Platforms: unknown");
                _platformBindingSource.DataSource = null;
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
                    SetSnapshotTooltip(null, "Snapshot missing runtime block.");
                    UpdatePlatformCount("Platforms: invalid");
                    _platformBindingSource.DataSource = null;
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
                SetSnapshotTooltip(snapshot, null);

                UpdatePlatformCount(
                    $"Platforms: {snapshot.Platforms?.Count ?? 0}"
                );
                _platformBindingSource.DataSource =
                    snapshot.Platforms;

                _lastSuccessfulRefreshUtc = DateTime.UtcNow;
                UpdateLastRefreshCounter();
            }
            catch
            {
                UpdateSnapshotStatus("Snapshot: error reading");
                ApplySnapshotHealthStyle(SnapshotHealthState.Invalid);
                UpdateTrayIconHealth(SnapshotHealthState.Invalid);
                SetSnapshotTooltip(null, "Exception reading snapshot.");
                UpdatePlatformCount("Platforms: error");
            }
            finally
            {
                _refreshInProgress = false;
            }
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
                Show();
                WindowState = FormWindowState.Normal;
                Activate();
            };

            var itemStatus =
                new ToolStripMenuItem("Status: (placeholder)")
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
            _trayMenu.Items.Add(itemStatus);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemPlatforms);
            _trayMenu.Items.Add(itemSettings);
            _trayMenu.Items.Add(new ToolStripSeparator());
            _trayMenu.Items.Add(itemExit);

            trayIcon.ContextMenuStrip = _trayMenu;

            trayIcon.DoubleClick += (_, __) =>
            {
                Show();
                WindowState = FormWindowState.Normal;
                Activate();
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

            trayIcon.Text =
                $"StreamSuites - {health}";
            trayIcon.BalloonTipTitle =
                "StreamSuites Snapshot Status";

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

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Platform),
                    HeaderText = "Platform",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.AllCells
                });

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Display_State),
                    HeaderText = "State",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.AllCells
                });

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Telemetry_Display),
                    HeaderText = "Telemetry",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.AllCells
                });

            gridPlatforms.Columns.Add(
                new DataGridViewTextBoxColumn
                {
                    DataPropertyName =
                        nameof(PlatformStatus.Capabilities),
                    HeaderText = "Capabilities",
                    AutoSizeMode =
                        DataGridViewAutoSizeColumnMode.Fill,
                    MinimumWidth = 120
                });

            EnableDoubleBuffering(gridPlatforms);
            gridPlatforms.ScrollBars = ScrollBars.Both;

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
                return;
            }

            PopulateInspector(p);
        }

        // -----------------------------------------------------------------
        // Inspector (STEP G — FIXED PANEL, NON-COLLAPSIBLE)
        // -----------------------------------------------------------------

        private Button _btnToggleClient;
        private Button _btnConfigureClient;
        private PictureBox _inspectorIcon;

        private Image? _inspectorIconOwned; // we own/dispose this

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

            _inspectorIcon = new PictureBox
            {
                Width = 24,
                Height = 24,
                Margin = new Padding(0, 6, 6, 6),
                SizeMode = PictureBoxSizeMode.StretchImage,
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

            var actionsPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Bottom,
                Height = 56,
                Padding = new Padding(8),
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false,
                AutoSize = false
            };

            _btnToggleClient = new Button
            {
                Text = "Enable / Disable Client",
                Width = 170
            };

            _btnConfigureClient = new Button
            {
                Text = "Configure Client",
                Width = 150
            };

            actionsPanel.Controls.Add(_btnToggleClient);
            actionsPanel.Controls.Add(_btnConfigureClient);

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
            panelRuntimeRight.Invalidate();

            // -------------------------------------------------------------
            // SAFE splitter setup AFTER layout is real
            // -------------------------------------------------------------

            Shown -= ApplyInspectorSplitterAfterShown;
            Shown += ApplyInspectorSplitterAfterShown;

            splitRuntime.SizeChanged -= ClampInspectorSplitter;
            splitRuntime.SizeChanged += ClampInspectorSplitter;
        }

        private void ApplyInspectorSplitterAfterShown(object? sender, EventArgs e)
        {
            Shown -= ApplyInspectorSplitterAfterShown;

            // Only now set min sizes (avoids InvalidOperationException)
            splitRuntime.Panel2MinSize = 260;
            splitRuntime.Panel1MinSize = 420;

            ClampInspectorSplitter(null, EventArgs.Empty);
        }

        private void ClampInspectorSplitter(object? sender, EventArgs e)
        {
            var total = splitRuntime.ClientSize.Width;
            if (total <= 0)
                return;

            const int desiredInspectorWidth = 320;

            var min1 = splitRuntime.Panel1MinSize;
            var min2 = splitRuntime.Panel2MinSize;
            var max = total - min2;

            if (max < min1)
            {
                splitRuntime.SplitterDistance = Math.Max(0, max);
                return;
            }

            var desired = total - desiredInspectorWidth;

            if (desired < min1)
                desired = min1;
            if (desired > max)
                desired = max;

            splitRuntime.SplitterDistance = desired;
        }

        private void PopulateInspector(PlatformStatus p)
        {
            _inspectorTitle.Text = ToTitleCase(p.Platform);

            SetInspectorIconForPlatform(p.Platform);

            _btnToggleClient.Text =
                p.Enabled ? "Disable Client" : "Enable Client";

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
            // Dispose previous image we owned
            if (_inspectorIconOwned != null)
            {
                try { _inspectorIconOwned.Dispose(); } catch { }
                _inspectorIconOwned = null;
            }

            _inspectorIcon.Image = null;

            // Try multiple common locations/names
            var baseDir = AppDomain.CurrentDomain.BaseDirectory;
            var assetsDir = Path.Combine(baseDir, "assets");

            var key = (platform ?? string.Empty).Trim();
            var lower = key.ToLowerInvariant();

            var candidates = new[]
            {
                Path.Combine(assetsDir, $"{lower}.png"),
                Path.Combine(assetsDir, $"{lower}.ico"),
                Path.Combine(baseDir, $"{lower}.png"),
                Path.Combine(baseDir, $"{lower}.ico"),
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

                    _inspectorIconOwned = new Bitmap(raw, new Size(24, 24));
                    _inspectorIcon.Image = _inspectorIconOwned;
                    return;
                }
                catch
                {
                    // try next candidate
                }
            }
        }

        private void ClearInspector()
        {
            _inspectorTitle.Text = "Platform Inspector";

            if (_inspectorIconOwned != null)
            {
                try { _inspectorIconOwned.Dispose(); } catch { }
                _inspectorIconOwned = null;
            }

            _inspectorIcon.Image = null;
            _inspectorBody.Text = "No platform selected.";
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
            if (InvokeRequired)
                Invoke(new Action(() => lblSnapshotStatus.Text = text));
            else
                lblSnapshotStatus.Text = text;
        }

        private void UpdatePlatformCount(string text)
        {
            if (InvokeRequired)
                Invoke(new Action(() => lblPlatformCount.Text = text));
            else
                lblPlatformCount.Text = text;
        }

        private static string GetSnapshotPath()
        {
            var configuredPath =
                ConfigurationManager.AppSettings["SnapshotDirectory"];

            if (string.IsNullOrWhiteSpace(configuredPath))
                return string.Empty;

            return Path.Combine(configuredPath, "runtime_snapshot.json");
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
    }
}

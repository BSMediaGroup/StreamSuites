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
using System.Text.Json;
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
        private readonly BindingSource _creatorsBindingSource;
        private readonly BindingSource _platformFlagsBindingSource;
        private readonly BindingSource _clipsBindingSource;
        private readonly BindingSource _pollsBindingSource;
        private readonly BindingSource _talliesBindingSource;
        private readonly BindingSource _scoreboardsBindingSource;
        private readonly BindingSource _chatEventsBindingSource;
        private readonly BindingSource _pollVotesBindingSource;
        private readonly BindingSource _tallyEventsBindingSource;
        private readonly BindingSource _scoreEventsBindingSource;
        private readonly BindingSource _chatTriggersBindingSource;
        private readonly ToolTip _snapshotToolTip;
        private RuntimeVersionInfo _runtimeVersionInfo;
        private SnapshotHealthState _lastTrayHealth = SnapshotHealthState.Invalid;

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

        private DataGridView _creatorsGrid;
        private Label _creatorsSummary;
        private Label _creatorDetails;
        private Button _creatorEnableButton;
        private Button _creatorDisableButton;
        private SplitContainer _creatorsSplit;

        private Label _dataSignalsSummary;
        private Label _clipsSummary;
        private Label _pollsSummary;
        private Label _talliesSummary;
        private Label _scoreboardsSummary;
        private Label _chatTriggersSummary;
        private Label _rateLimitsSummary;
        private Label _chatReplaySummary;
        private Label _supportSummary;
        private Label _updatesSummary;
        private Label _aboutSummary;
        private DataGridView _clipsGrid;
        private DataGridView _pollsGrid;
        private DataGridView _talliesGrid;
        private DataGridView _scoreboardsGrid;
        private DataGridView _chatEventsGrid;
        private DataGridView _pollVotesGrid;
        private DataGridView _tallyEventsGrid;
        private DataGridView _scoreEventsGrid;
        private DataGridView _clipsManagementGrid;
        private DataGridView _pollsManagementGrid;
        private DataGridView _talliesManagementGrid;
        private DataGridView _scoreboardsManagementGrid;
        private DataGridView _chatTriggersGrid;
        private DataGridView _rateLimitsGrid;
        private DataGridView _chatReplayGrid;

        private Label _settingsRestartSummary;
        private Label _settingsSystemSummary;
        private Label _settingsPollingSummary;
        private Label _settingsImportExportSummary;
        private DataGridView _settingsPlatformGrid;

        private ComboBox _discordGuildSelector;
        private CheckBox _discordLoggingEnabledToggle;
        private TextBox _discordLoggingChannelId;
        private TextBox _discordNotificationsGeneral;
        private TextBox _discordNotificationsRumble;
        private TextBox _discordNotificationsYoutube;
        private TextBox _discordNotificationsKick;
        private TextBox _discordNotificationsPilled;
        private TextBox _discordNotificationsTwitch;
        private Button _discordConfigSaveButton;
        private Label _discordConfigStatus;
        private DiscordConfigExport _discordConfigCache = new DiscordConfigExport();

        private TabPage _tabChatTriggers;
        private TabPage _tabClips;
        private TabPage _tabPolls;
        private TabPage _tabTallies;
        private TabPage _tabScoreboards;
        private TabPage _tabRateLimits;
        private TabPage _tabChatReplay;
        private TabPage _tabSupport;
        private TabPage _tabUpdates;
        private TabPage _tabAbout;

        private readonly Dictionary<string, PlatformTabControls> _platformTabControls
            = new(StringComparer.OrdinalIgnoreCase);

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
            _runtimeVersionInfo = RuntimeVersionInfo.Unavailable();

            _platformBindingSource = new BindingSource();
            _jobsBindingSource = new BindingSource();
            _telemetryEventsBindingSource = new BindingSource();
            _telemetryErrorsBindingSource = new BindingSource();
            _telemetryRatesBindingSource = new BindingSource();
            _creatorsBindingSource = new BindingSource();
            _platformFlagsBindingSource = new BindingSource();
            _clipsBindingSource = new BindingSource();
            _pollsBindingSource = new BindingSource();
            _talliesBindingSource = new BindingSource();
            _scoreboardsBindingSource = new BindingSource();
            _chatEventsBindingSource = new BindingSource();
            _pollVotesBindingSource = new BindingSource();
            _tallyEventsBindingSource = new BindingSource();
            _scoreEventsBindingSource = new BindingSource();
            _chatTriggersBindingSource = new BindingSource();
            gridPlatforms.DataSource = _platformBindingSource;

            InitializeNavigationTabs();
            InitializePlatformGrid();
            InitializeInspectorPanel();
            InitializeMenu();
            InitializeJobsTab();
            InitializeTelemetryTab();
            InitializeCreatorsTab();
            InitializeChatTriggersTab();
            InitializeClipsTab();
            InitializePollsTab();
            InitializeTalliesTab();
            InitializeScoreboardsTab();
            InitializeDataSignalsTab();
            InitializeRateLimitsTab();
            InitializeSettingsTab();
            InitializeChatReplayTab();
            InitializeSupportTab();
            InitializeUpdatesTab();
            InitializeAboutTab();
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
            RefreshRuntimeVersionInfo();

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

            var menuNavigate = new ToolStripMenuItem("Navigate");
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Overview", tabRuntime));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Creators", tabCreators));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Chat Triggers", _tabChatTriggers));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Jobs", tabJobs));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Clips", _tabClips));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Polls", _tabPolls));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Tallies", _tabTallies));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Scoreboards", _tabScoreboards));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Data & Signals", tabDataSignals));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Rate Limits", _tabRateLimits));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Telemetry", tabTelemetry));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Settings", tabSettings));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Chat Replay", _tabChatReplay));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Support", _tabSupport));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Updates", _tabUpdates));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("About", _tabAbout));
            menuNavigate.DropDownItems.Add(BuildNavigationMenuItem("Paths", tabPaths));

            var menuNavigatePlatforms = new ToolStripMenuItem("Platforms");
            foreach (var platform in GetPlatformNames())
            {
                var menuItem = new ToolStripMenuItem(platform);
                menuItem.Click += (_, __) =>
                {
                    var tab = tabMain.TabPages.Cast<TabPage>()
                        .FirstOrDefault(existing =>
                            string.Equals(existing.Text, platform, StringComparison.OrdinalIgnoreCase));
                    if (tab != null)
                        tabMain.SelectedTab = tab;
                };

                menuNavigatePlatforms.DropDownItems.Add(menuItem);
            }

            menuNavigate.DropDownItems.Add(new ToolStripSeparator());
            menuNavigate.DropDownItems.Add(menuNavigatePlatforms);

            var menuHelp = new ToolStripMenuItem("Help");
            var itemAbout = new ToolStripMenuItem("About");
            itemAbout.Click += async (_, __) => await ShowAboutDialogAsync();
            menuHelp.DropDownItems.Add(itemAbout);

            _menuMain.Items.Add(menuFile);
            _menuMain.Items.Add(menuOptions);
            _menuMain.Items.Add(menuNavigate);
            _menuMain.Items.Add(menuHelp);

            Controls.Add(_menuMain);
            MainMenuStrip = _menuMain;
            EnsureDockOrder();
        }

        private ToolStripMenuItem BuildNavigationMenuItem(string label, TabPage? tab)
        {
            var menuItem = new ToolStripMenuItem(label);
            menuItem.Click += (_, __) =>
            {
                if (tab != null)
                    tabMain.SelectedTab = tab;
            };

            return menuItem;
        }

        private void EnsureDockOrder()
        {
            if (_menuMain == null)
                return;

            Controls.SetChildIndex(tabMain, 0);
            Controls.SetChildIndex(statusBar, 1);
            Controls.SetChildIndex(toolMain, 2);
            Controls.SetChildIndex(_menuMain, 3);
        }

        private void InitializeNavigationTabs()
        {
            tabRuntime.Text = "Overview";
            tabCreators.Text = "Creators";
            tabJobs.Text = "Jobs";
            tabDataSignals.Text = "Data & Signals";
            tabTelemetry.Text = "Telemetry";
            tabSettings.Text = "Settings";
            tabPaths.Text = "Paths";

            _tabChatTriggers = new TabPage("Chat Triggers") { Padding = new Padding(8) };
            _tabClips = new TabPage("Clips") { Padding = new Padding(8) };
            _tabPolls = new TabPage("Polls") { Padding = new Padding(8) };
            _tabTallies = new TabPage("Tallies") { Padding = new Padding(8) };
            _tabScoreboards = new TabPage("Scoreboards") { Padding = new Padding(8) };
            _tabRateLimits = new TabPage("Rate Limits") { Padding = new Padding(8) };
            _tabChatReplay = new TabPage("Chat Replay") { Padding = new Padding(8) };
            _tabSupport = new TabPage("Support") { Padding = new Padding(8) };
            _tabUpdates = new TabPage("Updates") { Padding = new Padding(8) };
            _tabAbout = new TabPage("About") { Padding = new Padding(8) };

            tabMain.TabPages.Clear();
            tabMain.TabPages.Add(tabRuntime);
            tabMain.TabPages.Add(tabCreators);
            tabMain.TabPages.Add(_tabChatTriggers);
            tabMain.TabPages.Add(tabJobs);
            tabMain.TabPages.Add(_tabClips);
            tabMain.TabPages.Add(_tabPolls);
            tabMain.TabPages.Add(_tabTallies);
            tabMain.TabPages.Add(_tabScoreboards);
            tabMain.TabPages.Add(tabDataSignals);
            tabMain.TabPages.Add(_tabRateLimits);
            tabMain.TabPages.Add(tabTelemetry);
            tabMain.TabPages.Add(tabSettings);
            tabMain.TabPages.Add(_tabChatReplay);
            tabMain.TabPages.Add(_tabSupport);
            tabMain.TabPages.Add(_tabUpdates);
            tabMain.TabPages.Add(_tabAbout);
            tabMain.TabPages.Add(tabPaths);
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

        private void InitializeChatTriggersTab()
        {
            if (_tabChatTriggers == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

            _chatTriggersSummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Chat triggers: —"
            };

            var actions = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false
            };

            var btnEnable = new Button
            {
                Text = "Enable (placeholder)",
                AutoSize = true,
                Enabled = false
            };

            var btnDisable = new Button
            {
                Text = "Disable (placeholder)",
                AutoSize = true,
                Enabled = false
            };

            actions.Controls.Add(btnEnable);
            actions.Controls.Add(btnDisable);

            _chatTriggersGrid = BuildDataSignalsGrid();
            _chatTriggersGrid.Columns.Add(BuildTextColumn(nameof(ChatTriggerRow.TriggerId), "Trigger ID", 140));
            _chatTriggersGrid.Columns.Add(BuildTextColumn(nameof(ChatTriggerRow.Creator), "Creator", 140));
            _chatTriggersGrid.Columns.Add(BuildTextColumn(nameof(ChatTriggerRow.Type), "Type", 100));
            _chatTriggersGrid.Columns.Add(BuildTextColumn(nameof(ChatTriggerRow.Command), "Command", 120));
            _chatTriggersGrid.Columns.Add(BuildTextColumn(nameof(ChatTriggerRow.CooldownSeconds), "Cooldown", 90));
            _chatTriggersGrid.Columns.Add(BuildTextColumn(nameof(ChatTriggerRow.Description), "Description", 260));
            _chatTriggersGrid.Columns.Add(BuildTextColumn(nameof(ChatTriggerRow.UpdatedAt), "Updated", 160));
            _chatTriggersGrid.DataSource = _chatTriggersBindingSource;
            EnableDoubleBuffering(_chatTriggersGrid);

            layout.Controls.Add(_chatTriggersSummary, 0, 0);
            layout.Controls.Add(actions, 0, 1);
            layout.Controls.Add(_chatTriggersGrid, 0, 2);

            panel.Controls.Add(layout);
            _tabChatTriggers.Controls.Clear();
            _tabChatTriggers.Controls.Add(panel);
        }

        private void InitializeClipsTab()
        {
            if (_tabClips == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

            _clipsSummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Clips: —"
            };

            var actions = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false
            };

            actions.Controls.Add(new Button
            {
                Text = "Create Clip (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            _clipsManagementGrid = BuildDataSignalsGrid();
            _clipsManagementGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.ClipId), "Clip ID", 120));
            _clipsManagementGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.Title), "Title", 200));
            _clipsManagementGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.Creator), "Creator", 120));
            _clipsManagementGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.State), "State", 100));
            _clipsManagementGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.PublishedAt), "Published", 150));
            _clipsManagementGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.Duration), "Duration", 90));
            _clipsManagementGrid.DataSource = _clipsBindingSource;
            EnableDoubleBuffering(_clipsManagementGrid);

            layout.Controls.Add(_clipsSummary, 0, 0);
            layout.Controls.Add(actions, 0, 1);
            layout.Controls.Add(_clipsManagementGrid, 0, 2);

            panel.Controls.Add(layout);
            _tabClips.Controls.Clear();
            _tabClips.Controls.Add(panel);
        }

        private void InitializePollsTab()
        {
            if (_tabPolls == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

            _pollsSummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Polls: —"
            };

            var actions = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false
            };

            actions.Controls.Add(new Button
            {
                Text = "Create Poll (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            actions.Controls.Add(new Button
            {
                Text = "End Poll (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            _pollsManagementGrid = BuildDataSignalsGrid();
            _pollsManagementGrid.Columns.Add(BuildTextColumn(nameof(PollRow.PollId), "Poll ID", 130));
            _pollsManagementGrid.Columns.Add(BuildTextColumn(nameof(PollRow.Question), "Question", 220));
            _pollsManagementGrid.Columns.Add(BuildTextColumn(nameof(PollRow.Creator), "Creator", 120));
            _pollsManagementGrid.Columns.Add(BuildTextColumn(nameof(PollRow.State), "State", 90));
            _pollsManagementGrid.Columns.Add(BuildTextColumn(nameof(PollRow.OpenedAt), "Opened", 150));
            _pollsManagementGrid.Columns.Add(BuildTextColumn(nameof(PollRow.ClosedAt), "Closed", 150));
            _pollsManagementGrid.Columns.Add(BuildTextColumn(nameof(PollRow.OptionsSummary), "Options", 220));
            _pollsManagementGrid.DataSource = _pollsBindingSource;
            EnableDoubleBuffering(_pollsManagementGrid);

            layout.Controls.Add(_pollsSummary, 0, 0);
            layout.Controls.Add(actions, 0, 1);
            layout.Controls.Add(_pollsManagementGrid, 0, 2);

            panel.Controls.Add(layout);
            _tabPolls.Controls.Clear();
            _tabPolls.Controls.Add(panel);
        }

        private void InitializeTalliesTab()
        {
            if (_tabTallies == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

            _talliesSummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Tallies: —"
            };

            var actions = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false
            };

            actions.Controls.Add(new Button
            {
                Text = "Increment (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            actions.Controls.Add(new Button
            {
                Text = "Decrement (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            actions.Controls.Add(new Button
            {
                Text = "Reset (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            _talliesManagementGrid = BuildDataSignalsGrid();
            _talliesManagementGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.TallyId), "Tally ID", 130));
            _talliesManagementGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.Label), "Label", 200));
            _talliesManagementGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.Creator), "Creator", 120));
            _talliesManagementGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.Count), "Count", 90));
            _talliesManagementGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.UpdatedAt), "Updated", 150));
            _talliesManagementGrid.DataSource = _talliesBindingSource;
            EnableDoubleBuffering(_talliesManagementGrid);

            layout.Controls.Add(_talliesSummary, 0, 0);
            layout.Controls.Add(actions, 0, 1);
            layout.Controls.Add(_talliesManagementGrid, 0, 2);

            panel.Controls.Add(layout);
            _tabTallies.Controls.Clear();
            _tabTallies.Controls.Add(panel);
        }

        private void InitializeScoreboardsTab()
        {
            if (_tabScoreboards == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));

            _scoreboardsSummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Scoreboards: —"
            };

            var actions = new FlowLayoutPanel
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false
            };

            actions.Controls.Add(new Button
            {
                Text = "Update Score (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            actions.Controls.Add(new Button
            {
                Text = "Reset (placeholder)",
                AutoSize = true,
                Enabled = false
            });

            _scoreboardsManagementGrid = BuildDataSignalsGrid();
            _scoreboardsManagementGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.ScoreboardId), "Scoreboard ID", 150));
            _scoreboardsManagementGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.Title), "Title", 200));
            _scoreboardsManagementGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.Creator), "Creator", 120));
            _scoreboardsManagementGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.Entries), "Entries", 90));
            _scoreboardsManagementGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.FinalizedAt), "Finalized", 150));
            _scoreboardsManagementGrid.DataSource = _scoreboardsBindingSource;
            EnableDoubleBuffering(_scoreboardsManagementGrid);

            layout.Controls.Add(_scoreboardsSummary, 0, 0);
            layout.Controls.Add(actions, 0, 1);
            layout.Controls.Add(_scoreboardsManagementGrid, 0, 2);

            panel.Controls.Add(layout);
            _tabScoreboards.Controls.Clear();
            _tabScoreboards.Controls.Add(panel);
        }

        private void InitializeRateLimitsTab()
        {
            if (_tabRateLimits == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
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

            _rateLimitsSummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Rate limits: —"
            };

            _rateLimitsGrid = BuildTelemetryGrid();
            _rateLimitsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Window),
                HeaderText = "Window",
                MinimumWidth = 120
            });
            _rateLimitsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Metric),
                HeaderText = "Metric",
                MinimumWidth = 140
            });
            _rateLimitsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Platform),
                HeaderText = "Platform",
                MinimumWidth = 120
            });
            _rateLimitsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(TelemetryRateRow.Value),
                HeaderText = "Value",
                MinimumWidth = 80
            });
            _rateLimitsGrid.DataSource = _telemetryRatesBindingSource;
            EnableDoubleBuffering(_rateLimitsGrid);

            layout.Controls.Add(_rateLimitsSummary, 0, 0);
            layout.Controls.Add(_rateLimitsGrid, 0, 1);

            panel.Controls.Add(layout);
            _tabRateLimits.Controls.Clear();
            _tabRateLimits.Controls.Add(panel);
        }

        private void InitializeChatReplayTab()
        {
            if (_tabChatReplay == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
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

            _chatReplaySummary = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Chat replay: —"
            };

            _chatReplayGrid = BuildDataSignalsGrid();
            _chatReplayGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Timestamp), "Timestamp", 160));
            _chatReplayGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Creator), "Creator", 120));
            _chatReplayGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Platform), "Platform", 110));
            _chatReplayGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Username), "User", 120));
            _chatReplayGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Message), "Message", 280));
            _chatReplayGrid.DataSource = _chatEventsBindingSource;
            EnableDoubleBuffering(_chatReplayGrid);

            layout.Controls.Add(_chatReplaySummary, 0, 0);
            layout.Controls.Add(_chatReplayGrid, 0, 1);

            panel.Controls.Add(layout);
            _tabChatReplay.Controls.Clear();
            _tabChatReplay.Controls.Add(panel);
        }

        private void InitializeSupportTab()
        {
            if (_tabSupport == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(12)
            };

            _supportSummary = new Label
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                Text = "Support resources are available via the StreamSuites documentation and community channels."
            };

            var supportNote = new Label
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(0, 8, 0, 0),
                Text = "Use the web dashboard to access live support links, FAQs, and account tooling."
            };

            panel.Controls.Add(supportNote);
            panel.Controls.Add(_supportSummary);

            _tabSupport.Controls.Clear();
            _tabSupport.Controls.Add(panel);
        }

        private void InitializeUpdatesTab()
        {
            if (_tabUpdates == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(12)
            };

            _updatesSummary = new Label
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                Text = "Updates: —"
            };

            var note = new Label
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(0, 8, 0, 0),
                Text = "Release notes are published in runtime exports and the web dashboard."
            };

            panel.Controls.Add(note);
            panel.Controls.Add(_updatesSummary);

            _tabUpdates.Controls.Clear();
            _tabUpdates.Controls.Add(panel);
        }

        private void InitializeAboutTab()
        {
            if (_tabAbout == null)
                return;

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true,
                Padding = new Padding(12)
            };

            _aboutSummary = new Label
            {
                Dock = DockStyle.Top,
                AutoSize = true,
                Text = "About: —"
            };

            var btnAbout = new Button
            {
                Text = "Open About Dialog",
                AutoSize = true
            };
            btnAbout.Click += async (_, __) => await ShowAboutDialogAsync();

            panel.Controls.Add(btnAbout);
            panel.Controls.Add(_aboutSummary);

            _tabAbout.Controls.Clear();
            _tabAbout.Controls.Add(panel);
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

        private void InitializeCreatorsTab()
        {
            tabCreators.Padding = new Padding(8);

            _creatorsSplit = new SplitContainer
            {
                Dock = DockStyle.Fill,
                Orientation = Orientation.Vertical
            };

            var leftLayout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 3,
                Padding = new Padding(8)
            };

            leftLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            leftLayout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
            leftLayout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            _creatorsSummary = new Label
            {
                Text = "Creators: —",
                AutoSize = true,
                Dock = DockStyle.Fill
            };

            _creatorsGrid = new DataGridView
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

            _creatorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(CreatorRow.CreatorId),
                HeaderText = "Creator ID",
                MinimumWidth = 120
            });

            _creatorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(CreatorRow.DisplayName),
                HeaderText = "Display Name",
                MinimumWidth = 160
            });

            _creatorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(CreatorRow.PlatformsEnabled),
                HeaderText = "Platforms Enabled",
                MinimumWidth = 180
            });

            _creatorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(CreatorRow.Status),
                HeaderText = "Status",
                MinimumWidth = 100
            });

            _creatorsGrid.Columns.Add(new DataGridViewTextBoxColumn
            {
                DataPropertyName = nameof(CreatorRow.Notes),
                HeaderText = "Notes",
                MinimumWidth = 220
            });

            _creatorsGrid.DataSource = _creatorsBindingSource;
            EnableDoubleBuffering(_creatorsGrid);

            var actionsPanel = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false
            };

            _creatorEnableButton = new Button
            {
                Text = "Enable (placeholder)",
                AutoSize = true,
                Enabled = false
            };

            _creatorDisableButton = new Button
            {
                Text = "Disable (placeholder)",
                AutoSize = true,
                Enabled = false
            };

            var actionsNote = new Label
            {
                Text = "Read-only: creator edits apply in runtime export pipelines.",
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(12, 6, 0, 0)
            };

            actionsPanel.Controls.Add(_creatorEnableButton);
            actionsPanel.Controls.Add(_creatorDisableButton);
            actionsPanel.Controls.Add(actionsNote);

            leftLayout.Controls.Add(_creatorsSummary, 0, 0);
            leftLayout.Controls.Add(_creatorsGrid, 0, 1);
            leftLayout.Controls.Add(actionsPanel, 0, 2);

            var detailsGroup = new GroupBox
            {
                Text = "Creator Details",
                Dock = DockStyle.Fill,
                Padding = new Padding(8)
            };

            _creatorDetails = new Label
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                Text = "Select a creator to view details."
            };

            detailsGroup.Controls.Add(_creatorDetails);

            _creatorsSplit.Panel1.Controls.Add(leftLayout);
            _creatorsSplit.Panel2.Controls.Add(detailsGroup);

            tabCreators.Controls.Clear();
            tabCreators.Controls.Add(_creatorsSplit);

            _creatorsGrid.SelectionChanged += CreatorsGrid_SelectionChanged;

            Shown -= ApplyCreatorsSplitterAfterShown;
            Shown += ApplyCreatorsSplitterAfterShown;
        }

        private void InitializeDataSignalsTab()
        {
            tabDataSignals.Padding = new Padding(8);

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

            var noticeGroup = new GroupBox
            {
                Text = "Runtime-owned, dashboard-visible",
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            _dataSignalsSummary = new Label
            {
                AutoSize = true,
                Dock = DockStyle.Fill,
                Text = "Runtime exports provide read-only observability for entities and signals."
            };

            noticeGroup.Controls.Add(_dataSignalsSummary);

            var entitiesGroup = BuildDataSignalsGroup("Entities", out var entitiesTabs);
            var signalsGroup = BuildDataSignalsGroup("Signals", out var signalsTabs);

            _clipsGrid = BuildDataSignalsGrid();
            _clipsGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.ClipId), "Clip ID", 120));
            _clipsGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.Title), "Title", 200));
            _clipsGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.Creator), "Creator", 120));
            _clipsGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.State), "State", 100));
            _clipsGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.PublishedAt), "Published", 150));
            _clipsGrid.Columns.Add(BuildTextColumn(nameof(ClipRow.Duration), "Duration", 90));
            _clipsGrid.DataSource = _clipsBindingSource;
            EnableDoubleBuffering(_clipsGrid);

            _pollsGrid = BuildDataSignalsGrid();
            _pollsGrid.Columns.Add(BuildTextColumn(nameof(PollRow.PollId), "Poll ID", 130));
            _pollsGrid.Columns.Add(BuildTextColumn(nameof(PollRow.Question), "Question", 220));
            _pollsGrid.Columns.Add(BuildTextColumn(nameof(PollRow.Creator), "Creator", 120));
            _pollsGrid.Columns.Add(BuildTextColumn(nameof(PollRow.State), "State", 90));
            _pollsGrid.Columns.Add(BuildTextColumn(nameof(PollRow.OpenedAt), "Opened", 150));
            _pollsGrid.Columns.Add(BuildTextColumn(nameof(PollRow.ClosedAt), "Closed", 150));
            _pollsGrid.Columns.Add(BuildTextColumn(nameof(PollRow.OptionsSummary), "Options", 220));
            _pollsGrid.DataSource = _pollsBindingSource;
            EnableDoubleBuffering(_pollsGrid);

            _talliesGrid = BuildDataSignalsGrid();
            _talliesGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.TallyId), "Tally ID", 130));
            _talliesGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.Label), "Label", 200));
            _talliesGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.Creator), "Creator", 120));
            _talliesGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.Count), "Count", 90));
            _talliesGrid.Columns.Add(BuildTextColumn(nameof(TallyRow.UpdatedAt), "Updated", 150));
            _talliesGrid.DataSource = _talliesBindingSource;
            EnableDoubleBuffering(_talliesGrid);

            _scoreboardsGrid = BuildDataSignalsGrid();
            _scoreboardsGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.ScoreboardId), "Scoreboard ID", 150));
            _scoreboardsGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.Title), "Title", 200));
            _scoreboardsGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.Creator), "Creator", 120));
            _scoreboardsGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.Entries), "Entries", 90));
            _scoreboardsGrid.Columns.Add(BuildTextColumn(nameof(ScoreboardRow.FinalizedAt), "Finalized", 150));
            _scoreboardsGrid.DataSource = _scoreboardsBindingSource;
            EnableDoubleBuffering(_scoreboardsGrid);

            _chatEventsGrid = BuildDataSignalsGrid();
            _chatEventsGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Timestamp), "Timestamp", 160));
            _chatEventsGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Creator), "Creator", 120));
            _chatEventsGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Platform), "Platform", 110));
            _chatEventsGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Username), "User", 120));
            _chatEventsGrid.Columns.Add(BuildTextColumn(nameof(ChatEventRow.Message), "Message", 280));
            _chatEventsGrid.DataSource = _chatEventsBindingSource;
            EnableDoubleBuffering(_chatEventsGrid);

            _pollVotesGrid = BuildDataSignalsGrid();
            _pollVotesGrid.Columns.Add(BuildTextColumn(nameof(PollVoteRow.Timestamp), "Timestamp", 160));
            _pollVotesGrid.Columns.Add(BuildTextColumn(nameof(PollVoteRow.PollId), "Poll ID", 130));
            _pollVotesGrid.Columns.Add(BuildTextColumn(nameof(PollVoteRow.OptionId), "Option ID", 150));
            _pollVotesGrid.Columns.Add(BuildTextColumn(nameof(PollVoteRow.Creator), "Creator", 120));
            _pollVotesGrid.Columns.Add(BuildTextColumn(nameof(PollVoteRow.VoterId), "Voter ID", 150));
            _pollVotesGrid.DataSource = _pollVotesBindingSource;
            EnableDoubleBuffering(_pollVotesGrid);

            _tallyEventsGrid = BuildDataSignalsGrid();
            _tallyEventsGrid.Columns.Add(BuildTextColumn(nameof(TallyEventRow.Timestamp), "Timestamp", 160));
            _tallyEventsGrid.Columns.Add(BuildTextColumn(nameof(TallyEventRow.TallyId), "Tally ID", 130));
            _tallyEventsGrid.Columns.Add(BuildTextColumn(nameof(TallyEventRow.Creator), "Creator", 120));
            _tallyEventsGrid.Columns.Add(BuildTextColumn(nameof(TallyEventRow.Delta), "Delta", 80));
            _tallyEventsGrid.DataSource = _tallyEventsBindingSource;
            EnableDoubleBuffering(_tallyEventsGrid);

            _scoreEventsGrid = BuildDataSignalsGrid();
            _scoreEventsGrid.Columns.Add(BuildTextColumn(nameof(ScoreEventRow.Timestamp), "Timestamp", 160));
            _scoreEventsGrid.Columns.Add(BuildTextColumn(nameof(ScoreEventRow.ScoreboardId), "Scoreboard ID", 150));
            _scoreEventsGrid.Columns.Add(BuildTextColumn(nameof(ScoreEventRow.Creator), "Creator", 120));
            _scoreEventsGrid.Columns.Add(BuildTextColumn(nameof(ScoreEventRow.Label), "Label", 160));
            _scoreEventsGrid.Columns.Add(BuildTextColumn(nameof(ScoreEventRow.ScoreDelta), "Score Δ", 90));
            _scoreEventsGrid.DataSource = _scoreEventsBindingSource;
            EnableDoubleBuffering(_scoreEventsGrid);

            entitiesTabs.TabPages.Add(BuildTabPage("Clips", _clipsGrid));
            entitiesTabs.TabPages.Add(BuildTabPage("Polls", _pollsGrid));
            entitiesTabs.TabPages.Add(BuildTabPage("Tallies", _talliesGrid));
            entitiesTabs.TabPages.Add(BuildTabPage("Scoreboards", _scoreboardsGrid));

            signalsTabs.TabPages.Add(BuildTabPage("Chat trigger events", _chatEventsGrid));
            signalsTabs.TabPages.Add(BuildTabPage("Poll votes", _pollVotesGrid));
            signalsTabs.TabPages.Add(BuildTabPage("Tally increments", _tallyEventsGrid));
            signalsTabs.TabPages.Add(BuildTabPage("Score updates", _scoreEventsGrid));

            layout.Controls.Add(noticeGroup, 0, 0);
            layout.Controls.Add(entitiesGroup, 0, 1);
            layout.Controls.Add(signalsGroup, 0, 2);

            panel.Controls.Add(layout);

            tabDataSignals.Controls.Clear();
            tabDataSignals.Controls.Add(panel);
        }

        private void InitializeSettingsTab()
        {
            tabSettings.Padding = new Padding(8);

            var panel = new Panel
            {
                Dock = DockStyle.Fill,
                AutoScroll = true
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Top,
                ColumnCount = 1,
                RowCount = 6,
                AutoSize = true,
                Padding = new Padding(8)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            var restartGroup = BuildSettingsGroup("Pending Changes / Restart Queue", out _settingsRestartSummary);
            var systemGroup = BuildSettingsGroup("System Settings", out _settingsSystemSummary);
            var pollingGroup = BuildSettingsGroup("Platform Polling State", out _settingsPollingSummary);
            var discordGroup = BuildDiscordConfigGroup();

            var platformGroup = new GroupBox
            {
                Text = "Global Platform Service Enable Flags",
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            var platformLayout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 2,
                AutoSize = true
            };

            var platformNote = new Label
            {
                Text = "Read-only view. Runtime remains authoritative; enable changes require restart.",
                AutoSize = true,
                ForeColor = SystemColors.GrayText
            };

            _settingsPlatformGrid = BuildDataSignalsGrid();
            _settingsPlatformGrid.Height = 200;
            _settingsPlatformGrid.Columns.Add(BuildTextColumn(nameof(PlatformFlagRow.Platform), "Platform", 140));
            _settingsPlatformGrid.Columns.Add(BuildTextColumn(nameof(PlatformFlagRow.Enabled), "Enabled", 90));
            _settingsPlatformGrid.Columns.Add(BuildTextColumn(nameof(PlatformFlagRow.State), "Runtime State", 140));
            _settingsPlatformGrid.Columns.Add(BuildTextColumn(nameof(PlatformFlagRow.Notes), "Notes", 240));
            _settingsPlatformGrid.DataSource = _platformFlagsBindingSource;
            EnableDoubleBuffering(_settingsPlatformGrid);

            platformLayout.Controls.Add(platformNote, 0, 0);
            platformLayout.Controls.Add(_settingsPlatformGrid, 0, 1);

            platformGroup.Controls.Add(platformLayout);

            var importGroup = new GroupBox
            {
                Text = "Configuration Import / Export",
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            var importLayout = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false
            };

            var btnExport = new Button
            {
                Text = "Export Config (placeholder)",
                AutoSize = true,
                Enabled = false
            };

            var btnImport = new Button
            {
                Text = "Import Config (placeholder)",
                AutoSize = true,
                Enabled = false
            };

            _settingsImportExportSummary = new Label
            {
                Text = "Runtime-authoritative exports are read-only in this dashboard.",
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(12, 6, 0, 0)
            };

            importLayout.Controls.Add(btnExport);
            importLayout.Controls.Add(btnImport);
            importLayout.Controls.Add(_settingsImportExportSummary);

            importGroup.Controls.Add(importLayout);

            layout.Controls.Add(restartGroup, 0, 0);
            layout.Controls.Add(systemGroup, 0, 1);
            layout.Controls.Add(pollingGroup, 0, 2);
            layout.Controls.Add(platformGroup, 0, 3);
            layout.Controls.Add(discordGroup, 0, 4);
            layout.Controls.Add(importGroup, 0, 5);

            panel.Controls.Add(layout);

            tabSettings.Controls.Clear();
            tabSettings.Controls.Add(panel);
        }

        private static GroupBox BuildSettingsGroup(string title, out Label valueLabel)
        {
            var group = new GroupBox
            {
                Text = title,
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            valueLabel = new Label
            {
                AutoSize = true,
                Dock = DockStyle.Fill,
                Text = "—"
            };

            group.Controls.Add(valueLabel);
            return group;
        }

        private GroupBox BuildDiscordConfigGroup()
        {
            var group = new GroupBox
            {
                Text = "Discord Bot Configuration",
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 2,
                AutoSize = true
            };

            layout.ColumnStyles.Add(new ColumnStyle(SizeType.AutoSize));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));

            _discordGuildSelector = new ComboBox
            {
                DropDownStyle = ComboBoxStyle.DropDown,
                Width = 240,
                AutoCompleteMode = AutoCompleteMode.SuggestAppend,
                AutoCompleteSource = AutoCompleteSource.ListItems
            };

            _discordLoggingEnabledToggle = new CheckBox
            {
                Text = "Enabled",
                AutoSize = true
            };

            _discordLoggingChannelId = BuildDiscordChannelTextBox();
            _discordNotificationsGeneral = BuildDiscordChannelTextBox();
            _discordNotificationsRumble = BuildDiscordChannelTextBox();
            _discordNotificationsYoutube = BuildDiscordChannelTextBox();
            _discordNotificationsKick = BuildDiscordChannelTextBox();
            _discordNotificationsPilled = BuildDiscordChannelTextBox();
            _discordNotificationsTwitch = BuildDiscordChannelTextBox();

            _discordConfigSaveButton = new Button
            {
                Text = "Save Discord Bot Config",
                AutoSize = true
            };

            _discordConfigStatus = new Label
            {
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(8, 6, 0, 0)
            };

            AddDiscordConfigRow(layout, "Guild ID", _discordGuildSelector);
            AddDiscordConfigRow(layout, "Logging enabled", _discordLoggingEnabledToggle);
            AddDiscordConfigRow(layout, "Logging channel ID", _discordLoggingChannelId);
            AddDiscordConfigRow(layout, "General notifications channel", _discordNotificationsGeneral);
            AddDiscordConfigRow(layout, "Rumble clips channel", _discordNotificationsRumble);
            AddDiscordConfigRow(layout, "YouTube clips channel", _discordNotificationsYoutube);
            AddDiscordConfigRow(layout, "Kick clips channel", _discordNotificationsKick);
            AddDiscordConfigRow(layout, "Pilled clips channel", _discordNotificationsPilled);
            AddDiscordConfigRow(layout, "Twitch clips channel", _discordNotificationsTwitch);

            var actions = new FlowLayoutPanel
            {
                Dock = DockStyle.Fill,
                AutoSize = true,
                FlowDirection = FlowDirection.LeftToRight,
                WrapContents = false,
                Padding = new Padding(0, 6, 0, 0)
            };
            actions.Controls.Add(_discordConfigSaveButton);
            actions.Controls.Add(_discordConfigStatus);

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.Controls.Add(actions, 0, layout.RowStyles.Count - 1);
            layout.SetColumnSpan(actions, 2);

            group.Controls.Add(layout);

            _discordGuildSelector.SelectedIndexChanged += (_, __) => ApplyDiscordGuildSelection();
            _discordGuildSelector.Leave += (_, __) => ApplyDiscordGuildSelection();
            _discordConfigSaveButton.Click += async (_, __) => await SaveDiscordConfigAsync();

            return group;
        }

        private static TextBox BuildDiscordChannelTextBox()
        {
            return new TextBox
            {
                Width = 240,
                PlaceholderText = "Not set"
            };
        }

        private static void AddDiscordConfigRow(
            TableLayoutPanel layout,
            string labelText,
            Control control)
        {
            var label = new Label
            {
                Text = labelText,
                AutoSize = true,
                TextAlign = ContentAlignment.MiddleLeft,
                Padding = new Padding(0, 6, 8, 0)
            };

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            var rowIndex = layout.RowStyles.Count - 1;
            layout.Controls.Add(label, 0, rowIndex);
            layout.Controls.Add(control, 1, rowIndex);
        }

        private static GroupBox BuildDataSignalsGroup(string title, out TabControl tabs)
        {
            var group = new GroupBox
            {
                Text = title,
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            tabs = new TabControl
            {
                Dock = DockStyle.Top,
                Height = 260
            };

            group.Controls.Add(tabs);
            return group;
        }

        private static TabPage BuildTabPage(string title, Control content)
        {
            var tab = new TabPage
            {
                Text = title,
                Padding = new Padding(8)
            };

            content.Dock = DockStyle.Fill;
            tab.Controls.Add(content);
            return tab;
        }

        private static DataGridView BuildDataSignalsGrid()
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
                Height = 200
            };

            return grid;
        }

        private static DataGridViewTextBoxColumn BuildTextColumn(
            string propertyName,
            string headerText,
            int minWidth)
        {
            return new DataGridViewTextBoxColumn
            {
                DataPropertyName = propertyName,
                HeaderText = headerText,
                MinimumWidth = minWidth
            };
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
                var tab = tabMain.TabPages.Cast<TabPage>()
                    .FirstOrDefault(existing =>
                        string.Equals(existing.Text, platform, StringComparison.OrdinalIgnoreCase));

                if (tab == null)
                {
                    tab = new TabPage();
                    tabMain.TabPages.Add(tab);
                }

                tab.Text = platform;
                tab.Padding = new Padding(8);
                tab.Controls.Clear();

                _platformTabControls[platform] = BuildPlatformTab(tab, platform);
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

        private PlatformTabControls BuildPlatformTab(TabPage tab, string platform)
        {
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

            var globalGroup = BuildPlatformGroup("Global Service Status", out var globalLayout);
            var runtimeGroup = BuildPlatformGroup("Runtime Connectivity", out var runtimeLayout);
            var localGroup = BuildPlatformGroup("Local Configuration", out var localLayout);
            var moduleGroup = BuildPlatformGroup("Module Status", out var moduleLayout);

            var globalEnabled = BuildValueRow(globalLayout, "Service Enabled");
            var globalTelemetry = BuildValueRow(globalLayout, "Telemetry Enabled");
            var globalPaused = BuildValueRow(globalLayout, "Paused");
            var globalNote = BuildNoteRow(globalLayout, "Read-only controls. Toggle intent requires restart.");

            var runtimeState = BuildValueRow(runtimeLayout, "Runtime State");
            var runtimeStatus = BuildValueRow(runtimeLayout, "Status");
            var runtimeHeartbeat = BuildValueRow(runtimeLayout, "Last Heartbeat");
            var runtimeEvent = BuildValueRow(runtimeLayout, "Last Event");
            var runtimeSuccess = BuildValueRow(runtimeLayout, "Last Success");
            var runtimeMessages = BuildValueRow(runtimeLayout, "Messages Processed");
            var runtimeTriggers = BuildValueRow(runtimeLayout, "Triggers Fired");
            var runtimeActions = BuildValueRow(runtimeLayout, "Actions");
            var runtimeErrors = BuildValueRow(runtimeLayout, "Last Error");
            var runtimeNote = BuildNoteRow(runtimeLayout, "Runtime snapshots only; no live control.");

            var localCreators = BuildValueRow(localLayout, "Enabled Creators");
            var localCreatorList = BuildValueRow(localLayout, "Creator IDs");
            var localSource = BuildValueRow(localLayout, "Source");
            var localNote = BuildNoteRow(localLayout, "Local configs derived from creator exports.");

            var moduleStatus = BuildValueRow(moduleLayout, "Module Status");
            var moduleMode = BuildValueRow(moduleLayout, "Mode");
            var moduleReplay = BuildValueRow(moduleLayout, "Replay Supported");
            var moduleOverlay = BuildValueRow(moduleLayout, "Overlay Supported");
            var moduleNotes = BuildValueRow(moduleLayout, "Notes");
            var moduleNote = BuildNoteRow(moduleLayout, "Scaffolded modules remain read-only.");

            layout.Controls.Add(globalGroup, 0, 0);
            layout.Controls.Add(runtimeGroup, 0, 1);
            layout.Controls.Add(localGroup, 0, 2);
            layout.Controls.Add(moduleGroup, 0, 3);

            panel.Controls.Add(layout);
            tab.Controls.Add(panel);

            return new PlatformTabControls(
                platform,
                globalEnabled,
                globalTelemetry,
                globalPaused,
                globalNote,
                runtimeState,
                runtimeStatus,
                runtimeHeartbeat,
                runtimeEvent,
                runtimeSuccess,
                runtimeMessages,
                runtimeTriggers,
                runtimeActions,
                runtimeErrors,
                runtimeNote,
                localCreators,
                localCreatorList,
                localSource,
                localNote,
                moduleStatus,
                moduleMode,
                moduleReplay,
                moduleOverlay,
                moduleNotes,
                moduleNote);
        }

        private static GroupBox BuildPlatformGroup(string title, out TableLayoutPanel layout)
        {
            var group = new GroupBox
            {
                Text = title,
                Dock = DockStyle.Top,
                AutoSize = true,
                Padding = new Padding(8)
            };

            layout = new TableLayoutPanel
            {
                Dock = DockStyle.Top,
                ColumnCount = 2,
                RowCount = 0,
                AutoSize = true
            };

            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 160f));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));

            group.Controls.Add(layout);
            return group;
        }

        private static Label BuildValueRow(TableLayoutPanel layout, string label)
        {
            var rowIndex = layout.RowCount++;
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            var nameLabel = new Label
            {
                Text = label,
                AutoSize = true,
                Font = new Font("Segoe UI", 9F, FontStyle.Bold)
            };

            var valueLabel = new Label
            {
                Text = "—",
                AutoSize = true
            };

            layout.Controls.Add(nameLabel, 0, rowIndex);
            layout.Controls.Add(valueLabel, 1, rowIndex);
            return valueLabel;
        }

        private static Label BuildNoteRow(TableLayoutPanel layout, string text)
        {
            var rowIndex = layout.RowCount++;
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            var noteLabel = new Label
            {
                Text = text,
                AutoSize = true,
                ForeColor = SystemColors.GrayText,
                Padding = new Padding(0, 6, 0, 0)
            };

            layout.Controls.Add(noteLabel, 0, rowIndex);
            layout.SetColumnSpan(noteLabel, 2);
            return noteLabel;
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

            RefreshRuntimeVersionInfo();
            var appName = BuildAboutApplicationName(about);
            using var dialog = new AboutDialog(appName, about, _runtimeVersionInfo);
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

            RefreshRuntimeVersionInfo();

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
                    ClearCreatorsData();
                    ClearDataSignals();
                    ClearChatTriggers();
                    ClearSettingsData();
                    ClearPlatformTabs();
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
                var creatorConfig = await LoadCreatorConfigAsync()
                    .ConfigureAwait(true);
                var adminCreators = await LoadAdminCreatorsAsync()
                    .ConfigureAwait(true);
                var platformExport = await LoadPlatformsExportAsync()
                    .ConfigureAwait(true);
                UpdateCreatorsData(snapshot, creatorConfig, adminCreators);
                await RefreshDataSignalsAsync(_currentPathStatus.SnapshotRoot)
                    .ConfigureAwait(true);
                await RefreshChatTriggersAsync(_currentPathStatus.SnapshotRoot)
                    .ConfigureAwait(true);
                await RefreshDiscordConfigAsync()
                    .ConfigureAwait(true);
                UpdateSettingsData(snapshot);
                UpdatePlatformTabs(snapshot, creatorConfig, platformExport);
                UpdateUpdatesSummary();
                UpdateAboutSummary();

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
                ClearCreatorsData();
                ClearDataSignals();
                ClearChatTriggers();
                ClearSettingsData();
                ClearPlatformTabs();
                UpdatePlatformActionButtons(null);
            }
            finally
            {
                _refreshInProgress = false;
            }
        }

        private void HandleInvalidSnapshotPath(SnapshotPathStatus pathStatus)
        {
            var message = pathStatus?.Message ?? string.Empty;
            var label = string.IsNullOrWhiteSpace(message)
                ? "Snapshot: path not configured"
                : $"Snapshot: {message}";

            UpdateSnapshotStatus(label);
            ApplySnapshotHealthStyle(SnapshotHealthState.Invalid);
            UpdateTrayIconHealth(SnapshotHealthState.Invalid);
            UpdateSnapshotHealthIndicators(SnapshotHealthState.Invalid);
            SetSnapshotTooltip(null, message);
            UpdatePlatformCount("Platforms: unknown");
            _platformBindingSource.DataSource = null;
            UpdateStatusRuntime("Runtime: disconnected");
            _lastSuccessfulRefreshUtc = null;
            lblLastRefresh.Text = "Last refresh: —";
            ClearJobData();
            ClearTelemetryData();
            ClearCreatorsData();
            ClearDataSignals();
            ClearChatTriggers();
            ClearSettingsData();
            ClearPlatformTabs();
            UpdatePlatformActionButtons(null);
        }

        private SnapshotPathStatus RefreshSnapshotPathStatus()
        {
            _currentPathStatus = _pathConfigService
                .ValidateSnapshotRoot(txtSnapshotPath.Text);

            UpdatePathTabStatus(_currentPathStatus);
            RefreshRuntimeVersionInfo();
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
            UpdateRateLimitsSummary(ratesExport);
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

            if (_rateLimitsSummary != null)
            {
                _rateLimitsSummary.Text = "Rate limits: —";
            }

            ForceControlRefresh(tabTelemetry);
            if (_tabRateLimits != null)
                ForceControlRefresh(_tabRateLimits);
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

        private void UpdateRateLimitsSummary(TelemetryRatesExport? ratesExport)
        {
            if (_rateLimitsSummary == null)
                return;

            var windowCount = ratesExport?.Windows?.Count ?? 0;
            var generated = ratesExport?.Generated_At ?? "—";

            _rateLimitsSummary.Text =
                $"Rate limits: {windowCount} windows • Updated {generated}";
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

        // -----------------------------------------------------------------
        // Creators
        // -----------------------------------------------------------------

        private void CreatorsGrid_SelectionChanged(object? sender, EventArgs e)
        {
            if (_creatorsGrid.CurrentRow?.DataBoundItem is CreatorRow row)
            {
                UpdateCreatorDetails(row);
                return;
            }

            UpdateCreatorDetails(null);
        }

        private async Task<CreatorConfigExport?> LoadCreatorConfigAsync()
        {
            var configPath = ResolveSnapshotPath("shared", "config", "creators.json");
            return await _exportReader.TryReadAsync<CreatorConfigExport>(configPath ?? string.Empty)
                .ConfigureAwait(true);
        }

        private async Task<AdminCreatorsExport?> LoadAdminCreatorsAsync()
        {
            var adminPath = ResolveSnapshotPath("admin", "creators.json");
            return await _exportReader.TryReadAsync<AdminCreatorsExport>(adminPath ?? string.Empty)
                .ConfigureAwait(true);
        }

        private async Task<PlatformsExport?> LoadPlatformsExportAsync()
        {
            var platformsPath = ResolveSnapshotPath("platforms.json");
            return await _exportReader.TryReadAsync<PlatformsExport>(platformsPath ?? string.Empty)
                .ConfigureAwait(true);
        }

        private void UpdateCreatorsData(
            RuntimeSnapshot snapshot,
            CreatorConfigExport? creatorConfig,
            AdminCreatorsExport? adminCreators)
        {
            var snapshotCreators = snapshot.Creators ?? new List<CreatorStatus>();
            var rows = BuildCreatorRows(snapshotCreators, creatorConfig, adminCreators);

            _creatorsBindingSource.DataSource = rows;
            _creatorsSummary.Text =
                $"Creators: {rows.Count} • Runtime snapshot: {snapshotCreators.Count}";

            SelectFirstCreatorRow();
            ForceControlRefresh(tabCreators);
        }

        private void ClearCreatorsData()
        {
            _creatorsBindingSource.DataSource = null;
            if (_creatorsSummary != null)
            {
                _creatorsSummary.Text = "Creators: —";
            }

            UpdateCreatorDetails(null);
            ForceControlRefresh(tabCreators);
        }

        private void SelectFirstCreatorRow()
        {
            if (_creatorsGrid == null || _creatorsGrid.Rows.Count == 0)
                return;

            _creatorsGrid.ClearSelection();
            _creatorsGrid.CurrentCell = _creatorsGrid.Rows[0].Cells[0];
            _creatorsGrid.Rows[0].Selected = true;
        }

        private void UpdateCreatorDetails(CreatorRow? row)
        {
            if (_creatorDetails == null)
                return;

            if (row == null)
            {
                _creatorDetails.Text = "Select a creator to view details.";
                return;
            }

            var platforms = string.IsNullOrWhiteSpace(row.PlatformsEnabled)
                ? "—"
                : row.PlatformsEnabled;

            var notes = string.IsNullOrWhiteSpace(row.Notes)
                ? "—"
                : row.Notes;

            _creatorDetails.Text =
                $"Creator ID: {row.CreatorId}\n" +
                $"Display Name: {row.DisplayName}\n" +
                $"Status: {row.Status}\n" +
                $"Enabled: {(row.Enabled ? "Yes" : "No")}\n" +
                $"Platforms: {platforms}\n" +
                $"Last Heartbeat: {row.LastHeartbeat ?? "—"}\n" +
                $"Error: {row.Error ?? "None"}\n" +
                $"Notes: {notes}\n" +
                $"Sources: {row.SourceSummary}";
        }

        private static List<CreatorRow> BuildCreatorRows(
            IList<CreatorStatus> snapshotCreators,
            CreatorConfigExport? creatorConfig,
            AdminCreatorsExport? adminCreators)
        {
            var rows = new List<CreatorRow>();
            var creatorMap = new Dictionary<string, CreatorRow>(StringComparer.OrdinalIgnoreCase);

            void EnsureRow(string creatorId)
            {
                if (string.IsNullOrWhiteSpace(creatorId))
                    return;

                if (creatorMap.ContainsKey(creatorId))
                    return;

                var row = new CreatorRow
                {
                    CreatorId = creatorId,
                    DisplayName = creatorId,
                    PlatformsEnabled = "—",
                    Status = "Unknown",
                    Notes = "—",
                    SourceSummary = "—"
                };

                creatorMap[creatorId] = row;
                rows.Add(row);
            }

            if (creatorConfig?.Creators != null)
            {
                foreach (var creator in creatorConfig.Creators)
                {
                    EnsureRow(creator.Creator_Id);
                    var row = creatorMap[creator.Creator_Id];
                    row.DisplayName = string.IsNullOrWhiteSpace(creator.Display_Name)
                        ? row.DisplayName
                        : creator.Display_Name;
                    row.Notes = string.IsNullOrWhiteSpace(creator.Notes)
                        ? row.Notes
                        : creator.Notes;
                    row.ConfigPlatforms = creator.Platforms ?? new Dictionary<string, bool>();
                    row.Enabled = creator.Enabled;
                    row.SourceSummary = MergeSources(row.SourceSummary, "shared/config/creators.json");
                }
            }

            if (adminCreators?.Creators != null)
            {
                foreach (var creator in adminCreators.Creators)
                {
                    EnsureRow(creator.Creator_Id);
                    var row = creatorMap[creator.Creator_Id];
                    row.DisplayName = string.IsNullOrWhiteSpace(creator.Display_Name)
                        ? row.DisplayName
                        : creator.Display_Name;
                    row.AdminPlatforms = creator.Platforms ?? new Dictionary<string, AdminPlatformState>();
                    row.Notes = string.IsNullOrWhiteSpace(creator.Notes)
                        ? row.Notes
                        : creator.Notes;
                    row.SourceSummary = MergeSources(row.SourceSummary, "runtime/admin/creators.json");
                }
            }

            if (snapshotCreators != null)
            {
                foreach (var creator in snapshotCreators)
                {
                    EnsureRow(creator.Creator_Id);
                    var row = creatorMap[creator.Creator_Id];
                    row.DisplayName = string.IsNullOrWhiteSpace(creator.Display_Name)
                        ? row.DisplayName
                        : creator.Display_Name;
                    row.Enabled = creator.Enabled;
                    row.SnapshotPlatforms = creator.Platforms ?? new Dictionary<string, bool>();
                    row.LastHeartbeat = creator.Last_Heartbeat;
                    row.Error = creator.Error;
                    row.Status = BuildCreatorStatus(creator.Enabled, creator.Error);
                    row.SourceSummary = MergeSources(row.SourceSummary, "runtime_snapshot.json");
                }
            }

            foreach (var row in rows)
            {
                var platformList = BuildCreatorPlatformList(row);
                row.PlatformsEnabled = string.IsNullOrWhiteSpace(platformList)
                    ? "—"
                    : platformList;

                if (row.Status == "Unknown")
                {
                    row.Status = row.Enabled ? "Active" : "Registered";
                }
            }

            return rows
                .OrderBy(r => r.CreatorId, StringComparer.OrdinalIgnoreCase)
                .ToList();
        }

        private static string BuildCreatorStatus(bool enabled, string? error)
        {
            if (!string.IsNullOrWhiteSpace(error))
                return "Error";

            return enabled ? "Active" : "Disabled";
        }

        private static string BuildCreatorPlatformList(CreatorRow row)
        {
            var platforms = new Dictionary<string, bool>(StringComparer.OrdinalIgnoreCase);

            foreach (var entry in row.ConfigPlatforms)
            {
                platforms[entry.Key] = entry.Value;
            }

            foreach (var entry in row.AdminPlatforms)
            {
                platforms[entry.Key] = entry.Value?.Enabled ?? false;
            }

            foreach (var entry in row.SnapshotPlatforms)
            {
                platforms[entry.Key] = entry.Value;
            }

            var enabledPlatforms = platforms
                .Where(p => p.Value)
                .Select(p => ToTitleCase(p.Key))
                .OrderBy(p => p, StringComparer.OrdinalIgnoreCase)
                .ToList();

            return enabledPlatforms.Count == 0
                ? string.Empty
                : string.Join(", ", enabledPlatforms);
        }

        private static string MergeSources(string existing, string source)
        {
            if (string.IsNullOrWhiteSpace(existing) || existing == "—")
            {
                return source;
            }

            if (existing.Contains(source, StringComparison.OrdinalIgnoreCase))
            {
                return existing;
            }

            return $"{existing}, {source}";
        }

        // -----------------------------------------------------------------
        // Data & Signals
        // -----------------------------------------------------------------

        private async Task RefreshDataSignalsAsync(string? snapshotRoot)
        {
            if (string.IsNullOrWhiteSpace(snapshotRoot) || !Directory.Exists(snapshotRoot))
            {
                ClearDataSignals();
                return;
            }

            var clipsPath = ResolveSnapshotPath("clips.json");
            var pollsPath = ResolveSnapshotPath("polls.json");
            var talliesPath = ResolveSnapshotPath("tallies.json");
            var scoreboardsPath = ResolveSnapshotPath("scoreboards.json");

            var chatEventsPath = ResolveSnapshotPath("signals", "chat_events.json");
            var pollVotesPath = ResolveSnapshotPath("signals", "poll_votes.json");
            var tallyEventsPath = ResolveSnapshotPath("signals", "tally_events.json");
            var scoreEventsPath = ResolveSnapshotPath("signals", "score_events.json");

            var clipsExport = await _exportReader
                .TryReadAsync<ClipsExport>(clipsPath ?? string.Empty)
                .ConfigureAwait(true);
            var pollsExport = await _exportReader
                .TryReadAsync<PollsExport>(pollsPath ?? string.Empty)
                .ConfigureAwait(true);
            var talliesExport = await _exportReader
                .TryReadAsync<TalliesExport>(talliesPath ?? string.Empty)
                .ConfigureAwait(true);
            var scoreboardsExport = await _exportReader
                .TryReadAsync<ScoreboardsExport>(scoreboardsPath ?? string.Empty)
                .ConfigureAwait(true);

            var chatExport = await _exportReader
                .TryReadAsync<ChatEventsExport>(chatEventsPath ?? string.Empty)
                .ConfigureAwait(true);
            var pollVotesExport = await _exportReader
                .TryReadAsync<PollVotesExport>(pollVotesPath ?? string.Empty)
                .ConfigureAwait(true);
            var tallyEventsExport = await _exportReader
                .TryReadAsync<TallyEventsExport>(tallyEventsPath ?? string.Empty)
                .ConfigureAwait(true);
            var scoreEventsExport = await _exportReader
                .TryReadAsync<ScoreEventsExport>(scoreEventsPath ?? string.Empty)
                .ConfigureAwait(true);

            _clipsBindingSource.DataSource = clipsExport?.Clips?
                .Select(clip => new ClipRow
                {
                    ClipId = clip.Clip_Id,
                    Title = clip.Title,
                    Creator = clip.Creator,
                    State = clip.State,
                    PublishedAt = clip.Published_At ?? "—",
                    Duration = clip.Duration_Seconds > 0
                        ? $"{clip.Duration_Seconds}s"
                        : "—"
                })
                .OrderByDescending(row => ParseTimestamp(row.PublishedAt))
                .ToList();

            _pollsBindingSource.DataSource = pollsExport?.Polls?
                .Select(poll => new PollRow
                {
                    PollId = poll.Poll_Id,
                    Question = poll.Question,
                    Creator = poll.Creator,
                    State = poll.State,
                    OpenedAt = poll.Opened_At ?? "—",
                    ClosedAt = poll.Closed_At ?? "—",
                    OptionsSummary = BuildPollOptionsSummary(poll.Options)
                })
                .OrderByDescending(row => ParseTimestamp(row.OpenedAt))
                .ToList();

            _talliesBindingSource.DataSource = talliesExport?.Tallies?
                .Select(tally => new TallyRow
                {
                    TallyId = tally.Tally_Id,
                    Label = tally.Label,
                    Creator = tally.Creator,
                    Count = tally.Count,
                    UpdatedAt = tally.Last_Updated_At ?? "—"
                })
                .OrderByDescending(row => ParseTimestamp(row.UpdatedAt))
                .ToList();

            _scoreboardsBindingSource.DataSource = scoreboardsExport?.Scoreboards?
                .Select(scoreboard => new ScoreboardRow
                {
                    ScoreboardId = scoreboard.Scoreboard_Id,
                    Title = scoreboard.Title,
                    Creator = scoreboard.Creator,
                    Entries = scoreboard.Entries?.Count ?? 0,
                    FinalizedAt = scoreboard.Finalized_At ?? "—"
                })
                .OrderByDescending(row => ParseTimestamp(row.FinalizedAt))
                .ToList();

            _chatEventsBindingSource.DataSource = chatExport?.Events?
                .Select(evt => new ChatEventRow
                {
                    Timestamp = evt.Message_At ?? "—",
                    Creator = evt.Creator,
                    Platform = ToTitleCase(evt.Platform),
                    Username = evt.Username,
                    Message = evt.Message
                })
                .OrderByDescending(row => ParseTimestamp(row.Timestamp))
                .ToList();

            _pollVotesBindingSource.DataSource = pollVotesExport?.Votes?
                .Select(vote => new PollVoteRow
                {
                    Timestamp = vote.Voted_At ?? "—",
                    PollId = vote.Poll_Id,
                    OptionId = vote.Option_Id,
                    Creator = vote.Creator,
                    VoterId = vote.Voter_Id
                })
                .OrderByDescending(row => ParseTimestamp(row.Timestamp))
                .ToList();

            _tallyEventsBindingSource.DataSource = tallyEventsExport?.Events?
                .Select(evt => new TallyEventRow
                {
                    Timestamp = evt.Updated_At ?? "—",
                    TallyId = evt.Tally_Id,
                    Creator = evt.Creator,
                    Delta = evt.Delta
                })
                .OrderByDescending(row => ParseTimestamp(row.Timestamp))
                .ToList();

            _scoreEventsBindingSource.DataSource = scoreEventsExport?.Events?
                .Select(evt => new ScoreEventRow
                {
                    Timestamp = evt.Scored_At ?? "—",
                    ScoreboardId = evt.Scoreboard_Id,
                    Creator = evt.Creator,
                    Label = evt.Label,
                    ScoreDelta = evt.Score_Delta
                })
                .OrderByDescending(row => ParseTimestamp(row.Timestamp))
                .ToList();

            UpdateDataSignalsSummary(clipsExport, pollsExport, talliesExport, scoreboardsExport,
                chatExport, pollVotesExport, tallyEventsExport, scoreEventsExport);

            ForceControlRefresh(tabDataSignals);
        }

        private async Task RefreshChatTriggersAsync(string? snapshotRoot)
        {
            if (string.IsNullOrWhiteSpace(snapshotRoot) || !Directory.Exists(snapshotRoot))
            {
                ClearChatTriggers();
                return;
            }

            var triggersPath = ResolveAdminExportPath("chat_triggers.json");
            if (string.IsNullOrWhiteSpace(triggersPath))
            {
                ClearChatTriggers();
                return;
            }

            var triggersExport = await _exportReader
                .TryReadAsync<ChatTriggersExport>(triggersPath)
                .ConfigureAwait(true);

            if (triggersExport == null)
            {
                ClearChatTriggers();
                return;
            }

            _chatTriggersBindingSource.DataSource =
                triggersExport.Triggers.Select(trigger => new ChatTriggerRow
                {
                    TriggerId = trigger.Trigger_Id,
                    Creator = trigger.Creator,
                    Type = trigger.Type,
                    Command = trigger.Command,
                    CooldownSeconds = trigger.Cooldown_Seconds,
                    Description = trigger.Description,
                    UpdatedAt = trigger.Updated_At ?? "—"
                }).OrderBy(row => row.Command).ToList();

            UpdateChatTriggersSummary(triggersExport);

            if (_tabChatTriggers != null)
                ForceControlRefresh(_tabChatTriggers);
        }

        private void ClearDataSignals()
        {
            _clipsBindingSource.DataSource = null;
            _pollsBindingSource.DataSource = null;
            _talliesBindingSource.DataSource = null;
            _scoreboardsBindingSource.DataSource = null;
            _chatEventsBindingSource.DataSource = null;
            _pollVotesBindingSource.DataSource = null;
            _tallyEventsBindingSource.DataSource = null;
            _scoreEventsBindingSource.DataSource = null;

            if (_dataSignalsSummary != null)
            {
                _dataSignalsSummary.Text =
                    "Runtime exports provide read-only observability for entities and signals.";
            }

            if (_clipsSummary != null)
                _clipsSummary.Text = "Clips: —";
            if (_pollsSummary != null)
                _pollsSummary.Text = "Polls: —";
            if (_talliesSummary != null)
                _talliesSummary.Text = "Tallies: —";
            if (_scoreboardsSummary != null)
                _scoreboardsSummary.Text = "Scoreboards: —";
            if (_chatReplaySummary != null)
                _chatReplaySummary.Text = "Chat replay: —";

            ForceControlRefresh(tabDataSignals);
        }

        private void ClearChatTriggers()
        {
            _chatTriggersBindingSource.DataSource = null;

            if (_chatTriggersSummary != null)
            {
                _chatTriggersSummary.Text = "Chat triggers: —";
            }

            if (_tabChatTriggers != null)
                ForceControlRefresh(_tabChatTriggers);
        }

        private void UpdateDataSignalsSummary(
            ClipsExport? clipsExport,
            PollsExport? pollsExport,
            TalliesExport? talliesExport,
            ScoreboardsExport? scoreboardsExport,
            ChatEventsExport? chatExport,
            PollVotesExport? pollVotesExport,
            TallyEventsExport? tallyEventsExport,
            ScoreEventsExport? scoreEventsExport)
        {
            if (_dataSignalsSummary == null)
                return;

            var entityCount =
                (clipsExport?.Clips?.Count ?? 0) +
                (pollsExport?.Polls?.Count ?? 0) +
                (talliesExport?.Tallies?.Count ?? 0) +
                (scoreboardsExport?.Scoreboards?.Count ?? 0);

            var signalCount =
                (chatExport?.Events?.Count ?? 0) +
                (pollVotesExport?.Votes?.Count ?? 0) +
                (tallyEventsExport?.Events?.Count ?? 0) +
                (scoreEventsExport?.Events?.Count ?? 0);

            var updatedAt =
                GetMetaTimestamp(clipsExport?.Meta) ??
                GetMetaTimestamp(pollsExport?.Meta) ??
                GetMetaTimestamp(talliesExport?.Meta) ??
                GetMetaTimestamp(scoreboardsExport?.Meta) ??
                GetMetaTimestamp(chatExport?.Meta) ??
                GetMetaTimestamp(pollVotesExport?.Meta) ??
                GetMetaTimestamp(tallyEventsExport?.Meta) ??
                GetMetaTimestamp(scoreEventsExport?.Meta) ??
                "—";

            _dataSignalsSummary.Text =
                $"Runtime exports: {entityCount} entities • {signalCount} signals • Updated {updatedAt}";

            UpdateEntitySummaries(clipsExport, pollsExport, talliesExport, scoreboardsExport, chatExport);
        }

        private void UpdateEntitySummaries(
            ClipsExport? clipsExport,
            PollsExport? pollsExport,
            TalliesExport? talliesExport,
            ScoreboardsExport? scoreboardsExport,
            ChatEventsExport? chatExport)
        {
            if (_clipsSummary != null)
            {
                _clipsSummary.Text =
                    $"Clips: {clipsExport?.Clips?.Count ?? 0}";
            }

            if (_pollsSummary != null)
            {
                _pollsSummary.Text =
                    $"Polls: {pollsExport?.Polls?.Count ?? 0}";
            }

            if (_talliesSummary != null)
            {
                _talliesSummary.Text =
                    $"Tallies: {talliesExport?.Tallies?.Count ?? 0}";
            }

            if (_scoreboardsSummary != null)
            {
                _scoreboardsSummary.Text =
                    $"Scoreboards: {scoreboardsExport?.Scoreboards?.Count ?? 0}";
            }

            if (_chatReplaySummary != null)
            {
                _chatReplaySummary.Text =
                    $"Chat replay events: {chatExport?.Events?.Count ?? 0}";
            }
        }

        private void UpdateChatTriggersSummary(ChatTriggersExport? triggersExport)
        {
            if (_chatTriggersSummary == null)
                return;

            var updatedAt = GetMetaTimestamp(triggersExport?.Meta) ?? "—";

            _chatTriggersSummary.Text =
                $"Chat triggers: {triggersExport?.Triggers?.Count ?? 0} • Updated {updatedAt}";
        }

        private static string BuildPollOptionsSummary(List<PollOptionExport>? options)
        {
            if (options == null || options.Count == 0)
                return "—";

            return string.Join(", ",
                options.Select(option => $"{option.Label} ({option.Votes})"));
        }

        private static string? GetMetaTimestamp(AdminExportMeta? meta)
        {
            if (meta == null)
                return null;

            if (!string.IsNullOrWhiteSpace(meta.Generated_At))
                return meta.Generated_At;

            if (!string.IsNullOrWhiteSpace(meta.Captured_At))
                return meta.Captured_At;

            return null;
        }

        private static DateTime ParseTimestamp(string? value)
        {
            if (string.IsNullOrWhiteSpace(value) || value == "—")
                return DateTime.MinValue;

            return DateTime.TryParse(value, out var parsed)
                ? parsed
                : DateTime.MinValue;
        }

        // -----------------------------------------------------------------
        // Settings
        // -----------------------------------------------------------------

        private void UpdateSettingsData(RuntimeSnapshot snapshot)
        {
            var restart = snapshot.Restart_Intent;
            var pending = restart?.Pending;

            _settingsRestartSummary.Text =
                $"Restart required: {(restart?.Required == true ? "Yes" : "No")} • " +
                $"Pending sections: " +
                $"System {(pending?.System == true ? "Yes" : "No")}, " +
                $"Creators {(pending?.Creators == true ? "Yes" : "No")}, " +
                $"Triggers {(pending?.Triggers == true ? "Yes" : "No")}, " +
                $"Platforms {(pending?.Platforms == true ? "Yes" : "No")}.";

            var hotReload = snapshot.System?.Hot_Reload;
            _settingsSystemSummary.Text =
                $"Hot reload: {(hotReload?.Enabled == true ? "Enabled" : "Disabled")} • " +
                $"Watch path: {hotReload?.Watch_Path ?? "—"} • " +
                $"Interval: {(hotReload?.Interval_Seconds ?? 0):0.##}s • " +
                $"Runtime {_runtimeVersionInfo.ToDisplayVersion()} • " +
                $"{_runtimeVersionInfo.ToDisplayBuild()}.";

            var polling = snapshot.System?.Platform_Polling_Enabled;
            _settingsPollingSummary.Text =
                $"Platform polling enabled: {(polling?.Enabled == true ? "Yes" : "No")} • " +
                "Runtime-authoritative; dashboard is read-only.";

            var platformFlags = new List<PlatformFlagRow>();
            var platformStates = snapshot.Platforms ?? new List<PlatformStatus>();

            if (snapshot.System?.Platforms != null)
            {
                foreach (var entry in snapshot.System.Platforms.OrderBy(k => k.Key))
                {
                    var status = platformStates.FirstOrDefault(p =>
                        string.Equals(p.Platform, entry.Key, StringComparison.OrdinalIgnoreCase));
                    platformFlags.Add(new PlatformFlagRow
                    {
                        Platform = ToTitleCase(entry.Key),
                        Enabled = entry.Value ? "Yes" : "No",
                        State = status?.Display_State ?? "—",
                        Notes = status?.Error ?? "—"
                    });
                }
            }

            _platformFlagsBindingSource.DataSource = platformFlags;
            ForceControlRefresh(tabSettings);
        }

        private void ClearSettingsData()
        {
            if (_settingsRestartSummary != null)
                _settingsRestartSummary.Text = "—";
            if (_settingsSystemSummary != null)
                _settingsSystemSummary.Text = "—";
            if (_settingsPollingSummary != null)
                _settingsPollingSummary.Text = "—";

            _platformFlagsBindingSource.DataSource = null;
            ClearDiscordConfigSection();
            ForceControlRefresh(tabSettings);
        }

        private async Task RefreshDiscordConfigAsync()
        {
            var configPath = ResolveSnapshotPath("shared", "config", "discord.json");
            var config = await _exportReader
                .TryReadAsync<DiscordConfigExport>(configPath ?? string.Empty)
                .ConfigureAwait(true);

            _discordConfigCache = config ?? new DiscordConfigExport();
            _discordConfigCache.Normalize();
            UpdateDiscordConfigStatus(configPath);
            UpdateDiscordGuildList();
            ApplyDiscordGuildSelection();
        }

        private void UpdateDiscordConfigStatus(string? configPath)
        {
            if (_discordConfigStatus == null)
                return;

            if (string.IsNullOrWhiteSpace(configPath))
            {
                _discordConfigStatus.Text = "discord.json not found; using defaults.";
                _discordConfigStatus.ForeColor = SystemColors.GrayText;
                return;
            }

            _discordConfigStatus.Text = $"Loaded from {configPath}";
            _discordConfigStatus.ForeColor = SystemColors.GrayText;
        }

        private void UpdateDiscordGuildList()
        {
            if (_discordGuildSelector == null)
                return;

            var current = _discordGuildSelector.Text;
            _discordGuildSelector.Items.Clear();

            foreach (var guildId in _discordConfigCache.Guilds.Keys
                         .OrderBy(id => id, StringComparer.OrdinalIgnoreCase))
            {
                _discordGuildSelector.Items.Add(guildId);
            }

            if (!string.IsNullOrWhiteSpace(current))
            {
                _discordGuildSelector.Text = current;
            }
        }

        private void ApplyDiscordGuildSelection()
        {
            if (_discordGuildSelector == null)
                return;

            var guildId = _discordGuildSelector.Text?.Trim();
            if (string.IsNullOrWhiteSpace(guildId))
            {
                ClearDiscordConfigSection();
                return;
            }

            if (_discordConfigCache.Guilds.TryGetValue(guildId, out var config))
            {
                _discordLoggingEnabledToggle.Checked = config.Logging.Enabled;
                _discordLoggingChannelId.Text = FormatChannelId(config.Logging.Channel_Id);
                _discordNotificationsGeneral.Text = FormatChannelId(config.Notifications.General);
                _discordNotificationsRumble.Text = FormatChannelId(config.Notifications.Rumble_Clips);
                _discordNotificationsYoutube.Text = FormatChannelId(config.Notifications.Youtube_Clips);
                _discordNotificationsKick.Text = FormatChannelId(config.Notifications.Kick_Clips);
                _discordNotificationsPilled.Text = FormatChannelId(config.Notifications.Pilled_Clips);
                _discordNotificationsTwitch.Text = FormatChannelId(config.Notifications.Twitch_Clips);
                return;
            }

            _discordLoggingEnabledToggle.Checked = false;
            _discordLoggingChannelId.Text = string.Empty;
            _discordNotificationsGeneral.Text = string.Empty;
            _discordNotificationsRumble.Text = string.Empty;
            _discordNotificationsYoutube.Text = string.Empty;
            _discordNotificationsKick.Text = string.Empty;
            _discordNotificationsPilled.Text = string.Empty;
            _discordNotificationsTwitch.Text = string.Empty;
        }

        private void ClearDiscordConfigSection()
        {
            if (_discordGuildSelector != null)
                _discordGuildSelector.Text = string.Empty;

            if (_discordLoggingEnabledToggle != null)
                _discordLoggingEnabledToggle.Checked = false;

            if (_discordLoggingChannelId != null)
                _discordLoggingChannelId.Text = string.Empty;
            if (_discordNotificationsGeneral != null)
                _discordNotificationsGeneral.Text = string.Empty;
            if (_discordNotificationsRumble != null)
                _discordNotificationsRumble.Text = string.Empty;
            if (_discordNotificationsYoutube != null)
                _discordNotificationsYoutube.Text = string.Empty;
            if (_discordNotificationsKick != null)
                _discordNotificationsKick.Text = string.Empty;
            if (_discordNotificationsPilled != null)
                _discordNotificationsPilled.Text = string.Empty;
            if (_discordNotificationsTwitch != null)
                _discordNotificationsTwitch.Text = string.Empty;

            if (_discordConfigStatus != null)
                _discordConfigStatus.Text = "Discord config not loaded.";
        }

        private static string FormatChannelId(string? value)
        {
            return string.IsNullOrWhiteSpace(value) ? string.Empty : value;
        }

        private static bool TryNormalizeChannelId(string? raw, out string? value)
        {
            value = null;
            if (string.IsNullOrWhiteSpace(raw))
                return true;

            var trimmed = raw.Trim();
            if (trimmed.All(char.IsDigit))
            {
                value = trimmed;
                return true;
            }

            return false;
        }

        private async Task SaveDiscordConfigAsync()
        {
            if (_discordGuildSelector == null)
                return;

            var guildId = _discordGuildSelector.Text?.Trim();
            if (string.IsNullOrWhiteSpace(guildId))
            {
                _discordConfigStatus.Text = "Enter a guild ID before saving.";
                _discordConfigStatus.ForeColor = Color.DarkRed;
                return;
            }

            if (!TryNormalizeChannelId(_discordLoggingChannelId.Text, out var loggingChannelId))
            {
                _discordConfigStatus.Text = "Logging channel ID must be numeric.";
                _discordConfigStatus.ForeColor = Color.DarkRed;
                return;
            }

            if (!TryNormalizeChannelId(_discordNotificationsGeneral.Text, out var generalId) ||
                !TryNormalizeChannelId(_discordNotificationsRumble.Text, out var rumbleId) ||
                !TryNormalizeChannelId(_discordNotificationsYoutube.Text, out var youtubeId) ||
                !TryNormalizeChannelId(_discordNotificationsKick.Text, out var kickId) ||
                !TryNormalizeChannelId(_discordNotificationsPilled.Text, out var pilledId) ||
                !TryNormalizeChannelId(_discordNotificationsTwitch.Text, out var twitchId))
            {
                _discordConfigStatus.Text = "Notification channel IDs must be numeric.";
                _discordConfigStatus.ForeColor = Color.DarkRed;
                return;
            }

            var entry = new DiscordGuildConfig
            {
                Logging = new DiscordLoggingConfig
                {
                    Enabled = _discordLoggingEnabledToggle.Checked,
                    Channel_Id = loggingChannelId
                },
                Notifications = new DiscordNotificationsConfig
                {
                    General = generalId,
                    Rumble_Clips = rumbleId,
                    Youtube_Clips = youtubeId,
                    Kick_Clips = kickId,
                    Pilled_Clips = pilledId,
                    Twitch_Clips = twitchId
                }
            };

            _discordConfigCache.Guilds[guildId] = entry;
            _discordConfigCache.Normalize();

            var writePath = ResolveConfigWritePath("shared", "config", "discord.json");
            if (string.IsNullOrWhiteSpace(writePath))
            {
                _discordConfigStatus.Text = "Unable to resolve config path.";
                _discordConfigStatus.ForeColor = Color.DarkRed;
                return;
            }

            var json = JsonSerializer.Serialize(
                _discordConfigCache,
                new JsonSerializerOptions { WriteIndented = true }
            );

            var directory = Path.GetDirectoryName(writePath);
            if (!string.IsNullOrWhiteSpace(directory))
            {
                Directory.CreateDirectory(directory);
            }

            await File.WriteAllTextAsync(writePath, json).ConfigureAwait(true);
            _discordConfigStatus.Text = $"Saved to {writePath}";
            _discordConfigStatus.ForeColor = SystemColors.GrayText;
            UpdateDiscordGuildList();
        }

        // -----------------------------------------------------------------
        // Platform tabs
        // -----------------------------------------------------------------

        private void UpdatePlatformTabs(
            RuntimeSnapshot snapshot,
            CreatorConfigExport? creatorConfig,
            PlatformsExport? platformsExport)
        {
            foreach (var entry in _platformTabControls)
            {
                var platformKey = entry.Key;
                var controls = entry.Value;
                var platformStatus = snapshot.Platforms?
                    .FirstOrDefault(p =>
                        string.Equals(p.Platform, platformKey, StringComparison.OrdinalIgnoreCase));
                var platformFlag = GetPlatformFlag(snapshot, platformKey);

                var moduleStatus = platformsExport?.Platforms?
                    .FirstOrDefault(p =>
                        string.Equals(p.Name, platformKey, StringComparison.OrdinalIgnoreCase));

                controls.GlobalEnabled.Text = platformFlag.HasValue
                    ? platformFlag.Value
                        ? "Yes"
                        : "No"
                    : "—";
                controls.GlobalTelemetry.Text = platformStatus?.Telemetry_Display ?? "—";
                controls.GlobalPaused.Text = platformStatus?.Paused == true ? "Yes" : "No";

                controls.RuntimeState.Text = platformStatus?.Display_State ?? "—";
                controls.RuntimeStatus.Text = platformStatus?.Status ?? "—";
                controls.RuntimeHeartbeat.Text = platformStatus?.Last_Heartbeat ?? "—";
                controls.RuntimeEvent.Text = platformStatus?.Last_Event_Ts ?? "—";
                controls.RuntimeSuccess.Text = platformStatus?.Last_Success_Ts ?? "—";
                controls.RuntimeMessages.Text = platformStatus == null
                    ? "—"
                    : platformStatus.Counters.Messages.ToString();
                controls.RuntimeTriggers.Text = platformStatus == null
                    ? "—"
                    : platformStatus.Counters.Triggers.ToString();
                controls.RuntimeActions.Text = platformStatus == null
                    ? "—"
                    : $"{platformStatus.Counters.Actions} (fail {platformStatus.Counters.Actions_Failed})";
                controls.RuntimeErrors.Text = platformStatus?.Error ?? "None";

                var creatorInfo = BuildCreatorConfigSummary(creatorConfig, platformKey);
                controls.LocalCreators.Text = creatorInfo.EnabledCountText;
                controls.LocalCreatorList.Text = creatorInfo.CreatorListText;
                controls.LocalSource.Text = creatorInfo.Source;

                if (moduleStatus != null)
                {
                    controls.ModuleStatus.Text = FormatModuleStatus(moduleStatus.Status);
                    controls.ModuleMode.Text = string.IsNullOrWhiteSpace(moduleStatus.Mode)
                        ? "—"
                        : moduleStatus.Mode;
                    controls.ModuleReplay.Text = moduleStatus.Replay_Supported ? "Yes" : "No";
                    controls.ModuleOverlay.Text = moduleStatus.Overlay_Supported ? "Yes" : "No";
                    controls.ModuleNotes.Text = moduleStatus.Notes ?? "—";
                }
                else
                {
                    controls.ModuleStatus.Text = "—";
                    controls.ModuleMode.Text = "—";
                    controls.ModuleReplay.Text = "—";
                    controls.ModuleOverlay.Text = "—";
                    controls.ModuleNotes.Text = "—";
                }
            }
        }

        private void ClearPlatformTabs()
        {
            foreach (var entry in _platformTabControls.Values)
            {
                entry.Reset();
            }
        }

        private CreatorConfigSummary BuildCreatorConfigSummary(
            CreatorConfigExport? creatorConfig,
            string platformKey)
        {
            var creators = creatorConfig?.Creators ?? new List<CreatorConfigEntry>();
            var enabledCreators = new List<string>();

            foreach (var creator in creators)
            {
                if (creator.Platforms != null &&
                    creator.Platforms.TryGetValue(platformKey.ToLowerInvariant(), out var enabled) &&
                    enabled)
                {
                    enabledCreators.Add(creator.Creator_Id);
                }
            }

            var enabledCount = enabledCreators.Count;
            var listText = enabledCount == 0
                ? "—"
                : string.Join(", ", enabledCreators.OrderBy(c => c, StringComparer.OrdinalIgnoreCase));

            return new CreatorConfigSummary
            {
                EnabledCountText = enabledCount == 0 ? "0" : enabledCount.ToString(),
                CreatorListText = listText,
                Source = creatorConfig?.Creators?.Count > 0
                    ? "shared/config/creators.json"
                    : "—"
            };
        }

        private static bool? GetPlatformFlag(RuntimeSnapshot snapshot, string platformKey)
        {
            if (snapshot.System?.Platforms == null)
                return null;

            foreach (var entry in snapshot.System.Platforms)
            {
                if (string.Equals(entry.Key, platformKey, StringComparison.OrdinalIgnoreCase))
                    return entry.Value;
            }

            return null;
        }

        private static string FormatModuleStatus(string? status)
        {
            if (string.IsNullOrWhiteSpace(status))
                return "—";

            return status.Trim().ToLowerInvariant() switch
            {
                "active" => "Active",
                "planned" => "Planned",
                "scaffold" => "In Progress (Scaffold)",
                "scaffolded" => "In Progress (Scaffold)",
                "in_progress" => "In Progress",
                "paused" => "Paused",
                _ => ToTitleCase(status)
            };
        }

        private string? ResolveSnapshotPath(params string[] segments)
        {
            var roots = GetSnapshotRoots();
            if (roots.Count == 0)
                return null;

            foreach (var root in roots)
            {
                var candidate = Path.Combine(root, Path.Combine(segments));
                if (File.Exists(candidate))
                    return candidate;
            }

            return null;
        }

        private string? ResolveConfigWritePath(params string[] segments)
        {
            var roots = GetSnapshotRoots();
            if (roots.Count == 0)
                return null;

            foreach (var root in roots)
            {
                var sharedPath = Path.Combine(root, "shared");
                if (Directory.Exists(sharedPath))
                {
                    return Path.Combine(root, Path.Combine(segments));
                }
            }

            return null;
        }

        private string? ResolveAdminExportPath(string fileName)
        {
            return ResolveSnapshotPath("admin", fileName) ??
                ResolveSnapshotPath(fileName);
        }

        private List<string> GetSnapshotRoots()
        {
            var roots = new List<string>();
            var root = _currentPathStatus?.SnapshotRoot;

            if (!string.IsNullOrWhiteSpace(root))
            {
                roots.Add(root);

                var parent = Directory.GetParent(root)?.FullName;
                if (!string.IsNullOrWhiteSpace(parent))
                {
                    roots.Add(parent);

                    var grandParent = Directory.GetParent(parent)?.FullName;
                    if (!string.IsNullOrWhiteSpace(grandParent))
                    {
                        roots.Add(grandParent);
                    }
                }
            }

            return roots.Distinct(StringComparer.OrdinalIgnoreCase).ToList();
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

            _lastTrayHealth = health;
            var (dot, label) = GetHealthLabel(health);
            trayIcon.Text = BuildTrayTooltipText(dot, label);
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

        private void ApplyCreatorsSplitterAfterShown(object? sender, EventArgs e)
        {
            Shown -= ApplyCreatorsSplitterAfterShown;

            if (_creatorsSplit == null)
                return;

            _creatorsSplit.Panel1MinSize = 420;
            _creatorsSplit.Panel2MinSize = 260;

            var total = _creatorsSplit.ClientSize.Width;
            if (total <= 0)
                return;

            var desired = total - 320;
            var min1 = _creatorsSplit.Panel1MinSize;
            var min2 = _creatorsSplit.Panel2MinSize;
            var max = total - min2;

            if (desired < min1)
                desired = min1;
            if (desired > max)
                desired = max;

            _creatorsSplit.SplitterDistance = desired;
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
                    BuildSnapshotTooltipText(
                        fallback ?? "No snapshot data available.")
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
                    BuildSnapshotTooltipText(
                        $"Generated_At parse failure:\n{snapshot.Generated_At}")
                );
                return;
            }

            var ageSeconds = (DateTime.UtcNow - generatedAt).TotalSeconds;

            _snapshotToolTip.SetToolTip(
                lblSnapshotStatus,
                BuildSnapshotTooltipText(
                    $"Generated at: {generatedAt:yyyy-MM-dd HH:mm:ss} UTC\n" +
                    $"Snapshot age: {Math.Round(ageSeconds)} seconds\n" +
                    $"Stale threshold: {SnapshotStaleThresholdSeconds} seconds")
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

        private void RefreshRuntimeVersionInfo()
        {
            _runtimeVersionInfo =
                RuntimeVersionProvider.Load(_currentPathStatus?.SnapshotRoot);
            UpdateRuntimeVersionDisplay();
            UpdateUpdatesSummary();
            UpdateAboutSummary();
        }

        private void UpdateRuntimeVersionDisplay()
        {
            statusRuntimeVersion.Text =
                $"Runtime {_runtimeVersionInfo.ToDisplayVersion()} • {_runtimeVersionInfo.ToDisplayBuild()}";

            if (trayIcon != null)
            {
                var (dot, label) = GetHealthLabel(_lastTrayHealth);
                trayIcon.Text = BuildTrayTooltipText(dot, label);
            }
        }

        private string BuildTrayTooltipText(string dot, string label)
        {
            return $"{dot} StreamSuites {_runtimeVersionInfo.ToDisplayVersion()} • " +
                   $"{_runtimeVersionInfo.ToDisplayBuild()} - {label}";
        }

        private string BuildSnapshotTooltipText(string details)
        {
            return $"Runtime {_runtimeVersionInfo.ToDisplayVersion()} • " +
                   $"{_runtimeVersionInfo.ToDisplayBuild()}\n" +
                   details;
        }

        private void UpdateUpdatesSummary()
        {
            if (_updatesSummary == null)
                return;

            _updatesSummary.Text =
                $"Updates: Runtime {_runtimeVersionInfo.ToDisplayVersion()} • " +
                $"{_runtimeVersionInfo.ToDisplayBuild()}";
        }

        private void UpdateAboutSummary()
        {
            if (_aboutSummary == null)
                return;

            _aboutSummary.Text =
                $"StreamSuites Administrator Dashboard • Runtime {_runtimeVersionInfo.ToDisplayVersion()}";
        }

        private sealed class CreatorRow
        {
            public string CreatorId { get; set; } = string.Empty;
            public string DisplayName { get; set; } = string.Empty;
            public string PlatformsEnabled { get; set; } = string.Empty;
            public string Status { get; set; } = string.Empty;
            public string Notes { get; set; } = "—";
            public bool Enabled { get; set; }
            public string? LastHeartbeat { get; set; }
            public string? Error { get; set; }
            public string SourceSummary { get; set; } = "—";

            public Dictionary<string, bool> ConfigPlatforms { get; set; } = new();
            public Dictionary<string, AdminPlatformState> AdminPlatforms { get; set; } = new();
            public Dictionary<string, bool> SnapshotPlatforms { get; set; } = new();
        }

        private sealed class ClipRow
        {
            public string ClipId { get; set; } = string.Empty;
            public string Title { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public string State { get; set; } = string.Empty;
            public string PublishedAt { get; set; } = string.Empty;
            public string Duration { get; set; } = string.Empty;
        }

        private sealed class PollRow
        {
            public string PollId { get; set; } = string.Empty;
            public string Question { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public string State { get; set; } = string.Empty;
            public string OpenedAt { get; set; } = string.Empty;
            public string ClosedAt { get; set; } = string.Empty;
            public string OptionsSummary { get; set; } = string.Empty;
        }

        private sealed class TallyRow
        {
            public string TallyId { get; set; } = string.Empty;
            public string Label { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public int Count { get; set; }
            public string UpdatedAt { get; set; } = string.Empty;
        }

        private sealed class ScoreboardRow
        {
            public string ScoreboardId { get; set; } = string.Empty;
            public string Title { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public int Entries { get; set; }
            public string FinalizedAt { get; set; } = string.Empty;
        }

        private sealed class ChatEventRow
        {
            public string Timestamp { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public string Platform { get; set; } = string.Empty;
            public string Username { get; set; } = string.Empty;
            public string Message { get; set; } = string.Empty;
        }

        private sealed class ChatTriggerRow
        {
            public string TriggerId { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public string Type { get; set; } = string.Empty;
            public string Command { get; set; } = string.Empty;
            public int CooldownSeconds { get; set; }
            public string Description { get; set; } = string.Empty;
            public string UpdatedAt { get; set; } = string.Empty;
        }

        private sealed class PollVoteRow
        {
            public string Timestamp { get; set; } = string.Empty;
            public string PollId { get; set; } = string.Empty;
            public string OptionId { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public string VoterId { get; set; } = string.Empty;
        }

        private sealed class TallyEventRow
        {
            public string Timestamp { get; set; } = string.Empty;
            public string TallyId { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public int Delta { get; set; }
        }

        private sealed class ScoreEventRow
        {
            public string Timestamp { get; set; } = string.Empty;
            public string ScoreboardId { get; set; } = string.Empty;
            public string Creator { get; set; } = string.Empty;
            public string Label { get; set; } = string.Empty;
            public int ScoreDelta { get; set; }
        }

        private sealed class PlatformFlagRow
        {
            public string Platform { get; set; } = string.Empty;
            public string Enabled { get; set; } = string.Empty;
            public string State { get; set; } = string.Empty;
            public string Notes { get; set; } = string.Empty;
        }

        private sealed class CreatorConfigSummary
        {
            public string EnabledCountText { get; set; } = "0";
            public string CreatorListText { get; set; } = "—";
            public string Source { get; set; } = "—";
        }

        private sealed class PlatformTabControls
        {
            public PlatformTabControls(
                string platform,
                Label globalEnabled,
                Label globalTelemetry,
                Label globalPaused,
                Label globalNote,
                Label runtimeState,
                Label runtimeStatus,
                Label runtimeHeartbeat,
                Label runtimeEvent,
                Label runtimeSuccess,
                Label runtimeMessages,
                Label runtimeTriggers,
                Label runtimeActions,
                Label runtimeErrors,
                Label runtimeNote,
                Label localCreators,
                Label localCreatorList,
                Label localSource,
                Label localNote,
                Label moduleStatus,
                Label moduleMode,
                Label moduleReplay,
                Label moduleOverlay,
                Label moduleNotes,
                Label moduleNote)
            {
                Platform = platform;
                GlobalEnabled = globalEnabled;
                GlobalTelemetry = globalTelemetry;
                GlobalPaused = globalPaused;
                GlobalNote = globalNote;
                RuntimeState = runtimeState;
                RuntimeStatus = runtimeStatus;
                RuntimeHeartbeat = runtimeHeartbeat;
                RuntimeEvent = runtimeEvent;
                RuntimeSuccess = runtimeSuccess;
                RuntimeMessages = runtimeMessages;
                RuntimeTriggers = runtimeTriggers;
                RuntimeActions = runtimeActions;
                RuntimeErrors = runtimeErrors;
                RuntimeNote = runtimeNote;
                LocalCreators = localCreators;
                LocalCreatorList = localCreatorList;
                LocalSource = localSource;
                LocalNote = localNote;
                ModuleStatus = moduleStatus;
                ModuleMode = moduleMode;
                ModuleReplay = moduleReplay;
                ModuleOverlay = moduleOverlay;
                ModuleNotes = moduleNotes;
                ModuleNote = moduleNote;
            }

            public string Platform { get; }
            public Label GlobalEnabled { get; }
            public Label GlobalTelemetry { get; }
            public Label GlobalPaused { get; }
            public Label GlobalNote { get; }
            public Label RuntimeState { get; }
            public Label RuntimeStatus { get; }
            public Label RuntimeHeartbeat { get; }
            public Label RuntimeEvent { get; }
            public Label RuntimeSuccess { get; }
            public Label RuntimeMessages { get; }
            public Label RuntimeTriggers { get; }
            public Label RuntimeActions { get; }
            public Label RuntimeErrors { get; }
            public Label RuntimeNote { get; }
            public Label LocalCreators { get; }
            public Label LocalCreatorList { get; }
            public Label LocalSource { get; }
            public Label LocalNote { get; }
            public Label ModuleStatus { get; }
            public Label ModuleMode { get; }
            public Label ModuleReplay { get; }
            public Label ModuleOverlay { get; }
            public Label ModuleNotes { get; }
            public Label ModuleNote { get; }

            public void Reset()
            {
                GlobalEnabled.Text = "—";
                GlobalTelemetry.Text = "—";
                GlobalPaused.Text = "—";
                RuntimeState.Text = "—";
                RuntimeStatus.Text = "—";
                RuntimeHeartbeat.Text = "—";
                RuntimeEvent.Text = "—";
                RuntimeSuccess.Text = "—";
                RuntimeMessages.Text = "—";
                RuntimeTriggers.Text = "—";
                RuntimeActions.Text = "—";
                RuntimeErrors.Text = "—";
                LocalCreators.Text = "—";
                LocalCreatorList.Text = "—";
                LocalSource.Text = "—";
                ModuleStatus.Text = "—";
                ModuleMode.Text = "—";
                ModuleReplay.Text = "—";
                ModuleOverlay.Text = "—";
                ModuleNotes.Text = "—";
            }
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

using System.ComponentModel;
using System.Drawing;
using System.Windows.Forms;

namespace StreamSuites.DesktopAdmin
{
    partial class MainForm
    {
        private IContainer components = null;

        // Top toolbar
        private ToolStrip toolMain;
        private ToolStripButton btnRefresh;
        private ToolStripSeparator toolStripSeparator1;
        private ToolStripButton btnOpenLiveChat;
        private ToolStripSeparator toolStripSeparator2;
        private ToolStripLabel lblMode;

        // Footer status bar
        private StatusStrip statusBar;
        private ToolStripStatusLabel statusSnapshot;
        private ToolStripStatusLabel statusRuntimeVersion;
        private ToolStripStatusLabel statusSpacer;
        private ToolStripStatusLabel statusRuntime;

        // Tabs
        private TabControl tabMain;

        // Runtime tab
        private TabPage tabRuntime;
        private SplitContainer splitRuntime;
        private Panel panelRuntimeTable;
        private Panel panelRuntimeRight;

        private Label lblSnapshotStatus;
        private Label lblPlatformCount;
        private Label lblLastRefresh;
        private Label lblBridgeStatus;
        private DataGridView gridPlatforms;

        // Placeholder tabs
        private TabPage tabCreators;
        private TabPage tabDataSignals;
        private TabPage tabServices;
        private TabPage tabSettings;
        private TabPage tabJobs;
        private TabPage tabTelemetry;
        private TabPage tabPaths;

        // Services tab
        private TableLayoutPanel tableServices;
        private GroupBox groupAuthApi;
        private GroupBox groupCloudflare;
        private TableLayoutPanel tableAuthApi;
        private TableLayoutPanel tableCloudflare;
        private TableLayoutPanel tableAuthApiHeader;
        private TableLayoutPanel tableCloudflareHeader;
        private FlowLayoutPanel flowAuthApiActions;
        private FlowLayoutPanel flowCloudflareActions;
        private Label lblAuthApiStatus;
        private Label lblCloudflareStatus;
        private Button btnAuthApiStart;
        private Button btnAuthApiStop;
        private Button btnAuthApiRestart;
        private Button btnCloudflareStart;
        private Button btnCloudflareStop;
        private Button btnCloudflareRestart;
        private RichTextBox rtbAuthApiLog;
        private RichTextBox rtbCloudflareLog;

        // Snapshot path editor
        private Label lblSnapshotPathTitle;
        private TextBox txtSnapshotPath;
        private Button btnBrowseSnapshotPath;
        private Button btnSaveSnapshotPath;
        private Label lblSnapshotPathStatus;
        private Label lblSnapshotDetected;

        // Tray icon
        private NotifyIcon trayIcon;

        protected override void Dispose(bool disposing)
        {
            if (disposing)
            {
                DetachBridgeUi();

                if (components != null)
                    components.Dispose();

                if (_inspectorIconCache != null)
                {
                    foreach (var kvp in _inspectorIconCache)
                    {
                        try { kvp.Value.Dispose(); } catch { }
                    }

                    _inspectorIconCache.Clear();
                }
            }

            base.Dispose(disposing);
        }

        private void InitializeComponent()
        {
            components = new Container();

            toolMain = new ToolStrip();
            btnRefresh = new ToolStripButton();
            toolStripSeparator1 = new ToolStripSeparator();
            btnOpenLiveChat = new ToolStripButton();
            toolStripSeparator2 = new ToolStripSeparator();
            lblMode = new ToolStripLabel();

            statusBar = new StatusStrip();
            statusSnapshot = new ToolStripStatusLabel();
            statusRuntimeVersion = new ToolStripStatusLabel();
            statusSpacer = new ToolStripStatusLabel();
            statusRuntime = new ToolStripStatusLabel();

            tabMain = new TabControl();
            tabRuntime = new TabPage();
            tabCreators = new TabPage();
            tabDataSignals = new TabPage();
            tabServices = new TabPage();
            tabSettings = new TabPage();
            tabJobs = new TabPage();
            tabTelemetry = new TabPage();
            tabPaths = new TabPage();

            tableServices = new TableLayoutPanel();
            groupAuthApi = new GroupBox();
            groupCloudflare = new GroupBox();
            tableAuthApi = new TableLayoutPanel();
            tableCloudflare = new TableLayoutPanel();
            tableAuthApiHeader = new TableLayoutPanel();
            tableCloudflareHeader = new TableLayoutPanel();
            flowAuthApiActions = new FlowLayoutPanel();
            flowCloudflareActions = new FlowLayoutPanel();
            lblAuthApiStatus = new Label();
            lblCloudflareStatus = new Label();
            btnAuthApiStart = new Button();
            btnAuthApiStop = new Button();
            btnAuthApiRestart = new Button();
            btnCloudflareStart = new Button();
            btnCloudflareStop = new Button();
            btnCloudflareRestart = new Button();
            rtbAuthApiLog = new RichTextBox();
            rtbCloudflareLog = new RichTextBox();

            splitRuntime = new SplitContainer();
            panelRuntimeTable = new Panel();
            panelRuntimeRight = new Panel();

            lblSnapshotStatus = new Label();
            lblPlatformCount = new Label();
            lblLastRefresh = new Label();
            lblBridgeStatus = new Label();
            gridPlatforms = new DataGridView();

            trayIcon = new NotifyIcon(components);

            SuspendLayout();

            // Toolstrip
            toolMain.Dock = DockStyle.Top;
            toolMain.GripStyle = ToolStripGripStyle.Hidden;
            btnRefresh.Text = "Refresh";
            btnOpenLiveChat.Text = "Open LiveChat";
            btnOpenLiveChat.Click += BtnOpenLiveChat_Click;
            lblMode.Text = "Mode: Dashboard";
            toolMain.Items.Add(btnRefresh);
            toolMain.Items.Add(toolStripSeparator1);
            toolMain.Items.Add(btnOpenLiveChat);
            toolMain.Items.Add(toolStripSeparator2);
            toolMain.Items.Add(lblMode);

            // Status bar
            statusSnapshot.Text = "Snapshot: —";
            statusRuntimeVersion.Text = "Runtime Version unavailable • Build unavailable";
            statusRuntime.Text = "Runtime: disconnected";
            statusSpacer.Spring = true;
            statusBar.Items.Add(statusSnapshot);
            statusBar.Items.Add(statusRuntimeVersion);
            statusBar.Items.Add(statusSpacer);
            statusBar.Items.Add(statusRuntime);
            statusBar.Dock = DockStyle.Bottom;

            // Tabs
            tabMain.Dock = DockStyle.Fill;

            tabRuntime.Text = "Runtime";
            tabRuntime.Padding = new Padding(8);
            tabRuntime.Controls.Add(splitRuntime);

            tabCreators.Text = "Creators";
            tabDataSignals.Text = "Data & Signals";
            tabServices.Text = "Services";
            tabJobs.Text = "Jobs";
            tabTelemetry.Text = "Telemetry";
            tabSettings.Text = "Settings";
            tabPaths.Text = "Paths";
            tabPaths.Padding = new Padding(16);

            tabMain.TabPages.Add(tabRuntime);
            tabMain.TabPages.Add(tabCreators);
            tabMain.TabPages.Add(tabJobs);
            tabMain.TabPages.Add(tabDataSignals);
            tabMain.TabPages.Add(tabServices);
            tabMain.TabPages.Add(tabTelemetry);
            tabMain.TabPages.Add(tabSettings);
            tabMain.TabPages.Add(tabPaths);

            // Split runtime
            splitRuntime.Dock = DockStyle.Fill;
            splitRuntime.Orientation = Orientation.Vertical;
            splitRuntime.FixedPanel = FixedPanel.None;

            splitRuntime.Panel1.Controls.Add(panelRuntimeTable);
            splitRuntime.Panel2.Controls.Add(panelRuntimeRight);

            // Table panel
            panelRuntimeTable.Dock = DockStyle.Fill;
            panelRuntimeTable.Padding = new Padding(8);

            lblSnapshotStatus.AutoSize = true;
            lblSnapshotStatus.Location = new Point(8, 8);

            lblPlatformCount.AutoSize = true;
            lblPlatformCount.Location = new Point(8, 28);

            lblLastRefresh.AutoSize = true;
            lblLastRefresh.Location = new Point(8, 48);

            lblBridgeStatus.AutoSize = true;
            lblBridgeStatus.Location = new Point(8, 68);
            lblBridgeStatus.Text = "Bridge: —";

            // GRID — FIXED FOR RESIZE / SORT / REORDER
            gridPlatforms.Dock = DockStyle.Fill;
            gridPlatforms.ReadOnly = true;
            gridPlatforms.AllowUserToAddRows = false;
            gridPlatforms.AllowUserToDeleteRows = false;
            gridPlatforms.AllowUserToResizeRows = false;
            gridPlatforms.AllowUserToResizeColumns = true;
            gridPlatforms.AllowUserToOrderColumns = true;
            gridPlatforms.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
            gridPlatforms.RowHeadersVisible = false;
            gridPlatforms.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.None;
            gridPlatforms.ScrollBars = ScrollBars.Both;
            gridPlatforms.CellFormatting += GridPlatforms_CellFormatting;

            panelRuntimeTable.Controls.Add(gridPlatforms);
            panelRuntimeTable.Controls.Add(lblBridgeStatus);
            panelRuntimeTable.Controls.Add(lblLastRefresh);
            panelRuntimeTable.Controls.Add(lblPlatformCount);
            panelRuntimeTable.Controls.Add(lblSnapshotStatus);

            // Inspector panel
            panelRuntimeRight.Dock = DockStyle.Fill;
            panelRuntimeRight.Padding = new Padding(8);
            panelRuntimeRight.BackColor = SystemColors.ControlLight;

            // Services tab controls
            tabServices.Padding = new Padding(8);
            tabServices.Controls.Add(tableServices);

            tableServices.Dock = DockStyle.Fill;
            tableServices.ColumnCount = 1;
            tableServices.RowCount = 2;
            tableServices.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100F));
            tableServices.RowStyles.Add(new RowStyle(SizeType.Percent, 50F));
            tableServices.RowStyles.Add(new RowStyle(SizeType.Percent, 50F));
            tableServices.Controls.Add(groupAuthApi, 0, 0);
            tableServices.Controls.Add(groupCloudflare, 0, 1);

            groupAuthApi.Text = "Auth API";
            groupAuthApi.Dock = DockStyle.Fill;
            groupAuthApi.Padding = new Padding(8);
            groupAuthApi.Controls.Add(tableAuthApi);

            groupCloudflare.Text = "Cloudflare Tunnel";
            groupCloudflare.Dock = DockStyle.Fill;
            groupCloudflare.Padding = new Padding(8);
            groupCloudflare.Controls.Add(tableCloudflare);

            tableAuthApi.Dock = DockStyle.Fill;
            tableAuthApi.ColumnCount = 1;
            tableAuthApi.RowCount = 2;
            tableAuthApi.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            tableAuthApi.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
            tableAuthApi.Controls.Add(tableAuthApiHeader, 0, 0);
            tableAuthApi.Controls.Add(rtbAuthApiLog, 0, 1);

            tableCloudflare.Dock = DockStyle.Fill;
            tableCloudflare.ColumnCount = 1;
            tableCloudflare.RowCount = 2;
            tableCloudflare.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            tableCloudflare.RowStyles.Add(new RowStyle(SizeType.Percent, 100F));
            tableCloudflare.Controls.Add(tableCloudflareHeader, 0, 0);
            tableCloudflare.Controls.Add(rtbCloudflareLog, 0, 1);

            tableAuthApiHeader.Dock = DockStyle.Top;
            tableAuthApiHeader.ColumnCount = 2;
            tableAuthApiHeader.AutoSize = true;
            tableAuthApiHeader.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            tableAuthApiHeader.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            tableAuthApiHeader.Controls.Add(lblAuthApiStatus, 0, 0);
            tableAuthApiHeader.Controls.Add(flowAuthApiActions, 1, 0);

            tableCloudflareHeader.Dock = DockStyle.Top;
            tableCloudflareHeader.ColumnCount = 2;
            tableCloudflareHeader.AutoSize = true;
            tableCloudflareHeader.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            tableCloudflareHeader.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 50F));
            tableCloudflareHeader.Controls.Add(lblCloudflareStatus, 0, 0);
            tableCloudflareHeader.Controls.Add(flowCloudflareActions, 1, 0);

            lblAuthApiStatus.AutoSize = true;
            lblAuthApiStatus.Text = "● Stopped";
            lblAuthApiStatus.ForeColor = SystemColors.GrayText;
            lblAuthApiStatus.Dock = DockStyle.Left;

            lblCloudflareStatus.AutoSize = true;
            lblCloudflareStatus.Text = "● Stopped";
            lblCloudflareStatus.ForeColor = SystemColors.GrayText;
            lblCloudflareStatus.Dock = DockStyle.Left;

            flowAuthApiActions.Dock = DockStyle.Fill;
            flowAuthApiActions.FlowDirection = FlowDirection.LeftToRight;
            flowAuthApiActions.AutoSize = true;
            flowAuthApiActions.WrapContents = false;
            flowAuthApiActions.Controls.Add(btnAuthApiStart);
            flowAuthApiActions.Controls.Add(btnAuthApiStop);
            flowAuthApiActions.Controls.Add(btnAuthApiRestart);

            flowCloudflareActions.Dock = DockStyle.Fill;
            flowCloudflareActions.FlowDirection = FlowDirection.LeftToRight;
            flowCloudflareActions.AutoSize = true;
            flowCloudflareActions.WrapContents = false;
            flowCloudflareActions.Controls.Add(btnCloudflareStart);
            flowCloudflareActions.Controls.Add(btnCloudflareStop);
            flowCloudflareActions.Controls.Add(btnCloudflareRestart);

            btnAuthApiStart.Text = "Start";
            btnAuthApiStop.Text = "Stop";
            btnAuthApiRestart.Text = "Restart";

            btnCloudflareStart.Text = "Start";
            btnCloudflareStop.Text = "Stop";
            btnCloudflareRestart.Text = "Restart";

            rtbAuthApiLog.Dock = DockStyle.Fill;
            rtbAuthApiLog.ReadOnly = true;
            rtbAuthApiLog.BackColor = SystemColors.Window;
            rtbAuthApiLog.HideSelection = false;

            rtbCloudflareLog.Dock = DockStyle.Fill;
            rtbCloudflareLog.ReadOnly = true;
            rtbCloudflareLog.BackColor = SystemColors.Window;
            rtbCloudflareLog.HideSelection = false;

            // Paths tab controls
            lblSnapshotPathTitle = new Label
            {
                Text = "Runtime Snapshot Directory",
                Font = new Font("Segoe UI", 9F, FontStyle.Bold),
                Location = new Point(16, 16),
                AutoSize = true
            };

            txtSnapshotPath = new TextBox
            {
                Location = new Point(16, 44),
                Width = 700,
                ReadOnly = false
            };

            btnBrowseSnapshotPath = new Button
            {
                Text = "Browse…",
                Location = new Point(728, 42),
                Width = 90
            };

            btnSaveSnapshotPath = new Button
            {
                Text = "Save",
                Location = new Point(828, 42),
                Width = 90
            };

            lblSnapshotPathStatus = new Label
            {
                Location = new Point(16, 76),
                AutoSize = true,
                ForeColor = SystemColors.GrayText
            };

            lblSnapshotDetected = new Label
            {
                Location = new Point(16, 104),
                AutoSize = true,
                MaximumSize = new Size(900, 0)
            };

            tabPaths.Controls.Add(lblSnapshotPathTitle);
            tabPaths.Controls.Add(txtSnapshotPath);
            tabPaths.Controls.Add(btnBrowseSnapshotPath);
            tabPaths.Controls.Add(btnSaveSnapshotPath);
            tabPaths.Controls.Add(lblSnapshotPathStatus);
            tabPaths.Controls.Add(lblSnapshotDetected);

            // Tray icon
            trayIcon.Text = "StreamSuites™ Administrator";
            trayIcon.Visible = true;

            // MainForm
            ClientSize = new Size(1200, 800);
            MinimumSize = new Size(900, 650);
            Controls.Add(tabMain);
            Controls.Add(toolMain);
            Controls.Add(statusBar);
            Text = "StreamSuites™ Administrator Dashboard";

            ResumeLayout(false);
            PerformLayout();
        }
    }
}

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
        private ToolStripLabel lblMode;

        // Footer status bar
        private StatusStrip statusBar;
        private ToolStripStatusLabel statusSnapshot;
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
        private DataGridView gridPlatforms;

        // Placeholder tabs
        private TabPage tabJobs;
        private TabPage tabTelemetry;
        private TabPage tabPaths;

        // Snapshot path editor
        private Label lblSnapshotPathTitle;
        private TextBox txtSnapshotPath;
        private Button btnBrowseSnapshotPath;
        private Button btnSaveSnapshotPath;
        private Label lblSnapshotPathStatus;

        // Tray icon
        private NotifyIcon trayIcon;

        protected override void Dispose(bool disposing)
        {
            if (disposing && components != null)
                components.Dispose();

            base.Dispose(disposing);
        }

        private void InitializeComponent()
        {
            components = new Container();

            toolMain = new ToolStrip();
            btnRefresh = new ToolStripButton();
            toolStripSeparator1 = new ToolStripSeparator();
            lblMode = new ToolStripLabel();

            statusBar = new StatusStrip();
            statusSnapshot = new ToolStripStatusLabel();
            statusSpacer = new ToolStripStatusLabel();
            statusRuntime = new ToolStripStatusLabel();

            tabMain = new TabControl();
            tabRuntime = new TabPage();
            tabJobs = new TabPage();
            tabTelemetry = new TabPage();
            tabPaths = new TabPage();

            splitRuntime = new SplitContainer();
            panelRuntimeTable = new Panel();
            panelRuntimeRight = new Panel();

            lblSnapshotStatus = new Label();
            lblPlatformCount = new Label();
            lblLastRefresh = new Label();
            gridPlatforms = new DataGridView();

            trayIcon = new NotifyIcon(components);

            SuspendLayout();

            // Toolstrip
            toolMain.Dock = DockStyle.Top;
            toolMain.GripStyle = ToolStripGripStyle.Hidden;
            btnRefresh.Text = "Refresh";
            lblMode.Text = "Mode: Dashboard";
            toolMain.Items.Add(btnRefresh);
            toolMain.Items.Add(toolStripSeparator1);
            toolMain.Items.Add(lblMode);

            // Status bar
            statusSnapshot.Text = "Snapshot: —";
            statusRuntime.Text = "Runtime: disconnected";
            statusSpacer.Spring = true;
            statusBar.Items.Add(statusSnapshot);
            statusBar.Items.Add(statusSpacer);
            statusBar.Items.Add(statusRuntime);
            statusBar.Dock = DockStyle.Bottom;

            // Tabs
            tabMain.Dock = DockStyle.Fill;

            tabRuntime.Text = "Runtime";
            tabRuntime.Padding = new Padding(8);
            tabRuntime.Controls.Add(splitRuntime);

            tabJobs.Text = "Jobs";
            tabTelemetry.Text = "Telemetry";
            tabPaths.Text = "Paths";
            tabPaths.Padding = new Padding(16);

            tabMain.TabPages.Add(tabRuntime);
            tabMain.TabPages.Add(tabJobs);
            tabMain.TabPages.Add(tabTelemetry);
            tabMain.TabPages.Add(tabPaths);

            // Split runtime
            splitRuntime.Dock = DockStyle.Fill;
            splitRuntime.Orientation = Orientation.Vertical;
            splitRuntime.FixedPanel = FixedPanel.Panel2;

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
            panelRuntimeTable.Controls.Add(lblLastRefresh);
            panelRuntimeTable.Controls.Add(lblPlatformCount);
            panelRuntimeTable.Controls.Add(lblSnapshotStatus);

            // Inspector panel
            panelRuntimeRight.Dock = DockStyle.Fill;
            panelRuntimeRight.Padding = new Padding(8);
            panelRuntimeRight.BackColor = SystemColors.ControlLight;

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
                ReadOnly = true
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

            tabPaths.Controls.Add(lblSnapshotPathTitle);
            tabPaths.Controls.Add(txtSnapshotPath);
            tabPaths.Controls.Add(btnBrowseSnapshotPath);
            tabPaths.Controls.Add(btnSaveSnapshotPath);
            tabPaths.Controls.Add(lblSnapshotPathStatus);

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

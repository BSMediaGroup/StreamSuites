using System.Drawing;
using System.Windows.Forms;
using StreamSuites.DesktopAdmin.Models;

namespace StreamSuites.DesktopAdmin
{
    public class AboutDialog : Form
    {
        public AboutDialog(string applicationName, AboutExport export)
        {
            Text = $"About {applicationName}";
            StartPosition = FormStartPosition.CenterParent;
            FormBorderStyle = FormBorderStyle.FixedDialog;
            MaximizeBox = false;
            MinimizeBox = false;
            ClientSize = new Size(520, 320);

            var layout = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 2,
                RowCount = 6,
                Padding = new Padding(12),
                AutoSize = true
            };

            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 120f));
            layout.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100f));

            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));
            layout.RowStyles.Add(new RowStyle(SizeType.Percent, 100f));
            layout.RowStyles.Add(new RowStyle(SizeType.AutoSize));

            var lblName = new Label
            {
                Text = "Application",
                AutoSize = true,
                Font = new Font(Font, FontStyle.Bold)
            };

            var lblVersion = new Label
            {
                Text = "Version",
                AutoSize = true,
                Font = new Font(Font, FontStyle.Bold)
            };

            var lblBuild = new Label
            {
                Text = "Build",
                AutoSize = true,
                Font = new Font(Font, FontStyle.Bold)
            };

            var lblUpdated = new Label
            {
                Text = "Last Updated",
                AutoSize = true,
                Font = new Font(Font, FontStyle.Bold)
            };

            var lblLicense = new Label
            {
                Text = "License / Notice",
                AutoSize = true,
                Font = new Font(Font, FontStyle.Bold)
            };

            var txtName = new Label
            {
                Text = applicationName,
                AutoSize = true
            };

            var txtVersion = new Label
            {
                Text = export.Version,
                AutoSize = true
            };

            var txtBuild = new Label
            {
                Text = export.Build,
                AutoSize = true
            };

            var txtUpdated = new Label
            {
                Text = export.Last_Updated,
                AutoSize = true
            };

            var txtLicense = new TextBox
            {
                Text = BuildLicenseText(export),
                ReadOnly = true,
                Multiline = true,
                Dock = DockStyle.Fill,
                ScrollBars = ScrollBars.Vertical
            };

            var btnClose = new Button
            {
                Text = "Close",
                Anchor = AnchorStyles.Right,
                DialogResult = DialogResult.OK,
                Width = 90
            };

            layout.Controls.Add(lblName, 0, 0);
            layout.Controls.Add(txtName, 1, 0);
            layout.Controls.Add(lblVersion, 0, 1);
            layout.Controls.Add(txtVersion, 1, 1);
            layout.Controls.Add(lblBuild, 0, 2);
            layout.Controls.Add(txtBuild, 1, 2);
            layout.Controls.Add(lblUpdated, 0, 3);
            layout.Controls.Add(txtUpdated, 1, 3);
            layout.Controls.Add(lblLicense, 0, 4);
            layout.Controls.Add(txtLicense, 1, 4);
            layout.Controls.Add(btnClose, 1, 5);

            Controls.Add(layout);

            AcceptButton = btnClose;
        }

        private static string BuildLicenseText(AboutExport export)
        {
            if (!string.IsNullOrWhiteSpace(export.Notice))
            {
                return export.Notice;
            }

            return export.Copyright;
        }
    }
}

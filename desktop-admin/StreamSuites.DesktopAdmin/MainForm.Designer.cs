using System.ComponentModel;
using System.Windows.Forms;

namespace StreamSuites.DesktopAdmin;

partial class MainForm
{
    /// <summary>
    ///  Required designer variable.
    /// </summary>
    private IContainer? components = null;

    private StatusStrip statusStrip;
    private ToolStripStatusLabel modeStatusLabel;

    /// <summary>
    ///  Clean up any resources being used.
    /// </summary>
    /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
    protected override void Dispose(bool disposing)
    {
        if (disposing && (components != null))
        {
            components.Dispose();
        }
        base.Dispose(disposing);
    }

    #region Windows Form Designer generated code

    /// <summary>
    ///  Required method for Designer support - do not modify
    ///  the contents of this method with the code editor.
    /// </summary>
    private void InitializeComponent()
    {
        components = new Container();
        statusStrip = new StatusStrip();
        modeStatusLabel = new ToolStripStatusLabel();
        statusStrip.SuspendLayout();
        SuspendLayout();
        // 
        // statusStrip
        // 
        statusStrip.ImageScalingSize = new System.Drawing.Size(20, 20);
        statusStrip.Items.AddRange(new ToolStripItem[] { modeStatusLabel });
        statusStrip.Location = new System.Drawing.Point(0, 278);
        statusStrip.Name = "statusStrip";
        statusStrip.Padding = new Padding(1, 0, 12, 0);
        statusStrip.Size = new System.Drawing.Size(482, 22);
        statusStrip.SizingGrip = false;
        statusStrip.TabIndex = 0;
        statusStrip.Text = "statusStrip";
        // 
        // modeStatusLabel
        // 
        modeStatusLabel.Name = "modeStatusLabel";
        modeStatusLabel.Size = new System.Drawing.Size(83, 17);
        modeStatusLabel.Text = "Mode: Static";
        // 
        // MainForm
        // 
        AutoScaleDimensions = new System.Drawing.SizeF(7F, 15F);
        AutoScaleMode = AutoScaleMode.Font;
        ClientSize = new System.Drawing.Size(482, 300);
        Controls.Add(statusStrip);
        MinimumSize = new System.Drawing.Size(400, 250);
        Name = "MainForm";
        StartPosition = FormStartPosition.CenterScreen;
        Text = "StreamSuites Desktop Admin (Alpha)";
        statusStrip.ResumeLayout(false);
        statusStrip.PerformLayout();
        ResumeLayout(false);
        PerformLayout();
    }

    #endregion
}

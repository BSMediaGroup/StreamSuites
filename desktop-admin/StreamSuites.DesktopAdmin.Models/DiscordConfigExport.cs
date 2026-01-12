using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Models
{
    public class DiscordConfigExport
    {
        [JsonPropertyName("discord")]
        public DiscordConfigRoot Discord { get; set; } = new();

        [JsonPropertyName("guilds")]
        [JsonIgnore(Condition = JsonIgnoreCondition.WhenWritingNull)]
        public Dictionary<string, DiscordGuildConfig>? LegacyGuilds { get; set; }

        [JsonIgnore]
        public Dictionary<string, DiscordGuildConfig> Guilds
        {
            get => Discord.Guilds;
            set => Discord.Guilds = value;
        }

        public void Normalize()
        {
            Discord ??= new DiscordConfigRoot();
            Discord.Guilds ??= new Dictionary<string, DiscordGuildConfig>();

            if (LegacyGuilds != null && LegacyGuilds.Count > 0 && Discord.Guilds.Count == 0)
            {
                Discord.Guilds = LegacyGuilds;
            }

            LegacyGuilds = null;
        }
    }

    public class DiscordConfigRoot
    {
        [JsonPropertyName("guilds")]
        public Dictionary<string, DiscordGuildConfig> Guilds { get; set; } = new();
    }

    public class DiscordGuildConfig
    {
        [JsonPropertyName("logging")]
        public DiscordLoggingConfig Logging { get; set; } = new();

        [JsonPropertyName("notifications")]
        public DiscordNotificationsConfig Notifications { get; set; } = new();
    }

    public class DiscordLoggingConfig
    {
        [JsonPropertyName("enabled")]
        public bool Enabled { get; set; }

        [JsonPropertyName("channel_id")]
        public string? Channel_Id { get; set; }
    }

    public class DiscordNotificationsConfig
    {
        [JsonPropertyName("general")]
        public string? General { get; set; }

        [JsonPropertyName("rumble_clips")]
        public string? Rumble_Clips { get; set; }

        [JsonPropertyName("youtube_clips")]
        public string? Youtube_Clips { get; set; }

        [JsonPropertyName("kick_clips")]
        public string? Kick_Clips { get; set; }

        [JsonPropertyName("pilled_clips")]
        public string? Pilled_Clips { get; set; }

        [JsonPropertyName("twitch_clips")]
        public string? Twitch_Clips { get; set; }
    }
}

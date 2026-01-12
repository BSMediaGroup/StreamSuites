using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Models
{
    public class DiscordConfigExport
    {
        [JsonPropertyName("guilds")]
        public Dictionary<string, DiscordGuildConfig> Guilds { get; set; } = new();
    }

    public class DiscordGuildConfig
    {
        [JsonPropertyName("logging_enabled")]
        public bool Logging_Enabled { get; set; }

        [JsonPropertyName("logging_channel_id")]
        public long? Logging_Channel_Id { get; set; }

        [JsonPropertyName("notifications_general")]
        public long? Notifications_General { get; set; }

        [JsonPropertyName("notifications_rumble_clips")]
        public long? Notifications_Rumble_Clips { get; set; }

        [JsonPropertyName("notifications_youtube_clips")]
        public long? Notifications_Youtube_Clips { get; set; }

        [JsonPropertyName("notifications_kick_clips")]
        public long? Notifications_Kick_Clips { get; set; }

        [JsonPropertyName("notifications_pilled_clips")]
        public long? Notifications_Pilled_Clips { get; set; }

        [JsonPropertyName("notifications_twitch_clips")]
        public long? Notifications_Twitch_Clips { get; set; }
    }
}

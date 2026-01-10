using System.Collections.Generic;
using System.Text.Json.Serialization;

namespace StreamSuites.DesktopAdmin.Models
{
    public class ClipsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("clips")]
        public List<ClipExportItem> Clips { get; set; } = new();
    }

    public class ClipExportItem
    {
        [JsonPropertyName("clip_id")]
        public string Clip_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("title")]
        public string Title { get; set; } = string.Empty;

        [JsonPropertyName("state")]
        public string State { get; set; } = string.Empty;

        [JsonPropertyName("published_at")]
        public string? Published_At { get; set; }

        [JsonPropertyName("duration_seconds")]
        public int Duration_Seconds { get; set; }

        [JsonPropertyName("url")]
        public string? Url { get; set; }

        [JsonPropertyName("thumbnail_url")]
        public string? Thumbnail_Url { get; set; }
    }

    public class PollsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("polls")]
        public List<PollExportItem> Polls { get; set; } = new();
    }

    public class PollExportItem
    {
        [JsonPropertyName("poll_id")]
        public string Poll_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("question")]
        public string Question { get; set; } = string.Empty;

        [JsonPropertyName("options")]
        public List<PollOptionExport> Options { get; set; } = new();

        [JsonPropertyName("state")]
        public string State { get; set; } = string.Empty;

        [JsonPropertyName("opened_at")]
        public string? Opened_At { get; set; }

        [JsonPropertyName("closed_at")]
        public string? Closed_At { get; set; }
    }

    public class PollOptionExport
    {
        [JsonPropertyName("option_id")]
        public string Option_Id { get; set; } = string.Empty;

        [JsonPropertyName("label")]
        public string Label { get; set; } = string.Empty;

        [JsonPropertyName("votes")]
        public int Votes { get; set; }
    }

    public class TalliesExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("tallies")]
        public List<TallyExportItem> Tallies { get; set; } = new();
    }

    public class TallyExportItem
    {
        [JsonPropertyName("tally_id")]
        public string Tally_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("label")]
        public string Label { get; set; } = string.Empty;

        [JsonPropertyName("count")]
        public int Count { get; set; }

        [JsonPropertyName("last_updated_at")]
        public string? Last_Updated_At { get; set; }
    }

    public class ScoreboardsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("scoreboards")]
        public List<ScoreboardExportItem> Scoreboards { get; set; } = new();
    }

    public class ScoreboardExportItem
    {
        [JsonPropertyName("scoreboard_id")]
        public string Scoreboard_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("title")]
        public string Title { get; set; } = string.Empty;

        [JsonPropertyName("entries")]
        public List<ScoreboardEntryExport> Entries { get; set; } = new();

        [JsonPropertyName("finalized_at")]
        public string? Finalized_At { get; set; }
    }

    public class ScoreboardEntryExport
    {
        [JsonPropertyName("position")]
        public int Position { get; set; }

        [JsonPropertyName("label")]
        public string Label { get; set; } = string.Empty;

        [JsonPropertyName("score")]
        public int Score { get; set; }
    }

    public class ChatEventsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("events")]
        public List<ChatEventExportItem> Events { get; set; } = new();
    }

    public class ChatEventExportItem
    {
        [JsonPropertyName("event_id")]
        public string Event_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("platform")]
        public string Platform { get; set; } = string.Empty;

        [JsonPropertyName("user_id")]
        public string User_Id { get; set; } = string.Empty;

        [JsonPropertyName("username")]
        public string Username { get; set; } = string.Empty;

        [JsonPropertyName("message")]
        public string Message { get; set; } = string.Empty;

        [JsonPropertyName("message_at")]
        public string? Message_At { get; set; }
    }

    public class PollVotesExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("votes")]
        public List<PollVoteExportItem> Votes { get; set; } = new();
    }

    public class PollVoteExportItem
    {
        [JsonPropertyName("vote_id")]
        public string Vote_Id { get; set; } = string.Empty;

        [JsonPropertyName("poll_id")]
        public string Poll_Id { get; set; } = string.Empty;

        [JsonPropertyName("option_id")]
        public string Option_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("voter_id")]
        public string Voter_Id { get; set; } = string.Empty;

        [JsonPropertyName("voted_at")]
        public string? Voted_At { get; set; }
    }

    public class TallyEventsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("events")]
        public List<TallyEventExportItem> Events { get; set; } = new();
    }

    public class TallyEventExportItem
    {
        [JsonPropertyName("event_id")]
        public string Event_Id { get; set; } = string.Empty;

        [JsonPropertyName("tally_id")]
        public string Tally_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("delta")]
        public int Delta { get; set; }

        [JsonPropertyName("updated_at")]
        public string? Updated_At { get; set; }
    }

    public class ScoreEventsExport
    {
        [JsonPropertyName("meta")]
        public AdminExportMeta Meta { get; set; } = new();

        [JsonPropertyName("events")]
        public List<ScoreEventExportItem> Events { get; set; } = new();
    }

    public class ScoreEventExportItem
    {
        [JsonPropertyName("event_id")]
        public string Event_Id { get; set; } = string.Empty;

        [JsonPropertyName("scoreboard_id")]
        public string Scoreboard_Id { get; set; } = string.Empty;

        [JsonPropertyName("creator")]
        public string Creator { get; set; } = string.Empty;

        [JsonPropertyName("label")]
        public string Label { get; set; } = string.Empty;

        [JsonPropertyName("score_delta")]
        public int Score_Delta { get; set; }

        [JsonPropertyName("scored_at")]
        public string? Scored_At { get; set; }
    }
}

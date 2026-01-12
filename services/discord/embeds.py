from __future__ import annotations

import discord


def info_embed(title: str, description: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.blurple(),
    )


def success_embed(title: str, description: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.green(),
    )


def error_embed(title: str, description: str | None = None) -> discord.Embed:
    return discord.Embed(
        title=title,
        description=description,
        color=discord.Color.red(),
    )

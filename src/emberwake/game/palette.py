"""Resurrect 64 by Kerrie Lake, the master palette. All art must use these colors."""

from __future__ import annotations

RESURRECT_64: tuple[str, ...] = (
    "#2e222f", "#3e3546", "#625565", "#966c6c", "#ab947a", "#694f62", "#7f708a", "#9babb2",
    "#c7dcd0", "#ffffff", "#6e2727", "#b33831", "#ea4f36", "#f57d4a", "#ae2334", "#e83b3b",
    "#fb6b1d", "#f79617", "#f9c22b", "#7a3045", "#9e4539", "#cd683d", "#e6904e", "#fbb954",
    "#4c3e24", "#676633", "#a2a947", "#d5e04b", "#fbff86", "#165a4c", "#239063", "#1ebc73",
    "#91db69", "#cddf6c", "#313638", "#374e4a", "#547e64", "#92a984", "#b2ba90", "#0b5e65",
    "#0b8a8f", "#0eaf9b", "#30e1b9", "#8ff8e2", "#323353", "#484a77", "#4d65b4", "#4d9be6",
    "#8fd3ff", "#45293f", "#6b3e75", "#905ea9", "#a884f3", "#eaaded", "#753c54", "#a24b6f",
    "#cf657f", "#ed8099", "#831c5d", "#c32454", "#f04f78", "#f68181", "#fca790", "#fdcbb0",
)  # fmt: skip

INK = "#2e222f"
NIGHT = "#323353"
DUSK = "#484a77"
HORIZON = "#6b3e75"
PLUM = "#45293f"
MIST = "#c7dcd0"
EMBER_CORE = "#fbff86"
EMBER_HOT = "#f9c22b"
EMBER_WARM = "#fb6b1d"
EMBER_COOL = "#b33831"

EMISSIVE: tuple[str, ...] = (
    "#fbff86",
    "#f9c22b",
    "#fbb954",
    "#f79617",
    "#fb6b1d",
    "#8ff8e2",
    "#30e1b9",
)
"""Colors that give off light: flame from core to warm, and the mint of eyes and lightforms.

Pixels in these colors are drawn again after the lighting, so they glow in the dark. Keep them
for things that shine (art bible: warm means light).
"""

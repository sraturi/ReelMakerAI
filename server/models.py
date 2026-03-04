"""Pydantic models for the ReelMaker AI editing pipeline."""

from pydantic import BaseModel, Field


class TextOverlay(BaseModel):
    """A text overlay to display on the reel."""
    text: str = Field(description="Text content to display")
    start_time: float = Field(description="When the text appears (seconds)")
    end_time: float = Field(description="When the text disappears (seconds)")
    position: str = Field(
        default="center",
        description="Position: top, center, bottom"
    )
    font_size: int = Field(default=64, description="Font size in pixels")
    color: str = Field(default="white", description="Text color")
    style: str = Field(
        default="title",
        description="Style: title, caption, highlight"
    )


class ClipPlan(BaseModel):
    """A single clip segment in the editing plan."""
    source_video: str = Field(description="Filename of the source video")
    source_index: int = Field(description="Index of the source video in the input list")
    start_time: float = Field(description="Start time in source video (seconds)")
    end_time: float = Field(description="End time in source video (seconds)")
    timeline_start: float = Field(description="Where this clip starts on the output timeline (seconds)")
    audio: str = Field(
        default="keep_audio",
        description="Audio mode: keep_audio (speech/dialogue) or mute (ambient/noise)"
    )
    transition: str = Field(
        default="fade",
        description="xfade transition type INTO this clip (e.g. fade, wipeleft, dissolve)"
    )
    ken_burns: str = Field(
        default="none",
        description="Ken Burns effect on this clip: none, zoom_in, zoom_out, pan_left, pan_right"
    )


class SceneInfo(BaseModel):
    """A scene window from video analysis (Pass 1)."""
    start: float = Field(description="Scene start time (seconds)")
    end: float = Field(description="Scene end time (seconds)")
    description: str = Field(description="What visually happens")
    interest: int = Field(description="1-5 visual interest rating")
    tags: list[str] = Field(default_factory=list, description="scenery, action, closeup, peak_moment, etc.")
    has_speech: bool = Field(default=False)
    has_action: bool = Field(default=False)
    is_peak_moment: bool = Field(default=False, description="True for climax/payoff moments")


class VideoAnalysis(BaseModel):
    """Analysis result for a single video (Pass 1)."""
    filename: str
    source_index: int
    duration: float
    summary: str = Field(description="One-sentence overview")
    scenes: list[SceneInfo]


class SceneAnalysisResult(BaseModel):
    """Complete scene analysis output from Pass 1."""
    videos: list[VideoAnalysis]


class EditingPlan(BaseModel):
    """Complete editing plan for the reel."""
    music_track: str = Field(description="Filename of the chosen music track")
    total_duration: float = Field(description="Total reel duration (seconds)")
    clips: list[ClipPlan] = Field(description="Ordered list of clip segments")
    text_overlays: list[TextOverlay] = Field(
        default_factory=list,
        description="Text overlays to display"
    )
    description: str = Field(
        default="",
        description="Brief description of the editing approach"
    )


class VideoInfo(BaseModel):
    """Probed metadata for a video file."""
    path: str
    filename: str
    duration: float = Field(description="Duration in seconds")
    width: int
    height: int
    fps: float = Field(default=30.0)
    rotation: int = Field(default=0, description="Rotation from metadata (degrees)")


class MusicTrack(BaseModel):
    """Metadata for a music track from the catalog."""
    filename: str
    name: str
    genre: str = Field(default="", description="Genre: pop, lofi, cinematic, trap, romantic, edm, acoustic")
    vibe: str
    bpm: int
    duration: float = Field(description="Duration in seconds")
    tags: list[str] = Field(default_factory=list, description="Mood/use-case tags")

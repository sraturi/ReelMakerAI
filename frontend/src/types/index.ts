// Mirrors Pydantic models from server/models.py

export interface VideoInfo {
  path: string;
  filename: string;
  duration: number;
  width: number;
  height: number;
  fps: number;
  rotation: number;
  index: number;
  thumbnail_url: string;
}

export interface SceneInfo {
  start: number;
  end: number;
  description: string;
  interest: number;
  tags: string[];
  has_speech: boolean;
  has_action: boolean;
  is_peak_moment: boolean;
}

export interface VideoAnalysis {
  filename: string;
  source_index: number;
  duration: number;
  summary: string;
  scenes: SceneInfo[];
}

export interface SceneAnalysisResult {
  videos: VideoAnalysis[];
}

export interface SubSource {
  source_video: string;
  source_index: number;
  start_time: number;
  end_time: number;
  position: string;
  thumbnail_url: string;
  video_url: string;
}

export interface ClipPlan {
  clip_id: string;
  source_video: string;
  source_index: number;
  start_time: number;
  end_time: number;
  timeline_start: number;
  audio: string;
  transition: string;
  ken_burns: string;
  thumbnail_url: string;
  video_url: string;
  layout: string;
  sub_sources: SubSource[];
}

export interface TextOverlay {
  overlay_id: string;
  text: string;
  start_time: number;
  end_time: number;
  position: string;
  font_size: number;
  color: string;
  style: string;
}

export interface EditingPlan {
  music_track: string;
  total_duration: number;
  clips: ClipPlan[];
  text_overlays: TextOverlay[];
  description: string;
}

export interface SessionSettings {
  prompt: string;
  reel_style: string;
  reel_approach: string;
  target_duration: number;
  bpm: number;
  captions: boolean;
  audio_mode: string;
  transition_style: string;
  gemini_model: string;
  composite_layouts: string[];
}

export interface ClipSuggestion {
  source_video: string;
  source_index: number;
  start_time: number;
  end_time: number;
  reason: string;
  thumbnail_url: string;
  video_url: string;
}

export interface CaptionSuggestion {
  text: string;
  style: string;
  tone: string;
}

export type Step = "home" | "upload" | "analyze" | "prompt" | "edit" | "render" | "preview";

export interface CompletedProject {
  project_id: string;
  name: string;
  description: string;
  output_url: string;
  thumbnail_url: string;
  duration: number;
  created_at: number;
}

export interface DraftInfo {
  session_id: string;
  video_count: number;
  has_analysis: boolean;
  has_plan: boolean;
  prompt: string;
  created_at: number;
}

export interface HomeData {
  projects: CompletedProject[];
  draft: DraftInfo | null;
}

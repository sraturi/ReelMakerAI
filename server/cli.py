"""CLI entry point for Reelvo."""

import argparse
import logging
import sys
from pathlib import Path

from config import VIDEO_EXTENSIONS


def _choose(prompt: str, options: list[tuple[str, str]]) -> str:
    """Present a numbered menu and return the chosen key."""
    print(f"\n{prompt}")
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}) {label}")
    while True:
        choice = input(f"Choice [1-{len(options)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(options):
            return options[int(choice) - 1][0]
        print("  Invalid choice, try again.")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Reelvo - Create beat-synced reels with AI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py --videos test-videos/ --prompt "Promote my eyelashes course"
  python cli.py --videos video1.mp4 video2.mp4 --prompt "Summer vibes montage"
        """,
    )
    parser.add_argument(
        "--videos", nargs="+", required=True,
        help="Video files or a folder containing videos",
    )
    parser.add_argument(
        "--prompt", required=True,
        help="Creative direction for the reel (e.g., 'Promote my eyelashes course')",
    )

    args = parser.parse_args()

    # Expand directories into video files
    video_paths: list[str] = []
    for vpath in args.videos:
        p = Path(vpath)
        if p.is_dir():
            found = sorted(f for f in p.iterdir() if f.suffix.lower() in VIDEO_EXTENSIONS)
            if not found:
                print(f"Error: No video files found in {vpath}")
                sys.exit(1)
            video_paths.extend(str(f) for f in found)
        elif p.exists():
            video_paths.append(str(p))
        else:
            print(f"Error: Not found: {vpath}")
            sys.exit(1)

    if not video_paths:
        print("Error: No video files provided")
        sys.exit(1)

    # Interactive menus
    reel_style = _choose("Reel style?", [
        ("travel", "Travel / Adventure"),
        ("vlog", "Mini Vlog"),
        ("tutorial", "Tutorial / How-to"),
        ("montage", "Montage / Highlight"),
        ("aesthetic", "Aesthetic / Cinematic"),
        ("promo", "Promo / Business"),
    ])

    reel_approach = _choose("Reel approach?", [
        ("hook", "Hook-first (best shot opens the reel)"),
        ("story", "Story (chronological narrative, build to climax)"),
    ])

    duration_options = [10, 15, 20, 30, 40, 45]
    print("\nSelect reel length:")
    for i, d in enumerate(duration_options, 1):
        print(f"  {i}) {d} seconds")
    while True:
        choice = input(f"Choice [1-{len(duration_options)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(duration_options):
            target_duration = duration_options[int(choice) - 1]
            break
        print("  Invalid choice, try again.")

    captions = _choose("Add captions?", [("yes", "Yes"), ("no", "No")]) == "yes"

    audio_mode = _choose("Audio mode?", [
        ("voice", "Voice only (smart — mutes ambient clips)"),
        ("original", "Original audio (keeps all clip audio as-is)"),
    ])

    transition_style = _choose("Transition style?", [
        ("auto", "Auto (AI picks per clip)"),
        ("smooth", "Smooth (fade, dissolve, fadeblack)"),
        ("dynamic", "Dynamic (wipes, slides)"),
        ("dramatic", "Dramatic (circle open, radial)"),
        ("cut", "Hard cut (no transitions)"),
    ])

    gemini_model = _choose("Gemini model?", [
        ("gemini-2.5-flash", "Gemini 2.5 Flash (fast, cheaper)"),
        ("gemini-2.5-pro", "Gemini 2.5 Pro (smarter, slower)"),
    ])

    # BPM prompt — match the song you'll add later on Instagram
    bpm_options = [90, 100, 110, 120, 128, 140]
    print("\nSong BPM? (match the song you'll add on Instagram)")
    for i, b in enumerate(bpm_options, 1):
        print(f"  {i}) {b} BPM")
    print(f"  {len(bpm_options) + 1}) Custom")
    bpm = 120  # default
    while True:
        bpm_choice = input(f"Choice [1-{len(bpm_options) + 1}]: ").strip()
        if bpm_choice.isdigit():
            idx = int(bpm_choice)
            if 1 <= idx <= len(bpm_options):
                bpm = bpm_options[idx - 1]
                break
            elif idx == len(bpm_options) + 1:
                custom = input("  Enter BPM (60-200): ").strip()
                if custom.isdigit() and 60 <= int(custom) <= 200:
                    bpm = int(custom)
                    break
                print("  Invalid BPM, try again.")
            else:
                print("  Invalid choice, try again.")
        else:
            print("  Invalid choice, try again.")

    # Summary
    style_labels = dict([
        ("travel", "Travel / Adventure"), ("vlog", "Mini Vlog"),
        ("tutorial", "Tutorial / How-to"), ("montage", "Montage / Highlight"),
        ("aesthetic", "Aesthetic / Cinematic"), ("promo", "Promo / Business"),
    ])
    approach_labels = {"hook": "Hook-first", "story": "Story"}
    audio_labels = {"voice": "Voice only (smart)", "original": "Original audio"}

    print("=" * 50)
    print("  Reelvo")
    print("=" * 50)
    print(f"  Videos: {len(video_paths)} files")
    for v in video_paths:
        print(f"    - {Path(v).name}")
    print(f"  Prompt: {args.prompt}")
    print(f"  Style: {style_labels[reel_style]}")
    print(f"  Approach: {approach_labels[reel_approach]}")
    print(f"  Duration: {target_duration}s")
    print(f"  Captions: {'Yes' if captions else 'No'}")
    print(f"  Audio: {audio_labels[audio_mode]}")
    print(f"  BPM: {bpm}")
    transition_labels = {"auto": "Auto", "smooth": "Smooth", "dynamic": "Dynamic", "dramatic": "Dramatic", "cut": "Hard cut"}
    print(f"  Transitions: {transition_labels[transition_style]}")
    print(f"  Model: {gemini_model}")
    print("=" * 50)

    from pipeline import run_pipeline

    try:
        output = run_pipeline(
            video_paths, args.prompt,
            target_duration=target_duration,
            captions=captions,
            audio_mode=audio_mode,
            bpm=bpm,
            reel_style=reel_style,
            reel_approach=reel_approach,
            transition_style=transition_style,
            model=gemini_model,
        )
        print(f"\n{'=' * 50}")
        print(f"  Output: {output}")
        print(f"{'=' * 50}")
    except Exception as e:
        logging.getLogger(__name__).error("Pipeline failed: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Build the lecture videos of the book from the slide modules in slides/.

For one lecture (a module in slides/ with NAME, KICKER and SLIDES): render
every slide step to a 1920 x 1080 PNG with headless Chrome, synthesize each
step's narration with edge-tts, lay out a timeline (narration plus pauses,
0.4 s crossfades between images) and encode an MP4 (H.264, AAC, Korean
subtitle track) with ffmpeg. Also writes the subtitles (SRT) and the script
(Markdown).

Usage:
  python build_lecture.py --lecture part1 --tts PATH_TO_edge-tts [--ffmpeg PATH] [--webm]
  python build_lecture.py --all --tts ...       # overview and every part lecture
  python build_lecture.py --lecture part1 --preview   # PNGs only, in build/part1/

ffmpeg defaults to the binary of the imageio-ffmpeg package if it is installed.
"""

import argparse
import html
import importlib
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
BUILD = HERE / "build"
VIDEOS = HERE / "videos"
SCRIPTS = HERE / "scripts"
LECTURES = sorted(p.stem for p in (HERE / "slides").glob("*.py") if p.stem not in ("__init__", "common"))
W, H, FPS = 1920, 1080, 10
FADE = 4                      # frames of crossfade between step images
PAUSE_STEP, PAUSE_SLIDE, LEAD = 0.45, 0.9, 0.6
RATE = 24000

SHOW = """<script>
const step = parseInt((location.hash || '#1').slice(1), 10);
for (const el of document.querySelectorAll('[data-s]')) {
  if (parseInt(el.getAttribute('data-s'), 10) > step) el.style.visibility = 'hidden';
}
</script>"""


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, **kw)


def render_slides(mod, build):
    css = (HERE / "lecture.css").read_text(encoding="utf-8")
    out = []
    n = len(mod.SLIDES)
    for i, s in enumerate(mod.SLIDES, 1):
        title = f"<div class='kicker'>{html.escape(mod.KICKER)}</div><h1>{html.escape(s['title'])}</h1>" \
            if s["title"] else ""
        doc = (f"<!doctype html><html lang='ko'><head><meta charset='utf-8'><style>{css}</style></head><body>"
               f"<div class='frame'><div class='topline'></div>{title}{s['html']}"
               f"<div class='bar' style='width:{1920 * i / n:.0f}px'></div><div class='pageno'>{i} / {n}</div></div>"
               f"{SHOW}</body></html>")
        page = build / f"slide{i:02d}.html"
        page.write_text(doc, encoding="utf-8")
        for k in range(1, len(s["steps"]) + 1):
            png = build / f"s{i:02d}_{k}.png"
            run(["google-chrome", "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                 "--allow-file-access-from-files", f"--window-size={W},{H}", "--virtual-time-budget=3000",
                 f"--screenshot={png}", f"{page.as_uri()}#{k}"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            out.append((i, k, png, s["steps"][k - 1]))
    return out


def tts(steps, build, exe, voice, rate):
    clips = []
    for i, k, _, text in steps:
        mp3 = build / f"a{i:02d}_{k}.mp3"
        wav = build / f"a{i:02d}_{k}.wav"
        txt = build / f"a{i:02d}_{k}.txt"
        if not mp3.exists() or not txt.exists() or txt.read_text(encoding="utf-8") != text:
            run([exe, "--voice", voice, f"--rate={rate}", "--text", text, "--write-media", str(mp3)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            txt.write_text(text, encoding="utf-8")
        run(["gst-launch-1.0", "-q", "filesrc", f"location={mp3}", "!", "decodebin", "!", "audioconvert", "!",
             "audioresample", "!", f"audio/x-raw,format=S16LE,rate={RATE},channels=1", "!", "wavenc", "!",
             "filesink", f"location={wav}"])
        with wave.open(str(wav)) as w:
            clips.append(w.readframes(w.getnframes()))
    return clips


def srt_time(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def build_one(name, args):
    mod = importlib.import_module(f"slides.{name}")
    build = BUILD / name
    build.mkdir(parents=True, exist_ok=True)
    steps = render_slides(mod, build)
    if args.preview:
        print(f"{name}: {len(steps)} step images in {build}")
        return
    clips = tts(steps, build, args.tts, args.voice, args.rate)

    # Timeline: lead-in, then each step's narration followed by a pause.
    audio = bytearray(b"\x00\x00" * int(LEAD * RATE))
    spans = []
    t = LEAD
    for idx, ((i, k, png, text), clip) in enumerate(zip(steps, clips)):
        last_of_slide = idx + 1 == len(steps) or steps[idx + 1][0] != i
        start = t
        audio += clip
        t += len(clip) / 2 / RATE
        spans.append((start, t, png, text))
        pause = PAUSE_SLIDE if last_of_slide else PAUSE_STEP
        audio += b"\x00\x00" * int(pause * RATE)
        t += pause
    total = t
    with wave.open(str(build / "narration.wav"), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(bytes(audio))

    # Frames: each step image is shown from its narration start (the first from 0)
    # until the next step starts; a crossfade leads into every new image.
    frames_dir = build / "frames"
    if frames_dir.exists():
        shutil.rmtree(frames_dir)
    frames_dir.mkdir()
    uniq = build / "uniq"
    uniq.mkdir(exist_ok=True)
    starts = [0.0] + [s for s, _, _, _ in spans[1:]]
    images = [png for _, _, png, _ in spans]
    nframes = int(total * FPS) + 1
    cache = {}

    def still(png):
        key = (png, None)
        if key not in cache:
            p = uniq / f"{png.stem}.jpg"
            Image.open(png).convert("RGB").save(p, quality=92)
            cache[key] = p
        return cache[key]

    def blend(a, b, j):
        key = (a, b, j)
        if key not in cache:
            p = uniq / f"{a.stem}__{b.stem}_{j}.jpg"
            Image.blend(Image.open(a).convert("RGB"), Image.open(b).convert("RGB"), j / FADE).save(p, quality=92)
            cache[key] = p
        return cache[key]

    seg = 0
    for f in range(nframes):
        tf = f / FPS
        while seg + 1 < len(starts) and tf >= starts[seg + 1]:
            seg += 1
        since = int((tf - starts[seg]) * FPS)
        if seg > 0 and since < FADE and images[seg] != images[seg - 1]:
            src = blend(images[seg - 1], images[seg], since + 1)
        else:
            src = still(images[seg])
        os.symlink(src, frames_dir / f"{f:05d}.jpg")

    # Subtitles and script.
    VIDEOS.mkdir(exist_ok=True)
    SCRIPTS.mkdir(exist_ok=True)
    srt = []
    md = [f"# {mod.KICKER} 대본", ""]
    last_slide = None
    for n, (start, end, png, text) in enumerate(spans, 1):
        srt += [str(n), f"{srt_time(start)} --> {srt_time(end)}", text, ""]
        slide = png.stem.split("_")[0]
        if slide != last_slide:
            num = int(slide[1:])
            title = mod.SLIDES[num - 1]["title"] or ("시작" if num == 1 else "마무리")
            md += [f"## {num}. {title}", ""]
            last_slide = slide
        md += [text, ""]
    srt_path = VIDEOS / f"{mod.NAME}.srt"
    srt_path.write_text("\n".join(srt), encoding="utf-8")
    (SCRIPTS / f"{mod.NAME}.md").write_text("\n".join(md), encoding="utf-8")

    out = VIDEOS / f"{mod.NAME}.mp4"
    run([args.ffmpeg, "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", str(frames_dir / "%05d.jpg"),
         "-i", str(build / "narration.wav"), "-i", str(srt_path),
         "-map", "0:v", "-map", "1:a", "-map", "2:s",
         "-c:v", "libx264", "-preset", "slow", "-tune", "stillimage", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-c:s", "mov_text", "-metadata:s:s:0", "language=kor",
         "-metadata", f"title={mod.KICKER}", "-movflags", "+faststart", "-shortest", str(out)])
    if args.webm:
        run(["gst-launch-1.0", "-q",
             "multifilesrc", f"location={frames_dir}/%05d.jpg", "index=0", f"caps=image/jpeg,framerate={FPS}/1",
             "!", "jpegdec", "!", "videoconvert", "!", "video/x-raw,format=I420", "!",
             "vp9enc", "deadline=1", "cpu-used=8", "threads=8", "target-bitrate=1500000", "end-usage=vbr",
             "keyframe-max-dist=50", "!", "queue", "!", "webmmux", "name=mux", "!", "filesink",
             f"location={out.with_suffix('.webm')}",
             "filesrc", f"location={build / 'narration.wav'}", "!", "wavparse", "!", "audioconvert", "!",
             "audioresample", "!", "audio/x-raw,rate=48000", "!", "opusenc", "bitrate=96000", "!", "queue", "!",
             "mux."])
    print(f"{out}: {total:.1f} s, {len(steps)} steps, {nframes} frames, {out.stat().st_size / 1e6:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lecture", choices=LECTURES)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--tts")
    ap.add_argument("--voice", default="ko-KR-SunHiNeural")
    ap.add_argument("--rate", default="+0%")
    ap.add_argument("--ffmpeg")
    ap.add_argument("--webm", action="store_true", help="also write a WebM (VP9, Opus) with GStreamer")
    ap.add_argument("--preview", action="store_true", help="render the step images only")
    args = ap.parse_args()
    if not args.preview:
        if not args.tts:
            ap.error("--tts is required unless --preview")
        if not args.ffmpeg:
            import imageio_ffmpeg
            args.ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    names = [n for n in LECTURES if (HERE / "slides" / f"{n}.py").exists()] if args.all else [args.lecture]
    for name in names:
        build_one(name, args)


if __name__ == "__main__":
    main()

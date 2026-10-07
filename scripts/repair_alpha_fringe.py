"""Offline green-screen fringe repair for alpha WebM character media.

Requires NumPy/OpenCV in the media-processing environment only. It does not
add application dependencies, change alpha, or alter animation timing. Output
must be staged separately; installation requires decoded and visual review.
"""

from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time


def repair_rgba(frame, edge_band: float = 8):
    """Restore contaminated edge hue, preserving matte and solid green props."""
    import cv2
    import numpy as np

    if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 4:
        raise ValueError("Expected an H x W x 4 uint8 RGBA frame")
    if edge_band <= 0:
        raise ValueError("edge_band must be positive")
    alpha = frame[:, :, 3]
    rgb = frame[:, :, :3].astype(np.float32)
    r, g, b = cv2.split(rgb)
    inside = cv2.distanceTransform(np.uint8(alpha >= 32), cv2.DIST_L2, 5)
    green = (g > r + 3) & (g > b + 12) & (alpha >= 64)
    _, labels, _, _ = cv2.connectedComponentsWithStats(np.uint8(green), 8)
    green_depth = cv2.distanceTransform(np.uint8(green), cv2.DIST_L2, 5)
    protected_ids = np.unique(labels[(green_depth >= 3) & (inside > edge_band)])
    protected = np.isin(labels, protected_ids[protected_ids != 0])
    safe = (alpha >= 240) & (inside > 3) & (
        (r - g >= .2 * np.maximum(r - b, 1))
        | ((rgb.max(axis=2) - rgb.min(axis=2)) <= 12)
        | (b >= g)
    )
    stats = {
        "recolored_pixels": 0,
        "protected_green_pixels": int(protected.sum()),
    }
    if not np.any(safe):
        return frame.copy(), stats

    def nearest(colors, valid):
        distances, indices = cv2.distanceTransformWithLabels(
            np.uint8(~valid), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
        )
        palette = np.zeros((int(indices.max()) + 1, 3), np.float32)
        palette[indices[valid]] = colors[valid]
        return palette[indices], distances

    donors, distances = nearest(rgb, safe)
    # R can exceed G in olive contamination, so strict G > R is insufficient.
    suspect = (g > b + 18) & (g > r - .18 * (r - b))
    affected = (
        (alpha > 0) & (inside <= edge_band) & suspect
        & ~protected & (distances <= 32)
    )
    # Keep the local stroke's shading instead of painting a bright flat collar.
    weights = np.array([.2126, .7152, .0722], np.float32)
    shade = np.clip((rgb @ weights) / np.maximum(donors @ weights, 1), .65, 1.2)
    rgb[affected] = (donors * shade[:, :, None])[affected]

    # Invisible RGB participates in YUV420 chroma averaging. Bleed clean
    # foreground through ten invisible pixels before the VP9 encoder sees it.
    padded, outside = nearest(rgb, alpha >= 64)
    collar = (alpha == 0) & (outside <= 10)
    rgb[collar] = padded[collar]
    rgb[(alpha == 0) & (outside > 10)] = 0
    result = frame.copy()
    result[:, :, :3] = np.uint8(np.clip(np.rint(rgb), 0, 255))
    stats["recolored_pixels"] = int(affected.sum())
    return result, stats


def probe_video(source: Path, ffmpeg: str) -> dict:
    """Read stream dimensions/rate without relying on the decoder's alpha hint."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    probe = Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix)
    if probe.is_file():
        result = subprocess.run(
            [str(probe), "-v", "error", "-select_streams", "v:0",
             "-show_streams", "-of", "json", str(source)],
            capture_output=True, check=True, creationflags=flags,
        )
        stream = json.loads(result.stdout)["streams"][0]
        rate = stream.get("avg_frame_rate", "0/0")
        if rate == "0/0":
            rate = stream["r_frame_rate"]
        return {"width": int(stream["width"]), "height": int(stream["height"]),
                "fps": str(Fraction(rate)), "codec": stream["codec_name"]}
    result = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", str(source), "-frames:v", "0",
         "-f", "null", "-"], capture_output=True, check=True, creationflags=flags,
    )
    header = result.stderr.decode("utf-8", errors="replace")
    line = next((s for s in header.splitlines() if "Video:" in s), "")
    size = re.search(r"(?<!\d)(\d{2,5})x(\d{2,5})(?!\d)", line)
    rate = re.search(r"([\d.]+) fps", line)
    if not size or not rate:
        raise ValueError("Cannot identify video dimensions/rate")
    return {"width": int(size[1]), "height": int(size[2]),
            "fps": str(Fraction(rate[1])), "codec": "vp9" if "vp9" in line else "unknown"}


def repair_video(source: Path, destination: Path, ffmpeg: str, edge_band: float = 8) -> dict:
    """Stage one clip with alpha-aware decode and lossless VP9 alpha encode."""
    import cv2
    import numpy as np

    source, destination = Path(source), Path(destination)
    if source.resolve() == destination.resolve():
        raise ValueError("Refusing to overwrite the input video")
    if destination.exists():
        raise FileExistsError(destination)
    metadata = probe_video(source, ffmpeg)
    if metadata["codec"] != "vp9":
        raise ValueError("This pipeline expects alpha VP9 WebM input")
    cv2.setNumThreads(1)
    width, height = metadata["width"], metadata["height"]
    destination.parent.mkdir(parents=True, exist_ok=True)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    temporary = tempfile.NamedTemporaryFile(
        prefix=destination.stem + "-", suffix=".webm", dir=destination.parent, delete=False
    )
    temporary.close()
    temporary_path = Path(temporary.name)
    frames = recolored = protected = 0
    processing_seconds = 0.
    started = time.perf_counter()
    decoder = encoder = None
    try:
        with tempfile.TemporaryFile() as decode_errors, tempfile.TemporaryFile() as encode_errors:
            decoder = subprocess.Popen(
                [ffmpeg, "-v", "error", "-threads", "1", "-c:v", "libvpx-vp9",
                 "-i", str(source), "-map", "0:v:0", "-vsync", "0",
                 "-f", "rawvideo", "-pix_fmt", "rgba", "pipe:1"],
                stdout=subprocess.PIPE, stderr=decode_errors, creationflags=flags,
            )
            encoder = subprocess.Popen(
                [ffmpeg, "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgba",
                 "-s", f"{width}x{height}", "-r", metadata["fps"], "-i", "pipe:0",
                 "-an", "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-auto-alt-ref", "0",
                 "-b:v", "0", "-lossless", "1", "-row-mt", "1", "-threads", "2",
                 "-cpu-used", "4", str(temporary_path)],
                stdin=subprocess.PIPE, stderr=encode_errors, creationflags=flags,
            )
            frame_bytes = width * height * 4
            while True:
                raw = decoder.stdout.read(frame_bytes)
                if not raw:
                    break
                if len(raw) != frame_bytes:
                    raise ValueError("Incomplete decoded RGBA frame")
                frame = np.frombuffer(raw, np.uint8).reshape(height, width, 4)
                processing_started = time.perf_counter()
                fixed, stats = repair_rgba(frame, edge_band)
                processing_seconds += time.perf_counter() - processing_started
                if not np.array_equal(fixed[:, :, 3], frame[:, :, 3]):
                    raise AssertionError("Alpha changed before encoding")
                encoder.stdin.write(fixed.tobytes())
                frames += 1
                recolored += stats["recolored_pixels"]
                protected += stats["protected_green_pixels"]
            decoder.stdout.close()
            encoder.stdin.close()
            if decoder.wait(timeout=30) or encoder.wait(timeout=120):
                decode_errors.seek(0)
                encode_errors.seek(0)
                raise RuntimeError((decode_errors.read() + encode_errors.read()).decode("utf-8", errors="replace"))
        if not frames:
            raise ValueError("No decoded frames")
        # A failure leaves the original untouched and cannot masquerade as a
        # completed destination. The caller still must decode the staged file.
        os.replace(temporary_path, destination)
    finally:
        for process in (decoder, encoder):
            if process is not None:
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=5)
                for stream in (process.stdin, process.stdout):
                    if stream and not stream.closed:
                        stream.close()
        if temporary_path.exists():
            temporary_path.unlink()
    return {
        "source": str(source), "destination": str(destination),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "sha256": hashlib.sha256(destination.read_bytes()).hexdigest(),
        **metadata, "frames": frames, "edge_band": edge_band,
        "recolored_pixels": recolored, "protected_green_pixels": protected,
        "processing_seconds": processing_seconds, "elapsed_seconds": time.perf_counter() - started,
        "alpha_preencode_exact": True, "visual_acceptance": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--edge-band", type=float, default=8)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    record = repair_video(args.source, args.destination, args.ffmpeg, args.edge_band)
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

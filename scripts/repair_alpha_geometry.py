"""Offline alpha antialiasing and a fixed uniform transform for each WebM.

NumPy/OpenCV are production-tool dependencies only. Choose the placement from
reviewed character landmarks, never from a prop/particle union or per-frame
recentering. Review the decoded output before installing it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import time

from scripts.repair_alpha_fringe import probe_video


def smooth_transform_rgba(frame, *, scale=1., dx=0., dy=0., sigma=.65):
    """Soften matte coverage and resample premultiplied RGBA without a halo."""
    import cv2
    import numpy as np

    if frame.dtype != np.uint8 or frame.ndim != 3 or frame.shape[2] != 4:
        raise ValueError("Expected an H x W x 4 uint8 RGBA frame")
    if not all(math.isfinite(value) for value in (scale, dx, dy, sigma)):
        raise ValueError("Transform parameters must be finite")
    if scale <= 0 or sigma < 0 or sigma > 2:
        raise ValueError("scale must be positive and sigma must be in [0, 2]")
    height, width = frame.shape[:2]
    alpha = frame[:, :, 3].astype(np.float32) / 255
    rgb = frame[:, :, :3].astype(np.float32) / 255
    valid = alpha >= 32 / 255
    if not np.any(valid):
        return np.zeros_like(frame), {"alpha_mass_before": float(alpha.sum()),
                                      "alpha_mass_after": 0., "partial_pixels": 0}

    def extend(colors, donors):
        distances, indices = cv2.distanceTransformWithLabels(
            np.uint8(~donors), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL
        )
        palette = np.zeros((int(indices.max()) + 1, 3), np.float32)
        palette[indices[donors]] = colors[donors]
        return palette[indices], distances

    # The new matte extends slightly outside the old silhouette. Fill its
    # color from the foreground before increasing coverage, so invisible
    # black, white or key-color RGB cannot enter the visible outline.
    donors, _ = extend(rgb, valid)
    rgb[alpha == 0] = donors[alpha == 0]
    if sigma:
        alpha_smooth = cv2.GaussianBlur(
            alpha, (0, 0), sigmaX=sigma, sigmaY=sigma,
            borderType=cv2.BORDER_CONSTANT,
        )
    else:
        alpha_smooth = alpha
    premultiplied = np.dstack((rgb * alpha_smooth[:, :, None], alpha_smooth))
    matrix = np.float32([[scale, 0, dx], [0, scale, dy]])
    warped = cv2.warpAffine(
        premultiplied, matrix, (width, height), flags=cv2.INTER_LANCZOS4,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0),
    )
    out_alpha = np.clip(warped[:, :, 3], 0, 1)
    out_rgb = np.clip(warped[:, :, :3], 0, out_alpha[:, :, None])
    out_rgb /= np.maximum(out_alpha[:, :, None], 1e-8)
    result = np.uint8(np.clip(np.rint(np.dstack((out_rgb, out_alpha)) * 255), 0, 255))
    # Chroma subsampling reads even zero-alpha RGB. Leave a clean invisible
    # collar for the alpha VP9 encoder, just as in the fringe repair tool.
    valid_out = result[:, :, 3] >= 32
    if np.any(valid_out):
        padded, distance = extend(result[:, :, :3].astype(np.float32), valid_out)
        collar = (result[:, :, 3] == 0) & (distance <= 10)
        result[:, :, :3][collar] = np.uint8(np.clip(padded[collar], 0, 255))
        result[:, :, :3][(result[:, :, 3] == 0) & (distance > 10)] = 0
    return result, {
        "alpha_mass_before": float(alpha.sum()),
        "alpha_mass_after": float(result[:, :, 3].sum() / 255),
        "partial_pixels": int(np.count_nonzero((result[:, :, 3] > 0) & (result[:, :, 3] < 255))),
    }


def transform_video(source: Path, destination: Path, ffmpeg: str, *,
                    scale=1., dx=0., dy=0., sigma=.65) -> dict:
    """Encode a staged alpha VP9 file, preserving the complete source timeline."""
    import numpy as np

    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination or destination.exists():
        raise ValueError("Use a separate, new destination; never overwrite source media")
    # Validate before launching processes, including empty or all-transparent
    # inputs whose processing otherwise might bypass parameter validation.
    smooth_transform_rgba(np.zeros((1, 1, 4), np.uint8), scale=scale, dx=dx, dy=dy, sigma=sigma)
    metadata = probe_video(source, ffmpeg)
    width, height = metadata["width"], metadata["height"]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = tempfile.NamedTemporaryFile(
        prefix=destination.stem + "-", suffix=".webm", dir=destination.parent, delete=False
    )
    temporary.close()
    temporary_path = Path(temporary.name)
    frames = partial = 0
    processing_seconds = 0.
    mass_before = mass_after = 0.
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
                fixed, stats = smooth_transform_rgba(frame, scale=scale, dx=dx, dy=dy, sigma=sigma)
                processing_seconds += time.perf_counter() - processing_started
                encoder.stdin.write(fixed.tobytes())
                frames += 1
                partial += stats["partial_pixels"]
                mass_before += stats["alpha_mass_before"]
                mass_after += stats["alpha_mass_after"]
            decoder.stdout.close()
            encoder.stdin.close()
            if decoder.wait(timeout=30) or encoder.wait(timeout=120):
                decode_errors.seek(0)
                encode_errors.seek(0)
                raise RuntimeError((decode_errors.read() + encode_errors.read()).decode("utf-8", errors="replace"))
        if not frames:
            raise ValueError("No decoded frames")
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
        **metadata, "frames": frames, "scale": scale, "dx": dx, "dy": dy, "sigma": sigma,
        "partial_pixels": partial, "alpha_mass_before": mass_before, "alpha_mass_after": mass_after,
        "processing_seconds": processing_seconds, "elapsed_seconds": time.perf_counter() - started,
        "visual_acceptance": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--scale", type=float, default=1.)
    parser.add_argument("--dx", type=float, default=0.)
    parser.add_argument("--dy", type=float, default=0.)
    parser.add_argument("--sigma", type=float, default=.65)
    parser.add_argument("--record", type=Path)
    args = parser.parse_args()
    result = transform_video(args.source, args.destination, args.ffmpeg,
                             scale=args.scale, dx=args.dx, dy=args.dy, sigma=args.sigma)
    if args.record:
        args.record.parent.mkdir(parents=True, exist_ok=True)
        args.record.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

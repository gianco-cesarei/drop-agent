"""
High-Resolution Artwork Manager for Drop Agent.
Handles downloading, Lanczos resizing (1400x1400px minimum), square cropping,
sRGB color normalization, and fallback artwork generation for vinyl/DJ releases.
"""

from __future__ import annotations

import io
import logging
import os
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Tuple

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageDraw = None
    ImageFont = None
    PIL_AVAILABLE = False

logger = logging.getLogger("drop_agent.artwork")

DEFAULT_MIN_DIMENSION = 1400
JPEG_QUALITY = 95


class ArtworkManager:
    """Manages downloading, processing, and generating high-resolution cover art."""

    def __init__(self, target_size: int = DEFAULT_MIN_DIMENSION):
        self.target_size = target_size

    def download_and_process_artwork(
        self,
        image_url: str,
        output_path: str,
        target_size: Optional[int] = None
    ) -> Optional[str]:
        """
        Downloads image from image_url, crops to square, scales to target_size x target_size,
        and saves as high-quality sRGB JPEG.
        Returns the absolute path to the saved artwork, or None if failed.
        """
        size = target_size or self.target_size
        if not image_url:
            return None

        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Accept": "image/webp,image/apng,image/*,*/*;q=0.8"
        }

        try:
            req = urllib.request.Request(image_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                if resp.status == 200:
                    raw_bytes = resp.read()
                    return self.process_image_bytes(raw_bytes, output_path, size=size)
        except Exception as e:
            logger.warning("Failed to download artwork from %s: %s", image_url, e)
            return None

    def process_image_bytes(
        self,
        image_bytes: bytes,
        output_path: str,
        size: Optional[int] = None
    ) -> Optional[str]:
        """Processes raw image bytes into standardized high-res JPEG."""
        if not PIL_AVAILABLE:
            logger.warning("Pillow (PIL) is not installed. Artwork processing skipped. Install via: pip install Pillow")
            return None

        dim = size or self.target_size
        try:
            img = Image.open(io.BytesIO(image_bytes))
            # Convert RGBA/P/etc. to RGB
            if img.mode != "RGB":
                img = img.convert("RGB")

            # Square crop (center)
            width, height = img.size
            min_edge = min(width, height)
            left = (width - min_edge) // 2
            top = (height - min_edge) // 2
            right = left + min_edge
            bottom = top + min_edge
            img_cropped = img.crop((left, top, right, bottom))

            # Resize to target dimension using Lanczos filter
            final_img = img_cropped.resize((dim, dim), Image.Resampling.LANCZOS)

            # Ensure parent directories exist
            out_p = Path(output_path)
            out_p.parent.mkdir(parents=True, exist_ok=True)

            # Save high-res JPEG
            final_img.save(
                str(out_p),
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
                progressive=True
            )
            logger.info("Saved high-res %dx%d artwork to %s", dim, dim, output_path)
            return str(out_p)
        except Exception as e:
            logger.error("Failed to process image bytes: %s", e)
            return None

    def generate_fallback_artwork(
        self,
        title: str,
        artist: str,
        label: Optional[str] = None,
        genre: Optional[str] = None,
        output_path: Optional[str] = None,
        size: Optional[int] = None
    ) -> Optional[str]:
        """
        Generates an elegant, minimalist vinyl/club style placeholder artwork (1400x1400)
        when no online cover art is found.
        """
        if not PIL_AVAILABLE:
            logger.warning("Pillow (PIL) is not installed. Fallback artwork generation skipped. Install via: pip install Pillow")
            return None

        dim = size or self.target_size
        out_file = output_path or "/tmp/drops_cover.jpg"
        
        # Dark minimalist background with radial DJ vinyl groove aesthetics
        img = Image.new("RGB", (dim, dim), color=(14, 16, 22))
        draw = ImageDraw.Draw(img)

        # Draw subtle vinyl grooves (rings)
        center = (dim // 2, dim // 2)
        for r in range(dim // 6, dim // 2, 28):
            draw.ellipse(
                (center[0] - r, center[1] - r, center[0] + r, center[1] + r),
                outline=(28, 32, 42),
                width=2
            )

        # Center label circle
        label_r = dim // 5
        draw.ellipse(
            (center[0] - label_r, center[1] - label_r, center[0] + label_r, center[1] + label_r),
            fill=(24, 28, 38),
            outline=(64, 70, 88),
            width=3
        )
        
        # Center spindle hole
        spindle_r = 24
        draw.ellipse(
            (center[0] - spindle_r, center[1] - spindle_r, center[0] + spindle_r, center[1] + spindle_r),
            fill=(14, 16, 22),
            outline=(120, 130, 150),
            width=2
        )

        # Draw typography text
        # Header / Branding
        draw.text((80, 80), "DROPS CURATED RELEASE", fill=(130, 140, 160))
        if genre:
            draw.text((dim - 80 - len(genre) * 12, 80), genre.upper(), fill=(90, 200, 160))

        # Bottom Artist & Title
        artist_display = (artist or "Unknown Artist")[:40]
        title_display = (title or "Exclusive Track")[:45]
        label_display = f"LABEL: {label}" if label else "DROPS ARCHIVE"

        draw.text((80, dim - 180), artist_display, fill=(240, 242, 245))
        draw.text((80, dim - 130), title_display, fill=(200, 205, 215))
        draw.text((80, dim - 85), label_display.upper(), fill=(110, 120, 140))

        # Save
        out_p = Path(out_file)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(out_p), format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return str(out_p)

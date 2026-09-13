"""
Metadata Tagger Engine for Drop Agent.
Embeds ID3v2.4 frames into MP3 files including:
- APIC (High-Resolution Cover Art JPEG)
- TPUB (Record Label / Publisher)
- TKEY (Camelot Key e.g. 8A, 11B)
- TBPM (Beats Per Minute)
- TSRC (Catalog Number / ISRC)
- TIT2, TPE1, TALB, TRCK, TDRC, TCON, COMM
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("drop_agent.tagger")


class MetadataTagger:
    """Writes standard ID3v2.4 metadata and high-res cover art into MP3 files."""

    @staticmethod
    def tag_mp3(
        file_path: str,
        artist: str,
        title: str,
        album: Optional[str] = None,
        track_num: Optional[int] = None,
        year: Optional[str] = None,
        genre: Optional[str] = None,
        record_label: Optional[str] = None,
        catalog_number: Optional[str] = None,
        bpm: Optional[float] = None,
        camelot_key: Optional[str] = None,
        key_name: Optional[str] = None,
        comment: Optional[str] = None,
        cover_image_path: Optional[str] = None
    ) -> bool:
        """
        Embeds full ID3v2.4 metadata and cover artwork into the MP3 file.
        Uses mutagen if installed, or high-performance FFmpeg container re-muxing.
        """
        if not os.path.exists(file_path):
            logger.error("Audio file does not exist: %s", file_path)
            return False

        # 1. Try Mutagen if installed
        try:
            import mutagen
            from mutagen.id3 import (
                ID3, ID3NoHeaderError, TIT2, TPE1, TALB, TRCK, TDRC, TCON,
                TPUB, TSRC, TBPM, TKEY, COMM, APIC, PictureType
            )

            try:
                tags = ID3(file_path)
            except ID3NoHeaderError:
                tags = ID3()

            if title:
                tags.add(TIT2(encoding=3, text=title))
            if artist:
                tags.add(TPE1(encoding=3, text=artist))
            if album:
                tags.add(TALB(encoding=3, text=album))
            if track_num:
                tags.add(TRCK(encoding=3, text=str(track_num)))
            if year:
                tags.add(TDRC(encoding=3, text=str(year)))
            if genre:
                tags.add(TCON(encoding=3, text=genre))
            if record_label:
                tags.add(TPUB(encoding=3, text=record_label))
            if catalog_number:
                tags.add(TSRC(encoding=3, text=catalog_number))
            if bpm:
                tags.add(TBPM(encoding=3, text=str(int(round(bpm)))))
            if camelot_key:
                tags.add(TKEY(encoding=3, text=camelot_key))

            # Build rich comment
            comm_parts = []
            if camelot_key:
                comm_parts.append(f"Camelot: {camelot_key}")
            if key_name:
                comm_parts.append(f"Key: {key_name}")
            if bpm:
                comm_parts.append(f"{round(bpm, 1)} BPM")
            if comment:
                comm_parts.append(comment)
            if comm_parts:
                tags.add(COMM(encoding=3, lang="eng", desc="", text=" | ".join(comm_parts)))

            # Cover Art (APIC)
            if cover_image_path and os.path.exists(cover_image_path):
                with open(cover_image_path, "rb") as art_f:
                    art_bytes = art_f.read()
                    tags.add(APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=PictureType.COVER_FRONT,
                        desc="Cover",
                        data=art_bytes
                    ))

            tags.save(file_path, v2_version=4)
            logger.info("Tagged ID3v2.4 using Mutagen: %s", os.path.basename(file_path))
            return True
        except ImportError:
            pass
        except Exception as e:
            logger.debug("Mutagen tagging failed, falling back to FFmpeg: %s", e)

        # 2. FFmpeg ID3v2.4 Tagging & APIC injection
        return MetadataTagger._tag_with_ffmpeg(
            file_path=file_path,
            artist=artist,
            title=title,
            album=album,
            track_num=track_num,
            year=year,
            genre=genre,
            record_label=record_label,
            catalog_number=catalog_number,
            bpm=bpm,
            camelot_key=camelot_key,
            key_name=key_name,
            comment=comment,
            cover_image_path=cover_image_path
        )

    @staticmethod
    def _tag_with_ffmpeg(
        file_path: str,
        artist: str,
        title: str,
        album: Optional[str] = None,
        track_num: Optional[int] = None,
        year: Optional[str] = None,
        genre: Optional[str] = None,
        record_label: Optional[str] = None,
        catalog_number: Optional[str] = None,
        bpm: Optional[float] = None,
        camelot_key: Optional[str] = None,
        key_name: Optional[str] = None,
        comment: Optional[str] = None,
        cover_image_path: Optional[str] = None
    ) -> bool:
        temp_out = file_path + ".tagged.mp3"
        has_cover = bool(cover_image_path and os.path.exists(cover_image_path))

        cmd = ["ffmpeg", "-y", "-i", file_path]
        if has_cover:
            cmd.extend(["-i", cover_image_path])

        cmd.extend(["-map", "0:a"])
        if has_cover:
            cmd.extend([
                "-map", "1:0",
                "-c:v", "copy",
                "-metadata:s:v", 'title="Album cover"',
                "-metadata:s:v", 'comment="Cover (front)"',
                "-disposition:v", "attached_pic"
            ])

        cmd.extend(["-c:a", "copy", "-id3v2_version", "4"])

        # Metadata args
        if title:
            cmd.extend(["-metadata", f"title={title}"])
        if artist:
            cmd.extend(["-metadata", f"artist={artist}"])
        if album:
            cmd.extend(["-metadata", f"album={album}"])
        if track_num:
            cmd.extend(["-metadata", f"track={track_num}"])
        if year:
            cmd.extend(["-metadata", f"date={year}", "-metadata", f"year={year}"])
        if genre:
            cmd.extend(["-metadata", f"genre={genre}"])
        if record_label:
            cmd.extend(["-metadata", f"publisher={record_label}", "-metadata", f"TPUB={record_label}"])
        if catalog_number:
            cmd.extend(["-metadata", f"ISRC={catalog_number}", "-metadata", f"TSRC={catalog_number}"])
        if bpm:
            cmd.extend(["-metadata", f"TBPM={int(round(bpm))}", "-metadata", f"BPM={round(bpm, 1)}"])
        if camelot_key:
            cmd.extend(["-metadata", f"initialkey={camelot_key}", "-metadata", f"TKEY={camelot_key}", "-metadata", f"KEY={camelot_key}"])

        # Build comment
        comm_parts = []
        if camelot_key:
            comm_parts.append(f"Camelot: {camelot_key}")
        if key_name:
            comm_parts.append(f"Key: {key_name}")
        if bpm:
            comm_parts.append(f"{round(bpm, 1)} BPM")
        if record_label:
            comm_parts.append(f"Label: {record_label}")
        if catalog_number:
            comm_parts.append(f"CatNo: {catalog_number}")
        if comment:
            comm_parts.append(comment)

        if comm_parts:
            cmd.extend(["-metadata", f"comment={' | '.join(comm_parts)}"])

        cmd.append(temp_out)

        try:
            subprocess.run(cmd, check=True, capture_output=True)
            os.replace(temp_out, file_path)
            logger.info("Tagged ID3v2.4 with FFmpeg: %s", os.path.basename(file_path))
            return True
        except subprocess.CalledProcessError as e:
            logger.error("FFmpeg tagging failed on %s: %s", file_path, e.stderr.decode("utf-8", errors="ignore"))
            if os.path.exists(temp_out):
                os.remove(temp_out)
            return False

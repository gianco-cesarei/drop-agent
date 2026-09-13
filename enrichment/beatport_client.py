"""
Beatport API & Scraper Client for Drop Agent.
Extracts label, catalog number, original key, BPM, subgenre, high-res artwork, and purchase links.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("drop_agent.beatport")

BEATPORT_SEARCH_URL = "https://www.beatport.com/api/v4/catalog/search"
BEATPORT_WEB_SEARCH = "https://www.beatport.com/search/tracks"
DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def _clean_term(term: str) -> str:
    # Strip remix tags or noise if needed
    cleaned = re.sub(r"[\[\(].*?[\]\)]", "", term)
    return re.sub(r"\s+", " ", cleaned).strip()


class BeatportClient:
    """Client for Beatport track search, BPM/Key extraction, and buy link resolution."""

    def __init__(self, user_agent: Optional[str] = None):
        self.user_agent = user_agent or DEFAULT_USER_AGENT

    def search_track(
        self,
        artist: str,
        title: str,
        label: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for track on Beatport.
        Returns parsed dictionary with:
          - bpm (float)
          - key (str)
          - genre (str) / subgenre (str)
          - label (str)
          - catalog_number (str)
          - release_year (str)
          - artwork_url (str)
          - buy_url (str)
        """
        query = f"{artist} {title}".strip()
        if not query:
            return None

        # 1. Try public search API or web endpoint
        encoded_q = urllib.parse.quote(query)
        url = f"https://www.beatport.com/api/v4/catalog/search?q={encoded_q}&per_page=5"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.beatport.com/",
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    tracks = data.get("tracks", [])
                    if tracks:
                        best = tracks[0]
                        return self._parse_api_track(best)
        except Exception as e:
            logger.debug("Beatport JSON API search failed for %s: %s", query, e)

        # 2. Fallback to HTML Scraping if JSON API is protected / unavailable
        return self._scrape_fallback(artist, title)

    def _parse_api_track(self, item: Dict[str, Any]) -> Dict[str, Any]:
        release = item.get("release", {}) or {}
        label = release.get("label", {}) or item.get("label", {}) or {}
        label_name = label.get("name")
        artists = item.get("artists", [])
        artist_names = ", ".join(a.get("name", "") for a in artists if a.get("name"))
        
        bpm = item.get("bpm")
        key = item.get("key", {}).get("name") if isinstance(item.get("key"), dict) else item.get("key")
        genre = item.get("genre", {}).get("name") if isinstance(item.get("genre"), dict) else item.get("genre")
        sub_genre = item.get("sub_genre", {}).get("name") if isinstance(item.get("sub_genre"), dict) else None

        image = item.get("image", {}) or release.get("image", {}) or {}
        artwork_url = image.get("dynamic_uri") or image.get("uri")
        if artwork_url and "{w}x{h}" in artwork_url:
            artwork_url = artwork_url.replace("{w}x{h}", "1400x1400")

        track_id = item.get("id")
        slug = item.get("slug") or "track"
        buy_url = f"https://www.beatport.com/track/{slug}/{track_id}" if track_id else None

        return {
            "source": "beatport",
            "title": item.get("name") or item.get("title"),
            "artist": artist_names,
            "label": label_name,
            "catalog_number": release.get("catalog_number"),
            "release_year": str(release.get("publish_date", ""))[:4] if release.get("publish_date") else None,
            "bpm": float(bpm) if bpm else None,
            "key": key,
            "genre": genre,
            "subgenre": sub_genre or genre,
            "artwork_url": artwork_url,
            "buy_url": buy_url,
        }

    def _scrape_fallback(self, artist: str, title: str) -> Optional[Dict[str, Any]]:
        """HTML Scraping fallback on Beatport Web Search."""
        query = f"{artist} {title}".strip()
        encoded_q = urllib.parse.quote(query)
        web_url = f"https://www.beatport.com/search/tracks?q={encoded_q}"
        
        req = urllib.request.Request(
            web_url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            }
        )

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    html = resp.read().decode("utf-8", errors="ignore")
                    # Try to extract Next.js / Hydration __NEXT_DATA__ JSON blob
                    next_data_match = re.search(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', html, re.DOTALL)
                    if next_data_match:
                        payload = json.loads(next_data_match.group(1))
                        props = payload.get("props", {}).get("pageProps", {})
                        tracks = (
                            props.get("data", {}).get("tracks", []) or
                            props.get("tracks", []) or
                            props.get("results", {}).get("tracks", []) or []
                        )
                        if tracks:
                            return self._parse_api_track(tracks[0])

                    # Regex fallback on basic HTML metadata
                    return {
                        "source": "beatport_search",
                        "buy_url": web_url,
                        "title": title,
                        "artist": artist,
                        "label": None,
                        "catalog_number": None,
                        "release_year": None,
                        "bpm": None,
                        "key": None,
                        "genre": None,
                        "artwork_url": None,
                    }
        except Exception as e:
            logger.debug("Beatport scrape fallback failed for %s: %s", query, e)
            return None

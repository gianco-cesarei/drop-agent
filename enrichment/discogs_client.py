"""
Discogs API Client for Drop Agent.
Provides rate-limited (60 req/min), cached querying for official release metadata,
catalog numbers, record labels, original release years, and primary artwork.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
import urllib.parse
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("drop_agent.discogs")

DISCOGS_API_BASE = "https://api.discogs.com"
DEFAULT_USER_AGENT = "DropAgent/2.0 +https://drops.giancarlocesarei.workers.dev"


def _clean_string(value: Optional[str]) -> str:
    if not value:
        return ""
    # Normalize spaces, strip brackets/parentheses noise
    return re.sub(r"\s+", " ", value).strip()


class DiscogsClient:
    """Rate-limited client with disk caching for Discogs API v2."""

    def __init__(
        self,
        token: Optional[str] = None,
        user_agent: Optional[str] = None,
        cache_dir: Optional[str] = None,
        rate_limit_seconds: float = 1.0,
    ):
        self.token = (token or os.environ.get("DISCOGS_TOKEN", "") or os.environ.get("DISCOGS_API_TOKEN", "")).strip()
        self.user_agent = (user_agent or os.environ.get("DISCOGS_USER_AGENT", DEFAULT_USER_AGENT)).strip()
        
        # Setup cache
        cache_root = Path(cache_dir or os.path.join(os.path.dirname(__file__), "..", ".cache", "discogs"))
        self.cache_dir = cache_root
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_time = 0.0
        self._lock = threading.Lock()

    @property
    def is_authenticated(self) -> bool:
        return bool(self.token)

    def _get_cache_path(self, url: str) -> Path:
        hashed = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{hashed}.json"

    def _throttle(self) -> None:
        """Enforce rate limiting (default 1 req per sec = 60 req/min)."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < self.rate_limit_seconds:
                sleep_time = self.rate_limit_seconds - elapsed
                time.sleep(sleep_time)
            self._last_request_time = time.time()

    def _request(self, endpoint: str, params: Optional[Dict[str, str]] = None) -> Optional[Dict[str, Any]]:
        """Make an authenticated and cached HTTP GET request to Discogs API."""
        query_str = urllib.parse.urlencode({k: v for k, v in (params or {}).items() if v})
        full_url = f"{DISCOGS_API_BASE}{endpoint}" + (f"?{query_str}" if query_str else "")
        
        cache_file = self._get_cache_path(full_url)
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                return data
            except Exception as e:
                logger.debug("Cache read error for %s: %s", full_url, e)

        self._throttle()

        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/json",
        }
        if self.token:
            headers["Authorization"] = f"Discogs token={self.token}"

        req = urllib.request.Request(full_url, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=12) as resp:
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8")
                    data = json.loads(raw_data)
                    # Cache successful response
                    try:
                        cache_file.write_text(raw_data, encoding="utf-8")
                    except Exception:
                        pass
                    return data
                return None
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning("Discogs Rate limit reached (429). Pacing up...")
                time.sleep(2.0)
            elif e.code in (401, 403):
                logger.warning("Discogs Auth error (%d): check DISCOGS_TOKEN", e.code)
            else:
                logger.debug("Discogs HTTP Error %d on %s: %s", e.code, full_url, e.reason)
            return None
        except Exception as e:
            logger.debug("Discogs connection error on %s: %s", full_url, e)
            return None

    def search_release(
        self,
        artist: str,
        title: str,
        label: Optional[str] = None,
        year: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Search for a release matching artist and title on Discogs.
        Returns extracted metadata: label, catalog_number, year, styles, genres, image_url, discogs_url.
        """
        clean_art = _clean_string(artist)
        clean_tit = _clean_string(title)
        
        # 1. Precise search query
        query_candidates = [
            f"{clean_art} {clean_tit}",
            clean_tit
        ]
        
        for q in query_candidates:
            params = {
                "q": q,
                "type": "release",
                "per_page": "5"
            }
            if clean_art:
                params["artist"] = clean_art
            if clean_tit:
                params["track"] = clean_tit
                
            res = self._request("/database/search", params)
            if not res or not res.get("results"):
                # Try broader search without type constraints
                res = self._request("/database/search", {"q": q, "per_page": "5"})

            if res and res.get("results"):
                for item in res["results"]:
                    # Match score / check
                    item_title = item.get("title", "")
                    # Extract details
                    extracted = self._parse_search_result(item)
                    if extracted:
                        return extracted
        return None

    def _parse_search_result(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """Extract standardized metadata fields from a Discogs search result item."""
        labels = item.get("label", [])
        primary_label = labels[0] if labels else None
        
        catnos = item.get("catno", "")
        if isinstance(catnos, list):
            catno = catnos[0] if catnos else None
        else:
            catno = str(catnos) if catnos else None

        year = str(item.get("year", "")) if item.get("year") else None
        country = item.get("country")
        styles = item.get("style", [])
        genres = item.get("genre", [])
        
        # Cover image (Discogs primary/cover_image or thumb)
        cover_image = item.get("cover_image") or item.get("thumb")
        uri = item.get("uri")
        discogs_url = f"https://www.discogs.com{uri}" if uri else None

        return {
            "source": "discogs",
            "discogs_id": item.get("id"),
            "title": item.get("title"),
            "label": primary_label,
            "catalog_number": catno,
            "release_year": year,
            "country": country,
            "styles": styles,
            "genres": genres,
            "cover_image_url": cover_image,
            "discogs_url": discogs_url,
        }

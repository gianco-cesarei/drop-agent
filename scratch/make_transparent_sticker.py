#!/usr/bin/env python3
"""
Convert die-cut sticker on white background into true transparent PNG.
Uses flood-fill from outer corners so the inner sticker white border remains intact.
"""

from PIL import Image
import numpy as np
from collections import deque
from pathlib import Path

SRC_JPG = Path("/Users/gianco/.gemini/antigravity/brain/6ad04ccf-02a4-4549-98ca-a9187c44bab4/vinylhead_stk_eureka_1789391959510.jpg")
OUT_PNG = Path("/Users/gianco/.gemini/antigravity/brain/6ad04ccf-02a4-4549-98ca-a9187c44bab4/vinylhead_eureka_transparent.png")
WEB_DEST = Path("/Users/gianco/Documents/Claude/Projects/Drops/drops-web-frontend/public/stickers/vinylhead_eureka.png")
WEB_DEST.parent.mkdir(parents=True, exist_ok=True)

def process_sticker():
    img = Image.open(SRC_JPG).convert("RGBA")
    width, height = img.size
    data = np.array(img)
    
    # Create mask for background floodfill
    # Outer background is pure/near white (R, G, B > 240)
    visited = np.zeros((height, width), dtype=bool)
    queue = deque()
    
    # Seed the floodfill from the four corners and borders
    for x in range(width):
        queue.append((0, x))
        queue.append((height - 1, x))
    for y in range(height):
        queue.append((y, 0))
        queue.append((y, width - 1))
        
    threshold = 242
    
    while queue:
        cy, cx = queue.popleft()
        if visited[cy, cx]:
            continue
        visited[cy, cx] = True
        
        r, g, b, a = data[cy, cx]
        if r >= threshold and g >= threshold and b >= threshold:
            # Mark as transparent
            data[cy, cx, 3] = 0
            
            # Add 4-way neighbors
            for ny, nx in [(cy - 1, cx), (cy + 1, cx), (cy, cx - 1), (cy, cx + 1)]:
                if 0 <= ny < height and 0 <= nx < width and not visited[ny, nx]:
                    queue.append((ny, nx))
                    
    # Smooth edges / feather slightly
    result = Image.fromarray(data, mode="RGBA")
    result.save(OUT_PNG, "PNG")
    result.save(WEB_DEST, "PNG")
    print(f"✅ Creato sticker PNG trasparente:")
    print(f"   - {OUT_PNG}")
    print(f"   - {WEB_DEST}")

if __name__ == "__main__":
    process_sticker()

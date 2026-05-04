#!/usr/bin/env python3
"""
Run once to install required fonts for image generation.
Usage: python scripts/install_fonts.py
"""
import os, shutil, sys
import urllib.request

FONT_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'fonts')
os.makedirs(FONT_DIR, exist_ok=True)

FONTS = [
    {
        'name': 'PlayfairDisplay-Bold',
        'file': 'PlayfairDisplay-Bold.ttf',
        'system_paths': [
            'C:/Windows/Fonts/georgiab.ttf',
            'C:/Windows/Fonts/timesbd.ttf',
        ],
        'urls': [
            # Multiple working sources
            'https://raw.githubusercontent.com/clauseggers/playfair/master/fonts/ttf/PlayfairDisplay-Bold.ttf',
            'https://github.com/google/fonts/raw/refs/heads/main/ofl/playfairdisplay/static/PlayfairDisplay-Bold.ttf',
        ]
    },
    {
        'name': 'OpenSans-Bold (subtext)',
        'file': 'OpenSans-Bold.ttf',
        'system_paths': [
            '/usr/share/fonts/truetype/open-sans/OpenSans-Bold.ttf',
            '/usr/share/fonts/opentype/open-sans/OpenSans-Bold.otf',
            'C:/Windows/Fonts/arialbd.ttf',
        ],
        'urls': [
            'https://raw.githubusercontent.com/googlefonts/opensans/main/fonts/ttf/OpenSans-Bold.ttf',
        ]
    },
    {
        'name': 'LiberationSerif-Bold (headline fallback)',
        'file': 'LiberationSerif-Bold.ttf',
        'system_paths': [
            '/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf',
            '/usr/share/fonts/truetype/liberation2/LiberationSerif-Bold.ttf',
        ],
        'urls': [] # Always available on Ubuntu/Debian
    },
]

def install_font(font):
    dest = os.path.join(FONT_DIR, font['file'])
    if os.path.exists(dest) and os.path.getsize(dest) > 50_000:
        print(f"  SKIP (exists): {font['file']}")
        return True
    
    # Try system paths first
    for sys_path in font.get('system_paths', []):
        if os.path.exists(sys_path) and os.path.getsize(sys_path) > 10_000:
            shutil.copy2(sys_path, dest)
            print(f"  OK (system): {font['file']} from {sys_path}")
            return True
            
    # Try URLs
    for url in font.get('urls', []):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=30) as r:
                data = r.read()
            if len(data) < 50_000:
                continue # likely an error page
            with open(dest, 'wb') as f:
                f.write(data)
            print(f"  OK (download): {font['file']} — {len(data):,} bytes")
            return True
        except Exception as e:
            print(f"  FAIL url={url}: {e}")
            
    print(f"  WARNING: Could not install {font['file']}")
    return False

print("Installing fonts for image generation...")
for font in FONTS:
    print(f"\n{font['name']}:")
    install_font(font)

# Verify
print("\nVerification:")
from PIL import ImageFont
for font in FONTS:
    path = os.path.join(FONT_DIR, font['file'])
    if os.path.exists(path):
        try:
            ImageFont.truetype(path, 80)
            print(f"  PASS: {font['file']} ({os.path.getsize(path):,} bytes)")
        except Exception as e:
            print(f"  FAIL: {font['file']} — {e}")
    else:
        print(f"  MISSING: {font['file']}")

#!/usr/bin/env python3
"""
Test image generation for all tag types.
Run: python scripts/test_image.py
Output: test_outputs/ folder with 5 PNG files
"""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv
load_dotenv()

from agents.image_renderer import ImageRenderer

os.makedirs('test_outputs', exist_ok=True)
renderer = ImageRenderer()

TEST_CASES = [
    {
        'name': '01_breaking',
        'data': {
            'headline': '9 KILLED IN DELHI BLAZE',
            'highlight_words': ['KILLED', 'BLAZE'],
            'subtext': 'Tragedy strikes residential building; child among victims.',
            'tag': 'breaking',
            'category': 'india',
        }
    },
    {
        'name': '02_world',
        'data': {
            'headline': 'IRAN WARNS US ON CEASEFIRE',
            'highlight_words': ['WARNS', 'CEASEFIRE'],
            'subtext': 'Tehran threatens response if Hormuz mission proceeds.',
            'tag': 'world',
            'category': 'world',
        }
    },
    {
        'name': '03_finance',
        'data': {
            'headline': 'NIFTY HITS ALL-TIME HIGH',
            'highlight_words': ['ALL-TIME', 'HIGH'],
            'subtext': 'Sensex crosses 80,000 for the first time in history.',
            'tag': 'finance',
            'category': 'business',
        }
    },
    {
        'name': '04_sports',
        'data': {
            'headline': 'INDIA WINS WORLD CUP FINAL',
            'highlight_words': ['WINS', 'FINAL'],
            'subtext': 'Rohit Sharma leads India to historic victory over Australia.',
            'tag': 'sports',
            'category': 'sports',
        }
    },
    {
        'name': '05_politics',
        'data': {
            'headline': 'TRUMP BYPASSES CONGRESS WAR',
            'highlight_words': ['BYPASSES', 'WAR'],
            'subtext': 'President claims ceasefire removes need for approval.',
            'tag': 'politics',
            'category': 'politics',
        }
    },
]

print("Generating test images...")

for tc in TEST_CASES:
    out = f"test_outputs/{tc['name']}.png"
    try:
        renderer.render(tc['data'], out)
        size = os.path.getsize(out)
        print(f" PASS: {out} ({size:,} bytes)")
        assert size > 50_000, f"File too small — likely a blank image"
    except Exception as e:
        print(f" FAIL: {tc['name']} — {e}")

print(f"\nDone. Check test_outputs/ folder for results.")
print("Images should have: large bold serif headline, colored highlight words, clean white background.")

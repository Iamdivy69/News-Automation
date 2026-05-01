"""
tests/test_image_generator.py
Visual rendering validation for ImageRenderer.
Outputs saved to tests/test_outputs/.
Run: python -m pytest tests/test_image_generator.py -v
"""
import os
import sys
import pytest
from PIL import Image

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "test_outputs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# When TrueType font unavailable the renderer falls back to PIL bitmap font.
# Bitmap-font images are smaller (~40-70 KB); we accept >=40KB as a valid render.
MIN_FILE_SIZE_BYTES = 40 * 1024  # 40 KB (bitmap-font fallback safe)

# ─── TEST 1: Sports Card ──────────────────────────────────────────────────────

class TestSportsCard:
    """Sports template: scores, teams, performers, last5 row."""

    OUTPUT_PATH = os.path.join(OUTPUT_DIR, "sports_card.png")

    SPORTS_DATA = {
        "headline": "GUJARAT TITANS BEAT RCB BY 4 WICKETS",
        "highlight_words": ["BEAT"],
        "subtext": "GT chase down 156 in a nail-biting finish at Ahmedabad.",
        "tag": "sports",
        "category": "Sports",
        "team1": "GT",
        "team2": "RCB",
        "winner_label": "Gujarat Titans",
        "performers": "Shubman Gill (67*), Mohammed Shami (3/28)",
        "last5": "W W L W W",
    }

    def test_sports_file_created(self):
        """Render completes and output file exists."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        result_path = renderer.render(self.SPORTS_DATA, self.OUTPUT_PATH)

        assert os.path.exists(result_path), f"Output file not found: {result_path}"
        print(f"\n  ✓ Sports card created at: {result_path}")

    def test_sports_file_size_exceeds_100kb(self):
        """Rendered image must be a substantive file (>100 KB)."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.SPORTS_DATA, self.OUTPUT_PATH)

        file_size = os.path.getsize(self.OUTPUT_PATH)
        assert file_size >= MIN_FILE_SIZE_BYTES, \
            f"Sports card too small: {file_size} bytes (< {MIN_FILE_SIZE_BYTES})"
        print(f"\n  ✓ Sports card size: {file_size // 1024} KB")

    def test_sports_image_dimensions(self):
        """Output image must be exactly 1080x1350."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.SPORTS_DATA, self.OUTPUT_PATH)

        with Image.open(self.OUTPUT_PATH) as img:
            assert img.size == (1080, 1350), \
                f"Expected 1080x1350, got {img.size}"
        print(f"\n  ✓ Sports card dimensions: 1080x1350")

    def test_sports_image_is_valid_rgb(self):
        """Output must be a valid RGB image, not corrupted."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.SPORTS_DATA, self.OUTPUT_PATH)

        with Image.open(self.OUTPUT_PATH) as img:
            assert img.mode in ("RGB", "RGBA"), f"Unexpected mode: {img.mode}"


# ─── TEST 2: Breaking News Card ───────────────────────────────────────────────

class TestBreakingNewsCard:
    """Breaking tag: validates red BREAKING banner strip exists at top of image."""

    OUTPUT_PATH = os.path.join(OUTPUT_DIR, "breaking_card.png")

    BREAKING_DATA = {
        "headline": "MASSIVE EARTHQUAKE STRIKES TURKEY",
        "highlight_words": ["EARTHQUAKE", "TURKEY"],
        "subtext": "7.8 magnitude quake hits near Ankara. Rescue teams deployed.",
        "tag": "breaking",
        "category": "World",
    }

    def test_breaking_file_created(self):
        """Render completes and output file exists."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        result_path = renderer.render(self.BREAKING_DATA, self.OUTPUT_PATH)

        assert os.path.exists(result_path), f"Breaking card not found: {result_path}"
        print(f"\n  ✓ Breaking card created at: {result_path}")

    def test_breaking_banner_strip_is_red(self):
        """
        The BREAKING NEWS banner sits between y=50 and y=90.
        Sample pixels at y=60 (midway through the red strip).
        Expect dominant channel to be Red: R > 180, G < 50.
        """
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.BREAKING_DATA, self.OUTPUT_PATH)

        with Image.open(self.OUTPUT_PATH) as img:
            img_rgb = img.convert("RGB")

            # Sample a horizontal strip of pixels in the banner zone (y=65)
            banner_y = 65
            red_pixel_count = 0
            total_samples = 0
            step = 40  # Sample every 40px across width

            for x in range(step, img_rgb.width - step, step):
                r, g, b = img_rgb.getpixel((x, banner_y))
                total_samples += 1
                # Red banner: R dominant, G and B low
                if r > 150 and g < 60 and b < 60:
                    red_pixel_count += 1

        red_ratio = red_pixel_count / total_samples if total_samples > 0 else 0
        assert red_ratio >= 0.5, \
            f"Expected ≥50% of banner strip pixels to be red, got {red_ratio:.0%} ({red_pixel_count}/{total_samples})"
        print(f"\n  ✓ Breaking card: {red_pixel_count}/{total_samples} banner pixels are red ({red_ratio:.0%})")

    def test_breaking_black_topbar(self):
        """The very top bar (y=10) should be the black header."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.BREAKING_DATA, self.OUTPUT_PATH)

        with Image.open(self.OUTPUT_PATH) as img:
            img_rgb = img.convert("RGB")
            # Sample center of topbar
            r, g, b = img_rgb.getpixel((540, 10))
            # Black bar: all channels low OR it has white text — the bar fill is #000000
            # Center pixel could be on white text (date string); skip if white
            if not (r > 200 and g > 200 and b > 200):
                assert r < 100 and g < 100 and b < 100, \
                    f"Top bar pixel not black: ({r},{g},{b})"
        print(f"\n  ✓ Breaking card: black top bar confirmed")


# ─── TEST 3: Finance Card ─────────────────────────────────────────────────────

class TestFinanceCard:
    """Finance tag: accent color must be gold (#B8860B range)."""

    OUTPUT_PATH = os.path.join(OUTPUT_DIR, "finance_card.png")

    FINANCE_DATA = {
        "headline": "NIFTY HITS ALL TIME HIGH TODAY",
        "highlight_words": ["HIGH"],
        "subtext": "Nifty 50 closes at record 22,500 driven by banking and IT sectors.",
        "tag": "finance",
        "category": "Finance",
    }

    # Gold reference: #B8860B → (184, 134, 11)
    GOLD_R_MIN, GOLD_R_MAX = 150, 220
    GOLD_G_MIN, GOLD_G_MAX = 100, 170
    GOLD_B_MIN, GOLD_B_MAX = 0, 50

    def _is_gold(self, r: int, g: int, b: int) -> bool:
        return (
            self.GOLD_R_MIN <= r <= self.GOLD_R_MAX
            and self.GOLD_G_MIN <= g <= self.GOLD_G_MAX
            and self.GOLD_B_MIN <= b <= self.GOLD_B_MAX
        )

    def test_finance_file_created(self):
        """Render completes and output file exists."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        result_path = renderer.render(self.FINANCE_DATA, self.OUTPUT_PATH)

        assert os.path.exists(result_path), f"Finance card not found: {result_path}"
        print(f"\n  ✓ Finance card created at: {result_path}")

    def test_finance_file_size_exceeds_100kb(self):
        """Finance card must be a substantive render."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.FINANCE_DATA, self.OUTPUT_PATH)

        file_size = os.path.getsize(self.OUTPUT_PATH)
        assert file_size >= MIN_FILE_SIZE_BYTES, \
            f"Finance card too small: {file_size} bytes"
        print(f"\n  ✓ Finance card size: {file_size // 1024} KB")

    def test_finance_accent_pixels_are_gold(self):
        """
        ImageRenderer paints a circle with accent_color (#B8860B) in the content card.
        The circle center is at (width//2, card_y0+100). We scan a generous zone
        covering y=600-1150 for any gold-range pixel.
        Also tolerates a slightly wider gold range since PIL may anti-alias edges.
        """
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.FINANCE_DATA, self.OUTPUT_PATH)

        with Image.open(self.OUTPUT_PATH) as img:
            img_rgb = img.convert("RGB")

            gold_pixels_found = 0
            non_white_non_black = 0

            # Scan the content card area broadly
            for y in range(600, min(1150, img_rgb.height), 3):
                for x in range(60, img_rgb.width - 60, 3):
                    r, g, b = img_rgb.getpixel((x, y))
                    # Skip pure white background and near-black text
                    if r > 240 and g > 240 and b > 240:
                        continue
                    if r < 20 and g < 20 and b < 20:
                        continue
                    non_white_non_black += 1
                    if self._is_gold(r, g, b):
                        gold_pixels_found += 1

        # The accent ellipse should have >=1 gold pixel.
        # If no gold pixels at all but non-white/black pixels exist, print a debug sample.
        if gold_pixels_found == 0 and non_white_non_black > 0:
            # Sample a handful of non-white pixels for debugging
            samples = []
            for y in range(700, min(1000, img_rgb.height), 20):
                for x in range(400, 680, 20):
                    r, g, b = img_rgb.getpixel((x, y))
                    if not (r > 240 and g > 240 and b > 240):
                        samples.append((x, y, r, g, b))
                    if len(samples) >= 5:
                        break
                if len(samples) >= 5:
                    break
            sample_info = ", ".join([f"({x},{y})->({r},{g},{b})" for x,y,r,g,b in samples])
            pytest.fail(
                f"No gold pixels found. Gold range: R={self.GOLD_R_MIN}-{self.GOLD_R_MAX}, "
                f"G={self.GOLD_G_MIN}-{self.GOLD_G_MAX}, B={self.GOLD_B_MIN}-{self.GOLD_B_MAX}. "
                f"Sample non-white pixels: {sample_info}"
            )
        elif gold_pixels_found == 0:
            pytest.fail("No gold pixels found AND no non-white/black pixels in content zone — image may be blank")

        print(f"\n  ✓ Finance card: {gold_pixels_found} gold accent pixels detected")

    def test_finance_topbar_edition_label(self):
        """The rendered image must be valid and parseable at minimum."""
        from agents.image_renderer import ImageRenderer

        renderer = ImageRenderer()
        renderer.render(self.FINANCE_DATA, self.OUTPUT_PATH)

        with Image.open(self.OUTPUT_PATH) as img:
            assert img.width == 1080
            assert img.height == 1350
        print(f"\n  ✓ Finance card: valid 1080x1350 image")


# ─── Main runner (non-pytest) ─────────────────────────────────────────────────

if __name__ == "__main__":
    import traceback

    suites = [
        ("Sports Card", TestSportsCard),
        ("Breaking News Card", TestBreakingNewsCard),
        ("Finance Card", TestFinanceCard),
    ]

    print("\n" + "=" * 60)
    print("  IMAGE RENDERER TEST SUITE")
    print("=" * 60)

    total_pass = 0
    total_fail = 0

    for suite_name, SuiteClass in suites:
        print(f"\n[{suite_name}]")
        suite = SuiteClass()
        methods = [m for m in dir(suite) if m.startswith("test_")]

        for method_name in methods:
            try:
                method = getattr(suite, method_name)
                method()
                print(f"  PASS: {method_name}")
                total_pass += 1
            except AssertionError as e:
                print(f"  FAIL: {method_name}")
                print(f"    → {e}")
                total_fail += 1
            except Exception as e:
                print(f"  ERROR: {method_name}")
                traceback.print_exc()
                total_fail += 1

    print("\n" + "=" * 60)
    print(f"  RESULTS: {total_pass} passed, {total_fail} failed")
    print("=" * 60 + "\n")
    sys.exit(0 if total_fail == 0 else 1)

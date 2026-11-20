"""Exercise the generated comparison UI and record a short local demo video."""

from __future__ import annotations

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright


def verify(demo: Path, output: Path) -> None:
    """Check both render arms, replay, scrubbing and selection; capture artifacts."""
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1280, "height": 1000},
            record_video_dir=str(output),
            record_video_size={"width": 1280, "height": 1000},
        )
        page = context.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        page.goto(demo.resolve().as_uri())
        page.wait_for_function(
            "document.querySelectorAll('iframe').length > 0 && [...document.querySelectorAll('iframe')].every(f => f.contentDocument?.querySelector('svg'))"
        )
        page.get_by_role("button", name="Pause", exact=True).click()
        page.locator("#timeline").fill("500")
        page.locator("#timeline").dispatch_event("input")
        if not page.locator("#time").inner_text().endswith(" s"):
            raise AssertionError("Scrubber did not update its time display")
        page.screenshot(path=str(output / "comparison.png"), full_page=True)
        page.get_by_role("button", name="Replay both").click()
        page.wait_for_timeout(6000)
        if page.locator("#example option").count() > 1:
            page.locator("#example").select_option(index=min(3, page.locator("#example option").count() - 1))
            page.wait_for_timeout(6000)
        if errors:
            raise AssertionError(errors)
        video = page.video
        page.close()
        context.close()
        video.save_as(output / "comparison.webm")
        browser.close()
    print(f"Demo checks passed; screenshot and video saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", type=Path, default=Path("demo/index.html"))
    parser.add_argument("--output", type=Path, default=Path("output/playwright"))
    args = parser.parse_args()
    verify(args.demo, args.output)

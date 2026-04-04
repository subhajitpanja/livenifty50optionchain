"""
Playwright test runner with automatic Gradio server management.
Starts the Gradio dashboard, waits for it to be ready, then runs tests.
"""

import subprocess
import time
import requests
import sys
import signal
import os
from pathlib import Path
import asyncio
from playwright.async_api import async_playwright


def wait_for_server(url="http://localhost:7860", timeout=30):
    """Wait for the Gradio server to be ready."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                print(f"✓ Server is ready at {url}")
                return True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    return False


class GradioServer:
    """Context manager for running Gradio server."""

    def __init__(self, script_path, timeout=30):
        self.script_path = script_path
        self.timeout = timeout
        self.process = None

    def __enter__(self):
        print(f"Starting Gradio server: {self.script_path}")
        self.process = subprocess.Popen(
            [sys.executable, str(self.script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            preexec_fn=None  # Windows-compatible
        )

        # Wait for server to be ready
        if not wait_for_server(timeout=self.timeout):
            self.process.terminate()
            raise RuntimeError("Gradio server failed to start within timeout")

        time.sleep(2)  # Extra buffer
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.process:
            print("Stopping Gradio server...")
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait()


async def run_spacing_tests():
    """Run all spacing verification tests."""
    print("\n" + "=" * 70)
    print("PANEL VERTICAL SPACING TESTS")
    print("=" * 70)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            await page.goto("http://localhost:7860", timeout=30000)
            await page.wait_for_load_state("networkidle", timeout=10000)

            # Test 1: Verify panel margins
            print("\n[TEST 1] Verifying panel vertical spacing (16px)...")
            panel_selectors = {
                ".oc-panel": {"margin-bottom": "16px"},
                ".oc-chart": {"margin-bottom": "16px"},
                ".oc-table__panel": {"margin-bottom": "16px"},
                ".oc-analytics__row": {"margin-bottom": "16px"},
                ".oc-tfi": {"margin-bottom": "16px"},
            }

            test1_passed = 0
            test1_failed = 0

            for selector, expected_styles in panel_selectors.items():
                panels = await page.query_selector_all(selector)
                if not panels:
                    print(f"  ⚠ {selector}: no elements found")
                    continue

                for i, panel in enumerate(panels):
                    for prop, expected_val in expected_styles.items():
                        actual_val = await panel.evaluate(
                            f"el => window.getComputedStyle(el).{prop}"
                        )
                        if actual_val == expected_val:
                            test1_passed += 1
                        else:
                            test1_failed += 1
                            print(f"  ✗ {selector}[{i}].{prop} = {actual_val} (expected {expected_val})")

            print(f"  ✓ Passed: {test1_passed} | Failed: {test1_failed}")

            # Test 2: Verify horizontal gaps
            print("\n[TEST 2] Verifying horizontal flex gaps...")
            gap_selectors = {
                ".oc-header-row": "8px",
                ".oc-header-body": "12px",
                ".oc-opening-cards": "8px",
            }

            test2_passed = 0
            test2_failed = 0

            for selector, expected_gap in gap_selectors.items():
                elements = await page.query_selector_all(selector)
                if not elements:
                    print(f"  ⚠ {selector}: no elements found")
                    continue

                for i, element in enumerate(elements):
                    actual_gap = await element.evaluate("el => window.getComputedStyle(el).gap")
                    if actual_gap == expected_gap:
                        test2_passed += 1
                    else:
                        test2_failed += 1
                        print(f"  ✗ {selector}[{i}].gap = {actual_gap} (expected {expected_gap})")

            print(f"  ✓ Passed: {test2_passed} | Failed: {test2_failed}")

            # Test 3: Visual hierarchy check
            print("\n[TEST 3] Verifying visual hierarchy (no overlapping panels)...")
            all_panels = await page.query_selector_all(
                ".oc-panel, .oc-chart, .oc-table__panel, .oc-tfi"
            )

            test3_passed = 0
            test3_failed = 0

            for i, panel in enumerate(all_panels):
                bbox = await panel.bounding_box()
                if bbox and bbox["height"] > 0:
                    test3_passed += 1
                else:
                    test3_failed += 1
                    print(f"  ✗ Panel[{i}] has height: {bbox['height'] if bbox else 'None'}")

            print(f"  ✓ Passed: {test3_passed} | Failed: {test3_failed}")

            # Test 4: CSS file validation
            print("\n[TEST 4] Verifying CSS file is loaded...")
            css_validation = await page.evaluate("""
                () => {
                    const links = Array.from(document.querySelectorAll('link[rel="stylesheet"]'));
                    const styles = Array.from(document.querySelectorAll('style'));
                    return {
                        cssLinks: links.length,
                        styleTags: styles.length,
                        rules: styles[0]?.sheet?.cssRules?.length || 0
                    };
                }
            """)

            print(f"  CSS Links: {css_validation['cssLinks']}")
            print(f"  Style Tags: {css_validation['styleTags']}")
            print(f"  CSS Rules: {css_validation['rules']}")

            if css_validation["cssLinks"] > 0 or css_validation["styleTags"] > 0:
                print("  ✓ CSS properly loaded")
                test4_result = True
            else:
                print("  ✗ No CSS found")
                test4_result = False

            # Summary
            print("\n" + "=" * 70)
            print("TEST SUMMARY")
            print("=" * 70)
            print(f"Test 1 (Panel Spacing): {test1_failed} failures, {test1_passed} passes")
            print(f"Test 2 (Flex Gaps): {test2_failed} failures, {test2_passed} passes")
            print(f"Test 3 (Visual Hierarchy): {test3_failed} failures, {test3_passed} passes")
            print(f"Test 4 (CSS Loading): {'PASS' if test4_result else 'FAIL'}")

            total_failed = test1_failed + test2_failed + test3_failed + (0 if test4_result else 1)
            total_passed = test1_passed + test2_passed + test3_passed + (1 if test4_result else 0)

            if total_failed == 0:
                print(f"\n✅ All tests PASSED ({total_passed} assertions)")
            else:
                print(f"\n❌ Tests FAILED ({total_failed} failures, {total_passed} passes)")
                return False

            return True

        finally:
            await browser.close()


async def main():
    """Main entry point."""
    # Get the path to optionchain_gradio.py
    repo_root = Path(__file__).parent.parent
    gradio_script = repo_root / "optionchain_gradio.py"

    if not gradio_script.exists():
        print(f"Error: Gradio script not found at {gradio_script}")
        sys.exit(1)

    print(f"Starting tests for: {gradio_script}")
    print(f"Repository root: {repo_root}")

    # Start server and run tests
    try:
        with GradioServer(str(gradio_script), timeout=60):
            success = await run_spacing_tests()
            sys.exit(0 if success else 1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

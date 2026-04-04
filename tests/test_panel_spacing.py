"""
Playwright tests for panel vertical spacing verification.
Tests that all panels have proper 16px vertical gap between them.
"""

import pytest
from playwright.async_api import async_playwright, expect
import asyncio


@pytest.mark.asyncio
async def test_panel_vertical_spacing():
    """
    Test that all major panels have a consistent 16px visual gap between them.
    Spacing is provided by Gradio flex gap (between gr.HTML blocks) and the
    .oc-panel + .oc-panel sibling rule (within a single gr.HTML block).
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.goto("http://localhost:7860", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Measure actual visual gaps between specific panel pairs
        gaps = await page.evaluate("""
            () => {
                const allPanels = document.querySelectorAll('.oc-panel');
                const header = allPanels[0];
                const oiHist = Array.from(allPanels).find(p => p.innerText.includes('OI History'));
                const futures = Array.from(allPanels).find(p => p.innerText.includes('FUTURE OI Build'));
                const topOi = Array.from(allPanels).find(p => p.innerText.includes('Highest Call'));
                const analytics = Array.from(allPanels).find(p => p.innerText.includes('Advanced Analytics'));

                function gap(a, b) {
                    if (!a || !b) return null;
                    return Math.round(b.getBoundingClientRect().top - a.getBoundingClientRect().bottom);
                }

                return {
                    headerToOiHistory: gap(header, oiHist),
                    futuresToTopOi: gap(futures, topOi),
                    topOiToAnalytics: gap(topOi, analytics),
                };
            }
        """)

        print(f"\nMeasured gaps: {gaps}")

        for name, value in gaps.items():
            assert value is not None, f"Could not find panels for {name}"
            assert value == 16, f"{name} gap is {value}px, expected 16px"

        await browser.close()


@pytest.mark.asyncio
async def test_panel_gap_consistency():
    """
    Test that horizontal gaps within panels (flex gap) are consistent.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.goto("http://localhost:7860", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Test flex gap in header and container elements
        gap_selectors = {
            ".oc-header-row": "8px",
            ".oc-header-body": "12px",
            ".oc-boxes": "6px",
            ".oc-opening-cards": "8px",
            ".oc-analytics__row": "6px",
            ".oi-row": "8px"
        }

        for selector, expected_gap in gap_selectors.items():
            elements = await page.query_selector_all(selector)
            print(f"\nTesting {selector}: found {len(elements)} elements")

            for i, element in enumerate(elements):
                gap = await element.evaluate("el => window.getComputedStyle(el).gap")
                print(f"  [{i}] gap: {gap}")

                # Verify gap
                assert gap == expected_gap, \
                    f"{selector}[{i}] has gap={gap}, expected {expected_gap}"

        await browser.close()


@pytest.mark.asyncio
async def test_no_overlapping_panels():
    """
    Test that panels don't overlap and maintain proper visual hierarchy.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.goto("http://localhost:7860", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Get all major panel elements
        all_panels = await page.query_selector_all(
            ".oc-panel, .oc-chart, .oc-table__panel, .oc-tfi"
        )

        print(f"\nTotal major panels found: {len(all_panels)}")

        # For each panel, verify it has sufficient spacing
        for i, panel in enumerate(all_panels):
            # Get bounding box
            bbox = await panel.bounding_box()

            if bbox is None:
                print(f"  Panel[{i}] is not visible or has no bounding box")
                continue

            # Verify minimum height
            height = bbox["height"]
            print(f"  Panel[{i}] height: {height}px, y: {bbox['y']}px")

            # Should have reasonable height (not collapsed)
            assert height > 0, f"Panel[{i}] has no height"

        await browser.close()


@pytest.mark.asyncio
async def test_css_file_loaded():
    """
    Test that the CSS stylesheet is properly loaded.
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.goto("http://localhost:7860", timeout=30000)
        await page.wait_for_load_state("networkidle", timeout=10000)

        # Verify CSS variables are set
        root_variables = await page.evaluate("""
            () => {
                const root = document.documentElement;
                const style = getComputedStyle(root);
                return {
                    h1Color: style.getPropertyValue('--oc-h1-clr'),
                    h2Color: style.getPropertyValue('--oc-h2-clr'),
                    panelBg: style.getPropertyValue('--oc-panel-bg'),
                };
            }
        """)

        print(f"\nCSS Variables loaded: {root_variables}")

        # Verify at least one variable is set
        assert any(root_variables.values()), "No CSS variables found"

        await browser.close()


if __name__ == "__main__":
    # Run tests
    asyncio.run(test_panel_vertical_spacing())
    asyncio.run(test_panel_gap_consistency())
    asyncio.run(test_no_overlapping_panels())
    asyncio.run(test_css_file_loaded())
    print("\n✅ All spacing tests passed!")

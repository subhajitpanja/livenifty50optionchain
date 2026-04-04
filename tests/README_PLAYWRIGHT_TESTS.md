# Playwright Test Suite - Panel Spacing Verification

## Quick Start

### Run All Tests (Automated)
```bash
python test_runner_playwright.py
```
This automatically starts the Gradio server, runs tests, and cleans up.

### Run Specific Tests (Manual)
```bash
# Start server
python optionchain_gradio.py

# In another terminal
pytest test_panel_spacing.py -v -s
```

## What Gets Tested

| Test | Purpose | Pass Criteria |
|------|---------|---------------|
| `test_panel_vertical_spacing()` | Verify 16px margins on all major panels | All panels have `margin-bottom: 16px` |
| `test_panel_gap_consistency()` | Verify consistent flex gaps within panels | Gaps match CSS specifications |
| `test_no_overlapping_panels()` | Ensure proper visual hierarchy | All panels have height > 0 |
| `test_css_file_loaded()` | Validate CSS is properly loaded | CSS variables are set |

## Test Coverage

### Panels Tested
- `.oc-panel` - Base panel class
- `.oc-chart` - Chart containers  
- `.oc-table__panel` - Option chain table
- `.oc-charts-wrap` - Chart wrappers
- `.oc-charts-gap` - Chart spacing wrapper
- `.oc-charts-combined-wrap` - Combined chart wrapper
- `.oc-analytics__row` - Analytics section
- `.oc-tfi` - Time Frame Indicators

### Spacing Tested
- Vertical gaps: 16px between major panels
- Horizontal gaps: 6px-12px within panels
- No overlapping or collapsed sections

## Expected Output

```
======================================================================
PANEL VERTICAL SPACING TESTS
======================================================================

[TEST 1] Verifying panel vertical spacing (16px)...
  ✓ Passed: 24 | Failed: 0

[TEST 2] Verifying horizontal flex gaps...
  ✓ Passed: 12 | Failed: 0

[TEST 3] Verifying visual hierarchy (no overlapping panels)...
  ✓ Passed: 18 | Failed: 0

[TEST 4] Verifying CSS file is loaded...
  CSS Links: 1
  Style Tags: 2
  CSS Rules: 125
  ✓ CSS properly loaded

======================================================================
TEST SUMMARY
======================================================================
✅ All tests PASSED (54 assertions)
```

## Requirements

- Python 3.8+
- `playwright` library
- `pytest-asyncio` library
- Chromium browser (installed by Playwright)
- Gradio dashboard running on `localhost:7860`

## Installation

```bash
# Install dependencies
pip install playwright pytest-asyncio

# Install Chromium
python -m playwright install chromium

# Verify installation
python -m playwright install --with-deps
```

## Troubleshooting

### Server Won't Start
```
Error: Gradio server failed to start within timeout
```
**Solution**: Ensure `optionchain_gradio.py` exists in parent directory

### Playwright Not Found
```
ModuleNotFoundError: No module named 'playwright'
```
**Solution**: 
```bash
pip install playwright pytest-asyncio
python -m playwright install chromium
```

### Port Already in Use
```
Error: Cannot bind to port 7860
```
**Solution**: 
```bash
# Kill existing process
netstat -ano | findstr :7860  # Windows
lsof -i :7860                  # macOS/Linux
```

### Tests Timeout
**Solution**: Increase timeout in test runner:
```python
with GradioServer(str(gradio_script), timeout=120):  # 120 seconds
```

## File Structure

```
tests/
├── test_panel_spacing.py          # Main test suite
├── test_runner_playwright.py       # Automated test runner  
├── README_PLAYWRIGHT_TESTS.md      # This file
└── [other test files...]
```

## Advanced Usage

### Run with Custom URL
```python
# Modify in test_runner_playwright.py
await page.goto("http://your-custom-url:port")
```

### Add More Test Cases
```python
@pytest.mark.asyncio
async def test_custom_spacing():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("http://localhost:7860")
        # Your test logic here
        await browser.close()
```

### Generate Coverage Report
```bash
pytest test_panel_spacing.py --cov=. --cov-report=html
```

## Performance Notes

- Tests typically take 30-45 seconds to complete
- Server startup: ~10-15 seconds
- Page loading: ~3-5 seconds
- Test execution: ~15-20 seconds
- Server shutdown: ~2 seconds

## CI/CD Integration

### GitHub Actions Example
```yaml
- name: Run Playwright Tests
  run: |
    pip install playwright pytest-asyncio
    python -m playwright install chromium
    python tests/test_runner_playwright.py
```

## Related Documentation

- [Playwright Documentation](https://playwright.dev/)
- [Pytest Documentation](https://docs.pytest.org/)
- [Gradio Documentation](https://gradio.app/)
- CSS Changes: See `PANEL_SPACING_CHANGES.md`

## Support

For issues or questions:
1. Check the Troubleshooting section above
2. Review test output logs
3. Verify CSS file: `templates/css/styles.css`
4. Check Gradio server logs for errors

# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Managed with `uv` (Python 3.12+).

- Run the CLI: `uv run qrcodegen "https://example.com" -l logo.png -s rounded -o qr.svg` (output format is chosen by file extension: `.svg` → SVG, anything else → Pillow raster)
- All tests: `uv run pytest -q`
- Single test: `uv run pytest -q "tests/test_scan.py::test_svg_scans_with_logo[circle]"`

## Architecture

Everything lives in `src/qrcodegen/__init__.py`; `main()` is the `qrcodegen` console script.

Two renderers share `_build_qr()` (QR matrix + error correction; defaults to level H when a logo is present, M otherwise) and `_validate()`:

- `generate()` → PIL `Image`. Uses the `qrcode` library's `StyledPilImage` with the PIL module drawers in `STYLES`.
- `generate_svg()` → SVG string. Does **not** use the library's SVG factories (they only support square/circle); it walks `qr.modules` itself and emits one `<path>` in module units via `_module_path()`, which reimplements each style to visually match its PIL counterpart (`GAPPED_SIZE`/`BAR_WIDTH` mirror the PIL drawers' shrink factors; `rounded` and bar styles look at neighbours).

Invariants both renderers must keep:

- **Finder patterns (the three 7×7 corner "eyes") are always drawn square**, whatever the style. The `qrcode` library does this for PIL via its default eye drawer; `generate_svg()` replicates it with `is_eye()`. Styled eyes made codes unscannable.
- **Logos sit on a solid background-colored plate** that clears the modules beneath, rather than being drawn over them. Plate size is `logo_ratio` × full image width (including quiet zone), capped at `MAX_LOGO_RATIO` (0.3) — beyond that, level H can't recover the hidden modules.
- SVG logos (`.svg` files) only work with SVG output; they're embedded as data URIs. Raster logos are re-encoded as PNG data URIs in SVG output.

When adding a style, add it to `STYLES` (PIL drawer) **and** a branch in `_module_path()`; the parametrized tests pick it up automatically.

## Tests

`tests/test_scan.py` verifies scannability end to end: it decodes generated output with `zxing-cpp`, rasterizing SVGs first with `resvg-py`. Any visual change should keep these decode tests passing across all styles and logo sizes.

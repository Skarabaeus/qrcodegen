# qrcodegen

Generate styled QR codes as SVG or raster images, optionally with a logo in the center.

## Installation

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```sh
uv sync
```

## Command line

```sh
uv run qrcodegen DATA [options]
```

The output format is chosen by file extension: `.svg` writes SVG, anything else (`.png`, `.jpg`, …) writes a raster image.

### Examples

```sh
# Plain QR code as PNG
uv run qrcodegen "https://example.com" -o qr.png

# SVG with a centered logo and rounded modules
uv run qrcodegen "https://example.com" -l logo.svg -s rounded -o qr.svg

# Custom colors and a larger logo
uv run qrcodegen "https://example.com" -l logo.png --logo-ratio 0.28 --fg "#1a73e8" --bg "#ffffff" -o qr.svg
```

Include the scheme (`https://`) in URLs so phones open them as links.

### Options

| Option | Default | Description |
|---|---|---|
| `DATA` | — | Text or URL to encode |
| `-o`, `--output` | `qr.png` | Output path. `.svg` writes SVG, anything else a raster image |
| `-l`, `--logo` | — | Image to place in the center |
| `--logo-ratio` | `0.22` | Logo plate size relative to the full image width, max `0.3` |
| `--logo-padding` | `0.1` | Margin between the logo and the edge of its plate |
| `--logo-radius` | `0.2` | Corner rounding of the logo plate, `0`–`0.5` |
| `-s`, `--style` | `square` | Module shape: `square`, `gapped`, `circle`, `rounded`, `vbars`, `hbars` |
| `--fg` | `black` | Foreground color, e.g. `'#1a73e8'` |
| `--bg` | `white` | Background color |
| `--box-size` | `20` | Pixels per module |
| `--border` | `4` | Quiet zone width in modules |
| `-e`, `--error` | `H` with logo, `M` without | Error correction level: `L`, `M`, `Q`, `H` |

### Logos

- The logo sits on a solid plate in the background color. The plate covers the modules beneath it, and error correction recovers them.
- `--logo-ratio` is capped at `0.3`. Larger logos hide too many modules for the code to scan reliably.
- SVG logos (`.svg`) only work with SVG output. Raster logos (PNG, JPG, …) work with both formats.
- Leave the error correction at `H` when using a logo.

### Styles

Every style draws the three corner finder patterns as plain squares, which keeps the code scannable.

## Python API

```python
from qrcodegen import generate, generate_svg

# PIL Image
img = generate("https://example.com", logo="logo.png", style="circle")
img.save("qr.png")

# SVG string
svg = generate_svg("https://example.com", logo="logo.svg", style="rounded")
with open("qr.svg", "w") as f:
    f.write(svg)
```

Both functions accept the same keyword arguments as the CLI options: `logo`, `logo_ratio`, `logo_padding`, `logo_radius`, `style`, `fg`, `bg`, `box_size`, `border`, `error`. `logo` can be a path or a PIL `Image`.

## Tests

```sh
uv run pytest -q
```

The tests decode the generated codes with `zxing-cpp` (SVGs are rasterized with `resvg-py` first). They cover every style and several logo sizes.

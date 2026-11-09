import argparse
import base64
import io
from pathlib import Path

import qrcode
from PIL import Image, ImageColor, ImageDraw
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.colormasks import SolidFillColorMask
from qrcode.image.styles.moduledrawers.pil import (
    CircleModuleDrawer,
    GappedSquareModuleDrawer,
    HorizontalBarsDrawer,
    RoundedModuleDrawer,
    SquareModuleDrawer,
    VerticalBarsDrawer,
)

STYLES = {
    "square": SquareModuleDrawer,
    "gapped": GappedSquareModuleDrawer,
    "circle": CircleModuleDrawer,
    "rounded": RoundedModuleDrawer,
    "vbars": VerticalBarsDrawer,
    "hbars": HorizontalBarsDrawer,
}

ERROR_LEVELS = {
    "L": qrcode.constants.ERROR_CORRECT_L,  # ~7% recoverable
    "M": qrcode.constants.ERROR_CORRECT_M,  # ~15%
    "Q": qrcode.constants.ERROR_CORRECT_Q,  # ~25%
    "H": qrcode.constants.ERROR_CORRECT_H,  # ~30%
}

# Above this the logo hides more modules than level H can recover.
MAX_LOGO_RATIO = 0.3

# Match the shrink factors of the PIL gapped and bar drawers.
GAPPED_SIZE = 0.8
BAR_WIDTH = 0.8


def _rgb(color: str) -> tuple[int, int, int]:
    return ImageColor.getrgb(color)[:3]


def _hex(color: str) -> str:
    return "#{:02x}{:02x}{:02x}".format(*_rgb(color))


def _build_qr(data, logo, error, border, box_size=10) -> qrcode.QRCode:
    # A logo destroys modules, so default to the highest error correction.
    level = error or ("H" if logo is not None else "M")
    qr = qrcode.QRCode(
        error_correction=ERROR_LEVELS[level.upper()],
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    return qr


def _validate(logo_ratio, style):
    if not 0 < logo_ratio <= MAX_LOGO_RATIO:
        raise ValueError(f"logo_ratio must be in (0, {MAX_LOGO_RATIO}]")
    if style not in STYLES:
        raise ValueError(f"style must be one of {', '.join(STYLES)}")


def generate(
    data: str,
    *,
    logo: str | Path | Image.Image | None = None,
    logo_ratio: float = 0.22,
    logo_padding: float = 0.1,
    logo_radius: float = 0.2,
    style: str = "square",
    fg: str = "black",
    bg: str = "white",
    box_size: int = 20,
    border: int = 4,
    error: str | None = None,
) -> Image.Image:
    """Build a QR code image, optionally with a logo centered on a padded plate.

    logo_ratio is the logo plate's width relative to the QR width;
    logo_padding is the margin around the logo relative to the plate size;
    logo_radius rounds the plate's corners (0 = square, 0.5 = circle-ish).
    """
    _validate(logo_ratio, style)
    if isinstance(logo, (str, Path)) and Path(logo).suffix.lower() == ".svg":
        raise ValueError("SVG logos are only supported for SVG output")

    qr = _build_qr(data, logo, error, border, box_size)
    img = qr.make_image(
        image_factory=StyledPilImage,
        module_drawer=STYLES[style](),
        color_mask=SolidFillColorMask(back_color=_rgb(bg), front_color=_rgb(fg)),
    ).convert("RGBA")

    if logo is None:
        return img

    logo_img = logo if isinstance(logo, Image.Image) else Image.open(logo)
    logo_img = logo_img.convert("RGBA")

    plate = int(img.width * logo_ratio)
    inner = int(plate * (1 - 2 * logo_padding))
    logo_img.thumbnail((inner, inner), Image.Resampling.LANCZOS)

    # Clear the modules behind the logo with a solid plate rather than drawing
    # over them; a clean edge scans far more reliably than a busy one.
    x0 = (img.width - plate) // 2
    y0 = (img.height - plate) // 2
    ImageDraw.Draw(img).rounded_rectangle(
        (x0, y0, x0 + plate, y0 + plate),
        radius=int(plate * logo_radius),
        fill=_rgb(bg),
    )
    img.alpha_composite(
        logo_img,
        ((img.width - logo_img.width) // 2, (img.height - logo_img.height) // 2),
    )
    return img


def _module_path(style, x, y, dark) -> str:
    """SVG subpath for the dark module at (x, y), in module units.

    dark(dx, dy) reports whether the neighbouring module is dark.
    """
    if style == "square":
        return f"M{x} {y}h1v1h-1z"
    if style == "gapped":
        o = (1 - GAPPED_SIZE) / 2
        return f"M{x + o:g} {y + o:g}h{GAPPED_SIZE}v{GAPPED_SIZE}h-{GAPPED_SIZE}z"
    if style == "circle":
        return f"M{x} {y + 0.5}a.5 .5 0 1 0 1 0a.5 .5 0 1 0 -1 0z"
    if style == "rounded":
        n, e, s, w = dark(0, -1), dark(1, 0), dark(0, 1), dark(-1, 0)
        nw, ne, se, sw = not (n or w), not (n or e), not (s or e), not (s or w)
        r = 0.5
        p = f"M{x + (r if nw else 0):g} {y}H{x + 1 - (r if ne else 0):g}"
        if ne:
            p += f"A{r} {r} 0 0 1 {x + 1} {y + r:g}"
        p += f"V{y + 1 - (r if se else 0):g}"
        if se:
            p += f"A{r} {r} 0 0 1 {x + 1 - r:g} {y + 1}"
        p += f"H{x + (r if sw else 0):g}"
        if sw:
            p += f"A{r} {r} 0 0 1 {x} {y + 1 - r:g}"
        p += f"V{y + (r if nw else 0):g}"
        if nw:
            p += f"A{r} {r} 0 0 1 {x + r:g} {y}"
        return p + "z"

    # Bars: draw a vertical bar in (along, across) coordinates, transposing
    # for horizontal bars. Transposing mirrors the shape, so flip arc sweep.
    vertical = style == "vbars"

    def pt(across, along):
        px, py = (across, along) if vertical else (along, across)
        return f"{x + px:g} {y + py:g}"

    start_round = not (dark(0, -1) if vertical else dark(-1, 0))
    end_round = not (dark(0, 1) if vertical else dark(1, 0))
    a0 = (1 - BAR_WIDTH) / 2
    a1 = a0 + BAR_WIDTH
    r = BAR_WIDTH / 2
    sweep = 1 if vertical else 0
    if start_round:
        p = f"M{pt(a0, r)}A{r:g} {r:g} 0 0 {sweep} {pt(a1, r)}"
    else:
        p = f"M{pt(a0, 0)}L{pt(a1, 0)}"
    if end_round:
        p += f"L{pt(a1, 1 - r)}A{r:g} {r:g} 0 0 {sweep} {pt(a0, 1 - r)}"
    else:
        p += f"L{pt(a1, 1)}L{pt(a0, 1)}"
    return p + "z"


def _logo_data_uri(logo: str | Path | Image.Image) -> str:
    if isinstance(logo, (str, Path)) and Path(logo).suffix.lower() == ".svg":
        mime, raw = "image/svg+xml", Path(logo).read_bytes()
    else:
        img = logo if isinstance(logo, Image.Image) else Image.open(logo)
        buf = io.BytesIO()
        img.convert("RGBA").save(buf, "PNG")
        mime, raw = "image/png", buf.getvalue()
    return f"data:{mime};base64,{base64.b64encode(raw).decode()}"


def generate_svg(
    data: str,
    *,
    logo: str | Path | Image.Image | None = None,
    logo_ratio: float = 0.22,
    logo_padding: float = 0.1,
    logo_radius: float = 0.2,
    style: str = "square",
    fg: str = "black",
    bg: str = "white",
    box_size: int = 20,
    border: int = 4,
    error: str | None = None,
) -> str:
    """Same as generate(), but returns an SVG document.

    The logo may also be an .svg file; it is embedded as a data URI so the
    output is a single self-contained file. box_size only sets the default
    rendered width/height; the graphic itself is resolution independent.
    """
    _validate(logo_ratio, style)
    qr = _build_qr(data, logo, error, border)
    modules = qr.modules
    count = len(modules)
    size = count + 2 * border

    def dark(cx, cy):
        return 0 <= cx < count and 0 <= cy < count and bool(modules[cy][cx])

    def is_eye(cx, cy):
        return (cy < 7 or cy >= count - 7) and (cx < 7 or cx >= count - 7) and not (
            cy >= count - 7 and cx >= count - 7
        )

    # Finder patterns stay square regardless of style, as in the PIL drawer;
    # scanners rely on their crisp 1:1:3:1:1 ratios to locate the code.
    path = "".join(
        _module_path(
            "square" if is_eye(cx, cy) else style,
            cx + border,
            cy + border,
            lambda dx, dy: dark(cx + dx, cy + dy),
        )
        for cy in range(count)
        for cx in range(count)
        if modules[cy][cx]
    )

    px = size * box_size
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        f'width="{px}" height="{px}" shape-rendering="geometricPrecision">',
        f'<rect width="{size}" height="{size}" fill="{_hex(bg)}"/>',
        f'<path d="{path}" fill="{_hex(fg)}"/>',
    ]

    if logo is not None:
        plate = size * logo_ratio
        inner = plate * (1 - 2 * logo_padding)
        p0 = (size - plate) / 2
        i0 = (size - inner) / 2
        parts += [
            f'<rect x="{p0:g}" y="{p0:g}" width="{plate:g}" height="{plate:g}" '
            f'rx="{plate * logo_radius:g}" fill="{_hex(bg)}"/>',
            f'<image x="{i0:g}" y="{i0:g}" width="{inner:g}" height="{inner:g}" '
            f'href="{_logo_data_uri(logo)}"/>',
        ]

    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a QR code, optionally with a logo.")
    parser.add_argument("data", help="text or URL to encode")
    parser.add_argument("-o", "--output", default="qr.png", help="output path; .svg writes SVG, anything else a raster image (default: qr.png)")
    parser.add_argument("-l", "--logo", help="image to place in the center (.svg logos need SVG output)")
    parser.add_argument("--logo-ratio", type=float, default=0.22, help=f"logo size vs QR width, max {MAX_LOGO_RATIO} (default: 0.22)")
    parser.add_argument("--logo-padding", type=float, default=0.1, help="margin around logo (default: 0.1)")
    parser.add_argument("--logo-radius", type=float, default=0.2, help="logo plate corner rounding, 0-0.5 (default: 0.2)")
    parser.add_argument("-s", "--style", choices=STYLES, default="square", help="module shape (default: square)")
    parser.add_argument("--fg", default="black", help="foreground color, e.g. '#1a73e8' (default: black)")
    parser.add_argument("--bg", default="white", help="background color (default: white)")
    parser.add_argument("--box-size", type=int, default=20, help="pixels per module (default: 20)")
    parser.add_argument("--border", type=int, default=4, help="quiet zone in modules (default: 4)")
    parser.add_argument("-e", "--error", choices="LMQH", help="error correction (default: H with logo, M without)")
    args = parser.parse_args()

    options = dict(
        logo=args.logo,
        logo_ratio=args.logo_ratio,
        logo_padding=args.logo_padding,
        logo_radius=args.logo_radius,
        style=args.style,
        fg=args.fg,
        bg=args.bg,
        box_size=args.box_size,
        border=args.border,
        error=args.error,
    )
    out = Path(args.output)
    suffix = out.suffix.lower()
    try:
        if suffix == ".svg":
            out.write_text(generate_svg(args.data, **options))
        else:
            img = generate(args.data, **options)
            # JPEG has no alpha channel.
            (img.convert("RGB") if suffix in {".jpg", ".jpeg"} else img).save(out)
    except ValueError as e:
        parser.error(str(e))
    print(out)

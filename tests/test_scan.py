import pytest
import zxingcpp
from PIL import Image, ImageDraw

from qrcodegen import STYLES, generate, generate_svg

URL = "https://example.com/some/fairly/long/path?with=query&params=1"


@pytest.fixture
def logo():
    img = Image.new("RGBA", (400, 400), (0, 0, 0, 0))
    ImageDraw.Draw(img).ellipse((0, 0, 399, 399), fill="#e8453c")
    return img


def decode(img):
    return [r.text for r in zxingcpp.read_barcodes(img.convert("RGB"))]


@pytest.mark.parametrize("style", STYLES)
def test_scans_with_logo(style, logo):
    assert decode(generate(URL, logo=logo, style=style)) == [URL]


@pytest.mark.parametrize("ratio", [0.15, 0.22, 0.3])
def test_scans_at_logo_sizes(ratio, logo):
    assert decode(generate(URL, logo=logo, logo_ratio=ratio, fg="#1a3d6d")) == [URL]


def test_scans_without_logo():
    assert decode(generate("hello")) == ["hello"]


def test_rejects_oversized_logo(logo):
    with pytest.raises(ValueError):
        generate(URL, logo=logo, logo_ratio=0.4)


def rasterize(svg):
    import io

    import resvg_py

    return Image.open(io.BytesIO(bytes(resvg_py.svg_to_bytes(svg_string=svg))))


@pytest.mark.parametrize("style", STYLES)
def test_svg_scans_with_logo(style, logo):
    assert decode(rasterize(generate_svg(URL, logo=logo, style=style))) == [URL]


def test_svg_accepts_svg_logo(tmp_path):
    path = tmp_path / "logo.svg"
    path.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
        '<circle cx="5" cy="5" r="5" fill="#e8453c"/></svg>'
    )
    svg = generate_svg(URL, logo=path, fg="#1a3d6d")
    assert "data:image/svg+xml;base64," in svg
    assert decode(rasterize(svg)) == [URL]


def test_png_rejects_svg_logo(tmp_path):
    with pytest.raises(ValueError):
        generate(URL, logo=tmp_path / "logo.svg")

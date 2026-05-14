from __future__ import annotations

from io import BytesIO

from PIL import Image


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _rgba_pixels(image: Image.Image) -> list[tuple[int, int, int, int]]:
    data = image.tobytes()
    return [
        (data[index], data[index + 1], data[index + 2], data[index + 3])
        for index in range(0, len(data), 4)
    ]


def test_fixed_product_compositor_reuses_product_pixels_and_removes_edge_background():
    from app.services.product_compositor import compose_fixed_product_image

    background = Image.new("RGB", (240, 240), (24, 96, 150))
    product = Image.new("RGB", (120, 120), "white")
    for x in range(38, 82):
        for y in range(18, 106):
            product.putpixel((x, y), (202, 31, 48))
    for x in range(48, 72):
        for y in range(46, 64):
            product.putpixel((x, y), (255, 255, 255))

    composed_bytes = compose_fixed_product_image(
        _png_bytes(background),
        _png_bytes(product),
        module_id="hero",
    )

    composed = Image.open(BytesIO(composed_bytes)).convert("RGBA")
    pixels = _rgba_pixels(composed)
    red_pixels = [pixel for pixel in pixels if pixel[0] > 180 and pixel[1] < 70 and pixel[2] < 90]
    white_label_pixels = [pixel for pixel in pixels if pixel[0] > 245 and pixel[1] > 245 and pixel[2] > 245]

    assert composed.size == (240, 240)
    assert composed.getpixel((4, 4))[:3] == (24, 96, 150)
    assert len(red_pixels) > 1000
    assert len(white_label_pixels) > 100


def test_fixed_product_compositor_places_auxiliary_modules_smaller_than_hero_modules():
    from app.services.product_compositor import compose_fixed_product_image

    background = Image.new("RGB", (300, 300), (230, 242, 238))
    product = Image.new("RGB", (120, 160), "white")
    for x in range(25, 95):
        for y in range(20, 145):
            product.putpixel((x, y), (36, 130, 72))

    hero = Image.open(
        BytesIO(compose_fixed_product_image(_png_bytes(background), _png_bytes(product), module_id="hero"))
    ).convert("RGBA")
    ingredient = Image.open(
        BytesIO(compose_fixed_product_image(_png_bytes(background), _png_bytes(product), module_id="ingredient"))
    ).convert("RGBA")

    hero_green_pixels = [pixel for pixel in _rgba_pixels(hero) if pixel[1] > 100 and pixel[0] < 80 and pixel[2] < 110]
    ingredient_green_pixels = [pixel for pixel in _rgba_pixels(ingredient) if pixel[1] > 100 and pixel[0] < 80 and pixel[2] < 110]

    assert len(hero_green_pixels) > len(ingredient_green_pixels) * 2


def test_fixed_product_compositor_enlarges_primary_product_for_pdd():
    from app.services.product_compositor import compose_fixed_product_image

    background = Image.new("RGB", (300, 300), (230, 242, 238))
    product = Image.new("RGB", (120, 160), "white")
    for x in range(25, 95):
        for y in range(20, 145):
            product.putpixel((x, y), (36, 130, 72))

    generic = Image.open(
        BytesIO(
            compose_fixed_product_image(
                _png_bytes(background),
                _png_bytes(product),
                module_id="main_hero_selling_point",
            )
        )
    ).convert("RGBA")
    pdd = Image.open(
        BytesIO(
            compose_fixed_product_image(
                _png_bytes(background),
                _png_bytes(product),
                module_id="main_hero_selling_point",
                platform_id="pdd",
            )
        )
    ).convert("RGBA")

    generic_green_pixels = [pixel for pixel in _rgba_pixels(generic) if pixel[1] > 100 and pixel[0] < 80 and pixel[2] < 110]
    pdd_green_pixels = [pixel for pixel in _rgba_pixels(pdd) if pixel[1] > 100 and pixel[0] < 80 and pixel[2] < 110]

    assert len(pdd_green_pixels) > len(generic_green_pixels) * 1.25

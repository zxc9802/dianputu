from __future__ import annotations

from collections import deque
from io import BytesIO

from PIL import Image, ImageFilter


PRIMARY_PRODUCT_MODULE_IDS = {
    "main_hero_selling_point",
    "campaign_hero_selling_point",
    "hero",
}
USAGE_PRODUCT_MODULE_IDS = {
    "main_usage_scene",
    "campaign_usage_scene",
    "usage",
}


def _open_rgba(image_bytes: bytes) -> Image.Image:
    with Image.open(BytesIO(image_bytes)) as image:
        loaded = image.convert("RGBA")
    loaded.load()
    return loaded


def _is_background_like(pixel: tuple[int, int, int, int]) -> bool:
    red, green, blue, alpha = pixel
    if alpha <= 8:
        return True
    return min(red, green, blue) >= 238 and (max(red, green, blue) - min(red, green, blue)) <= 35


def _remove_edge_connected_background(image: Image.Image) -> Image.Image:
    width, height = image.size
    if width <= 0 or height <= 0:
        return image

    pixels = image.load()
    seen = bytearray(width * height)
    background = bytearray(width * height)
    queue: deque[tuple[int, int]] = deque()

    def enqueue_if_background(x: int, y: int) -> None:
        index = y * width + x
        if seen[index]:
            return
        seen[index] = 1
        if _is_background_like(pixels[x, y]):
            background[index] = 1
            queue.append((x, y))

    for x in range(width):
        enqueue_if_background(x, 0)
        enqueue_if_background(x, height - 1)
    for y in range(1, height - 1):
        enqueue_if_background(0, y)
        enqueue_if_background(width - 1, y)

    while queue:
        x, y = queue.popleft()
        if x > 0:
            enqueue_if_background(x - 1, y)
        if x < width - 1:
            enqueue_if_background(x + 1, y)
        if y > 0:
            enqueue_if_background(x, y - 1)
        if y < height - 1:
            enqueue_if_background(x, y + 1)

    if not any(background):
        return image

    alpha = bytearray(image.getchannel("A").tobytes())
    for index, is_background in enumerate(background):
        if is_background:
            alpha[index] = 0

    cutout = image.copy()
    cutout.putalpha(Image.frombytes("L", image.size, bytes(alpha)))
    return cutout


def _trim_to_visible_content(image: Image.Image) -> Image.Image:
    bbox = image.getchannel("A").getbbox()
    return image.crop(bbox) if bbox else image


def _placement_for_module(module_id: str | None) -> tuple[float, float, float, float]:
    if module_id in PRIMARY_PRODUCT_MODULE_IDS:
        return 0.46, 0.72, 0.50, 0.56
    if module_id in USAGE_PRODUCT_MODULE_IDS:
        return 0.30, 0.46, 0.74, 0.66
    return 0.26, 0.38, 0.78, 0.72


def _resize_product(product: Image.Image, background_size: tuple[int, int], module_id: str | None) -> Image.Image:
    bg_width, bg_height = background_size
    max_width_ratio, max_height_ratio, _, _ = _placement_for_module(module_id)
    max_width = max(1, int(bg_width * max_width_ratio))
    max_height = max(1, int(bg_height * max_height_ratio))
    scale = min(max_width / product.width, max_height / product.height)
    next_size = (
        max(1, round(product.width * scale)),
        max(1, round(product.height * scale)),
    )
    return product.resize(next_size, Image.Resampling.LANCZOS)


def _product_position(product_size: tuple[int, int], background_size: tuple[int, int], module_id: str | None) -> tuple[int, int]:
    product_width, product_height = product_size
    bg_width, bg_height = background_size
    _, _, center_x_ratio, center_y_ratio = _placement_for_module(module_id)
    margin_x = max(8, round(bg_width * 0.035))
    margin_y = max(8, round(bg_height * 0.035))
    x = round(bg_width * center_x_ratio - product_width / 2)
    y = round(bg_height * center_y_ratio - product_height / 2)
    x = min(max(margin_x, x), max(margin_x, bg_width - product_width - margin_x))
    y = min(max(margin_y, y), max(margin_y, bg_height - product_height - margin_y))
    return x, y


def _drop_shadow(product: Image.Image, background_size: tuple[int, int]) -> Image.Image:
    bg_width, bg_height = background_size
    blur_radius = max(4, round(min(bg_width, bg_height) * 0.018))
    alpha = product.getchannel("A").filter(ImageFilter.GaussianBlur(blur_radius))
    shadow_alpha = alpha.point(lambda value: min(92, round(value * 0.32)))
    shadow = Image.new("RGBA", product.size, (0, 0, 0, 0))
    shadow.putalpha(shadow_alpha)
    return shadow


def compose_fixed_product_image(background_bytes: bytes, product_bytes: bytes, *, module_id: str | None = None) -> bytes:
    """Composite the uploaded product pixels onto a generated background.

    The image model may create the background and atmosphere, but this keeps
    the SKU itself from being redrawn between modules.
    """
    background = _open_rgba(background_bytes)
    product = _trim_to_visible_content(_remove_edge_connected_background(_open_rgba(product_bytes)))
    product = _resize_product(product, background.size, module_id)
    x, y = _product_position(product.size, background.size, module_id)
    shadow = _drop_shadow(product, background.size)
    shadow_offset = (
        max(2, round(background.width * 0.012)),
        max(2, round(background.height * 0.014)),
    )

    canvas = background.copy()
    canvas.alpha_composite(shadow, (x + shadow_offset[0], y + shadow_offset[1]))
    canvas.alpha_composite(product, (x, y))

    output = BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

import base64
from io import BytesIO
import unittest

from PIL import Image

from app.services.image_model import _load_reference_image_files


def _image_data_url(image: Image.Image, *, image_format: str = "PNG") -> str:
    output = BytesIO()
    image.save(output, format=image_format)
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    mime = "image/png" if image_format.upper() == "PNG" else "image/jpeg"
    return f"data:{mime};base64,{encoded}"


class ImageModelReferenceTests(unittest.IsolatedAsyncioTestCase):
    async def test_reference_loader_downscales_oversized_images_for_model_upload(self):
        source = Image.new("RGB", (2400, 1200), "white")

        image_files = await _load_reference_image_files([_image_data_url(source)])

        filename, content, mime = image_files[0]
        resized = Image.open(BytesIO(content))
        self.assertEqual(mime, "image/jpeg")
        self.assertEqual(filename, "reference-1.jpeg")
        self.assertLessEqual(max(resized.size), 1536)
        self.assertEqual(resized.size, (1536, 768))

    async def test_reference_loader_keeps_small_images_unmodified(self):
        source = Image.new("RGB", (640, 640), "white")
        data_url = _image_data_url(source)
        original = base64.b64decode(data_url.partition(",")[2])

        image_files = await _load_reference_image_files([data_url])

        filename, content, mime = image_files[0]
        self.assertEqual(mime, "image/png")
        self.assertEqual(filename, "reference-1.png")
        self.assertEqual(content, original)

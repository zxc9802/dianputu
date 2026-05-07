import unittest

from app.core.config import ObjectStorageSettings
from app.services.object_storage import build_public_url, decode_data_url


class ObjectStorageTests(unittest.TestCase):
    def test_decode_data_url_extracts_content_type_and_bytes(self):
        decoded = decode_data_url("data:image/png;base64,aGVsbG8=")

        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded.content, b"hello")
        self.assertEqual(decoded.content_type, "image/png")
        self.assertEqual(decoded.extension, "png")

    def test_build_public_url_preserves_key_prefix_path(self):
        settings = ObjectStorageSettings(
            endpoint="https://example.r2.cloudflarestorage.com",
            access_key_id="access",
            secret_access_key="secret",
            bucket="dianpu",
            region="auto",
            public_base_url="https://img.example.com/",
            key_prefix="prod",
        )

        self.assertEqual(
            build_public_url(settings, "prod/generated/main/image.png"),
            "https://img.example.com/prod/generated/main/image.png",
        )


if __name__ == "__main__":
    unittest.main()

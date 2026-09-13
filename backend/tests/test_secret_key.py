import tempfile
import unittest
from pathlib import Path

from backend.app.secret_key import GENERATED_SECRET_LENGTH, load_or_create_secret_key


class SecretKeyTests(unittest.TestCase):
    def test_generated_secret_has_expected_length_and_is_persisted(self):
        with tempfile.TemporaryDirectory() as data_dir:
            first = load_or_create_secret_key(None, data_dir)
            second = load_or_create_secret_key("", data_dir)

            self.assertEqual(len(first), GENERATED_SECRET_LENGTH)
            self.assertEqual(second, first)
            self.assertEqual((Path(data_dir) / ".secret_key").read_text().strip(), first)

    def test_custom_secret_takes_precedence_without_creating_a_file(self):
        with tempfile.TemporaryDirectory() as data_dir:
            custom = "custom-secret-that-is-managed-outside-the-app"

            self.assertEqual(load_or_create_secret_key(custom, data_dir), custom)
            self.assertFalse((Path(data_dir) / ".secret_key").exists())

    def test_legacy_default_is_replaced_with_a_persisted_random_secret(self):
        with tempfile.TemporaryDirectory() as data_dir:
            generated = load_or_create_secret_key("mouse-secret-key-2026", data_dir)

            self.assertEqual(len(generated), GENERATED_SECRET_LENGTH)
            self.assertNotEqual(generated, "mouse-secret-key-2026")
            self.assertTrue((Path(data_dir) / ".secret_key").is_file())


if __name__ == "__main__":
    unittest.main()

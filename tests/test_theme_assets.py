import tempfile
import unittest
from pathlib import Path

from pic_record_manager.theme_assets import ThemeAssets


class ThemeAssetsTest(unittest.TestCase):
    def test_resolves_default_launcher_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            asset = root / "Themes" / "Default" / "MainWindow" / "LauncherFrame" / "button-start.png"
            asset.parent.mkdir(parents=True)
            asset.write_bytes(b"png")

            theme = ThemeAssets(root)

            self.assertEqual(asset, theme.launcher("button-start.png"))

    def test_returns_none_for_missing_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            theme = ThemeAssets(Path(tmp))

            self.assertIsNone(theme.launcher("missing.png"))

    def test_resolves_end_field_icon_from_default_theme_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            icon = root / "Themes" / "Default" / "EndField.ico"
            icon.parent.mkdir(parents=True)
            icon.write_bytes(b"ico")

            theme = ThemeAssets(root)

            self.assertEqual(icon, theme.end_field_icon())

    def test_lists_only_photoimage_supported_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "Themes" / "Default" / "MainWindow" / "LauncherFrame"
            base.mkdir(parents=True)
            (base / "ok.png").write_bytes(b"png")
            (base / "ok.webp").write_bytes(b"webp")
            (base / "unsupported.txt").write_text("text", encoding="utf-8")

            theme = ThemeAssets(root)

            self.assertEqual([base / "ok.png", base / "ok.webp"], theme.available_launcher_images())


if __name__ == "__main__":
    unittest.main()

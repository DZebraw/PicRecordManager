import tempfile
import unittest
from pathlib import Path

from endfielddoc.theme_assets import ThemeAssets


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

    def test_lists_only_photoimage_supported_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "Themes" / "Default" / "MainWindow" / "LauncherFrame"
            base.mkdir(parents=True)
            (base / "ok.png").write_bytes(b"png")
            (base / "unsupported.webp").write_bytes(b"webp")

            theme = ThemeAssets(root)

            self.assertEqual([base / "ok.png"], theme.available_launcher_images())


if __name__ == "__main__":
    unittest.main()

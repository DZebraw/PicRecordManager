from __future__ import annotations

from pathlib import Path


class ThemeAssets:
    """Resolve image assets copied from the XXMI launcher theme structure."""

    PHOTOIMAGE_EXTENSIONS = {".png", ".gif"}

    def __init__(self, workspace: Path | str, theme_name: str = "Default"):
        self.workspace = Path(workspace)
        self.theme_name = theme_name
        self.root = self.workspace / "Themes" / theme_name
        self.launcher_root = self.root / "MainWindow" / "LauncherFrame"

    def launcher(self, relative_path: str | Path) -> Path | None:
        path = self.launcher_root / relative_path
        return path if path.is_file() else None

    def top_bar(self, relative_path: str | Path) -> Path | None:
        return self.launcher(Path("TopBarFrame") / relative_path)

    def bottom_bar(self, relative_path: str | Path) -> Path | None:
        return self.launcher(Path("BottomBarFrame") / relative_path)

    def tool_bar(self, relative_path: str | Path) -> Path | None:
        return self.launcher(Path("ToolBarFrame") / relative_path)

    def available_launcher_images(self) -> list[Path]:
        if not self.launcher_root.is_dir():
            return []
        return sorted(
            path
            for path in self.launcher_root.rglob("*")
            if path.is_file() and path.suffix.lower() in self.PHOTOIMAGE_EXTENSIONS
        )

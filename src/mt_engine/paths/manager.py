"""Resolve portable application, bundle and data locations without hardcoded drives."""

from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PathManager:
    app_root: Path
    bundle_root: Path
    data_root: Path
    portable: bool

    @classmethod
    def detect(
        cls,
        *,
        source_root: Path | None = None,
        executable: Path | None = None,
        frozen: bool | None = None,
        local_appdata: Path | None = None,
    ) -> PathManager:
        is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen
        if is_frozen:
            root = (executable or Path(sys.executable)).resolve().parent
            bundled = Path(getattr(sys, "_MEIPASS", root)).resolve()
        else:
            root = (source_root or Path(__file__).resolve().parents[3]).resolve()
            bundled = root

        portable = (root / "portable.flag").is_file()
        if portable:
            data = root / "data"
        else:
            appdata = local_appdata or Path(
                os.environ.get("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")
            )
            data = appdata.resolve() / "MT" / "MediaStudio"
        return cls(root, bundled, data, portable)

    def resource(self, *parts: str) -> Path:
        return self._inside(self.bundle_root / "resources", *parts)

    def data(self, *parts: str) -> Path:
        return self._inside(self.data_root, *parts)

    @staticmethod
    def _inside(base: Path, *parts: str) -> Path:
        base = base.resolve()
        resolved = base.joinpath(*parts).resolve()
        if not resolved.is_relative_to(base):
            raise ValueError("Path escapes its managed root")
        return resolved

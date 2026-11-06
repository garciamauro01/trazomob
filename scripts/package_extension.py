# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, Mauro Garcia and IngeTrazo contributors.
"""Empacotador oficial do plugin TrazoMob para o catálogo ingetrazo-extensions.

Gera:
- dist/trazomob.zip (com pasta raiz 'trazomob/' e caminhos POSIX compatíveis)
- dist/trazomob.toml (ficha técnica pronta para o catálogo oficial com SHA-256 calculado)
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import zipfile
from pathlib import Path

PLUGIN_ID = "trazomob"
VERSION = "1.0.0"
INGETRAZO_VERSION = "0.5.11"
AUTHOR = "Mauro Garcia"
AUTHOR_URL = "https://github.com/garciamauro01"
REPOSITORY = "https://github.com/garciamauro01/trazomob"
LICENSE = "GPL-3.0-or-later"

EXCLUDE_PREFIXES = (
    ".git",
    "dist",
    "scripts",
    "tests",
    "__pycache__",
    ".pytest_cache",
)

EXCLUDE_FILES = {
    ".gitignore",
    ".DS_Store",
    "Thumbs.db",
}


def get_tracked_files(repo_root: Path) -> list[Path]:
    """Obtém a lista de arquivos rastreados pelo Git ou varre o diretório."""
    try:
        out = subprocess.check_output(
            ["git", "ls-files"], cwd=str(repo_root), text=True, encoding="utf-8"
        )
        files = [repo_root / line.strip() for line in out.splitlines() if line.strip()]
        return [f for f in files if f.is_file()]
    except Exception:
        return [p for p in repo_root.rglob("*") if p.is_file()]


def should_include(rel_posix: str, filename: str) -> bool:
    if filename in EXCLUDE_FILES or filename.endswith((".pyc", ".pyo", ".log", ".zip")):
        return False
    parts = rel_posix.split("/")
    for part in parts:
        if part in EXCLUDE_PREFIXES or part.startswith("."):
            return False
    return True


def build_package() -> tuple[Path, str, Path]:
    repo_root = Path(__file__).resolve().parent.parent
    dist_dir = repo_root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)

    zip_path = dist_dir / f"{PLUGIN_ID}.zip"
    files = get_tracked_files(repo_root)

    included_count = 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(files):
            rel_posix = file_path.relative_to(repo_root).as_posix()
            if not should_include(rel_posix, file_path.name):
                continue
            arcname = f"{PLUGIN_ID}/{rel_posix}"
            # Usa ZipInfo fixo para reprodutibilidade e permissões limpas (sem symlinks)
            info = zipfile.ZipInfo(arcname)
            info.date_time = (2026, 1, 1, 0, 0, 0)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, file_path.read_bytes())
            included_count += 1

    zip_bytes = zip_path.read_bytes()
    sha256_hash = hashlib.sha256(zip_bytes).hexdigest()

    download_url = f"{REPOSITORY}/releases/download/v{VERSION}/{PLUGIN_ID}.zip"

    toml_content = f'''# Copy this file to extensions/{PLUGIN_ID}.toml in ingelibre/ingetrazo-extensions
id = "{PLUGIN_ID}"
version = "{VERSION}"
author = "{AUTHOR}"
author_url = "{AUTHOR_URL}"

license = "{LICENSE}"

repository = "{REPOSITORY}"

download = "{download_url}"
sha256 = "{sha256_hash}"

ingetrazo = "{INGETRAZO_VERSION}"

tags = ["fabrication", "architecture", "bim", "productivity"]

# Optional: a picture in screenshots/ (png, jpg or webp, under 600 KB, ~1200x750).
# screenshot = "{PLUGIN_ID}.png"

[name]
pt = "TrazoMob - Marcenaria e Modulação 3D"
es = "TrazoMob - Carpintería y Modulación 3D"
en = "TrazoMob - Cabinet & Woodworking 3D"

[summary]
pt = "Modulação paramétrica de móveis sob medida, ambientes 2D/3D, furações CNC, orçamento e plano de corte integrado."
es = "Modulación paramétrica de muebles a medida, ambientes 2D/3D, mecanizado CNC, presupuesto y plano de corte integrado."
en = "Parametric custom cabinet design, 2D/3D rooms, CNC boring, pricing and integrated cutlist optimizer for woodworking."
'''

    toml_path = dist_dir / f"{PLUGIN_ID}.toml"
    toml_path.write_text(toml_content, encoding="utf-8")

    print(f"Pacote gerado com sucesso: {zip_path} ({included_count} arquivos, {len(zip_bytes) / 1024:.1f} KB)")
    print(f"SHA-256: {sha256_hash}")
    print(f"Ficha TOML gerada em: {toml_path}")
    return zip_path, sha256_hash, toml_path


if __name__ == "__main__":
    build_package()


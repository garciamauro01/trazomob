# SPDX-License-Identifier: GPL-3.0-or-later
"""Gerenciador e orquestrador de renderização foto-realista do TrazoMob.

Executa o Blender em segundo plano de forma 100% autônoma, usando o script
exclusivo do TrazoMob (`blender_scripts/photoreal_render.py`).
"""
from __future__ import annotations

import json
import os
import sys
import glob
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from PySide6.QtCore import QObject, QProcess, Signal, QSettings
from PySide6.QtGui import QVector3D


class TrazoMobRenderEngine(QObject):
    """Orquestra a criação do job e o processo em background do Blender."""

    progress_updated = Signal(int, str)  # percent (0..100 or -1 for indeterminate), message
    render_finished = Signal(str)  # Caminho da imagem gerada
    render_failed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._process: Optional[QProcess] = None
        self._output_path: Optional[str] = None

    @staticmethod
    def get_blender_executable() -> Optional[str]:
        """Localiza o executável do Blender no sistema operacional."""
        settings = QSettings()
        custom = settings.value("render/blender_path", "")
        if custom and os.path.isfile(custom):
            return str(custom)

        candidates = []
        if sys.platform == "win32":
            roots = [os.environ.get(k) for k in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA")]
            for root in filter(None, roots):
                candidates += sorted(glob.glob(os.path.join(root, "Blender Foundation", "Blender*", "blender.exe")), reverse=True)
                candidates.append(os.path.join(root, "Steam", "steamapps", "common", "Blender", "blender.exe"))
        elif sys.platform == "darwin":
            candidates += sorted(glob.glob("/Applications/Blender*.app/Contents/MacOS/Blender"), reverse=True)
        else:
            candidates += ["/usr/bin/blender", "/usr/local/bin/blender", "/snap/bin/blender"]
            candidates += sorted(glob.glob("/opt/blender*/blender"), reverse=True)

        for p in candidates:
            if os.path.isfile(p):
                return p
        return None

    def start_render(
        self,
        scene,
        camera,
        preset: str = "dia",
        engine: str = "cycles",
        quality: str = "high",
        width: int = 1920,
        height: int = 1080,
        correct_verticals: bool = True
    ) -> bool:
        """Inicia a renderização fotorrealista via Blender em segundo plano."""
        blender_exe = self.get_blender_executable()
        if not blender_exe:
            self.render_failed.emit(
                "O Blender não foi encontrado automaticamente no seu computador.\n"
                "Instale o Blender (gratuito) em www.blender.org ou aponte o executável nas configurações."
            )
            return False

        # Cria pasta temporária exclusiva para este render
        stamp = time.strftime("%Y%m%d-%H%M%S")
        from PySide6.QtCore import QStandardPaths
        base_cache = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericCacheLocation)
        work_dir = Path(base_cache) / "IngeTrazo" / "trazomob_renders" / stamp
        work_dir.mkdir(parents=True, exist_ok=True)

        # 1. Exporta o modelo para GLB
        glb_path = work_dir / "scene.glb"
        from formats.gltf import save_glb
        save_glb(scene, glb_path)

        # 2. Amostras conforme a qualidade
        samples_map = {
            "draft": 32 if engine == "cycles" else 16,
            "medium": 128 if engine == "cycles" else 32,
            "high": 256 if engine == "cycles" else 64,
            "ultra": 512 if engine == "cycles" else 128,
        }
        samples = samples_map.get(quality, 128)

        # 3. Calcula vetor de luz do sol do IngeTrazo se dia/tarde
        from core.render_blender import sun_toward, camera_dict
        sun_vec = sun_toward(scene) if preset in ("dia", "tarde") else None

        # 4. Monta o job.json
        output_img = work_dir / "render_trazomob.png"
        self._output_path = str(output_img)

        job = {
            "glb": str(glb_path),
            "output": str(output_img),
            "engine": engine,
            "preset": preset,
            "samples": samples,
            "width": width,
            "height": height,
            "correct_verticals": correct_verticals,
            "camera": camera_dict(camera),
            "sun": sun_vec,
            "exposure": 0.0 if preset in ("dia", "noturno", "estudio") else -0.1,
            "blend_file": str(work_dir / "cena_marcenaria_trazomob.blend"),
        }

        job_path = work_dir / "job.json"
        job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")

        # 5. Localiza o script autônomo do TrazoMob
        curr_dir = Path(__file__).resolve().parent
        script_path = curr_dir / "blender_scripts" / "photoreal_render.py"

        # 6. Prepara e executa o QProcess
        self._process = QProcess(self)
        from core.render_blender import clean_env
        from PySide6.QtCore import QProcessEnvironment
        q_env = QProcessEnvironment()
        for k, v in clean_env().items():
            q_env.insert(k, v)
        self._process.setProcessEnvironment(q_env)

        args = ["-b", "--factory-startup", "--python", str(script_path), "--", str(job_path)]

        self._process.readyReadStandardOutput.connect(self._on_stdout)
        self._process.readyReadStandardError.connect(self._on_stderr)
        self._process.finished.connect(self._on_finished)

        self.progress_updated.emit(5, "Iniciando motor do Blender e shaders PBR...")
        self._process.start(blender_exe, args)
        return True

    def cancel(self):
        """Cancela a renderização se estiver em andamento."""
        if self._process and self._process.state() != QProcess.NotRunning:
            self._process.kill()
            self.progress_updated.emit(0, "Renderização cancelada.")

    def _on_stdout(self):
        if not self._process:
            return
        data = self._process.readAllStandardOutput().data().decode("utf-8", errors="ignore")
        for line in data.splitlines():
            line_str = line.strip()
            if not line_str:
                continue

            if "TRAZOMOB_RENDER" in line_str:
                parts = line_str.split("TRAZOMOB_RENDER", 1)[-1].strip()
                if "rendering" in parts:
                    self.progress_updated.emit(20, "🎨 Renderizando cena foto-realista no Blender...")
                elif "imported" in parts:
                    self.progress_updated.emit(10, "📦 Geometria e texturas de marcenaria carregadas...")
                elif "gpu_enabled" in parts:
                    self.progress_updated.emit(15, "🚀 Aceleração por Placa de Vídeo (GPU) ativada!")
            elif "Sample " in line_str:
                # Exemplo Cycles: "Sample 25/128" ou "Sample 15/128 | Time: 00:03.21"
                import re
                match = re.search(r"Sample\s+(\d+)\s*/\s*(\d+)", line_str)
                if match:
                    cur = int(match.group(1))
                    tot = int(match.group(2))
                    pct = int(20 + (cur / max(1, tot)) * 75)
                    self.progress_updated.emit(pct, f"Amostragem Cycles ({cur}/{tot} samples)")
                else:
                    self.progress_updated.emit(-1, f"Calculando iluminação: {line_str}")
            elif "Denoising" in line_str or "denoise" in line_str.lower():
                self.progress_updated.emit(96, "✨ Aplicando Inteligência Artificial Denoiser (redução de ruído)...")
            elif "Writing: " in line_str or "Saved: " in line_str:
                self.progress_updated.emit(99, "💾 Gravando arquivo PNG final com alta fidelidade...")

    def _on_stderr(self):
        if not self._process:
            return
        # Apenas consome stderr sem travar o buffer
        self._process.readAllStandardError()

    def _on_finished(self, exit_code, exit_status):
        if exit_code == 0 and self._output_path and os.path.isfile(self._output_path):
            self.progress_updated.emit(100, "✅ Imagem foto-realista concluída!")
            self.render_finished.emit(self._output_path)
        else:
            self.render_failed.emit("O processo de renderização foi interrompido ou falhou.")

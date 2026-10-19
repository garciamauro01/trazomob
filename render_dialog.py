# SPDX-License-Identifier: GPL-3.0-or-later
"""Diálogo Visual do TrazoMob para Renderização Foto-Realista de Ambientes e Marcenaria."""
from __future__ import annotations

import os
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QFrame,
    QLabel, QPushButton, QComboBox, QCheckBox, QProgressBar,
    QFileDialog, QMessageBox, QGraphicsView, QGraphicsScene,
    QGraphicsPixmapItem
)

from .render_engine import TrazoMobRenderEngine


class TrazoMobRenderDialog(QDialog):
    """Janela de Render Foto-Realista integrada à barra de ferramentas do TrazoMob."""

    def __init__(self, viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.setWindowTitle("📸 TrazoMob — Render Foto-Realista de Interiores")
        self.setMinimumSize(920, 640)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        self._engine = TrazoMobRenderEngine(self)
        self._engine.progress_updated.connect(self._on_progress)
        self._engine.render_finished.connect(self._on_finished)
        self._engine.render_failed.connect(self._on_failed)

        self._current_image_path: str | None = None
        self._build_ui()

    def _build_ui(self):
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)

        # ── PAINEL LATERAL ESQUERDO: CONTROLES E PRESETS ──
        ctrl_frame = QFrame()
        ctrl_frame.setFixedWidth(300)
        ctrl_frame.setStyleSheet("QFrame { background-color: palette(base); border: 1px solid palette(mid); border-radius: 6px; }")
        l_ctrl = QVBoxLayout(ctrl_frame)
        l_ctrl.setContentsMargins(10, 10, 10, 10)
        l_ctrl.setSpacing(10)

        lbl_sec_preset = QLabel("<b>🎨 Iluminação do Ambiente</b>")
        l_ctrl.addWidget(lbl_sec_preset)

        self.cb_preset = QComboBox()
        self.cb_preset.addItems([
            "☀️ Dia Claro (Luz Solar + Céu Físico)",
            "🌅 Entardecer / Golden Hour (Luz Dourada)",
            "🛋️ Noturno Aconchegante (Fitas LED + Luz Suave)",
            "🏢 Estúdio Comercial (Catálogo de Marcenaria)"
        ])
        l_ctrl.addWidget(self.cb_preset)

        l_ctrl.addSpacing(6)
        lbl_sec_quality = QLabel("<b>⚙️ Motor e Resolução</b>")
        l_ctrl.addWidget(lbl_sec_quality)

        form_opts = QFormLayout()
        form_opts.setSpacing(8)

        self.cb_engine = QComboBox()
        self.cb_engine.addItems(["Cycles (Máximo Foto-Realismo)", "EEVEE Next (Ultra-Rápido)"])
        form_opts.addRow("Motor:", self.cb_engine)

        self.cb_quality = QComboBox()
        self.cb_quality.addItems(["Rápido (Prévia)", "Média", "Alta Definição (Cliente)", "Ultra / 4K"])
        self.cb_quality.setCurrentIndex(2)  # Alta Definição padrão
        form_opts.addRow("Amostras:", self.cb_quality)

        self.cb_resolution = QComboBox()
        self.cb_resolution.addItems(["1280 × 720 (HD)", "1920 × 1080 (Full HD)", "2560 × 1440 (2K)", "3840 × 2160 (4K)"])
        self.cb_resolution.setCurrentIndex(1)  # Full HD padrão
        form_opts.addRow("Resolução:", self.cb_resolution)

        l_ctrl.addLayout(form_opts)

        self.chk_verticals = QCheckBox("Corrigir Verticais (Perspectiva 2 Pontos)")
        self.chk_verticals.setToolTip("Mantém as paredes a 90° perfeitos sem inclinação, padrão de fotografia imobiliária.")
        self.chk_verticals.setChecked(True)
        l_ctrl.addWidget(self.chk_verticals)

        l_ctrl.addStretch()

        self.btn_render = QPushButton("🚀 Iniciar Render Foto-Realista")
        self.btn_render.setStyleSheet(
            "QPushButton { background-color: #16A34A; color: white; font-weight: bold; font-size: 13px; padding: 12px; border-radius: 6px; }"
            "QPushButton:hover { background-color: #15803D; }"
            "QPushButton:disabled { background-color: #94A3B8; }"
        )
        self.btn_render.clicked.connect(self._start_render)
        l_ctrl.addWidget(self.btn_render)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setVisible(False)
        self.btn_cancel.clicked.connect(self._cancel_render)
        l_ctrl.addWidget(self.btn_cancel)

        main_layout.addWidget(ctrl_frame)

        # ── PAINEL PRINCIPAL DIREITO: VISUALIZADOR DA IMAGEM ──
        view_layout = QVBoxLayout()
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.setSpacing(6)

        # Área Gráfica
        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("background-color: #1E293B; border-radius: 6px;")
        self._pix_item = QGraphicsPixmapItem()
        self.scene.addItem(self._pix_item)
        view_layout.addWidget(self.view, 1)

        # Barra de Progresso e Status
        h_status = QHBoxLayout()
        self.lbl_status = QLabel("Pronto para renderizar a vista atual da câmera.")
        self.lbl_status.setStyleSheet("font-weight: bold; color: palette(text);")
        h_status.addWidget(self.lbl_status, 1)

        self.btn_save = QPushButton("💾 Salvar Imagem...")
        self.btn_save.setEnabled(False)
        self.btn_save.clicked.connect(self._save_image)
        h_status.addWidget(self.btn_save)

        view_layout.addLayout(h_status)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 0)
        self.progress_bar.setVisible(False)
        view_layout.addWidget(self.progress_bar)

        main_layout.addLayout(view_layout, 1)

    def _start_render(self):
        preset_keys = ["dia", "tarde", "noturno", "estudio"]
        preset = preset_keys[self.cb_preset.currentIndex()]

        engine = "cycles" if self.cb_engine.currentIndex() == 0 else "eevee"

        qual_keys = ["draft", "medium", "high", "ultra"]
        quality = qual_keys[self.cb_quality.currentIndex()]

        res_map = [(1280, 720), (1920, 1080), (2560, 1440), (3840, 2160)]
        w, h = res_map[self.cb_resolution.currentIndex()]

        vert = self.chk_verticals.isChecked()

        self.btn_render.setEnabled(False)
        self.btn_cancel.setVisible(True)
        self.btn_save.setEnabled(False)
        self.progress_bar.setVisible(True)

        ok = self._engine.start_render(
            scene=self.viewport.scene,
            camera=self.viewport.camera,
            preset=preset,
            engine=engine,
            quality=quality,
            width=w,
            height=h,
            correct_verticals=vert
        )
        if not ok:
            self._reset_buttons()

    def _cancel_render(self):
        self._engine.cancel()
        self._reset_buttons()

    def _reset_buttons(self):
        self.btn_render.setEnabled(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setVisible(False)

    def _on_progress(self, msg: str):
        self.lbl_status.setText(msg)

    def _on_finished(self, img_path: str):
        self._reset_buttons()
        self._current_image_path = img_path
        pix = QPixmap(img_path)
        self._pix_item.setPixmap(pix)
        self.scene.setSceneRect(self._pix_item.boundingRect())
        self.view.fitInView(self._pix_item, Qt.KeepAspectRatio)
        self.btn_save.setEnabled(True)
        self.lbl_status.setText(f"✅ Render concluído com sucesso ({pix.width()} × {pix.height()} px)!")

    def _on_failed(self, err_msg: str):
        self._reset_buttons()
        self.lbl_status.setText("❌ Falha na renderização.")
        QMessageBox.warning(self, "Render Foto-Realista", err_msg)

    def _save_image(self):
        if not self._current_image_path or not os.path.isfile(self._current_image_path):
            return
        dest, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Render Foto-Realista",
            "render_ambiente.png",
            "Imagens PNG (*.png);;Imagens JPEG (*.jpg)"
        )
        if dest:
            import shutil
            shutil.copyfile(self._current_image_path, dest)
            QMessageBox.information(self, "Imagem Salva", f"Render salvo com sucesso em:\n{dest}")

# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Interface gráfica principal do TrazoMob (TrazoMobDialog)."""

from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QDialog

from ..interaction.module_aligner import ModuleAlignerMixin
from ..production.cutlist_tab import CutListTabMixin
from ..ui.module_gallery import DialogGalleryMixin
from .module_dialog_build import ModuleDialogBuildMixin
from .module_dialog_form import ModuleDialogFormMixin
from .module_dialog_actions import ModuleDialogActionsMixin
from .module_dialog_style import ModuleDialogStyleMixin
from .module_dialog_sections import ModuleDialogSectionsMixin
from .module_dialog_options import ModuleDialogOptionsMixin


class TrazoMobDialog(
    ModuleDialogBuildMixin,
    ModuleDialogSectionsMixin,
    ModuleDialogOptionsMixin,
    ModuleDialogFormMixin,
    ModuleDialogActionsMixin,
    ModuleDialogStyleMixin,
    QDialog,
    ModuleAlignerMixin,
    CutListTabMixin,
    DialogGalleryMixin,
):
    """Janela principal com Biblioteca Paramétrica Dinâmica e Plano de Corte."""

    def __init__(self, viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.scene = viewport.scene
        # Transforma o diálogo em janela de primeira classe com Maximizar, Minimizar e redimensionamento nativo
        self.setWindowFlags(Qt.Window)
        self.setSizeGripEnabled(True)
        self._pedra_widgets = []  # populated in _build_modules_tab
        self._fundo_widgets = []
        self._travessa_widgets = []
        self._gaveta_widgets = []

        # Tamanho mínimo flexível para que a janela nunca trave o redimensionamento
        self.setMinimumSize(720, 460)

        self._editing_module: Group | None = None
        self._parts: list[dict[str, Any]] = []
        self._detect_selected_module()
        self._build_ui()
        self._reload_parts()

        st = QSettings()
        geo = st.value("ui/trazomob_geometry")
        if geo:
            self.restoreGeometry(geo)
        else:
            screen = self.screen() or (QApplication.primaryScreen() if QApplication.instance() else None)
            if screen:
                avail = screen.availableGeometry()
                init_w = min(1000, max(750, int(avail.width() * 0.70)))
                init_h = min(580, max(460, int(avail.height() * 0.68)))
                pos_x = avail.x() + (avail.width() - init_w) // 2
                pos_y = avail.y() + (avail.height() - init_h) // 2
                self.setGeometry(pos_x, pos_y, init_w, init_h)
            else:
                self.resize(920, 540)

    def _save_geom(self) -> None:
        QSettings().setValue("ui/trazomob_geometry", self.saveGeometry())

    def accept(self) -> None:
        self._save_geom()
        super().accept()

    def reject(self) -> None:
        self._save_geom()
        super().reject()

    def closeEvent(self, event) -> None:
        self._save_geom()
        super().closeEvent(event)

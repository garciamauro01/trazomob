# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Montagem da aba Materiais e Fitas da barra lateral."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)


class SidebarMateriaisMixin:
    """Cria as secoes de materiais, chapas e fitas."""

    def _build_materiais_section(self) -> None:
        """Monta as secoes de materiais e fitas."""
        # --- Padrões de MDF e Chapas ---
        from ..domain.materials_catalog import ALL_BOX_MATERIALS, MDF_MATERIALS


        self.cb_material = QComboBox()
        self.cb_material.addItems(ALL_BOX_MATERIALS)
        self.lbl_material_caixa = QLabel("Caixa:")
        self.sec_materiais.form_layout.addRow(self.lbl_material_caixa, self.cb_material)

        self.cb_espessura = QComboBox()
        self.cb_espessura.addItems(["15 mm", "18 mm", "20 mm", "25 mm", "40 mm"])
        self.lbl_espessura_caixa = QLabel("Esp. Caixa:")
        self.sec_materiais.form_layout.addRow(self.lbl_espessura_caixa, self.cb_espessura)

        self.cb_fita_caixa = QComboBox()
        self.cb_fita_caixa.addItems([
            "Frontal 1L (Bordo Aparente)",
            "2L (Frontal e Traseiro)",
            "4L (Todos os 4 Bordos)",
            "Sem Fita de Borda",
        ])
        self.lbl_fita_caixa = QLabel("Fita Caixa:")
        self.sec_materiais.form_layout.addRow(self.lbl_fita_caixa, self.cb_fita_caixa)

        self.cb_material_fita_caixa = QComboBox()
        self.cb_material_fita_caixa.addItems(["(Mesmo da Caixa)"] + MDF_MATERIALS)
        self.lbl_material_fita_caixa = QLabel("Padrão Fita Cx:")
        self.sec_materiais.form_layout.addRow(self.lbl_material_fita_caixa, self.cb_material_fita_caixa)

        self.cb_material_frentes = QComboBox()
        self.cb_material_frentes.addItems(["(Mesmo da Caixa)"] + MDF_MATERIALS)
        self.lbl_material_frentes = QLabel("Frentes:")
        self.sec_materiais.form_layout.addRow(self.lbl_material_frentes, self.cb_material_frentes)

        self.cb_espessura_frentes = QComboBox()
        self.cb_espessura_frentes.addItems([
            "(Mesma da Caixa)",
            "15 mm",
            "18 mm",
            "25 mm",
        ])
        self.lbl_espessura_frentes = QLabel("Esp. Frentes:")
        self.sec_materiais.form_layout.addRow(self.lbl_espessura_frentes, self.cb_espessura_frentes)

        # Botões para Troca Rápida Global de Cores e Padrões no Ambiente (Estilo Promob)
        self.btn_aplicar_frentes_todos = QPushButton("🎨 Aplicar Padrão de Frentes em Todo o Projeto")
        self.btn_aplicar_frentes_todos.setToolTip("Substitui o padrão de MDF das frentes (portas e gavetas) de todos os armários da cena")
        self.btn_aplicar_frentes_todos.setStyleSheet(
            "QPushButton { background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px; padding: 5px; font-weight: bold; color: #334155; }"
            "QPushButton:hover { background-color: #E2E8F0; color: #0F172A; border-color: #94A3B8; }"
        )
        self.btn_aplicar_frentes_todos.clicked.connect(self._on_apply_frentes_to_all_modules)
        self.sec_materiais.form_layout.addRow(self.btn_aplicar_frentes_todos)

        self.btn_aplicar_caixa_todos = QPushButton("🪵 Aplicar Padrão de Caixaria em Todo o Projeto")
        self.btn_aplicar_caixa_todos.setToolTip("Substitui o padrão de MDF da caixaria (laterais, bases, prateleiras) de todos os armários da cena")
        self.btn_aplicar_caixa_todos.setStyleSheet(
            "QPushButton { background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px; padding: 5px; font-weight: bold; color: #334155; }"
            "QPushButton:hover { background-color: #E2E8F0; color: #0F172A; border-color: #94A3B8; }"
        )
        self.btn_aplicar_caixa_todos.clicked.connect(self._on_apply_caixa_to_all_modules)
        self.sec_materiais.form_layout.addRow(self.btn_aplicar_caixa_todos)



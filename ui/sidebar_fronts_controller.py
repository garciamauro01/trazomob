# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Montagem da aba Frentes e Estrutura da barra lateral."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)
from ..domain.i18n import tr


class SidebarFrentesMixin:
    """Cria as secoes internas e de fundo da aba Frentes & Estrutura."""

    def _build_frentes_section(self) -> None:
        """Monta as secoes internas e de fundo."""
        # --- Configurações de Forno (balcao_forno) na Estrutura ---
        self.lbl_forno_section = QLabel("<b>🔥 Balcão para Forno Embutido:</b>")
        self.sec_frentes.form_layout.addRow(self.lbl_forno_section)

        self.chk_forno_tem_gaveta = QCheckBox(tr("Possui Gaveta Inferior"))
        self.chk_forno_tem_gaveta.setChecked(True)
        self.lbl_forno_tem_gaveta = QLabel(tr("Gaveta Inferior:"))
        self.sec_frentes.form_layout.addRow(self.lbl_forno_tem_gaveta, self.chk_forno_tem_gaveta)

        self.sp_forno_alt_gaveta = QSpinBox()
        self.sp_forno_alt_gaveta.setRange(80, 500)
        self.sp_forno_alt_gaveta.setValue(150)
        self.sp_forno_alt_gaveta.setSuffix(" mm")
        self.lbl_forno_alt_gaveta = QLabel(tr("Altura da Gaveta:"))
        self.sec_frentes.form_layout.addRow(self.lbl_forno_alt_gaveta, self.sp_forno_alt_gaveta)

        self._forno_sidebar_widgets = [
            self.lbl_forno_section,
            self.lbl_forno_tem_gaveta, self.chk_forno_tem_gaveta,
            self.lbl_forno_alt_gaveta, self.sp_forno_alt_gaveta,
        ]
        for w in self._forno_sidebar_widgets:
            w.setVisible(False)

        def _on_sb_forno_tem_gaveta_changed(state):
            tem_g = self.chk_forno_tem_gaveta.isChecked()
            is_f = getattr(self, "_current_selected_tipo", "") == "balcao_forno"
            self.lbl_forno_alt_gaveta.setVisible(is_f and tem_g)
            self.sp_forno_alt_gaveta.setVisible(is_f and tem_g)
            if hasattr(self, "_gaveta_sidebar_widgets") and is_f:
                for gw in self._gaveta_sidebar_widgets:
                    gw.setVisible(tem_g)
        self.chk_forno_tem_gaveta.stateChanged.connect(_on_sb_forno_tem_gaveta_changed)

        # --- Configurações de Porta-Tempero (porta_tempero) na Estrutura ---
        self.lbl_tempero_section = QLabel("<b>🧂 Porta-Tempero / Toalheiro:</b>")
        self.sec_frentes.form_layout.addRow(self.lbl_tempero_section)

        self.cb_tipo_estrutura_tempero = QComboBox()
        self.cb_tipo_estrutura_tempero.addItems([
            tr("📦 100% MDF (Marcenaria / Sob Medida)"),
            tr("✨ Kit Aramado Telescópico (Ferragem Comercial)"),
        ])
        self.cb_tipo_estrutura_tempero.setToolTip(tr("Escolha entre bandejas sob medida em MDF ou kit aramado metálico comercial"))
        self.lbl_tipo_estrutura_tempero = QLabel(tr("Estrutura Interna:"))
        self.sec_frentes.form_layout.addRow(self.lbl_tipo_estrutura_tempero, self.cb_tipo_estrutura_tempero)

        self.cb_cor_aramado = QComboBox()
        self.cb_cor_aramado.addItems([
            tr("Inox / Cromado"),
            tr("Preto Fosco (Black)"),
        ])
        self.cb_cor_aramado.setToolTip(tr("Acabamento metálico do cesto aramado"))
        self.lbl_cor_aramado = QLabel(tr("Cor do Aramado:"))
        self.sec_frentes.form_layout.addRow(self.lbl_cor_aramado, self.cb_cor_aramado)

        self._tempero_sidebar_widgets = [
            self.lbl_tempero_section,
            self.lbl_tipo_estrutura_tempero, self.cb_tipo_estrutura_tempero,
            self.lbl_cor_aramado, self.cb_cor_aramado,
        ]
        for w in self._tempero_sidebar_widgets:
            w.setVisible(False)

        def _on_sb_tipo_estrutura_tempero_changed(idx):
            is_aramado = (idx == 1)
            is_pt = getattr(self, "_current_selected_tipo", "") == "porta_tempero"
            self.lbl_cor_aramado.setVisible(is_pt and is_aramado)
            self.cb_cor_aramado.setVisible(is_pt and is_aramado)
        self.cb_tipo_estrutura_tempero.currentIndexChanged.connect(_on_sb_tipo_estrutura_tempero_changed)

        # --- Elementos Internos & Rodapé ---



        self.sp_largura_gaveteiro = QSpinBox()
        self.sp_largura_gaveteiro.setRange(250, 1200)
        self.sp_largura_gaveteiro.setValue(450)
        self.sp_largura_gaveteiro.setSingleStep(50)
        self.sp_largura_gaveteiro.setSuffix(" mm")
        self.sp_largura_gaveteiro.setToolTip(tr("Largura externa da seção de gavetas no balcão misto"))
        self.lbl_largura_gaveteiro = QLabel(tr("Largura Gaveteiro:"))
        self.sec_frentes.form_layout.addRow(self.lbl_largura_gaveteiro, self.sp_largura_gaveteiro)
        self.lbl_largura_gaveteiro.setVisible(False)
        self.sp_largura_gaveteiro.setVisible(False)

        self.cb_lado_gaveteiro = QComboBox()
        self.cb_lado_gaveteiro.addItems([
            tr("⬅️ À Esquerda"),
            tr("➡️ À Direita"),
        ])
        self.cb_lado_gaveteiro.setToolTip(tr("Define em qual lado do balcão misto fica o gaveteiro (Esquerda ou Direita)"))
        self.lbl_lado_gaveteiro = QLabel(tr("Lado Gaveteiro:"))
        self.sec_frentes.form_layout.addRow(self.lbl_lado_gaveteiro, self.cb_lado_gaveteiro)
        self.lbl_lado_gaveteiro.setVisible(False)
        self.cb_lado_gaveteiro.setVisible(False)



        self.sp_prateleiras = QSpinBox()
        self.sp_prateleiras.setRange(0, 6)
        self.sp_prateleiras.setValue(1)
        self.lbl_prateleiras = QLabel(tr("Prateleiras:"))
        self.sec_frentes.form_layout.addRow(self.lbl_prateleiras, self.sp_prateleiras)

        # --- Divisórias Internas e Vãos Livres Dinâmicos ---
        self.sp_divisoes = QSpinBox()
        self.sp_divisoes.setRange(0, 5)
        self.sp_divisoes.setValue(0)
        self.sp_divisoes.setToolTip(tr("Quantidade de divisórias verticais internas. Divide o armário em múltiplos vãos com cálculo automático de luz livre."))
        self.lbl_divisoes = QLabel(tr("Divisórias Vert.:"))
        self.sec_frentes.form_layout.addRow(self.lbl_divisoes, self.sp_divisoes)

        self.lbl_vaos_livres = QLabel("")
        self.lbl_vaos_livres.setStyleSheet(
            "QLabel { background: #F8FAFC; border: 1px dashed #94A3B8; border-radius: 4px; padding: 4px 6px; font-size: 10px; color: #0284C7; font-weight: bold; }"
        )
        self.lbl_vaos_livres.setWordWrap(True)
        self.sec_frentes.form_layout.addRow(self.lbl_vaos_livres)
        self.lbl_vaos_livres.setVisible(False)

        def _update_vaos_livres_preview():
            """Calcula a luz livre / vão útil em tempo real conforme largura e divisórias."""
            try:
                if getattr(self, "_auto_divisoes", False):
                    self.lbl_vaos_livres.setVisible(False)
                    return
                L = float(self.sp_largura.value())
                esp = 15.0
                if hasattr(self, "cb_espessura"):
                    esp = float(self.cb_espessura.currentText().split()[0])
                num_div = self.sp_divisoes.value()
                # Largura útil interna descontando as 2 laterais da caixa
                luz_total = max(0.0, L - (2.0 * esp))
                if num_div <= 0:
                    self.lbl_vaos_livres.setVisible(False)
                    return
                # Luz livre de cada vão descontando a espessura das divisórias
                luz_util = max(0.0, luz_total - (num_div * esp))
                vao_mm = luz_util / (num_div + 1)
                texto_vaos = f"📏 {num_div + 1} Vãos Livres: {int(round(vao_mm))} mm cada (Luz interna)"
                self.lbl_vaos_livres.setText(texto_vaos)
                self.lbl_vaos_livres.setVisible(True)
            except Exception:
                self.lbl_vaos_livres.setVisible(False)

        self.sp_largura.valueChanged.connect(_update_vaos_livres_preview)
        self.sp_divisoes.valueChanged.connect(_update_vaos_livres_preview)
        self.cb_espessura.currentIndexChanged.connect(_update_vaos_livres_preview)

        self.sp_rodape = QSpinBox()
        self.sp_rodape.setRange(0, 300)
        self.sp_rodape.setValue(0)
        self.sp_rodape.setSuffix(" mm")
        self.lbl_rodape = QLabel(tr("Rodapé:"))
        self.sec_frentes.form_layout.addRow(self.lbl_rodape, self.sp_rodape)

        # --- Fundo TrazoMob ---

        self.cb_tipo_fundo = QComboBox()
        self.cb_tipo_fundo.addItems([
            tr("Canal / Rasgo"),
            tr("Sobreposto"),
            tr("Sem Fundo"),
        ])
        self.cb_tipo_fundo.currentIndexChanged.connect(self._on_tipo_fundo_changed)
        self.lbl_tipo_fundo = QLabel(tr("Fundo:"))
        self.sec_frentes.form_layout.addRow(self.lbl_tipo_fundo, self.cb_tipo_fundo)

        self.cb_esp_fundo = QComboBox()
        self.cb_esp_fundo.addItems(["6 mm", "3 mm", "15 mm"])
        self.lbl_esp_fundo = QLabel(tr("Esp. Fundo:"))
        self.sec_frentes.form_layout.addRow(self.lbl_esp_fundo, self.cb_esp_fundo)

        self.sp_recuo_fundo = QSpinBox()
        self.sp_recuo_fundo.setRange(0, 100)
        self.sp_recuo_fundo.setValue(15)
        self.sp_recuo_fundo.setSuffix(" mm")
        self.lbl_recuo_fundo = QLabel(tr("Recuo Fundo:"))
        self.sec_frentes.form_layout.addRow(self.lbl_recuo_fundo, self.sp_recuo_fundo)

        self.sp_prof_rasgo = QSpinBox()
        self.sp_prof_rasgo.setRange(1, 15)
        self.sp_prof_rasgo.setValue(7)
        self.sp_prof_rasgo.setSuffix(" mm")
        self.lbl_prof_rasgo = QLabel(tr("Rasgo:"))
        self.sec_frentes.form_layout.addRow(self.lbl_prof_rasgo, self.sp_prof_rasgo)

        self._fundo_sidebar_widgets = [
            self.lbl_tipo_fundo, self.cb_tipo_fundo,
            self.lbl_esp_fundo, self.cb_esp_fundo,
            self.lbl_recuo_fundo, self.sp_recuo_fundo,
            self.lbl_prof_rasgo, self.sp_prof_rasgo,
        ]



    def _on_tipo_fundo_changed(self) -> None:
        idx = self.cb_tipo_fundo.currentIndex()
        if idx == 0:  # Canal / Rasgo
            self.cb_esp_fundo.setEnabled(True)
            self.sp_recuo_fundo.setEnabled(True)
            self.sp_prof_rasgo.setEnabled(True)
        elif idx == 1:  # Sobreposto
            self.cb_esp_fundo.setEnabled(True)
            self.sp_recuo_fundo.setEnabled(False)
            self.sp_prof_rasgo.setEnabled(False)
        else:  # Sem Fundo
            self.cb_esp_fundo.setEnabled(False)
            self.sp_recuo_fundo.setEnabled(False)
            self.sp_prof_rasgo.setEnabled(False)


# Aliases
SidebarFrontsMixin = SidebarFrentesMixin


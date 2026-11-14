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
from ..domain.ui_contract import (
    DEFAULT_PROF_RASGO_MM,
    DEFAULT_RECUO_FUNDO_MM,
    should_show_lado_porta_armario,
)


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
        self.sp_qtd_elem = QSpinBox()
        self.sp_qtd_elem.setRange(0, 8)
        self.sp_qtd_elem.setValue(2)
        self.lbl_qtd_elem = QLabel(tr("Portas / Gavetas:"))
        self.sec_frentes.form_layout.addRow(self.lbl_qtd_elem, self.sp_qtd_elem)
        self.sp_qtd_elem.valueChanged.connect(self._on_qtd_elem_changed_update_lado_porta)

        self.cb_lado_porta_armario = QComboBox()
        self.cb_lado_porta_armario.addItems([
            tr("⬅️ Dobradiça à Esquerda (Padrão)"),
            tr("➡️ Dobradiça à Direita (Invertido)"),
        ])
        self.cb_lado_porta_armario.setToolTip(
            "Define o lado da dobradiça na porta única (1 porta) ou na porta isolada (em módulos ímpares, ex: 3 portas), "
            "ou inverte o lado do montante cego em balcões de canto"
        )
        self.lbl_lado_porta_armario = QLabel(tr("Lado Porta Única/Isolada:"))
        self.sec_frentes.form_layout.addRow(self.lbl_lado_porta_armario, self.cb_lado_porta_armario)
        self.lbl_lado_porta_armario.setVisible(False)
        self.cb_lado_porta_armario.setVisible(False)

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
        self.sp_recuo_fundo.setValue(int(DEFAULT_RECUO_FUNDO_MM))
        self.sp_recuo_fundo.setSuffix(" mm")
        self.lbl_recuo_fundo = QLabel(tr("Recuo Fundo:"))
        self.sec_frentes.form_layout.addRow(self.lbl_recuo_fundo, self.sp_recuo_fundo)

        self.sp_prof_rasgo = QSpinBox()
        self.sp_prof_rasgo.setRange(1, 15)
        self.sp_prof_rasgo.setValue(int(DEFAULT_PROF_RASGO_MM))
        self.sp_prof_rasgo.setSuffix(" mm")
        self.lbl_prof_rasgo = QLabel(tr("Rasgo:"))
        self.sec_frentes.form_layout.addRow(self.lbl_prof_rasgo, self.sp_prof_rasgo)

        self._fundo_sidebar_widgets = [
            self.lbl_tipo_fundo, self.cb_tipo_fundo,
            self.lbl_esp_fundo, self.cb_esp_fundo,
            self.lbl_recuo_fundo, self.sp_recuo_fundo,
            self.lbl_prof_rasgo, self.sp_prof_rasgo,
        ]

        # --- Travessas Superiores (Geometria — exclusivas para Cozinha Inferiores) ---
        self.lbl_travessa_section = QLabel(tr("<b>🔩 Travessas Superiores:</b>"))
        self.sec_frentes.form_layout.addRow(self.lbl_travessa_section)

        self.sp_larg_travessa_frontal = QSpinBox()
        self.sp_larg_travessa_frontal.setRange(20, 300)
        self.sp_larg_travessa_frontal.setValue(70)
        self.sp_larg_travessa_frontal.setSuffix(" mm")
        self.sp_larg_travessa_frontal.setToolTip(tr("Largura (profundidade) da travessa frontal superior"))
        self.lbl_larg_trav_frontal = QLabel(tr("Frontal (larg.):"))
        self.sec_frentes.form_layout.addRow(self.lbl_larg_trav_frontal, self.sp_larg_travessa_frontal)

        self.sp_larg_travessa_traseira = QSpinBox()
        self.sp_larg_travessa_traseira.setRange(20, 300)
        self.sp_larg_travessa_traseira.setValue(70)
        self.sp_larg_travessa_traseira.setSuffix(" mm")
        self.sp_larg_travessa_traseira.setToolTip(tr("Largura (profundidade) da travessa traseira superior"))
        self.lbl_larg_trav_traseira = QLabel(tr("Traseira (larg.):"))
        self.sec_frentes.form_layout.addRow(self.lbl_larg_trav_traseira, self.sp_larg_travessa_traseira)

        self.chk_travessa_frontal_em_pe = QCheckBox(tr("Frontal em pé (vertical)"))
        self.chk_travessa_frontal_em_pe.setChecked(False)
        self.chk_travessa_frontal_em_pe.setToolTip(
            tr(
                "Ativado: travessa frontal fica em pé (vertical).\n"
                "Desativado: travessa deitada (horizontal)."
            )
        )
        self.lbl_trav_frontal_pe = QLabel(tr("Orient. Frontal:"))
        self.sec_frentes.form_layout.addRow(self.lbl_trav_frontal_pe, self.chk_travessa_frontal_em_pe)

        self.chk_travessa_traseira_em_pe = QCheckBox(tr("Traseira em pé (vertical)"))
        self.chk_travessa_traseira_em_pe.setChecked(False)
        self.chk_travessa_traseira_em_pe.setToolTip(
            tr(
                "Ativado: travessa traseira fica em pé (vertical).\n"
                "Desativado: travessa deitada (horizontal)."
            )
        )
        self.lbl_trav_traseira_pe = QLabel(tr("Orient. Traseira:"))
        self.sec_frentes.form_layout.addRow(self.lbl_trav_traseira_pe, self.chk_travessa_traseira_em_pe)

        self.sp_recuo_porta_topo = QSpinBox()
        self.sp_recuo_porta_topo.setRange(0, 200)
        self.sp_recuo_porta_topo.setValue(50)
        self.sp_recuo_porta_topo.setSuffix(" mm")
        self.sp_recuo_porta_topo.setToolTip(
            tr(
                "Rebaixo do topo das portas quando a travessa frontal está em pé.\n"
                "Padrão: 50 mm."
            )
        )
        self.lbl_recuo_porta_topo = QLabel(tr("Rebaixo Portas:"))
        self.sec_frentes.form_layout.addRow(self.lbl_recuo_porta_topo, self.sp_recuo_porta_topo)

        self._travessa_estrutura_widgets = [
            self.lbl_travessa_section,
            self.lbl_larg_trav_frontal, self.sp_larg_travessa_frontal,
            self.lbl_larg_trav_traseira, self.sp_larg_travessa_traseira,
            self.lbl_trav_frontal_pe, self.chk_travessa_frontal_em_pe,
            self.lbl_trav_traseira_pe, self.chk_travessa_traseira_em_pe,
            self.lbl_recuo_porta_topo, self.sp_recuo_porta_topo,
        ]
        for w in self._travessa_estrutura_widgets:
            w.setVisible(False)

        self.chk_travessa_frontal_em_pe.stateChanged.connect(self._on_travessa_frontal_em_pe_changed)
        self.chk_travessa_traseira_em_pe.stateChanged.connect(self._on_travessa_traseira_em_pe_changed)

    def _on_qtd_elem_changed_update_lado_porta(self, num_portas: int) -> None:
        """Atualiza a visibilidade de Lado da Porta Única/Isolada conforme quantidade de portas."""
        if not hasattr(self, "cb_lado_porta_armario"):
            return
        tipo = getattr(self, "_current_selected_tipo", "")
        has_porta_arm = getattr(self, "_current_has_porta_arm", False)
        vis = should_show_lado_porta_armario(tipo, has_porta_arm, int(num_portas))
        self.lbl_lado_porta_armario.setVisible(vis)
        self.cb_lado_porta_armario.setVisible(vis)

    def _on_travessa_frontal_em_pe_changed(self, *_args) -> None:
        """Exibe Rebaixo Portas apenas quando módulo tem travessas e a frontal está em pé."""
        has_trav = getattr(self, "_current_has_travessa", False)
        em_pe = self.chk_travessa_frontal_em_pe.isChecked()
        vis = bool(has_trav and em_pe)
        self.lbl_recuo_porta_topo.setVisible(vis)
        self.sp_recuo_porta_topo.setVisible(vis)

    def _get_espessura_travessa_traseira_mm(self) -> int:
        """Retorna a espessura efetiva da travessa traseira em milímetros."""
        try:
            if hasattr(self, "cb_espessura_travessas"):
                txt_tr = self.cb_espessura_travessas.currentText()
                if "mm" in txt_tr.lower():
                    return int(round(float(txt_tr.split()[0])))
            if hasattr(self, "cb_espessura"):
                txt_cx = self.cb_espessura.currentText()
                if "mm" in txt_cx.lower():
                    return int(round(float(txt_cx.split()[0])))
        except (ValueError, IndexError):
            pass
        return 15

    def _sync_recuo_fundo_state(self) -> None:
        """Sincroniza habilitação e valor de sp_recuo_fundo com tipo de fundo e travessa traseira em pé."""
        idx = self.cb_tipo_fundo.currentIndex()
        has_trav = getattr(self, "_current_has_travessa", False)
        trav_traseira_pe = (
            has_trav
            and hasattr(self, "chk_travessa_traseira_em_pe")
            and self.chk_travessa_traseira_em_pe.isChecked()
        )
        if idx == 0:  # Canal / Rasgo
            self.cb_esp_fundo.setEnabled(True)
            self.sp_prof_rasgo.setEnabled(True)
            if trav_traseira_pe:
                if not getattr(self, "_recuo_fundo_locked_by_travessa", False):
                    self._recuo_fundo_before_travessa_lock = self.sp_recuo_fundo.value()
                esp_trav = self._get_espessura_travessa_traseira_mm()
                self.sp_recuo_fundo.blockSignals(True)
                self.sp_recuo_fundo.setValue(esp_trav)
                self.sp_recuo_fundo.blockSignals(False)
                self.sp_recuo_fundo.setEnabled(False)
                self._recuo_fundo_locked_by_travessa = True
            else:
                if getattr(self, "_recuo_fundo_locked_by_travessa", False):
                    prev = getattr(self, "_recuo_fundo_before_travessa_lock", int(DEFAULT_RECUO_FUNDO_MM))
                    self.sp_recuo_fundo.blockSignals(True)
                    self.sp_recuo_fundo.setValue(int(prev))
                    self.sp_recuo_fundo.blockSignals(False)
                    self._recuo_fundo_locked_by_travessa = False
                self.sp_recuo_fundo.setEnabled(True)
        elif idx == 1:  # Sobreposto
            self.cb_esp_fundo.setEnabled(True)
            self.sp_recuo_fundo.setEnabled(False)
            self.sp_prof_rasgo.setEnabled(False)
            self._recuo_fundo_locked_by_travessa = False
        else:  # Sem Fundo
            self.cb_esp_fundo.setEnabled(False)
            self.sp_recuo_fundo.setEnabled(False)
            self.sp_prof_rasgo.setEnabled(False)
            self._recuo_fundo_locked_by_travessa = False

    def _on_travessa_traseira_em_pe_changed(self, *_args) -> None:
        self._sync_recuo_fundo_state()

    def _on_tipo_fundo_changed(self) -> None:
        self._sync_recuo_fundo_state()


# Aliases
SidebarFrontsMixin = SidebarFrentesMixin


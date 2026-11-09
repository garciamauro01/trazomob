# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Montagem da aba Ajustes Especiais da barra lateral."""
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

from ..domain.materials_catalog import MDF_MATERIALS


class SidebarAjustesMixin:
    """Cria as secoes especiais de ajustes adicionais na aba Avancado."""

    def _build_ajustes_section(self) -> None:
        """Monta as secoes especiais de ajustes."""
        # --- Travessas Superiores (Cozinha Inferiores) ---
        self.lbl_travessa_section = QLabel("<b>🔩 Travessas Superiores:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_travessa_section)

        self.sp_larg_travessa_frontal = QSpinBox()
        self.sp_larg_travessa_frontal.setRange(20, 300)
        self.sp_larg_travessa_frontal.setValue(70)
        self.sp_larg_travessa_frontal.setSuffix(" mm")
        self.sp_larg_travessa_frontal.setToolTip("Largura (profundidade) da travessa frontal superior")
        self.lbl_larg_trav_frontal = QLabel("Frontal (larg.):")
        self.sec_ajustes.form_layout.addRow(self.lbl_larg_trav_frontal, self.sp_larg_travessa_frontal)

        self.sp_larg_travessa_traseira = QSpinBox()
        self.sp_larg_travessa_traseira.setRange(20, 300)
        self.sp_larg_travessa_traseira.setValue(70)
        self.sp_larg_travessa_traseira.setSuffix(" mm")
        self.sp_larg_travessa_traseira.setToolTip("Largura (profundidade) da travessa traseira superior")
        self.lbl_larg_trav_traseira = QLabel("Traseira (larg.):")
        self.sec_ajustes.form_layout.addRow(self.lbl_larg_trav_traseira, self.sp_larg_travessa_traseira)

        self.chk_travessa_frontal_em_pe = QCheckBox("Frontal em pé (vertical)")
        self.chk_travessa_frontal_em_pe.setChecked(False)
        self.chk_travessa_frontal_em_pe.setToolTip(
            "Ativado: travessa frontal fica em pé (vertical).\n"
            "Desativado: travessa deitada (horizontal)."
        )
        self.lbl_trav_frontal_pe = QLabel("Orient. Frontal:")
        self.sec_ajustes.form_layout.addRow(self.lbl_trav_frontal_pe, self.chk_travessa_frontal_em_pe)

        self.chk_travessa_traseira_em_pe = QCheckBox("Traseira em pé (vertical)")
        self.chk_travessa_traseira_em_pe.setChecked(False)
        self.chk_travessa_traseira_em_pe.setToolTip(
            "Ativado: travessa traseira fica em pé (vertical).\n"
            "Desativado: travessa deitada (horizontal)."
        )
        self.lbl_trav_traseira_pe = QLabel("Orient. Traseira:")
        self.sec_ajustes.form_layout.addRow(self.lbl_trav_traseira_pe, self.chk_travessa_traseira_em_pe)

        self.sp_recuo_porta_topo = QSpinBox()
        self.sp_recuo_porta_topo.setRange(0, 200)
        self.sp_recuo_porta_topo.setValue(50)
        self.sp_recuo_porta_topo.setSuffix(" mm")
        self.sp_recuo_porta_topo.setToolTip(
            "Rebaixo do topo das portas quando a travessa frontal está em pé.\n"
            "Padrão: 50 mm."
        )
        self.lbl_recuo_porta_topo = QLabel("Rebaixo Portas:")
        self.sec_ajustes.form_layout.addRow(self.lbl_recuo_porta_topo, self.sp_recuo_porta_topo)

        # Padrão e Espessura das Travessas
        self.cb_material_travessas = QComboBox()
        self.cb_material_travessas.addItems(["(Mesmo da Caixa)"] + MDF_MATERIALS)
        self.lbl_material_travessas = QLabel("Padrão Trav.:")
        self.sec_ajustes.form_layout.addRow(self.lbl_material_travessas, self.cb_material_travessas)

        self.cb_espessura_travessas = QComboBox()
        self.cb_espessura_travessas.addItems([
            "(Mesma da Caixa)",
            "15 mm",
            "18 mm",
            "25 mm",
        ])
        self.lbl_espessura_travessas = QLabel("Esp. Trav.:")
        self.sec_ajustes.form_layout.addRow(self.lbl_espessura_travessas, self.cb_espessura_travessas)

        # Fita de borda das travessas
        self.cb_fita_travessas = QComboBox()
        self.cb_fita_travessas.addItems([
            "Frontal 1L (Bordo Aparente)",
            "2L (2 Bordos Longos)",
            "4L (Todos os 4 Bordos)",
            "Sem Fita de Borda",
        ])
        self.lbl_fita_travessas = QLabel("Fita Trav.:")
        self.sec_ajustes.form_layout.addRow(self.lbl_fita_travessas, self.cb_fita_travessas)

        self.cb_material_fita_travessas = QComboBox()
        self.cb_material_fita_travessas.addItems(["(Mesmo da Travessa)"] + MDF_MATERIALS)
        self.lbl_material_fita_travessas = QLabel("Padrão Fita Tr.:")
        self.sec_ajustes.form_layout.addRow(self.lbl_material_fita_travessas, self.cb_material_fita_travessas)

        # Botão para troca/padronização de travessas em lote em todos os balcões da cena
        self.btn_aplicar_travessas_todos = QPushButton("🔄 Aplicar Travessas em Todos os Balcões")
        self.btn_aplicar_travessas_todos.setToolTip("Aplica a orientação (em pé/deitada), largura e materiais de travessa selecionados a todos os balcões inferiores da cena")
        self.btn_aplicar_travessas_todos.setStyleSheet(
            "QPushButton { background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px; padding: 5px; font-weight: bold; color: #334155; }"
            "QPushButton:hover { background-color: #E2E8F0; color: #0F172A; border-color: #94A3B8; }"
        )
        self.btn_aplicar_travessas_todos.clicked.connect(self._on_apply_travessas_to_all_modules)
        self.sec_ajustes.form_layout.addRow(self.btn_aplicar_travessas_todos)

        # Lista dos widgets de travessa para controle de visibilidade
        self._travessa_sidebar_widgets = [
            self.lbl_travessa_section,
            self.lbl_larg_trav_frontal, self.sp_larg_travessa_frontal,
            self.lbl_larg_trav_traseira, self.sp_larg_travessa_traseira,
            self.lbl_trav_frontal_pe, self.chk_travessa_frontal_em_pe,
            self.lbl_trav_traseira_pe, self.chk_travessa_traseira_em_pe,
            self.lbl_recuo_porta_topo, self.sp_recuo_porta_topo,
            self.lbl_material_travessas, self.cb_material_travessas,
            self.lbl_espessura_travessas, self.cb_espessura_travessas,
            self.lbl_fita_travessas, self.cb_fita_travessas,
            self.lbl_material_fita_travessas, self.cb_material_fita_travessas,
            self.btn_aplicar_travessas_todos,
        ]
        for w in self._travessa_sidebar_widgets:
            w.setVisible(False)

        # Mostrar/esconder rebaixo conforme travessa frontal em pé
        def _on_sb_trav_frontal_changed(state):
            em_pe = self.chk_travessa_frontal_em_pe.isChecked()
            self.lbl_recuo_porta_topo.setVisible(em_pe)
            self.sp_recuo_porta_topo.setVisible(em_pe)
        self.chk_travessa_frontal_em_pe.stateChanged.connect(_on_sb_trav_frontal_changed)

        # ── Configurações de Forno (balcao_forno) na Barra Lateral ───────────
        self.lbl_forno_section = QLabel("<b>🔥 Balcão para Forno Embutido:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_forno_section)

        self.chk_forno_tem_gaveta = QCheckBox("Possui Gaveta Inferior")
        self.chk_forno_tem_gaveta.setChecked(True)
        self.lbl_forno_tem_gaveta = QLabel("Gaveta Inferior:")
        self.sec_ajustes.form_layout.addRow(self.lbl_forno_tem_gaveta, self.chk_forno_tem_gaveta)

        self.sp_forno_alt_gaveta = QSpinBox()
        self.sp_forno_alt_gaveta.setRange(80, 500)
        self.sp_forno_alt_gaveta.setValue(150)
        self.sp_forno_alt_gaveta.setSuffix(" mm")
        self.lbl_forno_alt_gaveta = QLabel("Altura da Gaveta:")
        self.sec_ajustes.form_layout.addRow(self.lbl_forno_alt_gaveta, self.sp_forno_alt_gaveta)

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

        # ── Configurações de Geladeira (caixa_geladeira) na Barra Lateral ─────
        self.lbl_geladeira_section = QLabel("<b>❄️ Nicho de Geladeira & Maleiro:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_geladeira_section)

        self.sp_geladeira_alt_nicho = QSpinBox()
        self.sp_geladeira_alt_nicho.setRange(1200, 2400)
        self.sp_geladeira_alt_nicho.setValue(1800)
        self.sp_geladeira_alt_nicho.setSuffix(" mm")
        self.lbl_geladeira_alt_nicho = QLabel("Altura Vão Geladeira:")
        self.sec_ajustes.form_layout.addRow(self.lbl_geladeira_alt_nicho, self.sp_geladeira_alt_nicho)

        self.cb_geladeira_tipo_porta = QComboBox()
        self.cb_geladeira_tipo_porta.addItems([
            "2 Portas de Abrir",
            "1 Porta Basculante",
        ])
        self.lbl_geladeira_tipo_porta = QLabel("Portas do Maleiro:")
        self.sec_ajustes.form_layout.addRow(self.lbl_geladeira_tipo_porta, self.cb_geladeira_tipo_porta)

        self._geladeira_sidebar_widgets = [
            self.lbl_geladeira_section,
            self.lbl_geladeira_alt_nicho, self.sp_geladeira_alt_nicho,
            self.lbl_geladeira_tipo_porta, self.cb_geladeira_tipo_porta,
        ]
        for w in self._geladeira_sidebar_widgets:
            w.setVisible(False)

        # ── Configurações de Aéreo Micro-ondas na Barra Lateral ──────────────────
        self.lbl_micro_section = QLabel("<b>🚪 Portas do Micro-ondas:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_micro_section)

        self.cb_micro_tipo_porta = QComboBox()
        self.cb_micro_tipo_porta.addItems([
            "1 Porta Basculante",
            "2 Portas de Abrir",
        ])
        self.lbl_micro_tipo_porta = QLabel("Tipo de Porta:")
        self.sec_ajustes.form_layout.addRow(self.lbl_micro_tipo_porta, self.cb_micro_tipo_porta)

        self._micro_sidebar_widgets = [
            self.lbl_micro_section,
            self.lbl_micro_tipo_porta, self.cb_micro_tipo_porta,
        ]
        for w in self._micro_sidebar_widgets:
            w.setVisible(False)

        # ── Configurações de Caixa de Gaveta na Barra Lateral ──────────────────
        self.lbl_gaveta_section = QLabel("<b>⚙️ Caixa de Gaveta:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_gaveta_section)

        self.cb_tipo_fundo_gaveta = QComboBox()
        self.cb_tipo_fundo_gaveta.addItems([
            "Canal / Rasgo Lateral",
            "Por Baixo (Sobreposto)",
        ])
        self.lbl_tipo_fundo_gaveta = QLabel("Montagem Fundo:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tipo_fundo_gaveta, self.cb_tipo_fundo_gaveta)

        self.sp_folga_corredica = QSpinBox()
        self.sp_folga_corredica.setRange(10, 50)
        self.sp_folga_corredica.setValue(26)
        self.sp_folga_corredica.setSuffix(" mm")
        self.sp_folga_corredica.setToolTip("Folga total a descontar da largura para corrediças (ex.: 26mm)")
        self.lbl_folga_corredica = QLabel("Folga Corrediças:")
        self.sec_ajustes.form_layout.addRow(self.lbl_folga_corredica, self.sp_folga_corredica)

        self.cb_material_gaveta = QComboBox()
        self.cb_material_gaveta.addItems(["(Mesmo da Caixa)"] + MDF_MATERIALS)
        self.lbl_material_gaveta = QLabel("Material Gaveta:")
        self.sec_ajustes.form_layout.addRow(self.lbl_material_gaveta, self.cb_material_gaveta)

        self.cb_espessura_gaveta = QComboBox()
        self.cb_espessura_gaveta.addItems([
            "15 mm",
            "18 mm",
        ])
        self.lbl_espessura_gaveta = QLabel("Espessura Gaveta:")
        self.sec_ajustes.form_layout.addRow(self.lbl_espessura_gaveta, self.cb_espessura_gaveta)

        self.cb_material_fita_gaveta = QComboBox()
        self.cb_material_fita_gaveta.addItems(["(Mesmo da Gaveta)"] + MDF_MATERIALS)
        self.lbl_material_fita_gaveta = QLabel("Fita Borda Gav.:")
        self.sec_ajustes.form_layout.addRow(self.lbl_material_fita_gaveta, self.cb_material_fita_gaveta)

        self.cb_material_fundo_gaveta = QComboBox()
        self.cb_material_fundo_gaveta.addItems(["(Padrão Fundo)"] + MDF_MATERIALS)
        self.lbl_material_fundo_gaveta = QLabel("Material Fundo Gav.:")
        self.sec_ajustes.form_layout.addRow(self.lbl_material_fundo_gaveta, self.cb_material_fundo_gaveta)

        self.cb_esp_fundo_gaveta = QComboBox()
        self.cb_esp_fundo_gaveta.addItems([
            "6 mm",
            "3 mm",
            "15 mm",
        ])
        self.lbl_esp_fundo_gaveta = QLabel("Esp. Fundo Gav.:")
        self.sec_ajustes.form_layout.addRow(self.lbl_esp_fundo_gaveta, self.cb_esp_fundo_gaveta)

        self._gaveta_sidebar_widgets = [
            self.lbl_gaveta_section,
            self.lbl_tipo_fundo_gaveta, self.cb_tipo_fundo_gaveta,
            self.lbl_folga_corredica, self.sp_folga_corredica,
            self.lbl_material_gaveta, self.cb_material_gaveta,
            self.lbl_espessura_gaveta, self.cb_espessura_gaveta,
            self.lbl_material_fita_gaveta, self.cb_material_fita_gaveta,
            self.lbl_material_fundo_gaveta, self.cb_material_fundo_gaveta,
            self.lbl_esp_fundo_gaveta, self.cb_esp_fundo_gaveta,
        ]

        # ── Configurações de Marmoraria / Bancadas de Pedra ────────────────────
        self.lbl_pedra_section = QLabel("<b>🪨 Marmoraria & Bancada:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_pedra_section)

        self.sp_esp_pedra = QSpinBox()
        self.sp_esp_pedra.setRange(10, 60)
        self.sp_esp_pedra.setValue(20)
        self.sp_esp_pedra.setSuffix(" mm")
        self.sp_esp_pedra.setToolTip("Espessura da chapa de pedra (padrão: 20mm)")
        self.lbl_esp_pedra = QLabel("Espessura Pedra:")
        self.sec_ajustes.form_layout.addRow(self.lbl_esp_pedra, self.sp_esp_pedra)

        self.sp_altura_saia = QSpinBox()
        self.sp_altura_saia.setRange(20, 200)
        self.sp_altura_saia.setValue(40)
        self.sp_altura_saia.setSuffix(" mm")
        self.sp_altura_saia.setToolTip("Altura da saia/testeira engrossada frontal (padrão: 40mm ou 60mm)")
        self.lbl_altura_saia = QLabel("Altura Saia / Testeira:")
        self.sec_ajustes.form_layout.addRow(self.lbl_altura_saia, self.sp_altura_saia)

        self.sp_altura_frontao = QSpinBox()
        self.sp_altura_frontao.setRange(0, 300)
        self.sp_altura_frontao.setValue(100)
        self.sp_altura_frontao.setSuffix(" mm")
        self.sp_altura_frontao.setToolTip("Altura do rodabanca/frontão na parede (padrão: 100mm)")
        self.lbl_altura_frontao = QLabel("Rodabanca / Frontão:")
        self.sec_ajustes.form_layout.addRow(self.lbl_altura_frontao, self.sp_altura_frontao)

        self.chk_tem_saia_esq = QCheckBox("Saia Lateral Esquerda")
        self.chk_tem_saia_esq.setChecked(True)
        self.lbl_tem_saia_esq = QLabel("Saia Esquerda:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tem_saia_esq, self.chk_tem_saia_esq)

        self.chk_tem_saia_dir = QCheckBox("Saia Lateral Direita")
        self.chk_tem_saia_dir.setChecked(True)
        self.lbl_tem_saia_dir = QLabel("Saia Direita:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tem_saia_dir, self.chk_tem_saia_dir)

        self.cb_tipo_cuba = QComboBox()
        self.cb_tipo_cuba.addItems([
            "Cuba Inox Simples",
            "Cuba Inox Dupla",
            "Cuba Esculpida na Pedra",
            "Sem Cuba (Tampo Cego)",
        ])
        self.lbl_tipo_cuba = QLabel("Modelo Cuba:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tipo_cuba, self.cb_tipo_cuba)

        self.cb_posicao_cuba = QComboBox()
        self.cb_posicao_cuba.addItems([
            "🎯 Centralizada",
            "⬅️ À Esquerda",
            "➡️ À Direita",
        ])
        self.lbl_posicao_cuba = QLabel("Posição Cuba:")
        self.sec_ajustes.form_layout.addRow(self.lbl_posicao_cuba, self.cb_posicao_cuba)

        self.chk_tem_torneira = QCheckBox("Incluir Torneira Gourmet")
        self.chk_tem_torneira.setChecked(True)
        self.lbl_tem_torneira = QLabel("Torneira:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tem_torneira, self.chk_tem_torneira)

        self.cb_canto_recorte = QComboBox()
        self.cb_canto_recorte.addItems(["Cantos Arredondados (R20)", "Cantos Retos 90°"])
        self.lbl_canto_recorte = QLabel("Recorte Cuba:")
        self.sec_ajustes.form_layout.addRow(self.lbl_canto_recorte, self.cb_canto_recorte)

        self.chk_tem_area_molhada = QCheckBox("Área Molhada Rebaixada")
        self.chk_tem_area_molhada.setChecked(True)
        self.lbl_tem_area_molhada = QLabel("Área Molhada:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tem_area_molhada, self.chk_tem_area_molhada)

        self._pedra_sidebar_widgets = [
            self.lbl_pedra_section,
            self.lbl_esp_pedra, self.sp_esp_pedra,
            self.lbl_altura_saia, self.sp_altura_saia,
            self.lbl_altura_frontao, self.sp_altura_frontao,
            self.lbl_tem_saia_esq, self.chk_tem_saia_esq,
            self.lbl_tem_saia_dir, self.chk_tem_saia_dir,
            self.lbl_tipo_cuba, self.cb_tipo_cuba,
            self.lbl_posicao_cuba, self.cb_posicao_cuba,
            self.lbl_tem_torneira, self.chk_tem_torneira,
            self.lbl_canto_recorte, self.cb_canto_recorte,
            self.lbl_tem_area_molhada, self.chk_tem_area_molhada,
        ]
        for w in self._pedra_sidebar_widgets:
            w.setVisible(False)

        # ── Configurações de Tampo Engrossado (peca_tampo_engrossado) ─────────
        self.lbl_tampo_section = QLabel("<b>🪵 Configurações do Tampo:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_tampo_section)

        self.cb_tampo_esp_chapa = QComboBox()
        self.cb_tampo_esp_chapa.addItems(["18 mm", "15 mm", "25 mm"])
        self.lbl_tampo_esp_chapa = QLabel("Espessura Chapa:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tampo_esp_chapa, self.cb_tampo_esp_chapa)

        self.sp_tampo_qtd_engrosso = QSpinBox()
        self.sp_tampo_qtd_engrosso.setRange(1, 6)
        self.sp_tampo_qtd_engrosso.setValue(1)
        self.sp_tampo_qtd_engrosso.setSuffix(" camada(s)")
        self.sp_tampo_qtd_engrosso.setToolTip("Quantidade de réguas/camadas empilhadas no engrosso inferior (1 camada = chapa dupla, 2 camadas = chapa tripla, etc.)")
        self.lbl_tampo_qtd_engrosso = QLabel("Fatias Engrosso:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tampo_qtd_engrosso, self.sp_tampo_qtd_engrosso)

        self.sp_tampo_larg_engrosso = QSpinBox()
        self.sp_tampo_larg_engrosso.setRange(30, 200)
        self.sp_tampo_larg_engrosso.setValue(70)
        self.sp_tampo_larg_engrosso.setSuffix(" mm")
        self.sp_tampo_larg_engrosso.setToolTip("Largura das réguas perimetrais inferiores de engrosso (padrão: 70mm)")
        self.lbl_tampo_larg_engrosso = QLabel("Largura Réguas:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tampo_larg_engrosso, self.sp_tampo_larg_engrosso)

        self.cb_tampo_tipo_engrosso = QComboBox()
        self.cb_tampo_tipo_engrosso.addItems([
            "Frontal e Laterais (3 Lados)",
            "Perímetro Completo (4 Lados / Ilha)",
            "Apenas Frontal (1 Lado)",
        ])
        self.lbl_tampo_tipo_engrosso = QLabel("Lados Engrosso:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tampo_tipo_engrosso, self.cb_tampo_tipo_engrosso)

        self.chk_tampo_fechar_embaixo = QCheckBox("Fechar com chapa inferior")
        self.chk_tampo_fechar_embaixo.setChecked(False)
        self.chk_tampo_fechar_embaixo.setToolTip("Adiciona uma chapa inteiriça inferior de acabamento por baixo das réguas (tampo tipo sanduíche/tamburato)")
        self.lbl_tampo_fechar_embaixo = QLabel("Fundo do Tampo:")
        self.sec_ajustes.form_layout.addRow(self.lbl_tampo_fechar_embaixo, self.chk_tampo_fechar_embaixo)

        # Atualiza a altura total aparente no sp_altura ao mudar espessura, camadas ou fechamento
        def _recalc_tampo_height():
            if getattr(self, "_current_selected_tipo", "") in ("peca_tampo_engrossado", "tampo_engrossado"):
                try:
                    e_ch = float(self.cb_tampo_esp_chapa.currentText().split()[0])
                except Exception:
                    e_ch = 18.0
                n_cam = self.sp_tampo_qtd_engrosso.value()
                tem_fech = self.chk_tampo_fechar_embaixo.isChecked()
                total_h = e_ch * (1 + n_cam + (1 if tem_fech else 0))
                self.sp_altura.setValue(int(round(total_h)))

        self.cb_tampo_esp_chapa.currentIndexChanged.connect(_recalc_tampo_height)
        self.sp_tampo_qtd_engrosso.valueChanged.connect(_recalc_tampo_height)
        self.chk_tampo_fechar_embaixo.toggled.connect(_recalc_tampo_height)

        self._tampo_sidebar_widgets = [
            self.lbl_tampo_section,
            self.lbl_tampo_esp_chapa, self.cb_tampo_esp_chapa,
            self.lbl_tampo_qtd_engrosso, self.sp_tampo_qtd_engrosso,
            self.lbl_tampo_larg_engrosso, self.sp_tampo_larg_engrosso,
            self.lbl_tampo_tipo_engrosso, self.cb_tampo_tipo_engrosso,
            self.lbl_tampo_fechar_embaixo, self.chk_tampo_fechar_embaixo,
        ]
        for w in self._tampo_sidebar_widgets:
            w.setVisible(False)

        self.chk_gerar_furacao = QCheckBox("Gerar furações e usinagens")
        self.chk_gerar_furacao.setChecked(True)
        self.chk_gerar_furacao.setToolTip("Gera furações de dobradiças, corrediças e canais para este módulo")
        self.lbl_furacao = QLabel("Furação:")
        self.sec_ajustes.form_layout.addRow(self.lbl_furacao, self.chk_gerar_furacao)

        self.cb_dispositivo_fixacao = QComboBox()
        self.cb_dispositivo_fixacao.addItems([
            "Minifix + Cavilha",
            "Cavilha + Parafuso",
            "Apenas Parafuso",
            "Apenas Cavilhas",
        ])
        self.cb_dispositivo_fixacao.setToolTip("Dispositivo de junção da caixa (Minifix / Cavilha / Parafuso)")
        self.lbl_dispositivo_fixacao = QLabel("Fixação Caixa:")
        self.sec_ajustes.form_layout.addRow(self.lbl_dispositivo_fixacao, self.cb_dispositivo_fixacao)

        self.cb_dispositivo_prateleira = QComboBox()
        self.cb_dispositivo_prateleira.addItems([
            "Cavilhas de Topo (Ø8mm)",
            "Conector Häfele VB 35 (Ø20mm)",
            "Conector Häfele VB 36 com Aba (Ø20mm)",
        ])
        self.cb_dispositivo_prateleira.setToolTip("Dispositivo de fixação de prateleiras internas (Cavilha / VB 35 / VB 36)")
        self.lbl_dispositivo_prateleira = QLabel("Fixação Prateleira:")
        self.sec_ajustes.form_layout.addRow(self.lbl_dispositivo_prateleira, self.cb_dispositivo_prateleira)

        # ── Configurações de Cavilha em Divisória Vertical (peca_divisoria_vertical) ──
        self.lbl_divisoria_section = QLabel("<b>🔩 Cavilhas da Divisória:</b>")
        self.sec_ajustes.form_layout.addRow(self.lbl_divisoria_section)

        self.cb_cavilhas_divisoria = QComboBox()
        self.cb_cavilhas_divisoria.addItems([
            "Em Cima e Embaixo (Ambos)",
            "Apenas Em Cima (Topo Superior)",
            "Apenas Embaixo (Base Inferior)",
            "Sem Furação (Nenhum)",
        ])
        self.cb_cavilhas_divisoria.setToolTip("Configura a presença de furos para cavilhas no topo superior e/ou base inferior da divisória")
        self.lbl_cavilhas_divisoria = QLabel("Posição Cavilhas:")
        self.sec_ajustes.form_layout.addRow(self.lbl_cavilhas_divisoria, self.cb_cavilhas_divisoria)

        self._divisoria_sidebar_widgets = [
            self.lbl_divisoria_section,
            self.lbl_cavilhas_divisoria,
            self.cb_cavilhas_divisoria,
        ]
        for w in self._divisoria_sidebar_widgets:
            w.setVisible(False)



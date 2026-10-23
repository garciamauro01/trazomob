# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Interface gráfica principal do TrazoMob (TrazoMobDialog)."""
from __future__ import annotations

import csv
import json
import math
from typing import Any

from PySide6.QtCore import QPoint, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPalette,
    QPen,
    QShortcut,
    QVector3D,
)
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.group import Group
from core.history import SnapshotImport
from core.mesh import Mesh

from .builder import CabinetBuilder, create_board_group
from .catalog import MODULE_CATALOG
from .cut_plan_viewer import CutPlanViewerDialog
from .export import export_trazomob_csv, export_trazomob_json, format_trazomob_text
from .icons import get_module_thumbnail, make_cut_plan_icon, make_perfil_diagram_pixmap
from .param_mapper import extract_ui_module_params, populate_ui_from_module
from .styles import get_theme_palette, get_dialog_stylesheet
from .interact import CabinetInteract, CabinetInteractTool
from .parts import extract_parts, group_similar_parts
from . import perfis as perfis_lib
from .perfis_editor import PerfilLibraryDialog, fill_profile_combo
from .module_aligner import ModuleAlignerMixin
from .dialog_cutlist_tab import CutListTabMixin
from .dialog_gallery import DialogGalleryMixin


class TrazoMobDialog(QDialog, ModuleAlignerMixin, CutListTabMixin, DialogGalleryMixin):
    """Janela principal com Biblioteca Paramétrica Dinâmica e Plano de Corte."""

    def __init__(self, viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.scene = viewport.scene
        # Transforma o diálogo em janela de primeira classe com Maximizar, Minimizar e redimensionamento nativo
        self.setWindowFlags(Qt.Window)
        self.setSizeGripEnabled(True)

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

    def _detect_selected_module(self):
        """Detecta se há um módulo paramétrico selecionado no viewport para edição dinâmica."""
        sel = list(getattr(self.scene, "selection", []))
        # 1. Checa diretamente na seleção
        for item in sel:
            if hasattr(item, "ext") and isinstance(item.ext, dict):
                if "trazomob_module" in item.ext or "corte_cloud_module" in item.ext or "hellomob_module" in item.ext:
                    from .migration import migrate_legacy_group
                    migrate_legacy_group(item)
                    self._editing_module = item
                    return
        # 2. Se o usuário selecionou uma peça interna do armário, sobe para o módulo mestre
        for g in getattr(self.scene, "groups", []):
            if hasattr(g, "ext") and isinstance(g.ext, dict):
                if "trazomob_module" in g.ext or "corte_cloud_module" in g.ext or "hellomob_module" in g.ext:
                    children = getattr(g, "children", [])
                    if any(child in sel for child in children):
                        from .migration import migrate_legacy_group
                        migrate_legacy_group(g)
                        self._editing_module = g
                        return
        self._editing_module = None

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Módulos Paramétricos Dinâmicos
        tab_modules = QWidget()
        self._build_modules_tab(tab_modules)
        self.tabs.addTab(tab_modules, "🗂️ Módulos Dinâmicos (TrazoMob)")

        # Tab 2: Lista de Peças e TrazoMob
        tab_cutlist = QWidget()
        self._build_cutlist_tab(tab_cutlist)
        self.tabs.addTab(tab_cutlist, "📋 Lista de Peças & TrazoMob")

        footer = QHBoxLayout()
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.close)
        footer.addWidget(btn_close)
        footer.addStretch()
        main_layout.addLayout(footer)

        self._apply_dialog_styles()

    def _build_modules_tab(self, parent_widget):
        layout = QHBoxLayout(parent_widget)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(14)

        # -------------------------------------------------------------------
        # Painel Esquerdo: Galeria Visual de Módulos (Estilo TrazoMob)
        # -------------------------------------------------------------------
        gallery_box = QGroupBox("Catálogo de Módulos TrazoMob")
        v_gallery = QVBoxLayout(gallery_box)
        v_gallery.setContentsMargins(10, 12, 10, 10)
        v_gallery.setSpacing(10)

        # Cabeçalho da Galeria TrazoMob (Título + Filtro de Categoria)
        header_bar = QHBoxLayout()
        header_bar.setSpacing(10)

        self.lbl_cat_title = QLabel("Armários")
        header_bar.addWidget(self.lbl_cat_title)
        header_bar.addStretch()

        self.cb_category = QComboBox()
        self.cb_category.addItems(["Armários"] + [k for k in MODULE_CATALOG.keys() if k != "Armários"] + ["📂 Todas as Categorias"])
        self.cb_category.currentIndexChanged.connect(self._populate_module_cards)
        header_bar.addWidget(self.cb_category)

        v_gallery.addLayout(header_bar)

        # Barra de Busca Instantânea
        search_bar = QHBoxLayout()
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Filtrar módulos por nome...")
        self.txt_search.setClearButtonEnabled(True)
        self.txt_search.textChanged.connect(self._populate_module_cards)
        search_bar.addWidget(self.txt_search)
        v_gallery.addLayout(search_bar)

        # Banner azul TrazoMob
        self.banner = QLabel("clique sobre o módulo para inserir no projeto")
        self.banner.setAlignment(Qt.AlignCenter)
        v_gallery.addWidget(self.banner)

        # Grade / Grid Visual com Miniaturas dos Armários
        self.list_modules = QListWidget()
        self.list_modules.setViewMode(QListWidget.IconMode)
        self.list_modules.setIconSize(QSize(90, 90))
        self.list_modules.setGridSize(QSize(118, 132))
        self.list_modules.setResizeMode(QListWidget.Adjust)
        self.list_modules.setMovement(QListWidget.Static)
        self.list_modules.setWordWrap(True)
        self.list_modules.setSpacing(6)
        self.list_modules.currentItemChanged.connect(self._on_module_card_selected)
        self.list_modules.itemDoubleClicked.connect(lambda _: self._insert_or_update_module())
        v_gallery.addWidget(self.list_modules)

        layout.addWidget(gallery_box, stretch=3)

        # -------------------------------------------------------------------
        # Painel Direito: Configuração das Medidas e Ações (Fixo ~340px)
        # -------------------------------------------------------------------
        props_box = QGroupBox("Propriedades e Dimensões")
        props_box.setMinimumWidth(320)
        props_box.setMaximumWidth(400)
        v_props = QVBoxLayout(props_box)
        v_props.setContentsMargins(8, 8, 8, 8)
        v_props.setSpacing(6)

        # Card de Identificação do Módulo Selecionado
        self.card_info = QFrame()
        v_info = QVBoxLayout(self.card_info)
        v_info.setContentsMargins(6, 4, 6, 4)
        v_info.setSpacing(2)

        self.lbl_selected_title = QLabel("Selecione um Módulo")
        v_info.addWidget(self.lbl_selected_title)

        self.lbl_module_desc = QLabel()
        self.lbl_module_desc.setWordWrap(True)
        self.lbl_module_desc.setMaximumHeight(36)
        v_info.addWidget(self.lbl_module_desc)
        v_props.addWidget(self.card_info)

        # Status de Edição Dinâmica
        self.lbl_dyn_status = QLabel()
        self.lbl_dyn_status.setWordWrap(True)
        self.lbl_dyn_status.setStyleSheet("background-color: #E3F2FD; color: #0D47A1; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 11px;")
        v_props.addWidget(self.lbl_dyn_status)

        # Formulário de Medidas Dinâmicas com Ajustes Rápidos (+/- 50mm)
        scroll_form = QScrollArea()
        scroll_form.setWidgetResizable(True)
        scroll_form.setFrameShape(QFrame.NoFrame)
        scroll_form.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setContentsMargins(0, 2, 0, 2)
        form_layout.setSpacing(6)

        # Largura com botões rápidos
        h_larg = QHBoxLayout()
        self.sp_largura = QSpinBox()
        self.sp_largura.setRange(1, 3000)
        self.sp_largura.setValue(800)
        self.sp_largura.setSuffix(" mm")
        h_larg.addWidget(self.sp_largura)
        btn_l_minus = QPushButton("-50")
        btn_l_minus.setFixedWidth(38)
        btn_l_minus.clicked.connect(lambda: self.sp_largura.setValue(self.sp_largura.value() - 50))
        h_larg.addWidget(btn_l_minus)
        btn_l_plus = QPushButton("+50")
        btn_l_plus.setFixedWidth(38)
        btn_l_plus.clicked.connect(lambda: self.sp_largura.setValue(self.sp_largura.value() + 50))
        h_larg.addWidget(btn_l_plus)
        form_layout.addRow("Largura Total:", h_larg)

        # Altura com botões rápidos
        h_alt = QHBoxLayout()
        self.sp_altura = QSpinBox()
        self.sp_altura.setRange(1, 3000)
        self.sp_altura.setValue(720)
        self.sp_altura.setSuffix(" mm")
        h_alt.addWidget(self.sp_altura)
        btn_a_minus = QPushButton("-50")
        btn_a_minus.setFixedWidth(38)
        btn_a_minus.clicked.connect(lambda: self.sp_altura.setValue(self.sp_altura.value() - 50))
        h_alt.addWidget(btn_a_minus)
        btn_a_plus = QPushButton("+50")
        btn_a_plus.setFixedWidth(38)
        btn_a_plus.clicked.connect(lambda: self.sp_altura.setValue(self.sp_altura.value() + 50))
        h_alt.addWidget(btn_a_plus)
        form_layout.addRow("Altura Total:", h_alt)

        # Profundidade com botões rápidos
        h_prof = QHBoxLayout()
        self.sp_prof = QSpinBox()
        self.sp_prof.setRange(1, 2000)
        self.sp_prof.setValue(550)

        self.sp_prof.setSuffix(" mm")
        h_prof.addWidget(self.sp_prof)
        btn_p_minus = QPushButton("-50")
        btn_p_minus.setFixedWidth(38)
        btn_p_minus.clicked.connect(lambda: self.sp_prof.setValue(self.sp_prof.value() - 50))
        h_prof.addWidget(btn_p_minus)
        btn_p_plus = QPushButton("+50")
        btn_p_plus.setFixedWidth(38)
        btn_p_plus.clicked.connect(lambda: self.sp_prof.setValue(self.sp_prof.value() + 50))
        h_prof.addWidget(btn_p_plus)
        form_layout.addRow("Profundidade:", h_prof)

        self._step_buttons = [btn_l_minus, btn_l_plus, btn_a_minus, btn_a_plus, btn_p_minus, btn_p_plus]

        # Caixa (Corpo / Bancada)
        from .materials_catalog import ALL_BOX_MATERIALS, MDF_MATERIALS

        self.cb_material = QComboBox()
        self.cb_material.addItems(ALL_BOX_MATERIALS)
        self.lbl_material_caixa = QLabel("Padrão da Caixa / Pedra:")
        form_layout.addRow(self.lbl_material_caixa, self.cb_material)

        self.cb_espessura = QComboBox()
        self.cb_espessura.addItems(["15 mm", "18 mm", "20 mm", "25 mm", "40 mm"])
        self.lbl_espessura_caixa = QLabel("Espessura:")
        form_layout.addRow(self.lbl_espessura_caixa, self.cb_espessura)

        self.cb_fita_caixa = QComboBox()
        self.cb_fita_caixa.addItems([
            "Frontal 1L (Bordo Aparente)",
            "2L (Frontal e Traseiro)",
            "4L (Todos os 4 Bordos)",
            "Sem Fita de Borda",
        ])
        self.lbl_fita_caixa = QLabel("Fita da Caixa:")
        form_layout.addRow(self.lbl_fita_caixa, self.cb_fita_caixa)

        self.cb_material_fita_caixa = QComboBox()
        self.cb_material_fita_caixa.addItems(["(Mesmo da Caixa)"] + MDF_MATERIALS)
        self.lbl_material_fita_caixa = QLabel("Padrão Fita Caixa:")
        form_layout.addRow(self.lbl_material_fita_caixa, self.cb_material_fita_caixa)

        self.sp_rodape = QSpinBox()
        self.sp_rodape.setRange(0, 300)
        self.sp_rodape.setValue(0)
        self.sp_rodape.setSuffix(" mm")
        self.lbl_rodape = QLabel("Altura Rodapé:")
        form_layout.addRow(self.lbl_rodape, self.sp_rodape)

        # Frentes (Portas e Gavetas independentes)
        self.cb_material_frentes = QComboBox()
        self.cb_material_frentes.addItems(["(Mesmo da Caixa)"] + MDF_MATERIALS)
        self.lbl_material_frentes = QLabel("Padrão das Frentes:")
        form_layout.addRow(self.lbl_material_frentes, self.cb_material_frentes)

        self.cb_espessura_frentes = QComboBox()
        self.cb_espessura_frentes.addItems([
            "(Mesma da Caixa)",
            "15 mm",
            "18 mm",
            "25 mm",
        ])
        self.lbl_espessura_frentes = QLabel("Espessura das Frentes:")
        form_layout.addRow(self.lbl_espessura_frentes, self.cb_espessura_frentes)

        # Puxadores (Portas e Gavetas)
        self.lbl_puxadores_header = QLabel("<b>🚪 Puxadores (Portas / Gavetas):</b>")
        form_layout.addRow(self.lbl_puxadores_header)

        self.cb_puxador_tipo = QComboBox()
        self.cb_puxador_tipo.addItems([
            "Puxador Alça (Linear / Metálico)",
            "Puxador Perfil (Alumínio)",
            "Puxador Cava (Chanfro 45°)",
            "Puxador Ponto (Botão Minimalista)",
            "Sem Puxador (Toque / Fecho Pulsador)",
        ])
        self.lbl_puxador_tipo = QLabel("Tipo de Puxador:")
        form_layout.addRow(self.lbl_puxador_tipo, self.cb_puxador_tipo)

        self.cb_puxador_cor = QComboBox()
        self.cb_puxador_cor.addItems([
            "Preto Fosco",
            "Alumínio / Inox",
            "Dourado / Champanhe",
            "Cobre / Rosé",
            "Branco",
        ])
        self.lbl_puxador_cor = QLabel("Acabamento Puxador:")
        form_layout.addRow(self.lbl_puxador_cor, self.cb_puxador_cor)

        self.cb_puxador_pos = QComboBox()
        self.cb_puxador_pos.addItems([
            "📌 Automático / Padrão",
            "⬆️ Na Parte de Cima (Topo)",
            "↕️ Na Extensão da Porta (Lateral)",
            "⬇️ Na Parte de Baixo (Base)",
            "🎯 No Centro",
        ])
        self.lbl_puxador_pos = QLabel("Posição do Puxador:")
        form_layout.addRow(self.lbl_puxador_pos, self.cb_puxador_pos)

        # --- Card Estilo TrazoMob: Altura do Puxador Perfil ---
        self.frame_perfil = QFrame()
        self.frame_perfil.setFrameShape(QFrame.StyledPanel)
        self.frame_perfil.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 6px; }"
        )
        layout_perfil = QVBoxLayout(self.frame_perfil)
        layout_perfil.setContentsMargins(6, 6, 6, 6)
        layout_perfil.setSpacing(6)

        h_perfil_head = QHBoxLayout()
        h_perfil_head.setSpacing(8)

        self.lbl_perfil_diagram = QLabel()
        self.lbl_perfil_diagram.setPixmap(make_perfil_diagram_pixmap(115, 80, modelo="gola"))
        self.lbl_perfil_diagram.setStyleSheet("border: 1px solid #94A3B8; border-radius: 4px; background: #E2E8F0;")
        h_perfil_head.addWidget(self.lbl_perfil_diagram)

        v_perfil_text = QVBoxLayout()
        v_perfil_text.setSpacing(2)
        lbl_p_title = QLabel("Puxador Perfil de Alumínio")
        lbl_p_title.setStyleSheet("font-weight: bold; font-size: 12px; color: #1E293B;")
        v_perfil_text.addWidget(lbl_p_title)

        lbl_p_sub = QLabel("Escolha o perfil e a altura de desconto na porta/gaveta")
        lbl_p_sub.setStyleSheet("font-size: 10px; color: #64748B;")
        lbl_p_sub.setWordWrap(True)
        v_perfil_text.addWidget(lbl_p_sub)
        v_perfil_text.addStretch()

        h_perfil_head.addLayout(v_perfil_text)
        layout_perfil.addLayout(h_perfil_head)

        lbl_m_title = QLabel("Modelo do perfil:")
        lbl_m_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        h_mod_row = QHBoxLayout()
        self.cb_perfil_modelo = QComboBox()
        self.cb_perfil_modelo.setStyleSheet("font-size: 11px; padding: 3px;")
        h_mod_row.addWidget(self.cb_perfil_modelo, stretch=1)

        self.btn_gerenciar_perfis = QPushButton("⚙️ Perfis…")
        self.btn_gerenciar_perfis.setToolTip("Abrir editor de perfis (seções 2D personalizadas, medidas e extrusão)")
        self.btn_gerenciar_perfis.setStyleSheet("font-size: 11px; padding: 3px 8px;")
        self.btn_gerenciar_perfis.clicked.connect(self._open_perfis_manager)
        h_mod_row.addWidget(self.btn_gerenciar_perfis)
        layout_perfil.addLayout(h_mod_row)

        lbl_a_title = QLabel("Altura / Desconto do perfil:")
        lbl_a_title.setStyleSheet("font-size: 11px; font-weight: bold; color: #334155;")
        layout_perfil.addWidget(lbl_a_title)

        self.cb_altura_perfil = QComboBox()
        self.cb_altura_perfil.addItems([
            "Padrão do perfil",
            "35 MM",
            "40 MM",
            "38 MM",
            "32 MM",
            "30 MM",
            "25 MM",
            "22 MM",
        ])
        self.cb_altura_perfil.setStyleSheet("font-weight: bold; font-size: 11px; padding: 3px;")
        layout_perfil.addWidget(self.cb_altura_perfil)

        self._refresh_perfil_modelos()
        self.cb_perfil_modelo.currentIndexChanged.connect(self._on_dialog_perfil_modelo_changed)

        form_layout.addRow(self.frame_perfil)

        self.sp_desconto_perfil = QSpinBox()
        self.sp_desconto_perfil.setRange(15, 60)
        self.sp_desconto_perfil.setValue(35)
        self.sp_desconto_perfil.setVisible(False)
        self.cb_altura_perfil.currentTextChanged.connect(self._sync_desconto_perfil_from_combo)

        def _update_dialog_perfil_card(idx):
            is_perfil = (idx == 1)
            self.frame_perfil.setVisible(is_perfil)

        self.cb_puxador_tipo.currentIndexChanged.connect(_update_dialog_perfil_card)
        _update_dialog_perfil_card(self.cb_puxador_tipo.currentIndex())

        self.sp_qtd_elem = QSpinBox()
        self.sp_qtd_elem.setRange(0, 8)
        self.sp_qtd_elem.setValue(2)
        self.lbl_qtd_elem = QLabel("Número de Portas:")
        form_layout.addRow(self.lbl_qtd_elem, self.sp_qtd_elem)

        self.sp_largura_gaveteiro = QSpinBox()
        self.sp_largura_gaveteiro.setRange(250, 1200)
        self.sp_largura_gaveteiro.setValue(450)
        self.sp_largura_gaveteiro.setSingleStep(50)
        self.sp_largura_gaveteiro.setSuffix(" mm")
        self.sp_largura_gaveteiro.setToolTip("Largura externa da seção de gavetas no balcão misto")
        self.lbl_largura_gaveteiro = QLabel("Largura do Gaveteiro:")
        form_layout.addRow(self.lbl_largura_gaveteiro, self.sp_largura_gaveteiro)
        self.lbl_largura_gaveteiro.setVisible(False)
        self.sp_largura_gaveteiro.setVisible(False)

        self.sp_prateleiras = QSpinBox()
        self.sp_prateleiras.setRange(0, 6)
        self.sp_prateleiras.setValue(1)
        form_layout.addRow("Prateleiras Internas:", self.sp_prateleiras)

        # ── Configurações do Balcão de Forno (balcao_forno) ───────────────────
        self.lbl_forno_section = QLabel("<b>🔥 Balcão para Forno Embutido:</b>")
        form_layout.addRow(self.lbl_forno_section)

        self.chk_forno_tem_gaveta = QCheckBox("Possui Gaveta Inferior")
        self.chk_forno_tem_gaveta.setChecked(True)
        self.chk_forno_tem_gaveta.setToolTip(
            "Ativado: cria uma gaveta na parte inferior com prateleira de apoio acima dela e frente cega superior.\n"
            "Desativado: frente cega ocupa toda a altura da caixa para embutir o forno direto."
        )
        self.lbl_forno_tem_gaveta = QLabel("Gaveta Inferior:")
        form_layout.addRow(self.lbl_forno_tem_gaveta, self.chk_forno_tem_gaveta)

        self.sp_forno_alt_gaveta = QSpinBox()
        self.sp_forno_alt_gaveta.setRange(80, 500)
        self.sp_forno_alt_gaveta.setValue(150)
        self.sp_forno_alt_gaveta.setSuffix(" mm")
        self.sp_forno_alt_gaveta.setToolTip("Altura do vão da gaveta inferior (o restante vira a frente cega para embutir)")
        self.lbl_forno_alt_gaveta = QLabel("Altura da Gaveta:")
        form_layout.addRow(self.lbl_forno_alt_gaveta, self.sp_forno_alt_gaveta)

        self._forno_widgets = [
            self.lbl_forno_section,
            self.lbl_forno_tem_gaveta, self.chk_forno_tem_gaveta,
            self.lbl_forno_alt_gaveta, self.sp_forno_alt_gaveta,
        ]
        for w in self._forno_widgets:
            w.setVisible(False)

        def _on_forno_tem_gaveta_toggle(state):
            tem_g = self.chk_forno_tem_gaveta.isChecked()
            is_forno = getattr(self, "_current_module_id", "") == "balcao_forno"
            self.lbl_forno_alt_gaveta.setVisible(is_forno and tem_g)
            self.sp_forno_alt_gaveta.setVisible(is_forno and tem_g)
            if hasattr(self, "_gaveta_widgets") and is_forno:
                for gw in self._gaveta_widgets:
                    gw.setVisible(tem_g)
        self.chk_forno_tem_gaveta.stateChanged.connect(_on_forno_tem_gaveta_toggle)

        # ── Configurações de Caixa para Geladeira (caixa_geladeira) ───────────
        self.lbl_geladeira_section = QLabel("<b>❄️ Nicho para Geladeira & Maleiro:</b>")
        form_layout.addRow(self.lbl_geladeira_section)

        self.sp_geladeira_alt_nicho = QSpinBox()
        self.sp_geladeira_alt_nicho.setRange(1200, 2400)
        self.sp_geladeira_alt_nicho.setValue(1800)
        self.sp_geladeira_alt_nicho.setSuffix(" mm")
        self.sp_geladeira_alt_nicho.setToolTip("Altura livre interna do nicho para a geladeira")
        self.lbl_geladeira_alt_nicho = QLabel("Altura do Vão da Geladeira:")
        form_layout.addRow(self.lbl_geladeira_alt_nicho, self.sp_geladeira_alt_nicho)

        self.cb_geladeira_tipo_porta = QComboBox()
        self.cb_geladeira_tipo_porta.addItems([
            "2 Portas de Abrir",
            "1 Porta Basculante",
        ])
        self.lbl_geladeira_tipo_porta = QLabel("Portas do Maleiro:")
        form_layout.addRow(self.lbl_geladeira_tipo_porta, self.cb_geladeira_tipo_porta)

        self._geladeira_widgets = [
            self.lbl_geladeira_section,
            self.lbl_geladeira_alt_nicho, self.sp_geladeira_alt_nicho,
            self.lbl_geladeira_tipo_porta, self.cb_geladeira_tipo_porta,
        ]
        for w in self._geladeira_widgets:
            w.setVisible(False)

        # ── Configurações de Aéreo Micro-ondas ──────────────────────────────────
        self.lbl_micro_section = QLabel("<b>🚪 Portas do Micro-ondas:</b>")
        form_layout.addRow(self.lbl_micro_section)

        self.cb_micro_tipo_porta = QComboBox()
        self.cb_micro_tipo_porta.addItems([
            "1 Porta Basculante",
            "2 Portas de Abrir",
        ])
        self.lbl_micro_tipo_porta = QLabel("Tipo de Porta:")
        form_layout.addRow(self.lbl_micro_tipo_porta, self.cb_micro_tipo_porta)

        self._micro_widgets = [
            self.lbl_micro_section,
            self.lbl_micro_tipo_porta, self.cb_micro_tipo_porta,
        ]
        for w in self._micro_widgets:
            w.setVisible(False)



        # ── Configurações de Travessas (Cozinha Inferiores) ─────────────────────
        self.lbl_travessa_section = QLabel("<b>⚙️ Travessas Superiores:</b>")
        form_layout.addRow(self.lbl_travessa_section)

        # Balcão padrão: largura das travessas frontal e traseira
        self.sp_larg_travessa_frontal = QSpinBox()
        self.sp_larg_travessa_frontal.setRange(20, 300)
        self.sp_larg_travessa_frontal.setValue(70)
        self.sp_larg_travessa_frontal.setSuffix(" mm")
        self.sp_larg_travessa_frontal.setToolTip("Largura (profundidade visível) da travessa frontal superior")
        self.lbl_larg_travessa_frontal = QLabel("Travessa Frontal:")
        form_layout.addRow(self.lbl_larg_travessa_frontal, self.sp_larg_travessa_frontal)

        self.sp_larg_travessa_traseira = QSpinBox()
        self.sp_larg_travessa_traseira.setRange(20, 300)
        self.sp_larg_travessa_traseira.setValue(70)
        self.sp_larg_travessa_traseira.setSuffix(" mm")
        self.sp_larg_travessa_traseira.setToolTip("Largura (profundidade visível) da travessa traseira superior")
        self.lbl_larg_travessa_traseira = QLabel("Travessa Traseira:")
        form_layout.addRow(self.lbl_larg_travessa_traseira, self.sp_larg_travessa_traseira)

        # Balcão de pia: travessa frontal em pé (vertical)
        self.chk_travessa_em_pe = QCheckBox("Travessa frontal em pé (vertical)")
        self.chk_travessa_em_pe.setChecked(True)
        self.chk_travessa_em_pe.setToolTip(
            "Ativado: travessa frontal ocupa toda a altura da caixa (estilo balcão de pia).\n"
            "Desativado: travessa deitada, estilo balcão comum."
        )
        self.lbl_travessa_em_pe = QLabel("Orientação Frontal:")
        form_layout.addRow(self.lbl_travessa_em_pe, self.chk_travessa_em_pe)

        # Travessa traseira em pé (vertical)
        self.chk_travessa_traseira_em_pe = QCheckBox("Travessa traseira em pé (vertical)")
        self.chk_travessa_traseira_em_pe.setChecked(False)
        self.chk_travessa_traseira_em_pe.setToolTip(
            "Ativado: travessa traseira fica em pé (vertical), apoiada na lateral traseira.\n"
            "Desativado: travessa deitada (horizontal), padrão para a maioria dos módulos."
        )
        self.lbl_travessa_traseira_em_pe = QLabel("Orientação Traseira:")
        form_layout.addRow(self.lbl_travessa_traseira_em_pe, self.chk_travessa_traseira_em_pe)

        self.sp_recuo_porta_pia = QSpinBox()
        self.sp_recuo_porta_pia.setRange(0, 200)
        self.sp_recuo_porta_pia.setValue(50)
        self.sp_recuo_porta_pia.setSuffix(" mm")
        self.sp_recuo_porta_pia.setToolTip(
            "Rebaixo do topo das portas em relação ao topo do móvel quando a travessa frontal está em pé.\n"
            "Padrão: 50 mm (as portas começam mais baixas para liberar o visual/pingadeira da pia)."
        )
        self.lbl_recuo_porta_pia = QLabel("Rebaixo Superior Portas:")
        form_layout.addRow(self.lbl_recuo_porta_pia, self.sp_recuo_porta_pia)

        # Padrão e Espessura das Travessas
        self.cb_material_travessas = QComboBox()
        self.cb_material_travessas.addItems([
            "(Mesmo da Caixa)",
            "MDF Branco TX",
            "MDF Louro Freijó",
            "MDF Carvalho Boreal",
            "MDF Grafite",
            "MDF Cinza Sagrado",
        ])
        self.lbl_material_travessas = QLabel("Padrão Travessas:")
        form_layout.addRow(self.lbl_material_travessas, self.cb_material_travessas)

        self.cb_espessura_travessas = QComboBox()
        self.cb_espessura_travessas.addItems([
            "(Mesma da Caixa)",
            "15 mm",
            "18 mm",
            "25 mm",
        ])
        self.lbl_espessura_travessas = QLabel("Espessura Travessas:")
        form_layout.addRow(self.lbl_espessura_travessas, self.cb_espessura_travessas)

        # Fita de borda das travessas
        self.cb_fita_travessas = QComboBox()
        self.cb_fita_travessas.addItems([
            "Frontal 1L (Bordo Aparente)",
            "2L (2 Bordos Longos)",
            "4L (Todos os 4 Bordos)",
            "Sem Fita de Borda",
        ])
        self.lbl_fita_travessas = QLabel("Fita de Borda Trav.:")
        form_layout.addRow(self.lbl_fita_travessas, self.cb_fita_travessas)

        self.cb_material_fita_travessas = QComboBox()
        self.cb_material_fita_travessas.addItems([
            "(Mesmo da Travessa)",
            "MDF Branco TX",
            "MDF Louro Freijó",
            "MDF Carvalho Boreal",
            "MDF Grafite",
            "MDF Cinza Sagrado",
        ])
        self.lbl_material_fita_travessas = QLabel("Padrão Fita Trav.:")
        form_layout.addRow(self.lbl_material_fita_travessas, self.cb_material_fita_travessas)

        # Ocultar seção de travessas por padrão — aparece só para módulos relevantes
        self._travessa_widgets = [
            self.lbl_travessa_section,
            self.lbl_larg_travessa_frontal, self.sp_larg_travessa_frontal,
            self.lbl_larg_travessa_traseira, self.sp_larg_travessa_traseira,
            self.lbl_travessa_em_pe, self.chk_travessa_em_pe,
            self.lbl_travessa_traseira_em_pe, self.chk_travessa_traseira_em_pe,
            self.lbl_recuo_porta_pia, self.sp_recuo_porta_pia,
            self.lbl_material_travessas, self.cb_material_travessas,
            self.lbl_espessura_travessas, self.cb_espessura_travessas,
            self.lbl_fita_travessas, self.cb_fita_travessas,
            self.lbl_material_fita_travessas, self.cb_material_fita_travessas,
        ]
        for w in self._travessa_widgets:
            w.setVisible(False)

        # Conectar checkbox para mostrar/esconder recuo quando travessa frontal em pé
        def _on_travessa_em_pe_changed(state):
            em_pe = self.chk_travessa_em_pe.isChecked()
            self.lbl_recuo_porta_pia.setVisible(em_pe)
            self.sp_recuo_porta_pia.setVisible(em_pe)
        self.chk_travessa_em_pe.stateChanged.connect(_on_travessa_em_pe_changed)

        # ── Configurações da Caixa de Gaveta ──────────────────────────────────
        self.lbl_gaveta_section = QLabel("<b>⚙️ Caixa de Gaveta:</b>")
        form_layout.addRow(self.lbl_gaveta_section)

        self.cb_tipo_fundo_gaveta = QComboBox()
        self.cb_tipo_fundo_gaveta.addItems([
            "Canal / Rasgo Lateral",
            "Por Baixo (Sobreposto)",
        ])
        self.lbl_tipo_fundo_gaveta = QLabel("Montagem Fundo Gav.:")
        form_layout.addRow(self.lbl_tipo_fundo_gaveta, self.cb_tipo_fundo_gaveta)

        self.sp_folga_corredica = QSpinBox()
        self.sp_folga_corredica.setRange(10, 50)
        self.sp_folga_corredica.setValue(26)
        self.sp_folga_corredica.setSuffix(" mm")
        self.sp_folga_corredica.setToolTip("Vão / folga total a descontar da largura da caixa para corrediças (ex.: 26mm = 13mm de cada lado)")
        self.lbl_folga_corredica = QLabel("Folga Corrediças:")
        form_layout.addRow(self.lbl_folga_corredica, self.sp_folga_corredica)

        self.cb_material_gaveta = QComboBox()
        self.cb_material_gaveta.addItems([
            "(Mesmo da Caixa)",
            "MDF Branco TX",
            "MDF Louro Freijó",
            "MDF Carvalho Boreal",
            "MDF Grafite",
            "MDF Cinza Sagrado",
        ])
        self.lbl_material_gaveta = QLabel("Material Gaveta:")
        form_layout.addRow(self.lbl_material_gaveta, self.cb_material_gaveta)

        self.cb_espessura_gaveta = QComboBox()
        self.cb_espessura_gaveta.addItems([
            "15 mm",
            "18 mm",
        ])
        self.lbl_espessura_gaveta = QLabel("Espessura Gaveta:")
        form_layout.addRow(self.lbl_espessura_gaveta, self.cb_espessura_gaveta)

        self.cb_material_fita_gaveta = QComboBox()
        self.cb_material_fita_gaveta.addItems([
            "(Mesmo da Gaveta)",
            "MDF Branco TX",
            "MDF Louro Freijó",
            "MDF Carvalho Boreal",
            "MDF Grafite",
            "MDF Cinza Sagrado",
        ])
        self.lbl_material_fita_gaveta = QLabel("Fita Borda Gaveta:")
        form_layout.addRow(self.lbl_material_fita_gaveta, self.cb_material_fita_gaveta)

        self.cb_material_fundo_gaveta = QComboBox()
        self.cb_material_fundo_gaveta.addItems([
            "(Padrão Fundo)",
            "MDF Branco TX",
            "MDF Louro Freijó",
            "MDF Carvalho Boreal",
            "MDF Grafite",
            "MDF Cinza Sagrado",
        ])
        self.lbl_material_fundo_gaveta = QLabel("Material Fundo Gav.:")
        form_layout.addRow(self.lbl_material_fundo_gaveta, self.cb_material_fundo_gaveta)

        self.cb_esp_fundo_gaveta = QComboBox()
        self.cb_esp_fundo_gaveta.addItems([
            "6 mm",
            "3 mm",
            "15 mm",
        ])
        self.lbl_esp_fundo_gaveta = QLabel("Espessura Fundo Gav.:")
        form_layout.addRow(self.lbl_esp_fundo_gaveta, self.cb_esp_fundo_gaveta)

        self._gaveta_widgets = [
            self.lbl_gaveta_section,
            self.lbl_tipo_fundo_gaveta, self.cb_tipo_fundo_gaveta,
            self.lbl_folga_corredica, self.sp_folga_corredica,
            self.lbl_material_gaveta, self.cb_material_gaveta,
            self.lbl_espessura_gaveta, self.cb_espessura_gaveta,
            self.lbl_material_fita_gaveta, self.cb_material_fita_gaveta,
            self.lbl_material_fundo_gaveta, self.cb_material_fundo_gaveta,
            self.lbl_esp_fundo_gaveta, self.cb_esp_fundo_gaveta,
        ]
        for w in self._gaveta_widgets:
            w.setVisible(False)

        # ── Configurações de Marmoraria / Bancadas de Pedra ────────────────────
        self.lbl_pedra_section = QLabel("<b>🪨 Marmoraria & Bancada de Pedra:</b>")
        form_layout.addRow(self.lbl_pedra_section)

        self.sp_esp_pedra = QSpinBox()
        self.sp_esp_pedra.setRange(10, 60)
        self.sp_esp_pedra.setValue(20)
        self.sp_esp_pedra.setSuffix(" mm")
        self.sp_esp_pedra.setToolTip("Espessura da chapa de pedra (padrão: 20mm)")
        self.lbl_esp_pedra = QLabel("Espessura da Pedra:")
        form_layout.addRow(self.lbl_esp_pedra, self.sp_esp_pedra)

        self.sp_altura_saia = QSpinBox()
        self.sp_altura_saia.setRange(20, 200)
        self.sp_altura_saia.setValue(40)
        self.sp_altura_saia.setSuffix(" mm")
        self.sp_altura_saia.setToolTip("Altura da saia/testeira engrossada frontal (padrão: 40mm ou 60mm)")
        self.lbl_altura_saia = QLabel("Altura da Saia / Testeira:")
        form_layout.addRow(self.lbl_altura_saia, self.sp_altura_saia)

        self.sp_altura_frontao = QSpinBox()
        self.sp_altura_frontao.setRange(0, 300)
        self.sp_altura_frontao.setValue(100)
        self.sp_altura_frontao.setSuffix(" mm")
        self.sp_altura_frontao.setToolTip("Altura do rodabanca/frontão na parede (padrão: 100mm)")
        self.lbl_altura_frontao = QLabel("Rodabanca / Frontão:")
        form_layout.addRow(self.lbl_altura_frontao, self.sp_altura_frontao)

        self.sp_larg_asa = QSpinBox()
        self.sp_larg_asa.setRange(300, 1200)
        self.sp_larg_asa.setSingleStep(50)
        self.sp_larg_asa.setValue(600)
        self.sp_larg_asa.setSuffix(" mm")
        self.sp_larg_asa.setToolTip("Profundidade das asas da bancada em L (padrão: 600mm)")
        self.lbl_larg_asa = QLabel("Profundidade Asas (L):")
        form_layout.addRow(self.lbl_larg_asa, self.sp_larg_asa)

        self.chk_tem_saia_esq = QCheckBox("Saia Lateral Esquerda")
        self.chk_tem_saia_esq.setChecked(True)
        self.lbl_tem_saia_esq = QLabel("Saia Esquerda:")
        form_layout.addRow(self.lbl_tem_saia_esq, self.chk_tem_saia_esq)

        self.chk_tem_saia_dir = QCheckBox("Saia Lateral Direita")
        self.chk_tem_saia_dir.setChecked(True)
        self.lbl_tem_saia_dir = QLabel("Saia Direita:")
        form_layout.addRow(self.lbl_tem_saia_dir, self.chk_tem_saia_dir)

        self.cb_tipo_cuba = QComboBox()
        self.cb_tipo_cuba.addItems([
            "Cuba Inox Simples",
            "Cuba Inox Dupla",
            "Cuba Esculpida na Pedra",
            "Sem Cuba (Tampo Cego)",
        ])
        self.lbl_tipo_cuba = QLabel("Modelo da Cuba:")
        form_layout.addRow(self.lbl_tipo_cuba, self.cb_tipo_cuba)

        self.cb_posicao_cuba = QComboBox()
        self.cb_posicao_cuba.addItems([
            "🎯 Centralizada",
            "⬅️ À Esquerda",
            "➡️ À Direita",
        ])
        self.lbl_posicao_cuba = QLabel("Posição da Cuba:")
        form_layout.addRow(self.lbl_posicao_cuba, self.cb_posicao_cuba)

        self.chk_tem_torneira = QCheckBox("Incluir Torneira Gourmet")
        self.chk_tem_torneira.setChecked(True)
        self.lbl_tem_torneira = QLabel("Metais / Torneira:")
        form_layout.addRow(self.lbl_tem_torneira, self.chk_tem_torneira)

        self.cb_canto_recorte = QComboBox()
        self.cb_canto_recorte.addItems(["Cantos Arredondados (R20)", "Cantos Retos 90°"])
        self.lbl_canto_recorte = QLabel("Recorte da Cuba:")
        form_layout.addRow(self.lbl_canto_recorte, self.cb_canto_recorte)

        self.chk_tem_area_molhada = QCheckBox("Área Molhada Rebaixada")
        self.chk_tem_area_molhada.setChecked(True)
        self.lbl_tem_area_molhada = QLabel("Área Molhada:")
        form_layout.addRow(self.lbl_tem_area_molhada, self.chk_tem_area_molhada)

        self._pedra_widgets = [
            self.lbl_pedra_section,
            self.lbl_esp_pedra, self.sp_esp_pedra,
            self.lbl_altura_saia, self.sp_altura_saia,
            self.lbl_altura_frontao, self.sp_altura_frontao,
            self.lbl_larg_asa, self.sp_larg_asa,
            self.lbl_tem_saia_esq, self.chk_tem_saia_esq,
            self.lbl_tem_saia_dir, self.chk_tem_saia_dir,
            self.lbl_tipo_cuba, self.cb_tipo_cuba,
            self.lbl_posicao_cuba, self.cb_posicao_cuba,
            self.lbl_tem_torneira, self.chk_tem_torneira,
            self.lbl_canto_recorte, self.cb_canto_recorte,
            self.lbl_tem_area_molhada, self.chk_tem_area_molhada,
        ]
        for w in self._pedra_widgets:
            w.setVisible(False)

        # Fundo do móvel (agrupador para ocultar quando for pedra)
        self.lbl_fundo_section = QLabel("<b>⚙️ Fundo do Móvel (TrazoMob):</b>")
        form_layout.addRow(self.lbl_fundo_section)

        self.cb_tipo_fundo = QComboBox()
        self.cb_tipo_fundo.addItems([
            "Canal / Rasgo",
            "Sobreposto",
            "Sem Fundo",
        ])
        self.cb_tipo_fundo.currentIndexChanged.connect(self._on_tipo_fundo_changed)
        self.lbl_tipo_fundo = QLabel("Tipo de Fundo:")
        form_layout.addRow(self.lbl_tipo_fundo, self.cb_tipo_fundo)

        self.cb_esp_fundo = QComboBox()
        self.cb_esp_fundo.addItems(["6 mm", "3 mm", "15 mm"])
        self.lbl_esp_fundo = QLabel("Espessura Fundo:")
        form_layout.addRow(self.lbl_esp_fundo, self.cb_esp_fundo)

        self.sp_recuo_fundo = QSpinBox()
        self.sp_recuo_fundo.setRange(0, 100)
        self.sp_recuo_fundo.setValue(15)
        self.sp_recuo_fundo.setSuffix(" mm")
        self.lbl_recuo_fundo = QLabel("Recuo Traseiro:")
        form_layout.addRow(self.lbl_recuo_fundo, self.sp_recuo_fundo)

        self.sp_prof_rasgo = QSpinBox()
        self.sp_prof_rasgo.setRange(1, 15)
        self.sp_prof_rasgo.setValue(7)
        self.sp_prof_rasgo.setSuffix(" mm")
        self.lbl_prof_rasgo = QLabel("Prof. do Rasgo:")
        form_layout.addRow(self.lbl_prof_rasgo, self.sp_prof_rasgo)

        self.sp_folga_fundo = QSpinBox()
        self.sp_folga_fundo.setRange(0, 20)
        self.sp_folga_fundo.setValue(2)
        self.sp_folga_fundo.setSuffix(" mm")
        self.lbl_folga_fundo = QLabel("Folga do Fundo:")
        form_layout.addRow(self.lbl_folga_fundo, self.sp_folga_fundo)

        self.chk_fundo = QCheckBox()
        self.chk_fundo.setChecked(True)

        self._fundo_widgets = [
            self.lbl_fundo_section,
            self.lbl_tipo_fundo, self.cb_tipo_fundo,
            self.lbl_esp_fundo, self.cb_esp_fundo,
            self.lbl_recuo_fundo, self.sp_recuo_fundo,
            self.lbl_prof_rasgo, self.sp_prof_rasgo,
            self.lbl_folga_fundo, self.sp_folga_fundo,
        ]

        # Seção de Alinhamento e Encaixe (Estilo TrazoMob)
        form_layout.addRow(QLabel("<b>Alinhamento & Encaixe (TrazoMob):</b>"))

        self.cb_align_mode = QComboBox()
        self.cb_align_mode.addItems([
            "➡️ Ao lado (Direita)",
            "⬅️ Ao lado (Esquerda)",
            "⬆️ Sobrepor (Acima)",
            "🎯 Livre (Câmera)",
        ])
        form_layout.addRow("Posição ao Inserir:", self.cb_align_mode)

        self.cb_orientacao = QComboBox()
        self.cb_orientacao.addItems([
            "0° (Frente / Padrão)",
            "90° (Giro Horário / Parede Lateral Dir)",
            "180° (Costas / Invertido)",
            "270° (Giro Anti-horário / Parede Lateral Esq)",
        ])
        form_layout.addRow("Orientação ao Inserir:", self.cb_orientacao)

        self.sp_align_gap = QSpinBox()
        self.sp_align_gap.setRange(0, 500)
        self.sp_align_gap.setValue(0)
        self.sp_align_gap.setSuffix(" mm")
        form_layout.addRow("Folga / Vão:", self.sp_align_gap)

        self.lbl_align_ref = QLabel("📌 Encostar em: Origem (1º Módulo)")
        self.lbl_align_ref.setStyleSheet("font-size: 11px; font-style: italic; color: #64748B;")
        form_layout.addRow("", self.lbl_align_ref)

        h_align_btns = QHBoxLayout()
        btn_al_left = QPushButton("⬅️ Esq")
        btn_al_left.setToolTip("Encosta o módulo na lateral esquerda do vizinho")
        btn_al_left.clicked.connect(lambda: self._align_module("left"))
        h_align_btns.addWidget(btn_al_left)

        btn_al_right = QPushButton("➡️ Dir")
        btn_al_right.setToolTip("Encosta o módulo na lateral direita do vizinho")
        btn_al_right.clicked.connect(lambda: self._align_module("right"))
        h_align_btns.addWidget(btn_al_right)

        btn_al_z = QPushButton("📐 Altura")
        btn_al_z.setToolTip("Nivela a altura Z da base com o vizinho")
        btn_al_z.clicked.connect(lambda: self._align_module("height"))
        h_align_btns.addWidget(btn_al_z)

        btn_al_y = QPushButton("🧱 Parede")
        btn_al_y.setToolTip("Alinha o fundo / parede (profundidade Y) com o vizinho")
        btn_al_y.clicked.connect(lambda: self._align_module("depth"))
        h_align_btns.addWidget(btn_al_y)

        form_layout.addRow("Ajustar no 3D:", h_align_btns)

        h_rot_btns = QHBoxLayout()
        btn_rot_ccw = QPushButton("↺ Girar 90° Esq")
        btn_rot_ccw.setToolTip("Gira o módulo 90° para a esquerda (anti-horário)")
        btn_rot_ccw.clicked.connect(lambda: self._rotate_selected_module(-90.0))
        h_rot_btns.addWidget(btn_rot_ccw)

        btn_rot_cw = QPushButton("↻ Girar 90° Dir")
        btn_rot_cw.setToolTip("Gira o módulo 90° para a direita (horário)")
        btn_rot_cw.clicked.connect(lambda: self._rotate_selected_module(90.0))
        h_rot_btns.addWidget(btn_rot_cw)

        form_layout.addRow("Girar no 3D (90°):", h_rot_btns)

        self._align_buttons = [btn_al_left, btn_al_right, btn_al_z, btn_al_y, btn_rot_ccw, btn_rot_cw]

        scroll_form.setWidget(form_widget)
        v_props.addWidget(scroll_form)

        # Botões de Ação
        self.btn_insert = QPushButton("✨ Inserir no Projeto")
        self.btn_insert.setStyleSheet(
            "background-color: #1976D2; color: white; font-weight: bold; padding: 9px 12px; font-size: 12px; border-radius: 5px;"
        )
        self.btn_insert.clicked.connect(self._insert_or_update_module)
        v_props.addWidget(self.btn_insert)

        # Ações de Gestão do Módulo Selecionado (Duplicar, Novo, Excluir)
        h_dup_del = QHBoxLayout()
        h_dup_del.setSpacing(4)
        self.btn_duplicate = QPushButton("📋 Duplicar")
        self.btn_duplicate.setToolTip("Clona o módulo selecionado ao lado com todas as suas medidas e configurações (Atalho: Ctrl+D)")
        self.btn_duplicate.setStyleSheet(
            "QPushButton { background-color: #0284c7; color: white; font-weight: bold; padding: 5px 8px; border-radius: 4px; font-size: 11px; }"
            "QPushButton:disabled { background-color: #64748b; color: #cbd5e1; }"
        )
        self.btn_duplicate.clicked.connect(self._duplicate_selected_module)
        h_dup_del.addWidget(self.btn_duplicate)

        self.btn_new_mode = QPushButton("✨ Novo")
        self.btn_new_mode.setToolTip("Limpa seleção para criar um novo móvel")
        self.btn_new_mode.setStyleSheet("padding: 5px 8px; font-size: 11px;")
        self.btn_new_mode.clicked.connect(self._reset_to_new_module)
        h_dup_del.addWidget(self.btn_new_mode)

        self.btn_delete = QPushButton("🗑️ Excluir")
        self.btn_delete.setToolTip("Exclui o módulo selecionado da cena 3D (com Undo/Redo) (Atalho: Del)")
        self.btn_delete.setStyleSheet(
            "QPushButton { background-color: #dc2626; color: white; font-weight: bold; padding: 5px 8px; border-radius: 4px; font-size: 11px; }"
            "QPushButton:disabled { background-color: #64748b; color: #cbd5e1; }"
        )
        self.btn_delete.clicked.connect(self._delete_selected_module)
        h_dup_del.addWidget(self.btn_delete)
        v_props.addLayout(h_dup_del)

        # Atalhos de Teclado no Diálogo
        QShortcut(QKeySequence("Ctrl+D"), self, self._duplicate_selected_module)
        QShortcut(QKeySequence(Qt.Key_Delete), self, self._delete_selected_module)

        # Botões e Controle de Abertura Dinâmica (Estilo Promob)
        h_interact_box = QVBoxLayout()
        h_interact_box.setSpacing(4)

        h_interact_btns = QHBoxLayout()
        h_interact_btns.setSpacing(4)
        self.btn_toggle_interact = QPushButton("🚪 Abrir/Fechar")
        self.btn_toggle_interact.setStyleSheet("font-weight: 500; padding: 5px 8px; font-size: 11px;")
        self.btn_toggle_interact.setToolTip("Abre ou fecha todas as portas e gavetas do móvel selecionado")
        self.btn_toggle_interact.clicked.connect(self._toggle_doors_and_drawers)
        h_interact_btns.addWidget(self.btn_toggle_interact)

        self.btn_interact_tool = QPushButton("👆 Interagir (3D)")
        self.btn_interact_tool.setStyleSheet("font-weight: 500; padding: 5px 8px; font-size: 11px;")
        self.btn_interact_tool.setToolTip("Ativa a ferramenta de clique para abrir/fechar livremente no 3D")
        self.btn_interact_tool.clicked.connect(self._activate_interact_tool)
        h_interact_btns.addWidget(self.btn_interact_tool)

        self.btn_test_col = QPushButton("⚠️ Testar Colisão")
        self.btn_test_col.setStyleSheet("background-color: #f59e0b; color: white; font-weight: bold; padding: 5px 8px; font-size: 11px; border-radius: 4px;")
        self.btn_test_col.setToolTip("Testa se as portas/gavetas batem em puxadores, cantos ou outros armários")
        self.btn_test_col.clicked.connect(self._test_module_collisions)
        h_interact_btns.addWidget(self.btn_test_col)
        h_interact_box.addLayout(h_interact_btns)

        # Slider de abertura contínua no diálogo
        h_dlg_slider = QHBoxLayout()
        h_dlg_slider.setSpacing(6)
        lbl_sl_icon = QLabel("Abertura:")
        lbl_sl_icon.setStyleSheet("font-size: 11px; font-weight: bold;")
        h_dlg_slider.addWidget(lbl_sl_icon)

        self.sl_dlg_open = QSlider(Qt.Horizontal)
        self.sl_dlg_open.setRange(0, 100)
        self.sl_dlg_open.setValue(0)
        self.sl_dlg_open.valueChanged.connect(self._on_dialog_open_slider_changed)
        h_dlg_slider.addWidget(self.sl_dlg_open, 1)

        self.lbl_dlg_open_val = QLabel("0%")
        self.lbl_dlg_open_val.setStyleSheet("font-size: 10px; font-weight: bold; min-width: 30px;")
        h_dlg_slider.addWidget(self.lbl_dlg_open_val)
        h_interact_box.addLayout(h_dlg_slider)

        v_props.addLayout(h_interact_box)

        layout.addWidget(props_box, stretch=2)

        self._populate_module_cards()
        self._load_module_values_if_editing()

    def _load_module_values_if_editing(self):
        """Se houver um módulo selecionado, carrega seus valores nos campos."""
        if self._editing_module is not None:
            params = self._editing_module.ext.get("trazomob_module", {})
            tipo = params.get("tipo", "balcao")

            # Seleciona o card do módulo correspondente no grid visual
            for i in range(self.list_modules.count()):
                it = self.list_modules.item(i)
                data = it.data(Qt.UserRole)
                if data and data.get("id") == tipo:
                    self.list_modules.setCurrentItem(it)
                    self._on_module_card_selected(it)
                    break

            # Popula campos comuns via mapper compartilhado (preserva largura/profundidade paramétricas independentemente de rot_z)
            populate_ui_from_module(self, params)

            is_misto = (tipo == "balcao_misto")
            if hasattr(self, "lbl_largura_gaveteiro"):
                self.lbl_largura_gaveteiro.setVisible(is_misto)
                self.sp_largura_gaveteiro.setVisible(is_misto)
                if is_misto and "largura_gaveteiro" in params:
                    self.sp_largura_gaveteiro.setValue(int(round(float(params["largura_gaveteiro"]))))

            is_canto_l_mod = tipo in ("balcao_canto_l", "bancada_canto_l", "bancada_canto")
            if hasattr(self, "lbl_larg_asa"):
                self.lbl_larg_asa.setVisible(is_canto_l_mod)
                self.sp_larg_asa.setVisible(is_canto_l_mod)
                if is_canto_l_mod and "larg_asa" in params:
                    self.sp_larg_asa.setValue(int(round(float(params["larg_asa"]))))

            # Restaura configurações de travessas (se relevante)
            _IDS_COZINHA_INFERIORES = {
                "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
                "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
            }
            if hasattr(self, "sp_larg_travessa_frontal") and tipo in _IDS_COZINHA_INFERIORES:
                em_pe = bool(params.get("travessa_frontal_em_pe", (tipo == "balcao_pia")))
                self.chk_travessa_em_pe.setChecked(em_pe)
                self.chk_travessa_traseira_em_pe.setChecked(bool(params.get("travessa_traseira_em_pe", False)))
                larg_f = params.get("larg_travessa_frontal_mm", params.get("larg_travessa_mm", 70.0))
                larg_t = params.get("larg_travessa_traseira_mm", 70.0)
                recuo_t = params.get("recuo_porta_topo_mm", params.get("recuo_porta_pia_mm", 50.0))
                self.sp_larg_travessa_frontal.setValue(int(round(float(larg_f))))
                self.sp_larg_travessa_traseira.setValue(int(round(float(larg_t))))
                self.sp_recuo_porta_pia.setValue(int(round(float(recuo_t))))
                self.lbl_recuo_porta_pia.setVisible(em_pe)
                self.sp_recuo_porta_pia.setVisible(em_pe)

                # Material travessas
                mat_t = params.get("material_travessas")
                if mat_t and hasattr(self, "cb_material_travessas"):
                    m_idx = 0
                    for i in range(self.cb_material_travessas.count()):
                        t_txt = self.cb_material_travessas.itemText(i)
                        if t_txt in mat_t and not t_txt.startswith("("):
                            m_idx = i
                            break
                    self.cb_material_travessas.setCurrentIndex(m_idx)
                elif hasattr(self, "cb_material_travessas"):
                    self.cb_material_travessas.setCurrentIndex(0)

                # Espessura travessas
                esp_t = params.get("esp_travessas_mm", params.get("espessura_travessas"))
                if esp_t and hasattr(self, "cb_espessura_travessas"):
                    e_idx = self.cb_espessura_travessas.findText(f"{int(round(float(esp_t)))} mm")
                    self.cb_espessura_travessas.setCurrentIndex(e_idx if e_idx >= 0 else 0)
                elif hasattr(self, "cb_espessura_travessas"):
                    self.cb_espessura_travessas.setCurrentIndex(0)

                # Fita de borda travessas
                modo_f = params.get("fita_travessas_modo", "frontal_1L")
                if hasattr(self, "cb_fita_travessas"):
                    fita_map = {"frontal_1l": 0, "2l": 1, "4l": 2, "sem_fita": 3}
                    self.cb_fita_travessas.setCurrentIndex(fita_map.get(str(modo_f).lower(), 0))

                if hasattr(self, "cb_material_fita_travessas"):
                    mat_ftr = params.get("material_fita_travessas")
                    if mat_ftr:
                        idx_ftr = 0
                        for i in range(self.cb_material_fita_travessas.count()):
                            txt_i = self.cb_material_fita_travessas.itemText(i)
                            if txt_i in mat_ftr and not txt_i.startswith("("):
                                idx_ftr = i
                                break
                        self.cb_material_fita_travessas.setCurrentIndex(idx_ftr)
                    else:
                        self.cb_material_fita_travessas.setCurrentIndex(0)

            # Restaura configurações de Forno (se tipo balcao_forno)
            is_forno = (tipo == "balcao_forno")
            if hasattr(self, "_forno_widgets"):
                self.lbl_forno_section.setVisible(is_forno)
                self.lbl_forno_tem_gaveta.setVisible(is_forno)
                self.chk_forno_tem_gaveta.setVisible(is_forno)
                tem_gav_f = bool(params.get("tem_gaveta", True))
                if is_forno:
                    self.chk_forno_tem_gaveta.setChecked(tem_gav_f)
                    self.sp_forno_alt_gaveta.setValue(int(round(float(params.get("alt_gaveta_mm", 150.0)))))
                self.lbl_forno_alt_gaveta.setVisible(is_forno and tem_gav_f)
                self.sp_forno_alt_gaveta.setVisible(is_forno and tem_gav_f)

            # Restaura configurações de Caixa para Geladeira (caixa_geladeira)
            is_geladeira = (tipo == "caixa_geladeira")
            if hasattr(self, "_geladeira_widgets"):
                for w in self._geladeira_widgets:
                    w.setVisible(is_geladeira)
                if is_geladeira:
                    self.sp_geladeira_alt_nicho.setValue(int(round(float(params.get("alt_nicho_geladeira_mm", 1800.0)))))
                    is_b = (str(params.get("tipo_porta_superior", "")).lower() in ("basculante", "1_porta") or int(params.get("num_portas", 2)) == 1)
                    self.cb_geladeira_tipo_porta.setCurrentIndex(1 if is_b else 0)

            # Restaura configurações de Aéreo Micro-ondas (aereo_microondas)
            is_micro = (tipo == "aereo_microondas")
            if hasattr(self, "_micro_widgets"):
                for w in self._micro_widgets:
                    w.setVisible(is_micro)
                if is_micro:
                    is_b_micro = (str(params.get("tipo_porta_superior", "basculante")).lower() in ("basculante", "1_porta") or int(params.get("num_portas", 1)) == 1)
                    self.cb_micro_tipo_porta.setCurrentIndex(0 if is_b_micro else 1)


            # Restaura configurações de Caixa de Gaveta
            has_gav = ("num_gavetas" in params) or (tipo in ("gaveteiro", "balcao_misto", "torre_quente", "gabinete_banheiro")) or (is_forno and bool(params.get("tem_gaveta", True)))
            if hasattr(self, "_gaveta_widgets"):
                for w in self._gaveta_widgets:
                    w.setVisible(has_gav)
                if has_gav:
                    # Tipo de fundo da gaveta
                    m_fg = str(params.get("tipo_fundo_gaveta", "rasgo")).lower()
                    self.cb_tipo_fundo_gaveta.setCurrentIndex(1 if m_fg in ("por_baixo", "baixo") else 0)

                    # Folga da corrediça
                    self.sp_folga_corredica.setValue(int(round(float(params.get("folga_corredica_mm", 26.0)))))

                    # Material da gaveta
                    mg = params.get("material_gaveta")
                    if mg and hasattr(self, "cb_material_gaveta"):
                        idx_mg = 0
                        for i in range(self.cb_material_gaveta.count()):
                            t_txt = self.cb_material_gaveta.itemText(i)
                            if t_txt in mg and not t_txt.startswith("("):
                                idx_mg = i
                                break
                        self.cb_material_gaveta.setCurrentIndex(idx_mg)
                    else:
                        self.cb_material_gaveta.setCurrentIndex(0)

                    # Espessura da gaveta
                    eg = params.get("esp_gaveta_mm", 15.0)
                    idx_eg = self.cb_espessura_gaveta.findText(f"{int(round(float(eg)))} mm")
                    self.cb_espessura_gaveta.setCurrentIndex(idx_eg if idx_eg >= 0 else 0)

                    # Material fita gaveta
                    mfg = params.get("material_fita_gaveta")
                    if mfg and hasattr(self, "cb_material_fita_gaveta"):
                        idx_mfg = 0
                        for i in range(self.cb_material_fita_gaveta.count()):
                            t_txt = self.cb_material_fita_gaveta.itemText(i)
                            if t_txt in mfg and not t_txt.startswith("("):
                                idx_mfg = i
                                break
                        self.cb_material_fita_gaveta.setCurrentIndex(idx_mfg)
                    else:
                        self.cb_material_fita_gaveta.setCurrentIndex(0)

                    # Material fundo gaveta
                    m_fundo_g = params.get("material_fundo_gaveta")
                    if m_fundo_g and hasattr(self, "cb_material_fundo_gaveta"):
                        idx_mfg = 0
                        for i in range(self.cb_material_fundo_gaveta.count()):
                            t_txt = self.cb_material_fundo_gaveta.itemText(i)
                            if t_txt in m_fundo_g and not t_txt.startswith("("):
                                idx_mfg = i
                                break
                        self.cb_material_fundo_gaveta.setCurrentIndex(idx_mfg)
                    else:
                        self.cb_material_fundo_gaveta.setCurrentIndex(0)

                    # Espessura fundo gaveta
                    efg = params.get("esp_fundo_gaveta_mm", 6.0)
                    idx_efg = self.cb_esp_fundo_gaveta.findText(f"{int(round(float(efg)))} mm")
                    self.cb_esp_fundo_gaveta.setCurrentIndex(idx_efg if idx_efg >= 0 else 0)
            
            # Dispara atualizações contextuais de visibilidade/desconto
            if hasattr(self, "_on_tipo_fundo_changed"):
                self._on_tipo_fundo_changed()
            if hasattr(self, "_on_dialog_perfil_modelo_changed"):
                self._on_dialog_perfil_modelo_changed()
            if hasattr(self, "frame_perfil"):
                self.frame_perfil.setVisible(params.get("puxador_tipo") == "perfil")

            # Restaura valores de Marmoraria / Pedra se aplicável
            if "bancada" in str(tipo):
                self.sp_esp_pedra.setValue(int(round(float(params.get("esp_pedra", 20.0)))))
                self.sp_altura_saia.setValue(int(round(float(params.get("altura_saia", 40.0)))))
                self.sp_altura_frontao.setValue(int(round(float(params.get("altura_frontao", 100.0)))))
                self.chk_tem_saia_esq.setChecked(bool(params.get("tem_saia_esq", True)))
                self.chk_tem_saia_dir.setChecked(bool(params.get("tem_saia_dir", True)))

                is_canto_l = tipo in ("bancada_canto_l", "bancada_canto")
                self.lbl_larg_asa.setVisible(is_canto_l)
                self.sp_larg_asa.setVisible(is_canto_l)
                if is_canto_l:
                    self.sp_larg_asa.setValue(int(round(float(params.get("larg_asa", 600.0)))))

                tem_cuba = bool(params.get("has_cuba", (tipo == "bancada_pia")))
                self.lbl_tipo_cuba.setVisible(tem_cuba)
                self.cb_tipo_cuba.setVisible(tem_cuba)
                self.lbl_posicao_cuba.setVisible(tem_cuba)
                self.cb_posicao_cuba.setVisible(tem_cuba)
                self.lbl_tem_torneira.setVisible(tem_cuba)
                self.chk_tem_torneira.setVisible(tem_cuba)

                if tem_cuba:
                    cuba_val = str(params.get("tipo_cuba", "inox_simples")).lower()
                    cuba_map = {"inox_simples": 0, "inox_dupla": 1, "esculpida": 2, "sem_cuba": 3}
                    self.cb_tipo_cuba.setCurrentIndex(cuba_map.get(cuba_val, 0))

                    pos_val = str(params.get("posicao_cuba", "centro")).lower()
                    pos_cuba_map = {"centro": 0, "esquerda": 1, "direita": 2}
                    self.cb_posicao_cuba.setCurrentIndex(pos_cuba_map.get(pos_val, 0))

                    self.chk_tem_torneira.setChecked(bool(params.get("tem_torneira", True)))

                    canto_val = str(params.get("canto_recorte", "arredondado")).lower()
                    self.cb_canto_recorte.setCurrentIndex(1 if "reto" in canto_val else 0)
                    self.chk_tem_area_molhada.setChecked(bool(params.get("tem_area_molhada", True)))

                if hasattr(self, "lbl_canto_recorte"):
                    self.lbl_canto_recorte.setVisible(tem_cuba)
                    self.cb_canto_recorte.setVisible(tem_cuba)
                    self.lbl_tem_area_molhada.setVisible(tem_cuba)
                    self.chk_tem_area_molhada.setVisible(tem_cuba)

            if hasattr(self, "btn_duplicate"):
                self.btn_duplicate.setEnabled(True)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setEnabled(True)
            self.lbl_dyn_status.setText(f"🎯 Modo Dinâmico Ativo!\nEditando: {self._editing_module.name}")
            self.btn_insert.setText("🔄 Atualizar Módulo Dinâmico")
            self.btn_insert.setStyleSheet("background-color: #2e7d32; color: white; font-weight: bold; padding: 12px 14px; font-size: 13px; border-radius: 6px;")
            self.btn_new_mode.setVisible(True)
        else:
            if hasattr(self, "btn_duplicate"):
                self.btn_duplicate.setEnabled(False)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setEnabled(False)
            if self.list_modules.count() > 0:
                self.list_modules.setCurrentRow(0)
            self.lbl_dyn_status.setText("💡 Dica:\nSelecione um módulo no 3D para alterar suas medidas dinamicamente aqui.")
            self.btn_insert.setText("✨ Inserir Novo Módulo")
            self.btn_insert.setStyleSheet("background-color: #1976D2; color: white; font-weight: bold; padding: 12px 14px; font-size: 13px; border-radius: 6px;")
            self.btn_new_mode.setVisible(False)

    def _refresh_perfil_modelos(self, select_id: str | None = None) -> None:
        """Recarrega os modelos de perfil da biblioteca para o combobox."""
        if hasattr(self, "cb_perfil_modelo"):
            fill_profile_combo(self.cb_perfil_modelo, select_id=select_id)
            self._on_dialog_perfil_modelo_changed()

    def _on_dialog_perfil_modelo_changed(self) -> None:
        """Atualiza a prévia do diagrama e a indicação de desconto padrão."""
        if not hasattr(self, "cb_perfil_modelo"):
            return
        pid = self.cb_perfil_modelo.currentData() or "gola"
        p = perfis_lib.get_profile(pid)
        if hasattr(self, "lbl_perfil_diagram"):
            if pid in ("gola", "facetato", "canal_c", "sp7000"):
                self.lbl_perfil_diagram.setPixmap(make_perfil_diagram_pixmap(115, 80, modelo=pid))
            else:
                self.lbl_perfil_diagram.setPixmap(perfis_lib.render_profile_pixmap(p, 115, 80, cotas=True))

        desc = float(p.get("desconto_mm", 35.0))
        if hasattr(self, "cb_altura_perfil") and self.cb_altura_perfil.currentIndex() == 0:
            if hasattr(self, "sp_desconto_perfil"):
                self.sp_desconto_perfil.setValue(int(round(desc)))

    def _open_perfis_manager(self) -> None:
        """Abre o diálogo de gerenciamento/cadastro de perfis 2D com medidas e extrusão."""
        cur_id = self.cb_perfil_modelo.currentData() if hasattr(self, "cb_perfil_modelo") else "gola"
        dlg = PerfilLibraryDialog(parent=self, select_id=cur_id)
        if dlg.exec():
            selected = dlg.selected_id or cur_id
            self._refresh_perfil_modelos(select_id=selected)

    def _sync_desconto_perfil_from_combo(self, text: str) -> None:
        if "padrão" in text.lower():
            pid = self.cb_perfil_modelo.currentData() if hasattr(self, "cb_perfil_modelo") else "gola"
            val = int(round(float(perfis_lib.get_profile(pid).get("desconto_mm", 35.0))))
            self.sp_desconto_perfil.setValue(val)
        else:
            try:
                val = int(text.split()[0])
                self.sp_desconto_perfil.setValue(val)
            except (ValueError, IndexError):
                self.sp_desconto_perfil.setValue(35)

    def _reset_to_new_module(self):
        self._editing_module = None
        self._load_module_values_if_editing()

    def _insert_or_update_module(self):
        """Insere um novo módulo ou atualiza dinamicamente o módulo selecionado no mesmo ponto."""
        current_item = self.list_modules.currentItem()
        if not current_item:
            return
        mod_data = current_item.data(Qt.UserRole)
        if not mod_data:
            return

        tipo = mod_data.get("id", "balcao")
        params = extract_ui_module_params(self, base_params={"tipo": tipo})

        # Orientação e Rotação
        if self._editing_module is None:
            rot_angles = [0.0, 90.0, 180.0, 270.0]
            rot_idx = self.cb_orientacao.currentIndex() if hasattr(self, "cb_orientacao") else 0
            params["rot_z"] = rot_angles[rot_idx]
        else:
            _old_mod_ref = self._editing_module
            _old_cc_params = _old_mod_ref.ext.get("trazomob_module", {})
            params["rot_z"] = float(_old_cc_params.get("rot_z", 0.0) or 0.0) % 360.0

        if tipo == "balcao_misto":
            params["num_gavetas"] = self.sp_qtd_elem.value()
            params["num_portas"] = 2
            params["largura_gaveteiro"] = float(self.sp_largura_gaveteiro.value()) if hasattr(self, "sp_largura_gaveteiro") else float(mod_data.get("largura_gaveteiro", 450.0))
        elif tipo == "balcao_canto_l":
            params["larg_asa"] = float(self.sp_larg_asa.value()) if hasattr(self, "sp_larg_asa") else float(mod_data.get("larg_asa", 550.0))
            params["num_portas"] = 2
        elif mod_data.get("fixed_portas"):
            # Portas fixas: não ler do spinbox — usar o valor definido no catálogo
            params["num_portas"] = int(mod_data.get("num_portas", 2))
            if mod_data.get("has_gavetas"):
                params["num_gavetas"] = self.sp_qtd_elem.value()
        elif mod_data.get("has_gavetas"):
            params["num_gavetas"] = self.sp_qtd_elem.value()
        elif mod_data.get("has_portas"):
            params["num_portas"] = self.sp_qtd_elem.value()
        if mod_data.get("has_prateleiras"):
            params["num_prateleiras"] = self.sp_prateleiras.value()
        if tipo == "nicho":
            params["divisoes_vert"] = self.sp_qtd_elem.value()
            params["divisoes_horiz"] = self.sp_prateleiras.value()

        # Grava parâmetros de travessas (Cozinha Inferiores)
        _IDS_COZINHA_INFERIORES = {
            "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
            "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
        }
        if hasattr(self, "sp_larg_travessa_frontal") and tipo in _IDS_COZINHA_INFERIORES:
            params["travessa_frontal_em_pe"] = self.chk_travessa_em_pe.isChecked()
            params["travessa_traseira_em_pe"] = self.chk_travessa_traseira_em_pe.isChecked()
            params["larg_travessa_frontal_mm"] = float(self.sp_larg_travessa_frontal.value())
            params["larg_travessa_traseira_mm"] = float(self.sp_larg_travessa_traseira.value())
            params["recuo_porta_topo_mm"] = float(self.sp_recuo_porta_pia.value())
            # Compatibilidade legada para chaves antigas do balcao_pia
            params["larg_travessa_mm"] = float(self.sp_larg_travessa_frontal.value())
            params["recuo_porta_pia_mm"] = float(self.sp_recuo_porta_pia.value())

            # Material e espessura das travessas
            if hasattr(self, "cb_material_travessas"):
                mat_tr_txt = self.cb_material_travessas.currentText()
                esp_tr_txt = self.cb_espessura_travessas.currentText()
                esp_mm_caixa = float(params.get("espessura", 15.0))
                esp_tr_mm = esp_mm_caixa if esp_tr_txt.startswith("(") else float(esp_tr_txt.split()[0])
                if mat_tr_txt.startswith("("):
                    params["material_travessas"] = None
                else:
                    params["material_travessas"] = f"{mat_tr_txt} {int(esp_tr_mm)}mm"
                params["esp_travessas_mm"] = None if esp_tr_txt.startswith("(") else esp_tr_mm
                params["espessura_travessas"] = params["esp_travessas_mm"]

            # Fita de borda das travessas
            if hasattr(self, "cb_fita_travessas"):
                fita_modos = ["frontal_1L", "2L", "4L", "sem_fita"]
                f_idx = self.cb_fita_travessas.currentIndex()
                params["fita_travessas_modo"] = fita_modos[f_idx] if 0 <= f_idx < len(fita_modos) else "frontal_1L"

            if hasattr(self, "cb_material_fita_travessas"):
                mat_ftr_txt = self.cb_material_fita_travessas.currentText()
                params["material_fita_travessas"] = None if mat_ftr_txt.startswith("(") else mat_ftr_txt

        # Grava parâmetros de Forno (balcao_forno)
        if tipo == "balcao_forno":
            params["tem_gaveta"] = bool(self.chk_forno_tem_gaveta.isChecked())
            params["alt_gaveta_mm"] = float(self.sp_forno_alt_gaveta.value())

        # Grava parâmetros de Caixa para Geladeira (caixa_geladeira)
        if tipo == "caixa_geladeira":
            params["alt_nicho_geladeira_mm"] = float(self.sp_geladeira_alt_nicho.value())
            is_basc = (self.cb_geladeira_tipo_porta.currentIndex() == 1)
            params["tipo_porta_superior"] = "basculante" if is_basc else "duas_portas"
            params["num_portas"] = 1 if is_basc else 2

        # Grava parâmetros de Aéreo Micro-ondas (aereo_microondas)
        if tipo == "aereo_microondas":
            is_basc_m = (self.cb_micro_tipo_porta.currentIndex() == 0)
            params["tipo_porta_superior"] = "basculante" if is_basc_m else "duas_portas"
            params["num_portas"] = 1 if is_basc_m else 2


        # Grava parâmetros de Caixa de Gaveta
        has_gav = bool(mod_data.get("has_gavetas", False)) or (tipo in ("gaveteiro", "balcao_misto", "torre_quente", "gabinete_banheiro")) or (tipo == "balcao_forno" and params.get("tem_gaveta", True))
        if hasattr(self, "cb_tipo_fundo_gaveta") and has_gav:
            params["tipo_fundo_gaveta"] = "por_baixo" if self.cb_tipo_fundo_gaveta.currentIndex() == 1 else "rasgo"
            params["folga_corredica_mm"] = float(self.sp_folga_corredica.value())

            mat_g_txt = self.cb_material_gaveta.currentText()
            esp_g_txt = self.cb_espessura_gaveta.currentText()
            esp_g_mm = float(esp_g_txt.split()[0])
            params["material_gaveta"] = None if mat_g_txt.startswith("(") else f"{mat_g_txt} {int(esp_g_mm)}mm"
            params["esp_gaveta_mm"] = esp_g_mm

            mat_fg_txt = self.cb_material_fita_gaveta.currentText()
            params["material_fita_gaveta"] = None if mat_fg_txt.startswith("(") else mat_fg_txt

            mat_fd_txt = self.cb_material_fundo_gaveta.currentText()
            esp_fd_txt = self.cb_esp_fundo_gaveta.currentText()
            esp_fd_mm = float(esp_fd_txt.split()[0])
            if mat_fd_txt.startswith("("):
                params["material_fundo_gaveta"] = f"MDF Fundo {int(esp_fd_mm)}mm" if esp_fd_mm <= 6.0 else f"MDF Branco TX {int(esp_fd_mm)}mm"
            else:
                params["material_fundo_gaveta"] = f"{mat_fd_txt} {int(esp_fd_mm)}mm"
            params["esp_fundo_gaveta_mm"] = esp_fd_mm

        # Grava parâmetros de Marmoraria / Bancada de Pedra
        if "bancada" in str(tipo):
            params["esp_pedra"] = float(self.sp_esp_pedra.value())
            params["altura_saia"] = float(self.sp_altura_saia.value())
            params["altura_frontao"] = float(self.sp_altura_frontao.value())
            params["tem_saia_esq"] = bool(self.chk_tem_saia_esq.isChecked())
            params["tem_saia_dir"] = bool(self.chk_tem_saia_dir.isChecked())
            if tipo in ("bancada_canto_l", "bancada_canto"):
                params["larg_asa"] = float(self.sp_larg_asa.value())

            tem_cuba = bool(mod_data.get("has_cuba", (tipo == "bancada_pia")))
            if tem_cuba:
                cuba_tipos = ["inox_simples", "inox_dupla", "esculpida", "sem_cuba"]
                idx_cb = self.cb_tipo_cuba.currentIndex()
                params["tipo_cuba"] = cuba_tipos[idx_cb] if 0 <= idx_cb < len(cuba_tipos) else "inox_simples"

                cuba_posicoes = ["centro", "esquerda", "direita"]
                idx_cp = self.cb_posicao_cuba.currentIndex()
                params["posicao_cuba"] = cuba_posicoes[idx_cp] if 0 <= idx_cp < len(cuba_posicoes) else "centro"

                params["tem_torneira"] = bool(self.chk_tem_torneira.isChecked())
                params["canto_recorte"] = "arredondado" if self.cb_canto_recorte.currentIndex() == 0 else "reto"
                params["raio_canto_mm"] = 20.0 if params["canto_recorte"] == "arredondado" else 0.0
                params["tem_area_molhada"] = bool(self.chk_tem_area_molhada.isChecked())
                params["has_cuba"] = (params["tipo_cuba"] != "sem_cuba")

        # Determina a posição de ancoragem com Alinhamento Inteligente TrazoMob
        if self._editing_module is not None:
            _edit_cc = self._editing_module.ext.get("trazomob_module", {})
            if "rot_matrix_3d" in _edit_cc and isinstance(_edit_cc["rot_matrix_3d"], (list, tuple)):
                params["rot_matrix_3d"] = list(_edit_cc["rot_matrix_3d"])
            # Usa o offset original salvo (âncora pré-rotação).
            _orig_off = _edit_cc.get("offset")
            if _orig_off is not None and len(_orig_off) == 3:
                offset = tuple(_orig_off)
            else:
                offset = self._get_module_position(self._editing_module)
        else:
            # ── HERANÇA DE MEDIDAS DA MESMA CATEGORIA ────────────────────────
            from .module_ribbon import get_module_category, is_compatible_category
            cat_novo = get_module_category(tipo, default_z)
            ref_b = None
            ref_cc = {}
            if ref_mod is not None:
                ref_b = self._get_module_carcass_bounds(ref_mod)
                if hasattr(ref_mod, "ext") and "trazomob_module" in ref_mod.ext:
                    ref_cc = ref_mod.ext["trazomob_module"]
                
                ref_z = ref_b[4] if ref_b is not None else float(ref_cc.get("offset", (0, 0, 0))[2])
                ref_tipo = ref_cc.get("tipo", getattr(ref_mod, "name", ""))
                cat_ref = get_module_category(ref_tipo, ref_z)

                if is_compatible_category(cat_novo, cat_ref):
                    if "profundidade" in ref_cc and float(ref_cc["profundidade"]) > 0:
                        params["profundidade"] = float(ref_cc["profundidade"])
                    elif ref_b is not None:
                        ref_rot = float(ref_cc.get("rot_z", 0.0)) % 360.0
                        if abs(ref_rot) < 45.0 or abs(ref_rot - 180.0) < 45.0:
                            params["profundidade"] = round((ref_b[3] - ref_b[2]) * 1000.0)
                        else:
                            params["profundidade"] = round((ref_b[1] - ref_b[0]) * 1000.0)

                    if "altura" in ref_cc and float(ref_cc["altura"]) > 0:
                        params["altura"] = float(ref_cc["altura"])
                    elif ref_b is not None:
                        params["altura"] = round((ref_b[5] - ref_b[4]) * 1000.0)

                    if "rodape" in ref_cc and cat_novo in ("inferior", "alto"):
                        params["rodape"] = float(ref_cc["rodape"])
                    if ref_b is not None:
                        default_z = ref_b[4]

            novo_L_m = float(params.get("largura", 800.0)) / 1000.0

            # ── VERIFICAÇÃO DE PAREDE SELECIONADA (Prioridade Máxima) ───────────
            from .wall_selection import WallSelectionManager
            wall_mgr = WallSelectionManager.get_instance(self.viewport)
            sel_wf = wall_mgr.selected_wall_face

            if sel_wf is not None and sel_wf.face is not None:
                # Encosta o módulo contra a face da parede selecionada
                norm = sel_wf.normal
                n_dir = QVector3D(norm.x(), norm.y(), 0.0)
                if n_dir.length() > 1e-4:
                    n_dir.normalize()
                    # Rotação para as costas ficarem na parede e frente apontada para dentro (+n_dir)
                    angle_deg = math.degrees(math.atan2(n_dir.y(), n_dir.x())) + 90.0
                    params["rot_z"] = (round(angle_deg / 90.0) * 90.0) % 360.0

                    c_pt = sel_wf.center
                    u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()

                    # Se já houver um móvel de referência na mesma parede/orientação,
                    # posiciona imediatamente ao lado dele ao longo da parede
                    positioned_next_to_ref = False
                    if ref_mod is not None and ref_b is not None:
                        ref_rot = float(ref_cc.get("rot_z", 0.0)) % 360.0
                        if abs(ref_rot - params["rot_z"]) < 1e-2 or abs(abs(ref_rot - params["rot_z"]) - 360.0) < 1e-2:
                            novo_P_m = float(params.get("profundidade", 550.0)) / 1000.0
                            half_diff = (novo_L_m - novo_P_m) * 0.5
                            if abs(ref_rot) < 1e-4:
                                offset = (ref_b[1] + gap_m, ref_b[2], default_z)
                            elif abs(ref_rot - 180.0) < 1e-4:
                                cand_x = ref_b[0] - novo_L_m - gap_m
                                if cand_x < 0.14:
                                    cand_x = ref_b[1] + gap_m
                                offset = (cand_x, ref_b[2], default_z)
                            elif abs(ref_rot - 90.0) < 1e-4:
                                cand_min_y = ref_b[3] + gap_m
                                offset = (ref_b[0] - half_diff, cand_min_y + half_diff, default_z)
                            elif abs(ref_rot - 270.0) < 1e-4:
                                cand_min_y = ref_b[2] - novo_L_m - gap_m
                                if cand_min_y < 0.14:
                                    cand_min_y = ref_b[3] + gap_m
                                offset = (ref_b[0] - half_diff, cand_min_y + half_diff, default_z)
                            else:
                                offset = (ref_b[1] + gap_m, ref_b[2], default_z)
                            positioned_next_to_ref = True

                    if not positioned_next_to_ref:
                        pos_base = c_pt + n_dir * 0.001 - u_dir * (novo_L_m * 0.5)
                        offset = (pos_base.x(), pos_base.y(), default_z)
                else:
                    offset = (sel_wf.center.x(), sel_wf.center.y(), default_z)
            elif ref_mod is not None and align_mode in (0, 1, 2):
                ref_rot_z = 0.0
                if hasattr(ref_mod, "ext") and "trazomob_module" in ref_mod.ext:
                    ref_rot_z = float(ref_mod.ext["trazomob_module"].get("rot_z", 0.0)) % 360.0

                if ref_b is None:
                    ref_b = self._get_module_carcass_bounds(ref_mod)
                if ref_b is not None:
                    novo_P_m = float(params.get("profundidade", 550.0)) / 1000.0
                    half_diff = (novo_L_m - novo_P_m) * 0.5

                    if abs(ref_rot_z) < 1e-4:
                        # Rotação 0° (padrão)
                        if align_mode == 0:    # ➡️ Ao lado (Direita)
                            offset = (ref_b[1] + gap_m, ref_b[2], ref_b[4])
                        elif align_mode == 1:  # ⬅️ Ao lado (Esquerda)
                            offset = (ref_b[0] - novo_L_m - gap_m, ref_b[2], ref_b[4])
                        elif align_mode == 2:  # ⬆️ Sobrepor (Acima)
                            offset = (ref_b[0], ref_b[2], ref_b[5] + gap_m)
                    elif abs(ref_rot_z - 180.0) < 1e-4:
                        # Rotação 180°: Direita do móvel aponta para -X, fundo aponta para -Y
                        if align_mode == 0:    # ➡️ Ao lado (Direita local do móvel)
                            offset = (ref_b[0] - novo_L_m - gap_m, ref_b[2], ref_b[4])
                        elif align_mode == 1:  # ⬅️ Ao lado (Esquerda local do móvel)
                            offset = (ref_b[1] + gap_m, ref_b[2], ref_b[4])
                        elif align_mode == 2:  # ⬆️ Sobrepor (Acima)
                            offset = (ref_b[0], ref_b[2], ref_b[5] + gap_m)
                    elif abs(ref_rot_z - 90.0) < 1e-4:
                        # Rotação 90°: Direita local aponta para +Y
                        if align_mode == 0:    # ➡️ Ao lado (Direita local do móvel)
                            offset = (ref_b[0] - half_diff, (ref_b[3] + gap_m) + half_diff, ref_b[4])
                        elif align_mode == 1:  # ⬅️ Ao lado (Esquerda local do móvel)
                            offset = (ref_b[0] - half_diff, (ref_b[2] - novo_L_m - gap_m) + half_diff, ref_b[4])
                        elif align_mode == 2:  # ⬆️ Sobrepor (Acima)
                            offset = (ref_b[0] - half_diff, ref_b[2] + half_diff, ref_b[5] + gap_m)
                    elif abs(ref_rot_z - 270.0) < 1e-4:
                        # Rotação 270°: Direita local aponta para -Y
                        if align_mode == 0:    # ➡️ Ao lado (Direita local do móvel)
                            offset = (ref_b[0] - half_diff, (ref_b[2] - novo_L_m - gap_m) + half_diff, ref_b[4])
                        elif align_mode == 1:  # ⬅️ Ao lado (Esquerda local do móvel)
                            offset = (ref_b[0] - half_diff, (ref_b[3] + gap_m) + half_diff, ref_b[4])
                        elif align_mode == 2:  # ⬆️ Sobrepor (Acima)
                            offset = (ref_b[0] - half_diff, ref_b[2] + half_diff, ref_b[5] + gap_m)
                    else:
                        offset = (ref_b[1] + gap_m, ref_b[2], ref_b[4])
                else:
                    offset = (0.0, 0.0, default_z)
            new_module_group = CabinetBuilder.build_module_group(params, offset=offset)
            # Se inserido em relação a uma parede selecionada, ajusta a posição exata da traseira do móvel na face
            if self._editing_module is None and sel_wf is not None and sel_wf.face is not None:
                norm = sel_wf.normal
                n_dir = QVector3D(norm.x(), norm.y(), 0.0)
                if n_dir.length() > 1e-4:
                    n_dir.normalize()
                    from .magnetic_drag import get_module_bounds, get_bounds_min_projection
                    from .module_ribbon import get_module_carcass_bounds
                    b = get_module_carcass_bounds(new_module_group) or get_module_bounds(new_module_group)
                    if b is not None:
                        cur_min_n = get_bounds_min_projection(b, n_dir)
                        wall_face_n = QVector3D.dotProduct(sel_wf.center, n_dir)
                        delta_n = (wall_face_n - cur_min_n) + 0.001
                        if abs(delta_n) > 1e-4:
                            shift = n_dir * delta_n
                            targets = getattr(new_module_group, "children", []) or [new_module_group]
                            for t in targets:
                                m_sub = getattr(t, "mesh", None)
                                if m_sub and hasattr(m_sub, "vertices"):
                                    for v in m_sub.vertices:
                                        v.position += shift
                                    m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
                                if getattr(t, "ext", None) is not None:
                                    if "orig_vertices" in t.ext:
                                        t.ext["orig_vertices"] = [orig + shift for orig in t.ext["orig_vertices"]]
                                    if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                                        t.ext["hinge_pivot"] += shift
                            if "trazomob_module" in new_module_group.ext:
                                mod_ext = new_module_group.ext["trazomob_module"]
                                old_off = mod_ext.get("offset", (0.0, 0.0, 0.0))
                                mod_ext["offset"] = (
                                    float(old_off[0]) + float(shift.x()),
                                    float(old_off[1]) + float(shift.y()),
                                    float(old_off[2]) + float(shift.z()),
                                )
    
            # Ao editar módulo existente, preserva o alinhamento espacial e rotação
            if self._editing_module is not None:
                rot_z_eff = float(params.get("rot_z", 0.0))
                from .magnetic_drag import get_module_bounds
                from .module_ribbon import get_module_carcass_bounds, preserve_module_back_alignment
                b_old = get_module_carcass_bounds(self._editing_module) or get_module_bounds(self._editing_module)
                b_new = get_module_carcass_bounds(new_module_group) or get_module_bounds(new_module_group)
                has_3d_rot = isinstance(params.get("rot_matrix_3d"), (list, tuple)) and len(params["rot_matrix_3d"]) == 16
                if has_3d_rot or str(tipo).startswith("peca_"):
                    if b_old and b_new:
                        cx_old = (b_old[0] + b_old[1]) * 0.5
                        cy_old = (b_old[2] + b_old[3]) * 0.5
                        cz_old = (b_old[4] + b_old[5]) * 0.5
                        cx_new = (b_new[0] + b_new[1]) * 0.5
                        cy_new = (b_new[2] + b_new[3]) * 0.5
                        cz_new = (b_new[4] + b_new[5]) * 0.5
                        shift = QVector3D(cx_old - cx_new, cy_old - cy_new, cz_old - cz_new)
                        if shift.length() > 1e-7:
                            targets = getattr(new_module_group, "children", []) or [new_module_group]
                            for t in targets:
                                m_sub = getattr(t, "mesh", None)
                                if m_sub and hasattr(m_sub, "vertices"):
                                    for v in m_sub.vertices:
                                        v.position += shift
                                    m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
                                if getattr(t, "ext", None) is not None:
                                    if "orig_vertices" in t.ext:
                                        t.ext["orig_vertices"] = [orig + shift for orig in t.ext["orig_vertices"]]
                                    if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                                        t.ext["hinge_pivot"] += shift
                elif tipo in ("tampo_engrossado", "bancada_reta", "bancada_pia", "bancada_canto_l", "bancada_ilha"):
                    if b_old and b_new:
                        rot_norm = int(round(rot_z_eff / 90.0) * 90) % 360
                        if rot_norm == 90:
                            dx = b_old[1] - b_new[1]
                            dy = b_old[2] - b_new[2]
                        elif rot_norm == 180:
                            dx = b_old[1] - b_new[1]
                            dy = b_old[3] - b_new[3]
                        elif rot_norm == 270:
                            dx = b_old[0] - b_new[0]
                            dy = b_old[3] - b_new[3]
                        else:
                            dx = b_old[0] - b_new[0]
                            dy = b_old[2] - b_new[2]
                        dz = b_old[5] - b_new[5]
                        shift = QVector3D(dx, dy, dz)
                        if shift.length() > 1e-7:
                            targets = getattr(new_module_group, "children", []) or [new_module_group]
                            for t in targets:
                                m_sub = getattr(t, "mesh", None)
                                if m_sub and hasattr(m_sub, "vertices"):
                                    for v in m_sub.vertices:
                                        v.position += shift
                                    m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
                else:
                    preserve_module_back_alignment(self._editing_module, new_module_group, rot_z_eff)

                b_final = get_module_carcass_bounds(new_module_group) or get_module_bounds(new_module_group)
                if b_final and "trazomob_module" in new_module_group.ext:
                    mod_ext = new_module_group.ext["trazomob_module"]
                    cx_final = (b_final[0] + b_final[1]) * 0.5
                    cy_final = (b_final[2] + b_final[3]) * 0.5
                    cz_final = (b_final[4] + b_final[5]) * 0.5
                    unrot_span = mod_ext.get("_unrot_carcass_span")
                    if isinstance(unrot_span, (list, tuple)) and len(unrot_span) == 6:
                        mod_ext["offset"] = (
                            cx_final - float(unrot_span[0]),
                            cy_final - float(unrot_span[1]),
                            cz_final - float(unrot_span[2]),
                        )
                    else:
                        L_m = float(params.get("largura", 800.0)) / 1000.0
                        P_m = float(params.get("profundidade", 550.0)) / 1000.0
                        mod_ext["offset"] = (
                            cx_final - L_m * 0.5,
                            cy_final - P_m * 0.5,
                            b_final[4],
                        )
    
            # Transação no histórico (Undo/Redo)
            old_mod = self._editing_module
    
            def apply_transaction(scene):
                target_layer = getattr(new_module_group, 'layer', None)
                if target_layer and hasattr(scene, 'layer') and hasattr(scene, 'layers'):
                    if scene.layer(target_layer) is None:
                        from core.layers import Layer
                        scene.layers.append(Layer(target_layer))
                if old_mod is not None and old_mod in scene.groups:
                    scene.groups.remove(old_mod)
                scene.groups.append(new_module_group)
                scene.selection = {new_module_group}
    
            self.viewport.history.execute(SnapshotImport(apply_transaction))
            self.viewport.notify_scene_changed()
        # Enquadra e centraliza a câmera na peça inserida no Viewport
        try:
            lo, hi = self.scene.selection_bounds()
            if lo is not None and hi is not None and hasattr(self.viewport, "camera"):
                self.viewport.camera.fit_box(lo, hi)
        except Exception as e:
            print(f"[TrazoMob] Aviso ao enquadrar peça no viewport: {e}")

        self.viewport.update()

        # Atualiza a referência de último módulo inserido (usado para alinhamento automático do próximo)
        self._last_inserted_module = new_module_group
        was_editing = (old_mod is not None)
        if was_editing:
            self._editing_module = new_module_group
            self._load_module_values_if_editing()
        else:
            # Era inserção de um novo móvel: mantém o diálogo pronto para inserir novos móveis!
            self._editing_module = None
            self._update_align_reference_label()

        # Atualiza tabela de corte
        self._reload_parts()
        if hasattr(self, "lbl_dyn_status"):
            acao_txt = "atualizado" if was_editing else "inserido"
            self.lbl_dyn_status.setText(f"✅ Módulo '{new_module_group.name}' {acao_txt} com sucesso!")

    def _toggle_doors_and_drawers(self):
        """Abre ou fecha portas e gavetas do móvel selecionado no 3D."""
        target = self._editing_module or self._get_reference_module()
        if not target:
            QMessageBox.information(self, "Interação", "Selecione ou insira um móvel no 3D para abrir ou fechar suas portas e gavetas.")
            return
        CabinetInteract.toggle_all(target, self.scene, self.viewport)

    def _on_dialog_open_slider_changed(self, value: int):
        pct = int(value)
        self.lbl_dlg_open_val.setText(f"{pct}%")
        frac = pct / 100.0
        target = self._editing_module or self._get_reference_module()
        if target is not None:
            CabinetInteract.set_module_open_fraction(target, frac, self.scene, self.viewport)
        else:
            CabinetInteract.set_scene_open_fraction(self.scene, frac, self.viewport)

    def _test_module_collisions(self):
        """Testa se há colisões visuais com portas ou gavetas abertas."""
        from .collision import check_opening_collisions
        colisoes = check_opening_collisions(self.scene)
        if colisoes:
            msg = "⚠️ <b>Colisões Detectadas na Abertura:</b><br><br>"
            for c in colisoes[:5]:
                msg += f"• {c['desc']}<br>"
            if len(colisoes) > 5:
                msg += f"<br><i>(+ {len(colisoes) - 5} outras colisões encontradas)</i>"
            QMessageBox.warning(self, "Teste de Colisão de Abertura", msg)
        else:
            QMessageBox.information(
                self,
                "Teste de Colisão de Abertura",
                "✅ <b>Nenhuma colisão detectada!</b><br><br>"
                "Todas as portas e gavetas têm espaço livre para abertura completa sem encostar em puxadores ou cantos."
            )

    def _activate_interact_tool(self):
        """Ativa a ferramenta interativa de clique no 3D e fecha o diálogo."""
        self.close()
        win = self.viewport.window() if hasattr(self.viewport, "window") else None
        key = "plugin_trazomob_CabinetInteractTool"
        if win is not None and hasattr(win, "_activate_plugin_tool") and key in getattr(win, "_tools", {}):
            win._activate_plugin_tool(key)
        elif hasattr(self.viewport, "set_active_tool"):
            self.viewport.set_active_tool(CabinetInteractTool())

    def _apply_dialog_styles(self):
        """Aplica estilo coeso e adaptável (Dark/Light) garantindo excelente contraste nos combos e inputs."""
        c = get_theme_palette()
        self.setStyleSheet(get_dialog_stylesheet(c))

        bg_input = c["bg_input"]
        border_input = c["border_input"]
        border_focus = c["border_focus"]
        text_main = c["text_main"]
        text_title = c["text_title"]
        text_muted = c["text_muted"]
        bg_list = c["bg_list"]
        bg_card = c["bg_card"]
        border_card = c["border_card"]
        hover_card = c["hover_card"]
        select_card = c["select_card"]
        banner_bg = c["banner_bg"]
        banner_text = c["banner_text"]
        banner_border = c["banner_border"]
        btn_step_bg = c["btn_step_bg"]

        # Título da Categoria
        if hasattr(self, "lbl_cat_title"):
            self.lbl_cat_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: {text_title};")

        # Combobox de categoria com destaque
        if hasattr(self, "cb_category"):
            self.cb_category.setStyleSheet(f"""
                QComboBox {{
                    background-color: {bg_input};
                    color: {text_main};
                    border: 1.5px solid {border_input};
                    border-radius: 6px;
                    padding: 5px 10px;
                    font-size: 11px;
                    font-weight: 600;
                    min-width: 190px;
                }}
                QComboBox:hover {{
                    border: 1.5px solid {border_focus};
                }}
                QComboBox::drop-down {{
                    subcontrol-origin: padding;
                    subcontrol-position: top right;
                    width: 24px;
                    border-left: 1px solid {border_input};
                }}
                QComboBox QAbstractItemView {{
                    background-color: {bg_input};
                    color: {text_main};
                    border: 1.5px solid {border_focus};
                    border-radius: 6px;
                    selection-background-color: #2563EB;
                    selection-color: #FFFFFF;
                    padding: 4px;
                }}
                QComboBox QAbstractItemView::item {{
                    min-height: 26px;
                    padding: 4px 8px;
                    color: {text_main};
                }}
                QComboBox QAbstractItemView::item:selected {{
                    background-color: #2563EB;
                    color: #FFFFFF;
                }}
            """)

        # Banner azul TrazoMob
        if hasattr(self, "banner"):
            self.banner.setStyleSheet(
                f"background-color: {banner_bg}; color: {banner_text}; border: 1px solid {banner_border}; "
                f"border-radius: 6px; padding: 8px 12px; font-size: 12px; font-weight: bold;"
            )

        # Grade / Grid Visual com Miniaturas dos Armários
        if hasattr(self, "list_modules"):
            self.list_modules.setStyleSheet(f"""
                QListWidget {{
                    background-color: {bg_list};
                    border: 1px solid {border_input};
                    border-radius: 8px;
                    padding: 6px;
                }}
                QListWidget::item {{
                    background-color: {bg_card};
                    border: 1px solid {border_card};
                    border-radius: 8px;
                    margin: 4px;
                    padding: 6px;
                    color: {text_main};
                    font-weight: 500;
                    font-size: 11px;
                    text-align: center;
                }}
                QListWidget::item:hover {{
                    background-color: {hover_card};
                    border: 1.5px solid {border_focus};
                    color: {border_focus};
                }}
                QListWidget::item:selected {{
                    background-color: {select_card};
                    border: 2px solid {border_focus};
                    color: #FFFFFF;
                    font-weight: bold;
                }}
            """)

        # Card de Identificação do Módulo
        if hasattr(self, "card_info"):
            self.card_info.setStyleSheet(f"background-color: {bg_card}; border: 1px solid {border_card}; border-radius: 6px; padding: 6px;")
        if hasattr(self, "lbl_selected_title"):
            self.lbl_selected_title.setStyleSheet(f"font-size: 13px; font-weight: bold; color: {text_title};")
        if hasattr(self, "lbl_module_desc"):
            self.lbl_module_desc.setStyleSheet(f"color: {text_muted}; font-size: 11px;")

        # Botões de ajuste rápido (+/- 50mm) e Botões de Alinhamento
        step_btn_css = f"background-color: {btn_step_bg}; color: {text_main}; border: 1px solid {border_input}; border-radius: 4px; font-weight: bold; font-size: 11px;"
        for btn in getattr(self, "_step_buttons", []):
            btn.setStyleSheet(step_btn_css)
        for btn in getattr(self, "_align_buttons", []):
            btn.setStyleSheet(step_btn_css)

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



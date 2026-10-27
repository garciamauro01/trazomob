# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Painel lateral (Dock Widget) de edição de módulos dinâmicos do TrazoMob."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QIcon, QVector3D
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from core.group import Group
from core.history import SnapshotImport
from core.mesh import Mesh

from .builder import CabinetBuilder, RotateTrazoMobModuleCommand
from .catalog import MODULE_CATALOG
from .icons import (
    get_module_thumbnail,
    make_cabinet_icon,
    make_trazomob_icon,
    make_interact_icon,
    make_rotate_ccw_icon,
    make_rotate_cw_icon,
    make_perfil_diagram_pixmap,
)
from .interact import CabinetInteract, CabinetInteractTool
from .wall_builder import WallBuilderTool
from . import perfis as perfis_lib
from .perfis_editor import PerfilLibraryDialog, fill_profile_combo
from .sidebar_wall_controller import SidebarWallMixin
from .sidebar_collapsible import CollapsibleSection
from .param_mapper import extract_ui_module_params, populate_ui_from_module


class TrazoMobSidebarPanel(QWidget, SidebarWallMixin):
    """Painel de encaixe da barra lateral para edição dinâmica de módulos do TrazoMob."""

    def __init__(self, app, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._updating_ui = False
        self._selected_module: Group | None = None
        self._selected_wall: Group | None = None

        self._dock: QDockWidget | None = None
        self._form_built: bool = False

        self._build_ui()

        # Conecta sinal de atualização de cena se disponível
        viewport = self._get_viewport()
        if viewport is not None and hasattr(viewport, "sceneVersionChanged"):
            viewport.sceneVersionChanged.connect(self.on_scene_changed)

    def set_dock(self, dock: QDockWidget) -> None:
        """Associa o QDockWidget hospedeiro a este painel lateral."""
        self._dock = dock

    def focus_panel(self) -> None:
        """Traz a aba do TrazoMob para o primeiro plano na barra lateral."""
        self._ensure_form_built()
        if hasattr(self._app, "show_panel") and self._dock is not None:
            self._app.show_panel(self._dock)
        elif self._dock is not None:
            self._dock.show()
            self._dock.raise_()

    def _get_window(self):
        return getattr(self._app, "window", None) or getattr(self._app, "_window", None)

    def _get_viewport(self):
        vp = getattr(self._app, "viewport", None)
        if vp is not None:
            return vp
        win = self._get_window()
        return getattr(win, "viewport", None)

    def _get_scene(self):
        vp = self._get_viewport()
        return getattr(vp, "scene", None)

    def _build_ui(self) -> None:
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(6, 6, 6, 6)
        self._main_layout.setSpacing(6)

        # Cabeçalho de Status Compacto e Elegante (construído de imediato — < 5ms)
        self.card_header = QFrame()
        self.card_header.setStyleSheet(
            "QFrame { background-color: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 2px 4px; }"
        )
        h_head = QVBoxLayout(self.card_header)
        h_head.setContentsMargins(4, 3, 4, 3)
        h_head.setSpacing(2)

        self.lbl_title = QLabel("🪵 TrazoMob — Módulos")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 11px; color: palette(text);")
        h_head.addWidget(self.lbl_title)

        self.lbl_status = QLabel("💡 Selecione uma parede ou um módulo no 3D para editar.")
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-size: 10px; color: palette(placeholder-text);")
        h_head.addWidget(self.lbl_status)

        self._main_layout.addWidget(self.card_header)

        # ── Card de Alinhamento e Centralização Rápida (quando múltiplos objetos estão selecionados) ──
        self.card_align = QFrame()
        self.card_align.setStyleSheet(
            "QFrame { background-color: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 4px; }"
        )
        l_align = QVBoxLayout(self.card_align)
        l_align.setContentsMargins(4, 4, 4, 4)
        l_align.setSpacing(4)

        self.lbl_align_info = QLabel("🎯 <b>Centralizar Objeto Selecionado</b>")
        self.lbl_align_info.setStyleSheet("color: palette(text); font-size: 11px;")
        l_align.addWidget(self.lbl_align_info)

        self.lbl_align_desc = QLabel("Selecione 2 objetos com Ctrl para centralizar.")
        self.lbl_align_desc.setStyleSheet("font-size: 10px; color: palette(placeholder-text);")
        self.lbl_align_desc.setWordWrap(True)
        l_align.addWidget(self.lbl_align_desc)

        h_align_xy = QHBoxLayout()
        h_align_xy.setSpacing(4)
        self.btn_center_xy = QPushButton("✛ Centro (XY)")
        self.btn_center_xy.setToolTip("Centraliza no plano horizontal (Largura e Profundidade)")
        self.btn_center_xy.setStyleSheet("QPushButton { font-weight: bold; padding: 6px; border-radius: 4px; font-size: 11px; }")
        self.btn_center_xy.clicked.connect(lambda: self._trigger_center("xy"))
        h_align_xy.addWidget(self.btn_center_xy)

        self.btn_center_x = QPushButton("↔ Largura (X)")
        self.btn_center_x.setToolTip("Centraliza apenas no eixo X (Largura)")
        self.btn_center_x.setStyleSheet("QPushButton { padding: 6px; border-radius: 4px; font-size: 11px; }")
        self.btn_center_x.clicked.connect(lambda: self._trigger_center("x"))
        h_align_xy.addWidget(self.btn_center_x)
        l_align.addLayout(h_align_xy)

        h_align_yz = QHBoxLayout()
        h_align_yz.setSpacing(4)
        self.btn_center_y = QPushButton("↕ Profundidade (Y)")
        self.btn_center_y.setToolTip("Centraliza apenas no eixo Y (Profundidade)")
        self.btn_center_y.setStyleSheet("QPushButton { padding: 6px; border-radius: 4px; font-size: 11px; }")
        self.btn_center_y.clicked.connect(lambda: self._trigger_center("y"))
        h_align_yz.addWidget(self.btn_center_y)

        self.btn_center_z = QPushButton("⬍ Altura (Z)")
        self.btn_center_z.setToolTip("Centraliza apenas no eixo Z (Altura)")
        self.btn_center_z.setStyleSheet("QPushButton { padding: 6px; border-radius: 4px; font-size: 11px; }")
        self.btn_center_z.clicked.connect(lambda: self._trigger_center("z"))
        h_align_yz.addWidget(self.btn_center_z)
        l_align.addLayout(h_align_yz)

        self.card_align.setVisible(False)
        self._main_layout.addWidget(self.card_align)

        # ── Card de Abertura Dinâmica e Cinemática 3D (Estilo Promob) ──
        self.card_interact = QFrame()
        self.card_interact.setStyleSheet(
            "QFrame { background-color: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 4px; }"
        )
        l_interact = QVBoxLayout(self.card_interact)
        l_interact.setContentsMargins(4, 4, 4, 4)
        l_interact.setSpacing(4)

        h_dyn_title = QHBoxLayout()
        lbl_dyn_icon = QLabel("🚪 <b>Abertura Dinâmica 3D</b>")
        lbl_dyn_icon.setStyleSheet("color: palette(text); font-size: 11px;")
        h_dyn_title.addWidget(lbl_dyn_icon)
        h_dyn_title.addStretch()

        self.btn_dyn_check_col = QPushButton("⚠️ Testar Colisões")
        self.btn_dyn_check_col.setToolTip("Verifica se alguma gaveta ou porta aberta bate em puxadores, cantos ou paredes")
        self.btn_dyn_check_col.setStyleSheet(
            "QPushButton { background-color: #f59e0b; color: white; font-weight: bold; padding: 2px 6px; font-size: 10px; border-radius: 3px; }"
            "QPushButton:hover { background-color: #d97706; }"
        )
        self.btn_dyn_check_col.clicked.connect(self._check_dynamic_collisions)
        h_dyn_title.addWidget(self.btn_dyn_check_col)
        l_interact.addLayout(h_dyn_title)

        # Slider contínuo de 0 a 100% de abertura
        h_slider = QHBoxLayout()
        h_slider.setSpacing(6)
        self.sl_open_dyn = QSlider(Qt.Horizontal)
        self.sl_open_dyn.setRange(0, 100)
        self.sl_open_dyn.setValue(0)
        self.sl_open_dyn.setToolTip("Arraste para abrir ou fechar as portas e gavetas progressivamente em tempo real")
        self.sl_open_dyn.valueChanged.connect(self._on_dynamic_slider_changed)
        h_slider.addWidget(self.sl_open_dyn, 1)

        self.lbl_open_pct = QLabel("0%")
        self.lbl_open_pct.setStyleSheet("font-weight: bold; font-size: 10px; min-width: 32px;")
        h_slider.addWidget(self.lbl_open_pct)
        l_interact.addLayout(h_slider)

        # Botões rápidos: Fechar (0%), 50%, Abrir Tudo (100%), e Ferramenta Interativa de Clique (I)
        h_quick_btns = QHBoxLayout()
        h_quick_btns.setSpacing(3)
        btn_close_all = QPushButton("Fechar")
        btn_close_all.setStyleSheet("font-size: 10px; padding: 3px;")
        btn_close_all.clicked.connect(lambda: self.sl_open_dyn.setValue(0))
        h_quick_btns.addWidget(btn_close_all)

        btn_half_all = QPushButton("50%")
        btn_half_all.setStyleSheet("font-size: 10px; padding: 3px;")
        btn_half_all.clicked.connect(lambda: self.sl_open_dyn.setValue(50))
        h_quick_btns.addWidget(btn_half_all)

        btn_open_all = QPushButton("100%")
        btn_open_all.setStyleSheet("font-size: 10px; padding: 3px;")
        btn_open_all.clicked.connect(lambda: self.sl_open_dyn.setValue(100))
        h_quick_btns.addWidget(btn_open_all)

        btn_tool_click = QPushButton("👆 Clicar no 3D")
        btn_tool_click.setToolTip("Ativa o cursor interativo para clicar individualmente em qualquer porta ou gaveta")
        btn_tool_click.setStyleSheet("font-size: 10px; font-weight: bold; padding: 3px;")
        btn_tool_click.clicked.connect(self._activate_interact_tool)
        h_quick_btns.addWidget(btn_tool_click)
        l_interact.addLayout(h_quick_btns)

        # Banner de resultado de colisão
        self.lbl_collision_warn = QLabel("")
        self.lbl_collision_warn.setStyleSheet(
            "background-color: #fef2f2; color: #b91c1c; font-size: 10px; font-weight: bold; "
            "padding: 4px; border: 1px solid #fecaca; border-radius: 3px;"
        )
        self.lbl_collision_warn.setWordWrap(True)
        self.lbl_collision_warn.setVisible(False)
        l_interact.addWidget(self.lbl_collision_warn)

        self._main_layout.addWidget(self.card_interact)

        # ── Card de Edição de Iluminação (quando uma luz for clicada no 3D) ──
        self.card_luz = QFrame()
        self.card_luz.setStyleSheet(
            "QFrame { background-color: palette(base); border: 1px solid #0284C7; border-radius: 5px; padding: 6px; }"
        )
        l_luz = QVBoxLayout(self.card_luz)
        l_luz.setContentsMargins(4, 4, 4, 4)
        l_luz.setSpacing(6)

        lbl_luz_header = QLabel("💡 <b>Edição de Luz (3D)</b>")
        lbl_luz_header.setStyleSheet("color: #0284C7; font-size: 11px;")
        l_luz.addWidget(lbl_luz_header)

        self.lbl_luz_nome = QLabel("Luz Selecionada")
        self.lbl_luz_nome.setStyleSheet("font-weight: bold; font-size: 11px; color: palette(text);")
        l_luz.addWidget(self.lbl_luz_nome)

        # Botão Ligar/Desligar
        self.btn_luz_toggle = QPushButton("Desligar Luz")
        self.btn_luz_toggle.setStyleSheet("QPushButton { background-color: #059669; color: white; font-weight: bold; padding: 5px; border-radius: 4px; }")
        self.btn_luz_toggle.clicked.connect(self._toggle_light_on_off)
        l_luz.addWidget(self.btn_luz_toggle)

        form_luz = QFormLayout()
        form_luz.setContentsMargins(0, 2, 0, 2)
        form_luz.setSpacing(5)

        # Tipo de Distribuição da Luz (Omni 360° vs Spot Direcionado)
        self.cb_luz_tipo = QComboBox()
        self.cb_luz_tipo.addItem("💡 Omni (Todas as direções 360°)", "point")
        self.cb_luz_tipo.addItem("🎯 Spot Direcional (Foco para baixo)", "spot")
        self.cb_luz_tipo.currentIndexChanged.connect(self._on_sidebar_light_tipo_changed)
        form_luz.addRow("Distribuição:", self.cb_luz_tipo)

        # Potência
        self.sp_luz_power = QSpinBox()
        self.sp_luz_power.setRange(10, 10000)
        self.sp_luz_power.setSingleStep(50)
        self.sp_luz_power.setSuffix(" W")
        self.sp_luz_power.valueChanged.connect(self._on_sidebar_light_prop_changed)
        form_luz.addRow("Potência:", self.sp_luz_power)

        # Kelvin
        h_k = QHBoxLayout()
        self.sl_luz_kelvin = QSlider(Qt.Horizontal)
        self.sl_luz_kelvin.setRange(2200, 6500)
        self.sl_luz_kelvin.setSingleStep(100)
        self.sl_luz_kelvin.valueChanged.connect(self._on_sidebar_light_prop_changed)
        h_k.addWidget(self.sl_luz_kelvin, 1)
        self.lbl_luz_kelvin = QLabel("2700K")
        self.lbl_luz_kelvin.setStyleSheet("font-weight: bold; font-size: 10px;")
        h_k.addWidget(self.lbl_luz_kelvin)
        form_luz.addRow("Kelvin:", h_k)

        # Altura Z
        h_z = QHBoxLayout()
        self.sp_luz_z = QDoubleSpinBox()
        self.sp_luz_z.setRange(-10.0, 50.0)
        self.sp_luz_z.setSingleStep(0.05)
        self.sp_luz_z.setDecimals(2)
        self.sp_luz_z.setSuffix(" m")
        self.sp_luz_z.valueChanged.connect(self._on_sidebar_light_z_changed)
        h_z.addWidget(self.sp_luz_z, 1)

        btn_z_up = QPushButton("▲")
        btn_z_up.setToolTip("Subir 10cm (+0.10m)")
        btn_z_up.setFixedWidth(24)
        btn_z_up.clicked.connect(lambda: self.sp_luz_z.setValue(self.sp_luz_z.value() + 0.10))
        h_z.addWidget(btn_z_up)

        btn_z_dn = QPushButton("▼")
        btn_z_dn.setToolTip("Descer 10cm (-0.10m)")
        btn_z_dn.setFixedWidth(24)
        btn_z_dn.clicked.connect(lambda: self.sp_luz_z.setValue(self.sp_luz_z.value() - 0.10))
        h_z.addWidget(btn_z_dn)
        form_luz.addRow("Altura (Z):", h_z)

        # Ângulo do facho (Spot)
        self.row_luz_ang = QWidget()
        l_ang = QHBoxLayout(self.row_luz_ang)
        l_ang.setContentsMargins(0, 0, 0, 0)
        self.sp_luz_ang = QSpinBox()
        self.sp_luz_ang.setRange(10, 120)
        self.sp_luz_ang.setSuffix("°")
        self.sp_luz_ang.valueChanged.connect(self._on_sidebar_light_prop_changed)
        l_ang.addWidget(self.sp_luz_ang)
        form_luz.addRow("Ângulo Facho:", self.row_luz_ang)

        l_luz.addLayout(form_luz)

        # Botão Mirar Spot no 3D
        self.btn_luz_aim = QPushButton("🎯 Mirar Spot no 3D")
        self.btn_luz_aim.setStyleSheet("QPushButton { background-color: #0284C7; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }")
        self.btn_luz_aim.clicked.connect(self._aim_selected_light)
        l_luz.addWidget(self.btn_luz_aim)

        # Botões de Ação: Mover e Excluir
        h_act = QHBoxLayout()
        self.btn_luz_move = QPushButton("📍 Reposicionar")
        self.btn_luz_move.setStyleSheet("QPushButton { background-color: #2563EB; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }")
        self.btn_luz_move.clicked.connect(self._reposition_selected_light)
        h_act.addWidget(self.btn_luz_move)

        self.btn_luz_delete = QPushButton("🗑️ Excluir")
        self.btn_luz_delete.setStyleSheet("QPushButton { background-color: #DC2626; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }")
        self.btn_luz_delete.clicked.connect(self._delete_selected_light)
        h_act.addWidget(self.btn_luz_delete)
        l_luz.addLayout(h_act)

        # Botão para limpar/excluir todas as luzes do projeto
        self.btn_luz_clear_all = QPushButton("🧹 Remover Todas as Luzes")
        self.btn_luz_clear_all.setToolTip("Exclui todas as luminárias (tanto objetos 3D quanto luzes legadas salvas no documento)")
        self.btn_luz_clear_all.setStyleSheet("QPushButton { background-color: #4B5563; color: #F3F4F6; font-size: 10px; padding: 4px; border-radius: 4px; margin-top: 4px; }")
        self.btn_luz_clear_all.clicked.connect(self._delete_all_lights)
        l_luz.addWidget(self.btn_luz_clear_all)

        self.card_luz.setVisible(False)
        self._main_layout.addWidget(self.card_luz)
        self._selected_light_idx: int | None = None
        self._selected_light_grp: Group | None = None

    def _ensure_form_built(self) -> None:
        """Constrói os ~100 widgets do formulário sob demanda na primeira interação."""
        if self._form_built:
            return
        self._form_built = True
        main_layout = self._main_layout

        # ── Card: Construtor de Paredes (Design de Interiores) ───────────────────
        self.card_paredes = QFrame()
        self.card_paredes.setStyleSheet(
            "QFrame { background-color: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 2px 4px; }"
        )
        l_paredes = QVBoxLayout(self.card_paredes)
        l_paredes.setContentsMargins(4, 4, 4, 4)
        l_paredes.setSpacing(3)

        lbl_par_title = QLabel("🧱 <b>Construtor de Paredes</b>")
        lbl_par_title.setStyleSheet("color: palette(text); font-size: 11px;")
        l_paredes.addWidget(lbl_par_title)

        form_paredes = QFormLayout()
        form_paredes.setContentsMargins(0, 2, 0, 2)
        form_paredes.setSpacing(4)

        # --- Segmento e Comprimento Paramétrico da Parede ---
        self.cb_parede_segmento = QComboBox()
        self.cb_parede_segmento.setToolTip("Selecione qual parede do cômodo você deseja consultar ou alterar o comprimento.")
        self.cb_parede_segmento.currentIndexChanged.connect(self._on_wall_segment_combobox_changed)
        form_paredes.addRow("Parede / Seg:", self.cb_parede_segmento)

        self.sp_parede_comprimento = QSpinBox()
        self.sp_parede_comprimento.setRange(200, 50000)
        self.sp_parede_comprimento.setValue(3000)
        self.sp_parede_comprimento.setSuffix(" mm")
        self.sp_parede_comprimento.setSingleStep(50)
        self.sp_parede_comprimento.setToolTip("Comprimento desta parede. Altere a medida em milímetros e clique em 'Atualizar Parede Selecionada'.")
        form_paredes.addRow("Comprimento:", self.sp_parede_comprimento)

        self.sp_parede_altura = QSpinBox()
        self.sp_parede_altura.setRange(1000, 6000)
        self.sp_parede_altura.setValue(2600)
        self.sp_parede_altura.setSuffix(" mm")
        self.sp_parede_altura.setSingleStep(50)
        form_paredes.addRow("Pé-Direito:", self.sp_parede_altura)

        self.sp_parede_esp = QSpinBox()
        self.sp_parede_esp.setRange(50, 500)
        self.sp_parede_esp.setValue(150)
        self.sp_parede_esp.setSuffix(" mm")
        self.sp_parede_esp.setSingleStep(10)
        form_paredes.addRow("Espessura:", self.sp_parede_esp)

        self.cb_parede_alinhar = QComboBox()
        self.cb_parede_alinhar.addItems([
            "Face Interna (Medida Livre)",
            "Centro da Parede",
            "Face Externa",
        ])
        form_paredes.addRow("Alinhamento:", self.cb_parede_alinhar)

        self.chk_parede_todas = QCheckBox("Aplicar a todas as paredes")
        self.chk_parede_todas.setChecked(True)
        self.chk_parede_todas.setToolTip(
            "Se marcado, altera o pé-direito de todas as paredes interligadas do cômodo.\n"
            "Se desmarcado, altera somente a parede selecionada."
        )
        form_paredes.addRow("", self.chk_parede_todas)

        self.chk_parede_teto = QCheckBox("Gerar Teto / Forro ao fechar")
        from PySide6.QtCore import QSettings
        _saved_teto = QSettings().value("trazomob_wall/gerar_teto", False, type=bool)
        self.chk_parede_teto.setChecked(_saved_teto)
        def _on_teto_toggled(chk):
            QSettings().setValue("trazomob_wall/gerar_teto", bool(chk))
        self.chk_parede_teto.toggled.connect(_on_teto_toggled)
        self.chk_parede_teto.setToolTip(
            "Se marcado, cria automaticamente a laje/forro de teto no pé-direito ao fechar o perímetro de paredes."
        )
        form_paredes.addRow("", self.chk_parede_teto)

        # --- Réguas Paramétricas de Alturas (Linhas-Guia) ---
        from .wall_guides import WallGuideRulerManager, DEFAULT_RULER_PRESETS
        self._ruler_mgr = WallGuideRulerManager.get_instance()

        self.cb_regua_ambiente = QComboBox()
        self.cb_regua_ambiente.addItems(list(self._ruler_mgr.presets.keys()))
        self.cb_regua_ambiente.setCurrentText(self._ruler_mgr.active_preset_name)
        def _on_ruler_changed(preset_name):
            if preset_name:
                self._ruler_mgr.set_active_preset(preset_name)
                vp = self._get_viewport()
                if vp:
                    vp.update()
        self.cb_regua_ambiente.currentTextChanged.connect(_on_ruler_changed)

        self.btn_edit_reguas = QPushButton("⚙️")
        self.btn_edit_reguas.setFixedWidth(28)
        self.btn_edit_reguas.setToolTip("Configurar, criar e editar réguas e alturas personalizadas...")
        def _open_ruler_dialog():
            from .ruler_editor_dialog import RulerEditorDialog
            dlg = RulerEditorDialog(parent=self.window(), ruler_mgr=self._ruler_mgr)
            if dlg.exec():
                # Atualiza a lista de presets na combobox
                self.cb_regua_ambiente.blockSignals(True)
                self.cb_regua_ambiente.clear()
                self.cb_regua_ambiente.addItems(list(self._ruler_mgr.presets.keys()))
                self.cb_regua_ambiente.setCurrentText(self._ruler_mgr.active_preset_name)
                self.cb_regua_ambiente.blockSignals(False)
                vp = self._get_viewport()
                if vp:
                    vp.update()
        self.btn_edit_reguas.clicked.connect(_open_ruler_dialog)

        h_ruler_row = QHBoxLayout()
        h_ruler_row.setContentsMargins(0, 0, 0, 0)
        h_ruler_row.setSpacing(4)
        h_ruler_row.addWidget(self.cb_regua_ambiente)
        h_ruler_row.addWidget(self.btn_edit_reguas)

        form_paredes.addRow("📏 Régua Alturas:", h_ruler_row)

        self.chk_regua_visivel = QCheckBox("Exibir Linhas-Guia e Snap 3D")
        self.chk_regua_visivel.setChecked(self._ruler_mgr.visible)
        def _on_ruler_toggle(checked):
            self._ruler_mgr.visible = bool(checked)
            self._ruler_mgr.snap_enabled = bool(checked)
            self._ruler_mgr.save_preferences()
            vp = self._get_viewport()
            if vp:
                vp.update()
        self.chk_regua_visivel.toggled.connect(_on_ruler_toggle)
        form_paredes.addRow("", self.chk_regua_visivel)

        self.chk_regua_labels = QCheckBox("Exibir Rótulos das Guias (Texto)")
        self.chk_regua_labels.setChecked(self._ruler_mgr.show_labels)
        def _on_ruler_labels_toggle(checked):
            self._ruler_mgr.show_labels = bool(checked)
            self._ruler_mgr.save_preferences()
            vp = self._get_viewport()
            if vp:
                vp.update()
        self.chk_regua_labels.toggled.connect(_on_ruler_labels_toggle)
        form_paredes.addRow("", self.chk_regua_labels)

        l_paredes.addLayout(form_paredes)

        self.btn_toggle_wall_tool = QPushButton("✏️ Construir Paredes no 3D")
        self.btn_toggle_wall_tool.setCheckable(True)
        self.btn_toggle_wall_tool.setStyleSheet(
            "QPushButton { background-color: palette(highlight); color: palette(highlighted-text); font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { opacity: 0.9; }"
            "QPushButton:checked { background-color: palette(dark); border: 2px solid palette(highlight); }"
        )
        self.btn_toggle_wall_tool.clicked.connect(self._toggle_wall_builder)
        l_paredes.addWidget(self.btn_toggle_wall_tool)

        self.btn_apply_wall = QPushButton("🔄 Atualizar Parede Selecionada")
        self.btn_apply_wall.setVisible(False)
        self.btn_apply_wall.setStyleSheet(
            "QPushButton { background-color: palette(highlight); color: palette(highlighted-text); font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { opacity: 0.9; }"
        )
        self.btn_apply_wall.clicked.connect(self._apply_wall_changes)
        l_paredes.addWidget(self.btn_apply_wall)

        # Botão Inteligente: Encaixar Bancada / Tampo sobre Balcões desta Parede
        self.btn_encaixar_bancada = QPushButton("🪨 Encaixar Bancada sobre Balcões")
        self.btn_encaixar_bancada.setVisible(False)
        self.btn_encaixar_bancada.setToolTip("Cria e encaixa automaticamente uma bancada de pedra/tampo cobrindo com precisão todos os balcões encostados nesta parede.")
        self.btn_encaixar_bancada.setStyleSheet(
            "QPushButton { background-color: #0284C7; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0369A1; }"
        )
        self.btn_encaixar_bancada.clicked.connect(self._on_encaixar_bancada_sobre_balcoes)
        l_paredes.addWidget(self.btn_encaixar_bancada)

        # Bot?o Inteligente: Eleva??o T?cnica 2D da Parede com Cotas
        self.btn_elevacao_parede = QPushButton("?? Eleva??o 2D com Cotas")
        self.btn_elevacao_parede.setVisible(False)
        self.btn_elevacao_parede.setToolTip("Abre a vista ortogonal t?cnica 2D da parede com todos os m?veis e cotas milim?tricas detalhadas.")
        self.btn_elevacao_parede.setStyleSheet(
            "QPushButton { background-color: #4338CA; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3730A3; }"
        )
        self.btn_elevacao_parede.clicked.connect(self._on_abrir_elevacao_parede)
        l_paredes.addWidget(self.btn_elevacao_parede)

        # Bot?o Inteligente: R?gua de Fechamento / Arremate Autom?tico de Canto
        self.btn_fechar_vao = QPushButton("?? Inserir Arremate de Canto")
        self.btn_fechar_vao.setVisible(False)
        self.btn_fechar_vao.setToolTip("Detecta a folga residual entre o ?ltimo m?dulo e a parede de canto e insere uma r?gua de arremate sob medida.")
        self.btn_fechar_vao.setStyleSheet(
            "QPushButton { background-color: #0D9488; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0F766E; }"
        )
        self.btn_fechar_vao.clicked.connect(self._on_fechar_vao_canto)
        l_paredes.addWidget(self.btn_fechar_vao)



        # Botão direto para ocultar a parede selecionada
        self.btn_hide_selected_wall = QPushButton("👁️ Ocultar Parede Selecionada")
        self.btn_hide_selected_wall.setVisible(False)
        self.btn_hide_selected_wall.setStyleSheet(
            "QPushButton { background-color: #64748B; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #475569; }"
        )
        def _on_click_hide_selected_wall():
            w = getattr(self, "_selected_wall", None)
            vp = self._get_viewport()
            if w and vp and hasattr(vp, "history"):
                from core.history import HideCommand
                from .wall_selection import WallSelectionManager

                params = getattr(w, "ext", {}).get("trazomob_wall") if isinstance(getattr(w, "ext", None), dict) else {}
                face_map = params.get("face_segment_map", {}) if isinstance(params, dict) else {}
                seg_idx = params.get("selected_segment") if isinstance(params, dict) else None

                targets_to_hide = []
                if seg_idx is not None and face_map and hasattr(w, "mesh") and hasattr(w.mesh, "faces"):
                    seg_faces = [w.mesh.faces[f_idx] for f_idx, s in face_map.items() if s == seg_idx and f_idx < len(w.mesh.faces)]
                    targets_to_hide.extend(seg_faces)

                    # Coleta arestas que só pertencem a essas faces (sem faces visíveis restantes)
                    remaining_visible = set(f for f in w.mesh.faces if f not in seg_faces and not f.attrs.get("hidden"))
                    for e in getattr(w.mesh, "edges", []):
                        if any(f in seg_faces for f in e.faces) and not any(f in remaining_visible for f in e.faces):
                            targets_to_hide.append(e)

                # Se não mapeou faces do segmento, oculta o grupo inteiro
                if not targets_to_hide:
                    targets_to_hide = [w]

                vp.history.execute(HideCommand(targets_to_hide, hidden=True))
                if hasattr(vp, "scene"):
                    vp.scene.selection.discard(w)
                WallSelectionManager.get_instance().clear_selection()
                self._selected_wall = None
                self.btn_apply_wall.setVisible(False)
                self.btn_hide_selected_wall.setVisible(False)
                vp.update()
                if hasattr(vp, "flash_status"):
                    if len(targets_to_hide) == 1 and targets_to_hide[0] is w:
                        vp.flash_status("👁️ Grupo de paredes ocultado.")
                    else:
                        vp.flash_status(f"👁️ Parede #{seg_idx + 1} ocultada.")
        self.btn_hide_selected_wall.clicked.connect(_on_click_hide_selected_wall)
        l_paredes.addWidget(self.btn_hide_selected_wall)

        self.btn_lock_walls_floor = QPushButton("🔒 Trava de Posição: ATIVA")
        self.btn_lock_walls_floor.setCheckable(True)
        self.btn_lock_walls_floor.setChecked(True)
        self.btn_lock_walls_floor.setToolTip("Impede mover paredes e piso acidentalmente. Snaps, cotas e medições continuam funcionando normalmente!")
        self.btn_lock_walls_floor.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white; font-weight: bold; padding: 6px; border-radius: 4px; border: 1px solid #1b5e20; }"
            "QPushButton:hover { background-color: #388e3c; }"
            "QPushButton:!checked { background-color: palette(button); color: palette(text); border: 1px solid palette(mid); font-weight: normal; }"
        )
        self.btn_lock_walls_floor.clicked.connect(self._toggle_walls_floor_lock)
        l_paredes.addWidget(self.btn_lock_walls_floor)

        # Botão de reexibir todas as paredes/tetos ocultos
        self.btn_unhide_all_walls = QPushButton("👁️ Reexibir Paredes e Tetos")
        self.btn_unhide_all_walls.setStyleSheet(
            "QPushButton { background-color: palette(button); color: palette(text); padding: 5px; border-radius: 4px; border: 1px solid palette(mid); }"
            "QPushButton:hover { background-color: palette(midlight); }"
        )
        def _on_click_unhide_all():
            vp = self._get_viewport()
            if vp and hasattr(vp, "scene") and hasattr(vp, "history"):
                arch_to_show = []
                for g in getattr(vp.scene, "groups", []):
                    ext = getattr(g, "ext", {})
                    if isinstance(ext, dict) and ("trazomob_wall" in ext or "trazomob_ceiling" in ext):
                        if getattr(g, "hidden", False) or vp.scene.entity_hidden(g):
                            arch_to_show.append(g)
                if arch_to_show:
                    from core.history import HideCommand
                    vp.history.execute(HideCommand(arch_to_show, hidden=False))
                    vp.update()
                    if hasattr(vp, "flash_status"):
                        vp.flash_status(f"👁️ {len(arch_to_show)} elemento(s) reexibido(s).")
                else:
                    if hasattr(vp, "flash_status"):
                        vp.flash_status("Nenhuma parede ou teto oculto.")
        self.btn_unhide_all_walls.clicked.connect(_on_click_unhide_all)
        l_paredes.addWidget(self.btn_unhide_all_walls)

        main_layout.addWidget(self.card_paredes)

        # Scroll com o Formulário de Edição
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)

        self.form_container = QWidget()
        self.form_vbox = QVBoxLayout(self.form_container)
        self.form_vbox.setContentsMargins(0, 2, 0, 2)
        self.form_vbox.setSpacing(6)

        # Seções Colapsáveis Modernas (Accordion Cards)
        self.sec_dimensoes = CollapsibleSection("Dimensões Principais", "📏", collapsed=False)
        self.sec_frentes = CollapsibleSection("Frentes & Estrutura", "🚪", collapsed=True)
        self.sec_puxadores = CollapsibleSection("Puxadores & Perfis", "✨", collapsed=True)
        self.sec_materiais = CollapsibleSection("Materiais & Fitas", "🎨", collapsed=True)
        self.sec_ajustes = CollapsibleSection("Ajustes Especiais", "⚙️", collapsed=True)

        self.form_vbox.addWidget(self.sec_dimensoes)
        self.form_vbox.addWidget(self.sec_frentes)
        self.form_vbox.addWidget(self.sec_puxadores)
        self.form_vbox.addWidget(self.sec_materiais)
        self.form_vbox.addWidget(self.sec_ajustes)
        self.form_vbox.addStretch(1)

        # Alias de compatibilidade
        self.form_layout = self.sec_dimensoes.form_layout

        # --- Medidas Principais ---

        # Largura
        h_larg = QHBoxLayout()
        self.sp_largura = QSpinBox()
        self.sp_largura.setRange(1, 3000)
        self.sp_largura.setValue(800)
        self.sp_largura.setSuffix(" mm")
        h_larg.addWidget(self.sp_largura)
        btn_l_minus = QPushButton("-50")
        btn_l_minus.setFixedWidth(34)
        btn_l_minus.clicked.connect(lambda: self.sp_largura.setValue(self.sp_largura.value() - 50))
        h_larg.addWidget(btn_l_minus)
        btn_l_plus = QPushButton("+50")
        btn_l_plus.setFixedWidth(34)
        btn_l_plus.clicked.connect(lambda: self.sp_largura.setValue(self.sp_largura.value() + 50))
        h_larg.addWidget(btn_l_plus)
        self.sec_dimensoes.form_layout.addRow("Largura:", h_larg)

        # Altura
        h_alt = QHBoxLayout()
        self.sp_altura = QSpinBox()
        self.sp_altura.setRange(1, 3000)
        self.sp_altura.setValue(720)
        self.sp_altura.setSuffix(" mm")
        h_alt.addWidget(self.sp_altura)
        btn_a_minus = QPushButton("-50")
        btn_a_minus.setFixedWidth(34)
        btn_a_minus.clicked.connect(lambda: self.sp_altura.setValue(self.sp_altura.value() - 50))
        h_alt.addWidget(btn_a_minus)
        btn_a_plus = QPushButton("+50")
        btn_a_plus.setFixedWidth(34)
        btn_a_plus.clicked.connect(lambda: self.sp_altura.setValue(self.sp_altura.value() + 50))
        h_alt.addWidget(btn_a_plus)
        self.lbl_altura = QLabel("Altura:")
        self.sec_dimensoes.form_layout.addRow(self.lbl_altura, h_alt)

        # Profundidade
        h_prof = QHBoxLayout()
        self.sp_prof = QSpinBox()
        self.sp_prof.setRange(1, 2000)
        self.sp_prof.setValue(550)

        self.sp_prof.setSuffix(" mm")
        h_prof.addWidget(self.sp_prof)
        btn_p_minus = QPushButton("-50")
        btn_p_minus.setFixedWidth(34)
        btn_p_minus.clicked.connect(lambda: self.sp_prof.setValue(self.sp_prof.value() - 50))
        h_prof.addWidget(btn_p_minus)
        btn_p_plus = QPushButton("+50")
        btn_p_plus.setFixedWidth(34)
        btn_p_plus.clicked.connect(lambda: self.sp_prof.setValue(self.sp_prof.value() + 50))
        h_prof.addWidget(btn_p_plus)
        self.lbl_prof = QLabel("Profundidade:")
        self.sec_dimensoes.form_layout.addRow(self.lbl_prof, h_prof)

        # --- Puxadores (Portas e Gavetas) ---

        self.cb_puxador_tipo = QComboBox()
        self.cb_puxador_tipo.addItems([
            "Puxador Alça (Linear)",
            "Puxador Perfil (Alumínio)",
            "Puxador Cava (Chanfro 45°)",
            "Puxador Ponto (Botão)",
            "Sem Puxador (Toque)",
        ])
        self.lbl_puxador_tipo = QLabel("Modelo:")
        self.sec_puxadores.form_layout.addRow(self.lbl_puxador_tipo, self.cb_puxador_tipo)

        self.cb_puxador_cor = QComboBox()
        self.cb_puxador_cor.addItems([
            "Preto Fosco",
            "Alumínio / Inox",
            "Dourado / Champanhe",
            "Cobre / Rosé",
            "Branco",
        ])
        self.lbl_puxador_cor = QLabel("Acabamento:")
        self.sec_puxadores.form_layout.addRow(self.lbl_puxador_cor, self.cb_puxador_cor)

        self.cb_puxador_pos = QComboBox()
        self.cb_puxador_pos.addItems([
            "📌 Automático / Padrão",
            "⬆️ Na Parte de Cima (Topo)",
            "↕️ Na Extensão da Porta (Lateral)",
            "⬇️ Na Parte de Baixo (Base)",
            "🎯 No Centro",
        ])
        self.lbl_puxador_pos = QLabel("Posição:")
        self.sec_puxadores.form_layout.addRow(self.lbl_puxador_pos, self.cb_puxador_pos)

        # Botão para troca de puxadores em lote em todos os armários do ambiente (estilo Promob)
        self.btn_aplicar_puxador_todos = QPushButton("🔄 Aplicar Puxadores em Todo o Projeto")
        self.btn_aplicar_puxador_todos.setToolTip("Aplica o modelo, acabamento e posição de puxadores selecionados a todos os armários da cena")
        self.btn_aplicar_puxador_todos.setStyleSheet(
            "QPushButton { background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px; padding: 5px; font-weight: bold; color: #334155; }"
            "QPushButton:hover { background-color: #E2E8F0; color: #0F172A; border-color: #94A3B8; }"
        )
        self.btn_aplicar_puxador_todos.clicked.connect(self._on_apply_puxadores_to_all_modules)
        self.sec_puxadores.form_layout.addRow(self.btn_aplicar_puxador_todos)

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

        self.sp_desconto_perfil = QSpinBox()
        self.sp_desconto_perfil.setRange(15, 60)
        self.sp_desconto_perfil.setValue(35)
        self.sp_desconto_perfil.setVisible(False)

        self._refresh_perfil_modelos()
        self.cb_perfil_modelo.currentIndexChanged.connect(self._on_perfil_modelo_changed)
        self.cb_altura_perfil.currentTextChanged.connect(self._sync_desconto_perfil_from_combo)

        self.sec_puxadores.form_layout.addRow(self.frame_perfil)

        def _update_perfil_card_visibility(idx):
            is_perfil = (idx == 1)
            self.frame_perfil.setVisible(is_perfil)

        self.cb_puxador_tipo.currentIndexChanged.connect(_update_perfil_card_visibility)
        _update_perfil_card_visibility(self.cb_puxador_tipo.currentIndex())

        # --- Padrões de MDF e Chapas ---
        from .materials_catalog import ALL_BOX_MATERIALS, MDF_MATERIALS


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

        # --- Elementos Internos & Rodapé ---

        self.sp_qtd_elem = QSpinBox()
        self.sp_qtd_elem.setRange(0, 8)
        self.sp_qtd_elem.setValue(2)
        self.lbl_qtd_elem = QLabel("Portas / Gavetas:")
        self.sec_frentes.form_layout.addRow(self.lbl_qtd_elem, self.sp_qtd_elem)

        self.sp_largura_gaveteiro = QSpinBox()
        self.sp_largura_gaveteiro.setRange(250, 1200)
        self.sp_largura_gaveteiro.setValue(450)
        self.sp_largura_gaveteiro.setSingleStep(50)
        self.sp_largura_gaveteiro.setSuffix(" mm")
        self.sp_largura_gaveteiro.setToolTip("Largura externa da seção de gavetas no balcão misto")
        self.lbl_largura_gaveteiro = QLabel("Largura Gaveteiro:")
        self.sec_frentes.form_layout.addRow(self.lbl_largura_gaveteiro, self.sp_largura_gaveteiro)
        self.lbl_largura_gaveteiro.setVisible(False)
        self.sp_largura_gaveteiro.setVisible(False)

        self.sp_prateleiras = QSpinBox()
        self.sp_prateleiras.setRange(0, 6)
        self.sp_prateleiras.setValue(1)
        self.lbl_prateleiras = QLabel("Prateleiras:")
        self.sec_frentes.form_layout.addRow(self.lbl_prateleiras, self.sp_prateleiras)

        # --- Divisórias Internas e Vãos Livres Dinâmicos (Estilo Promob) ---
        self.sp_divisoes = QSpinBox()
        self.sp_divisoes.setRange(0, 5)
        self.sp_divisoes.setValue(0)
        self.sp_divisoes.setToolTip("Quantidade de divisórias verticais internas. Divide o armário em múltiplos vãos com cálculo automático de luz livre.")
        self.lbl_divisoes = QLabel("Divisórias Vert.:")
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
        self.lbl_rodape = QLabel("Rodapé:")
        self.sec_frentes.form_layout.addRow(self.lbl_rodape, self.sp_rodape)

        # --- Fundo TrazoMob ---

        self.cb_tipo_fundo = QComboBox()
        self.cb_tipo_fundo.addItems([
            "Canal / Rasgo",
            "Sobreposto",
            "Sem Fundo",
        ])
        self.cb_tipo_fundo.currentIndexChanged.connect(self._on_tipo_fundo_changed)
        self.lbl_tipo_fundo = QLabel("Fundo:")
        self.sec_frentes.form_layout.addRow(self.lbl_tipo_fundo, self.cb_tipo_fundo)

        self.cb_esp_fundo = QComboBox()
        self.cb_esp_fundo.addItems(["6 mm", "3 mm", "15 mm"])
        self.lbl_esp_fundo = QLabel("Esp. Fundo:")
        self.sec_frentes.form_layout.addRow(self.lbl_esp_fundo, self.cb_esp_fundo)

        self.sp_recuo_fundo = QSpinBox()
        self.sp_recuo_fundo.setRange(0, 100)
        self.sp_recuo_fundo.setValue(15)
        self.sp_recuo_fundo.setSuffix(" mm")
        self.lbl_recuo_fundo = QLabel("Recuo Fundo:")
        self.sec_frentes.form_layout.addRow(self.lbl_recuo_fundo, self.sp_recuo_fundo)

        self.sp_prof_rasgo = QSpinBox()
        self.sp_prof_rasgo.setRange(1, 15)
        self.sp_prof_rasgo.setValue(7)
        self.sp_prof_rasgo.setSuffix(" mm")
        self.lbl_prof_rasgo = QLabel("Rasgo:")
        self.sec_frentes.form_layout.addRow(self.lbl_prof_rasgo, self.sp_prof_rasgo)

        self._fundo_sidebar_widgets = [
            self.lbl_tipo_fundo, self.cb_tipo_fundo,
            self.lbl_esp_fundo, self.cb_esp_fundo,
            self.lbl_recuo_fundo, self.sp_recuo_fundo,
            self.lbl_prof_rasgo, self.sp_prof_rasgo,
        ]

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

        # Botão para troca/padronização de travessas em lote em todos os balcões da cena (estilo Promob)
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

        self.sp_larg_asa = QSpinBox()
        self.sp_larg_asa.setRange(300, 1200)
        self.sp_larg_asa.setSingleStep(50)
        self.sp_larg_asa.setValue(600)
        self.sp_larg_asa.setSuffix(" mm")
        self.sp_larg_asa.setToolTip("Profundidade das asas da bancada em L (padrão: 600mm)")
        self.lbl_larg_asa = QLabel("Profundidade Asas (L):")
        self.sec_ajustes.form_layout.addRow(self.lbl_larg_asa, self.sp_larg_asa)

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
            self.lbl_larg_asa, self.sp_larg_asa,
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
        self.lbl_dispositivo_fixacao = QLabel("Fixação:")
        self.sec_ajustes.form_layout.addRow(self.lbl_dispositivo_fixacao, self.cb_dispositivo_fixacao)

        # Conectar atualização reativa de badges
        self.sp_largura.valueChanged.connect(self._update_badges)
        self.sp_altura.valueChanged.connect(self._update_badges)
        self.sp_prof.valueChanged.connect(self._update_badges)
        self.sp_qtd_elem.valueChanged.connect(self._update_badges)
        self.sp_prateleiras.valueChanged.connect(self._update_badges)
        self.cb_puxador_tipo.currentTextChanged.connect(self._update_badges)
        self.cb_material.currentTextChanged.connect(self._update_badges)

        self.scroll_area.setWidget(self.form_container)
        main_layout.addWidget(self.scroll_area)

        # --- Botões de Ação na Barra Lateral ---
        self.btn_apply = QPushButton("🔄 Aplicar no Módulo 3D")
        self.btn_apply.setStyleSheet(
            "QPushButton { background-color: #16A34A; color: white; font-weight: bold; padding: 10px; border-radius: 6px; font-size: 12px; }"
            "QPushButton:hover { background-color: #15803D; }"
            "QPushButton:disabled { background-color: #94A3B8; }"
        )
        self.btn_apply.clicked.connect(self._apply_changes_to_selected)
        main_layout.addWidget(self.btn_apply)

        # Salvar valores atuais como padrão para futuros módulos desta categoria
        self.btn_save_defaults = QPushButton("⭐ Salvar como Medidas Padrão")
        self.btn_save_defaults.setToolTip(
            "Salva a altura, profundidade, materiais e puxadores atuais como padrão permanente.\n"
            "Sempre que você fechar e abrir o programa, novos módulos já virão com essas preferências!"
        )
        self.btn_save_defaults.setStyleSheet(
            "QPushButton { background-color: palette(button); color: palette(text); font-weight: bold; padding: 7px; border-radius: 4px; font-size: 11px; border: 1px solid palette(mid); }"
            "QPushButton:hover { background-color: palette(highlight); color: palette(highlighted-text); }"
        )
        self.btn_save_defaults.clicked.connect(self._save_current_as_default)
        main_layout.addWidget(self.btn_save_defaults)

        # Gestão Rápida: Excluir Módulo Selecionado
        self.btn_delete = QPushButton("🗑️ Excluir Módulo")
        self.btn_delete.setToolTip("Exclui o módulo selecionado da cena 3D")
        self.btn_delete.setStyleSheet(
            "QPushButton { background-color: #dc2626; color: white; font-weight: bold; padding: 7px; border-radius: 4px; font-size: 11px; }"
            "QPushButton:hover { background-color: #b91c1c; }"
            "QPushButton:disabled { background-color: #94a3b8; }"
        )
        self.btn_delete.clicked.connect(self._delete_selected)
        main_layout.addWidget(self.btn_delete)

        # Atualiza estado inicial
        self._set_editor_enabled(False)


    def _set_editor_enabled(self, enabled: bool) -> None:
        if enabled:
            self._ensure_form_built()
        if hasattr(self, "form_container"):
            self.form_container.setEnabled(enabled)
        if hasattr(self, "btn_apply"):
            self.btn_apply.setEnabled(enabled)
        if hasattr(self, "btn_save_defaults"):
            self.btn_save_defaults.setEnabled(enabled)
        if hasattr(self, "btn_delete"):
            self.btn_delete.setEnabled(enabled)
        if not enabled:
            if hasattr(self, "card_paredes"):
                self.card_paredes.setVisible(False)
            if hasattr(self, "scroll_area"):
                self.scroll_area.setVisible(False)
            if hasattr(self, "btn_apply"):
                self.btn_apply.setVisible(False)
            if hasattr(self, "btn_save_defaults"):
                self.btn_save_defaults.setVisible(False)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setVisible(False)
            self.lbl_title.setText("🪵 TrazoMob — Módulos")
            self.lbl_status.setText("💡 Selecione uma parede ou um módulo no 3D para editar.")
            self.card_header.setStyleSheet(
                "QFrame { background-color: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 2px 4px; }"
            )
        else:
            self.card_header.setStyleSheet(
                "QFrame { background-color: palette(base); border: 1px solid palette(highlight); border-radius: 4px; padding: 2px 4px; }"
            )

    def _save_current_as_default(self) -> None:
        """Salva as medidas, materiais e puxadores atuais como padrão permanente nas preferências."""
        mod = self._selected_module or self.find_selected_module()
        if mod is None:
            return
        old_params = mod.ext.get("trazomob_module", {}) if getattr(mod, "ext", None) else {}
        tipo = str(old_params.get("tipo", "balcao"))

        from .module_ribbon import get_module_category
        cat = get_module_category(tipo)

        from .preferences import TrazoMobPreferencesManager
        prefs = TrazoMobPreferencesManager.get_instance()

        # Extrai parâmetros atuais do formulário
        curr_params = extract_ui_module_params(self, base_params=old_params)

        # 1. Salva dimensões padrão para esta categoria e tipo
        def_dim = {}
        if "altura" in curr_params:
            def_dim["altura"] = float(curr_params["altura"])
        if "profundidade" in curr_params:
            def_dim["profundidade"] = float(curr_params["profundidade"])
        if "rodape" in curr_params:
            def_dim["rodape"] = float(curr_params["rodape"])
        if "bancada" in tipo:
            if "esp_pedra" in curr_params:
                def_dim["esp_pedra"] = float(curr_params["esp_pedra"])
            if "altura_saia" in curr_params:
                def_dim["altura_saia"] = float(curr_params["altura_saia"])
            if "altura_frontao" in curr_params:
                def_dim["altura_frontao"] = float(curr_params["altura_frontao"])

        prefs.set_module_defaults(cat, def_dim)
        prefs.set_module_defaults(tipo, def_dim)

        # 2. Salva preferências globais de materiais e acabamentos
        if "espessura" in curr_params:
            prefs.set_global("espessura_caixa_mm", float(curr_params["espessura"]))
        if "espessura_frentes" in curr_params:
            prefs.set_global("espessura_frentes_mm", float(curr_params["espessura_frentes"]))
        if "material" in curr_params:
            prefs.set_global("material_caixa", str(curr_params["material"]).rsplit(" ", 1)[0])
        if "material_frentes" in curr_params:
            prefs.set_global("material_frentes", str(curr_params["material_frentes"]).rsplit(" ", 1)[0])
        if "puxador_tipo" in curr_params:
            prefs.set_global("puxador_tipo", str(curr_params["puxador_tipo"]))
        if "puxador_cor" in curr_params:
            prefs.set_global("puxador_cor", str(curr_params["puxador_cor"]))
        if "puxador_pos" in curr_params:
            prefs.set_global("puxador_pos", str(curr_params["puxador_pos"]))
        if "perfil_modelo" in curr_params:
            prefs.set_global("perfil_modelo", str(curr_params["perfil_modelo"]))
        if "desconto_perfil" in curr_params:
            prefs.set_global("desconto_perfil_mm", float(curr_params["desconto_perfil"]))

        # 3. Fundo e Furações
        if "tipo_fundo" in curr_params:
            prefs.set_global("tipo_fundo", str(curr_params["tipo_fundo"]))
        if "esp_fundo" in curr_params:
            prefs.set_global("esp_fundo_mm", float(curr_params["esp_fundo"]))
        if "recuo_fundo" in curr_params:
            prefs.set_global("recuo_fundo_mm", float(curr_params["recuo_fundo"]))
        if "prof_rasgo" in curr_params:
            prefs.set_global("prof_rasgo_mm", float(curr_params["prof_rasgo"]))
        if "folga_fundo" in curr_params:
            prefs.set_global("folga_fundo_mm", float(curr_params["folga_fundo"]))
        if "dispositivo_fixacao" in curr_params:
            prefs.set_global("dispositivo_fixacao", str(curr_params["dispositivo_fixacao"]))

        # 4. Travessas Globais (em pé / deitada, larguras, materiais)
        if "travessa_frontal_em_pe" in curr_params:
            prefs.set_global("travessa_frontal_em_pe", bool(curr_params["travessa_frontal_em_pe"]))
        if "travessa_traseira_em_pe" in curr_params:
            prefs.set_global("travessa_traseira_em_pe", bool(curr_params["travessa_traseira_em_pe"]))
        if "larg_travessa_frontal_mm" in curr_params:
            prefs.set_global("larg_travessa_frontal_mm", float(curr_params["larg_travessa_frontal_mm"]))
        if "larg_travessa_traseira_mm" in curr_params:
            prefs.set_global("larg_travessa_traseira_mm", float(curr_params["larg_travessa_traseira_mm"]))
        if "recuo_porta_topo_mm" in curr_params:
            prefs.set_global("recuo_porta_topo_mm", float(curr_params["recuo_porta_topo_mm"]))
        if "material_travessas" in curr_params:
            prefs.set_global("material_travessas", curr_params["material_travessas"])
        if "esp_travessas_mm" in curr_params:
            prefs.set_global("esp_travessas_mm", curr_params["esp_travessas_mm"])
        if "fita_travessas_modo" in curr_params:
            prefs.set_global("fita_travessas_modo", str(curr_params["fita_travessas_modo"]))
        if "material_fita_travessas" in curr_params:
            prefs.set_global("material_fita_travessas", curr_params["material_fita_travessas"])

        ok = prefs.save()
        if ok:
            if hasattr(self, "_get_viewport"):
                vp = self._get_viewport()
                if vp and hasattr(vp, "flash_status"):
                    vp.flash_status(f"⭐ Padrões salvos! Novos módulos da categoria '{cat}' virão com estas medidas.")
            self.lbl_status.setText(f"⭐ Medidas salvas como padrão permanente ({cat})!")

    def _refresh_perfil_modelos(self, select_id: str | None = None) -> None:
        """Recarrega os modelos de perfil da biblioteca para o combobox."""
        fill_profile_combo(self.cb_perfil_modelo, select_id=select_id)
        self._on_perfil_modelo_changed()

    def _on_perfil_modelo_changed(self) -> None:
        """Atualiza a prévia do diagrama e a indicação de desconto padrão."""
        pid = self.cb_perfil_modelo.currentData() or "gola"
        p = perfis_lib.get_profile(pid)
        # Se for um dos modelos clássicos conhecidos pelo diagrama 3D vetorial, desenha ele; senão usa a seção 2D
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
        cur_id = self.cb_perfil_modelo.currentData()
        dlg = PerfilLibraryDialog(parent=self._get_window(), select_id=cur_id)
        if dlg.exec():
            selected = dlg.selected_id or cur_id
            self._refresh_perfil_modelos(select_id=selected)

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

    def find_selected_module(self) -> Group | None:
        """Encontra o módulo do TrazoMob correspondente à seleção atual no 3D."""
        scene = self._get_scene()
        if scene is None:
            return None

        selection = list(getattr(scene, "selection", []))
        if not selection:
            return None

        # 1. Checa se o item selecionado é diretamente um módulo mestre
        for item in selection:
            if hasattr(item, "ext") and isinstance(item.ext, dict):
                if "trazomob_module" in item.ext or "corte_cloud_module" in item.ext or "hellomob_module" in item.ext:
                    return item

        # 2. Checa se uma peça filha selecionada pertence a um módulo mestre
        for g in getattr(scene, "groups", []):
            if hasattr(g, "ext") and isinstance(g.ext, dict):
                if "trazomob_module" in g.ext or "corte_cloud_module" in g.ext or "hellomob_module" in g.ext:
                    children = getattr(g, "children", []) or []
                    if any(child in selection for child in children):
                        return g

    def find_selected_wall(self) -> Group | None:
        """Encontra se a seleção atual no 3D é uma parede paramétrica."""
        scene = self._get_scene()
        if scene is None:
            return None

        selection = list(getattr(scene, "selection", []))
        if not selection:
            return None

        for item in selection:
            if hasattr(item, "ext") and isinstance(item.ext, dict):
                if "trazomob_wall" in item.ext or "corte_cloud_wall" in item.ext:
                    return item

        for g in getattr(scene, "groups", []):
            if hasattr(g, "ext") and isinstance(g.ext, dict):
                if "trazomob_wall" in g.ext or "corte_cloud_wall" in g.ext:
                    if any(child in selection for child in (getattr(g, "children", []) or [])):
                        return g

        return None

    def find_selected_light(self) -> Group | None:
        """Encontra se a seleção atual no 3D é uma luminária / fonte de luz física."""
        scene = self._get_scene()
        if scene is None:
            return None

        selection = list(getattr(scene, "selection", []))
        if not selection:
            return None

        for item in selection:
            if hasattr(item, "ext") and isinstance(item.ext, dict):
                if "trazomob_light" in item.ext:
                    return item

        for g in getattr(scene, "groups", []):
            if hasattr(g, "ext") and isinstance(g.ext, dict):
                if "trazomob_light" in g.ext:
                    if any(child in selection for child in (getattr(g, "children", []) or [])):
                        return g

        return None

    def on_scene_changed(self) -> None:
        """Chamado automaticamente quando a seleção ou a cena 3D é alterada."""
        if self._updating_ui:
            return

        scene = self._get_scene()

        # Sincroniza automaticamente recortes/vãos de portas e janelas nas paredes da cena
        if scene is not None:
            from .wall_mesh_builder import WallMeshBuilder
            if WallMeshBuilder.sync_scene_wall_openings(scene):
                vp = self._get_viewport()
                if vp is not None:
                    vp.update()

        sel = list(getattr(scene, "selection", [])) if scene else []
        sel_groups = [it for it in sel if isinstance(it, Group)]

        # 0. Checa se uma luminária 3D foi clicada/selecionada no viewport
        light_grp = self.find_selected_light()
        if light_grp is not None:
            self._selected_wall = None
            self._selected_module = None
            self.load_light_group(light_grp)
            return
        elif self._selected_light_grp is not None and not sel:
            self.clear_light_selection()

        # 0.1 Checa se há múltiplos objetos selecionados (Modo Alinhamento / Centralização)
        if len(sel_groups) >= 2:
            self.focus_panel()
            alvo = sel_groups[-1]
            base = sel_groups[0]
            if hasattr(self, "card_align"):
                self.card_align.setVisible(True)
                self.lbl_align_info.setText(f"🎯 <b>Centralizar:</b> {alvo.name}")
                self.lbl_align_desc.setText(f"Objeto de Referência: <b>{base.name}</b>")
            if hasattr(self, "card_paredes"):
                self.card_paredes.setVisible(False)
            if hasattr(self, "card_luz"):
                self.card_luz.setVisible(False)
            if hasattr(self, "scroll_area"):
                self.scroll_area.setVisible(False)
            if hasattr(self, "btn_apply"):
                self.btn_apply.setVisible(False)
            if hasattr(self, "btn_save_defaults"):
                self.btn_save_defaults.setVisible(False)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setVisible(False)
            self._selected_module = None
            self._selected_wall = None
            self._selected_light_grp = None
            return
        else:
            if hasattr(self, "card_align"):
                self.card_align.setVisible(False)

        # 1. Checa se uma parede foi selecionada
        wall = self.find_selected_wall()
        if wall is not None:
            self._selected_wall = wall
            self._selected_module = None
            self._selected_light_grp = None
            if hasattr(self, "card_luz"):
                self.card_luz.setVisible(False)
            self.load_wall(wall)
            return

        self._selected_wall = None

        # 2. Checa se um módulo de marcenaria foi selecionado
        mod = self.find_selected_module()
        if mod is not self._selected_module:
            self._selected_module = mod
            self._selected_light_grp = None
            if hasattr(self, "card_luz"):
                self.card_luz.setVisible(False)
            if mod is not None:
                self.load_module(mod)
            else:
                self._selected_module = None
                self._set_editor_enabled(False)
                if hasattr(self, "card_paredes"):
                    self.card_paredes.setVisible(False)
                if hasattr(self, "scroll_area"):
                    self.scroll_area.setVisible(False)
                if hasattr(self, "btn_apply"):
                    self.btn_apply.setVisible(False)
                if hasattr(self, "btn_save_defaults"):
                    self.btn_save_defaults.setVisible(False)
                if hasattr(self, "btn_delete"):
                    self.btn_delete.setVisible(False)
        elif mod is not None and not getattr(self, "_updating_ui", False):
            # Se o módulo já estava selecionado mas foi redimensionado no 3D (ex: ferramenta Scale/S),
            # atualiza os spinboxes na barra lateral para sincronizar os valores imediatamente
            params = mod.ext.get("trazomob_module", {}) if getattr(mod, "ext", None) else {}
            if params:
                cur_l = int(round(float(params.get("largura", 0.0))))
                cur_p = int(round(float(params.get("profundidade", 0.0))))
                cur_a = int(round(float(params.get("altura", 0.0))))
                sp_l = int(self.sp_largura.value()) if hasattr(self, "sp_largura") else cur_l
                sp_p = int(self.sp_prof.value()) if hasattr(self, "sp_prof") else cur_p
                sp_a = int(self.sp_altura.value()) if hasattr(self, "sp_altura") else cur_a
                if cur_l != sp_l or cur_p != sp_p or cur_a != sp_a:
                    self.load_module(mod)

    def _trigger_center(self, axes: str) -> None:
        """Executa a centralização entre os objetos atualmente selecionados."""
        scene = self._get_scene()
        sel = list(getattr(scene, "selection", [])) if scene else []
        sel_groups = [it for it in sel if isinstance(it, Group)]
        if len(sel_groups) < 2:
            return
        from .align_tools import center_objects
        alvo = sel_groups[-1]
        base = sel_groups[0]
        vp = self._get_viewport()
        center_objects(alvo, base, axes=axes, viewport=vp)


    def _sync_desconto_perfil_from_combo(self, text: str) -> None:
        try:
            val = int(text.split()[0])
            self.sp_desconto_perfil.setValue(val)
        except (ValueError, IndexError):
            self.sp_desconto_perfil.setValue(35)

    def load_module(self, mod: Group) -> None:
        """Carrega os dados do módulo selecionado nos controles da barra lateral."""
        self.focus_panel()
        from .migration import migrate_legacy_group
        migrate_legacy_group(mod)
        self._updating_ui = True
        try:
            params = mod.ext.get("trazomob_module", {})
            tipo = params.get("tipo", "balcao")
            # Contexto Estrito: ao selecionar um módulo, esconde completamente as ferramentas de parede
            if hasattr(self, "card_paredes"):
                self.card_paredes.setVisible(False)
            if hasattr(self, "scroll_area"):
                self.scroll_area.setVisible(True)
            if hasattr(self, "btn_apply"):
                self.btn_apply.setVisible(True)
            if hasattr(self, "btn_save_defaults"):
                self.btn_save_defaults.setVisible(True)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setVisible(True)

            self._set_editor_enabled(True)
            self.lbl_title.setText(f"🎯 {mod.name}")
            self.lbl_status.setText(f"Tipo: {tipo} | Editando na barra lateral")

            # Popula valores comuns na barra lateral através do mapper centralizado
            populate_ui_from_module(self, params)

            self._on_perfil_modelo_changed()
            self.frame_perfil.setVisible(params.get("puxador_tipo", "alca") == "perfil")

            # Portas / Gavetas
            if "num_gavetas" in params:
                self.lbl_qtd_elem.setText("Gavetas:")
                self.sp_qtd_elem.setValue(params["num_gavetas"])
                self.sp_qtd_elem.setEnabled(True)
            elif "num_portas" in params:
                n_p = params["num_portas"]
                # Verifica se o módulo tem portas fixas pelo flag no catálogo (MODULE_CATALOG já importado)
                _mod_cat = next(
                    (m for cat in MODULE_CATALOG.values() for m in cat if m.get("id") == tipo),
                    {}
                ) if tipo else {}
                if _mod_cat.get("fixed_portas"):
                    self.lbl_qtd_elem.setText(f"Portas (fixo: {int(n_p)}):")
                    self.sp_qtd_elem.setValue(int(n_p))
                    self.sp_qtd_elem.setEnabled(False)
                else:
                    self.lbl_qtd_elem.setText("Portas:")
                    self.sp_qtd_elem.setValue(n_p)
                    self.sp_qtd_elem.setEnabled(True)
            else:
                self.lbl_qtd_elem.setText("Portas/Gavetas:")
                self.sp_qtd_elem.setValue(2)
                self.sp_qtd_elem.setEnabled(True)

            if "num_prateleiras" in params:
                self.sp_prateleiras.setValue(params["num_prateleiras"])

            is_misto = (tipo == "balcao_misto")
            if hasattr(self, "lbl_largura_gaveteiro"):
                self.lbl_largura_gaveteiro.setVisible(is_misto)
                self.sp_largura_gaveteiro.setVisible(is_misto)
                if is_misto:
                    self.sp_largura_gaveteiro.setValue(int(round(float(params.get("largura_gaveteiro", 450.0)))))

            is_canto_l_mod = tipo in ("balcao_canto_l", "bancada_canto_l", "bancada_canto")
            if hasattr(self, "lbl_larg_asa"):
                self.lbl_larg_asa.setVisible(is_canto_l_mod)
                self.sp_larg_asa.setVisible(is_canto_l_mod)
                if is_canto_l_mod:
                    self.sp_larg_asa.setValue(int(round(float(params.get("larg_asa", 550.0)))))

            # Fundo (sincronização de interface)
            self._on_tipo_fundo_changed()

            # Travessas Superiores — visíveis só para módulos de cozinha inferiores
            _IDS_COZINHA_INFERIORES = {
                "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
                "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
            }
            has_travessa = tipo in _IDS_COZINHA_INFERIORES
            if hasattr(self, "_travessa_sidebar_widgets"):
                for w in self._travessa_sidebar_widgets:
                    w.setVisible(has_travessa)
                if has_travessa:
                    tf_em_pe = bool(params.get("travessa_frontal_em_pe", (tipo in ("balcao_pia", "balcao_forno"))))
                    tt_em_pe = bool(params.get("travessa_traseira_em_pe", False))
                    self.chk_travessa_frontal_em_pe.setChecked(tf_em_pe)
                    self.chk_travessa_traseira_em_pe.setChecked(tt_em_pe)
                    larg_f = params.get("larg_travessa_frontal_mm", params.get("larg_travessa_mm", 70.0))
                    larg_t = params.get("larg_travessa_traseira_mm", 70.0)
                    recuo = params.get("recuo_porta_topo_mm", params.get("recuo_porta_pia_mm", 50.0))
                    self.sp_larg_travessa_frontal.setValue(int(round(float(larg_f))))
                    self.sp_larg_travessa_traseira.setValue(int(round(float(larg_t))))
                    self.sp_recuo_porta_topo.setValue(int(round(float(recuo))))
                    self.lbl_recuo_porta_topo.setVisible(tf_em_pe)
                    self.sp_recuo_porta_topo.setVisible(tf_em_pe)

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

            # Nicho de Forno (balcao_forno)
            self._current_selected_tipo = tipo
            is_forno = (tipo == "balcao_forno")
            if hasattr(self, "_forno_sidebar_widgets"):
                for w in self._forno_sidebar_widgets:
                    w.setVisible(is_forno)
                if is_forno:
                    tem_gav_f = bool(params.get("tem_gaveta", True))
                    self.chk_forno_tem_gaveta.setChecked(tem_gav_f)
                    self.sp_forno_alt_gaveta.setValue(int(round(float(params.get("alt_gaveta_mm", 150.0)))))
                    self.lbl_forno_alt_gaveta.setVisible(tem_gav_f)
                    self.sp_forno_alt_gaveta.setVisible(tem_gav_f)

            # Nicho de Geladeira (caixa_geladeira)
            is_geladeira = (tipo == "caixa_geladeira")
            if hasattr(self, "_geladeira_sidebar_widgets"):
                for w in self._geladeira_sidebar_widgets:
                    w.setVisible(is_geladeira)
                if is_geladeira:
                    self.sp_geladeira_alt_nicho.setValue(int(round(float(params.get("alt_nicho_geladeira_mm", 1800.0)))))
                    is_b = (str(params.get("tipo_porta_superior", "")).lower() in ("basculante", "1_porta") or int(params.get("num_portas", 2)) == 1)
                    self.cb_geladeira_tipo_porta.setCurrentIndex(1 if is_b else 0)

            # Aéreo Micro-ondas (aereo_microondas)
            is_micro = (tipo == "aereo_microondas")
            if hasattr(self, "_micro_sidebar_widgets"):
                for w in self._micro_sidebar_widgets:
                    w.setVisible(is_micro)
                if is_micro:
                    is_b_micro = (str(params.get("tipo_porta_superior", "basculante")).lower() in ("basculante", "1_porta") or int(params.get("num_portas", 1)) == 1)
                    self.cb_micro_tipo_porta.setCurrentIndex(0 if is_b_micro else 1)

            # Caixa de Gaveta — visíveis apenas para módulos com gavetas
            has_gav = ("num_gavetas" in params) or (tipo in ("gaveteiro", "balcao_misto", "torre_quente", "gabinete_banheiro")) or (is_forno and bool(params.get("tem_gaveta", True)))
            if hasattr(self, "_gaveta_sidebar_widgets"):
                for w in self._gaveta_sidebar_widgets:
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

            if hasattr(self, "chk_gerar_furacao"):
                self.chk_gerar_furacao.setChecked(bool(params.get("gerar_furacao", True)))
            if hasattr(self, "cb_dispositivo_fixacao"):
                disp = str(params.get("dispositivo_fixacao", "minifix_cavilha")).lower()
                disp_map = {"minifix_cavilha": 0, "cavilha_soberba": 1, "soberba": 2, "cavilha": 3}
                self.cb_dispositivo_fixacao.setCurrentIndex(disp_map.get(disp, 0))

            # ── Troca Dinâmica do Contexto da Barra Lateral (Móvel vs Pedra/Marmoraria) ──
            is_pedra = "bancada" in str(tipo)
            if hasattr(self, "sec_frentes"):
                self.sec_frentes.setVisible(not is_pedra)
            if hasattr(self, "sec_puxadores"):
                self.sec_puxadores.setVisible(not is_pedra)
            if hasattr(self, "_pedra_sidebar_widgets"):
                for w in self._pedra_sidebar_widgets:
                    w.setVisible(is_pedra)

            if is_pedra:
                # Oculta seções exclusivas de marcenaria
                if hasattr(self, "lbl_rodape"):
                    self.lbl_rodape.setVisible(False)
                self.sp_rodape.setVisible(False)

                if hasattr(self, "lbl_materiais_header"):
                    self.lbl_materiais_header.setVisible(False)
                if hasattr(self, "lbl_material_caixa"):
                    self.lbl_material_caixa.setText("Padrão da Pedra:")
                if hasattr(self, "lbl_espessura_caixa"):
                    self.lbl_espessura_caixa.setText("Espessura Chapa:")

                if hasattr(self, "lbl_fita_caixa"):
                    self.lbl_fita_caixa.setVisible(False)
                if hasattr(self, "cb_fita_caixa"):
                    self.cb_fita_caixa.setVisible(False)
                if hasattr(self, "lbl_material_fita_caixa"):
                    self.lbl_material_fita_caixa.setVisible(False)
                if hasattr(self, "cb_material_fita_caixa"):
                    self.cb_material_fita_caixa.setVisible(False)

                if hasattr(self, "lbl_material_frentes"):
                    self.lbl_material_frentes.setVisible(False)
                if hasattr(self, "cb_material_frentes"):
                    self.cb_material_frentes.setVisible(False)
                if hasattr(self, "lbl_espessura_frentes"):
                    self.lbl_espessura_frentes.setVisible(False)
                if hasattr(self, "cb_espessura_frentes"):
                    self.cb_espessura_frentes.setVisible(False)

                if hasattr(self, "lbl_puxadores_header"):
                    self.lbl_puxadores_header.setVisible(False)
                if hasattr(self, "lbl_puxador_tipo"):
                    self.lbl_puxador_tipo.setVisible(False)
                self.cb_puxador_tipo.setVisible(False)
                if hasattr(self, "lbl_puxador_cor"):
                    self.lbl_puxador_cor.setVisible(False)
                self.cb_puxador_cor.setVisible(False)
                if hasattr(self, "lbl_puxador_pos"):
                    self.lbl_puxador_pos.setVisible(False)
                self.cb_puxador_pos.setVisible(False)
                if hasattr(self, "frame_perfil"):
                    self.frame_perfil.setVisible(False)

                if hasattr(self, "lbl_estrutura_header"):
                    self.lbl_estrutura_header.setVisible(False)
                if hasattr(self, "lbl_qtd_elem"):
                    self.lbl_qtd_elem.setVisible(False)
                self.sp_qtd_elem.setVisible(False)
                if hasattr(self, "lbl_largura_gaveteiro"):
                    self.lbl_largura_gaveteiro.setVisible(False)
                if hasattr(self, "sp_largura_gaveteiro"):
                    self.sp_largura_gaveteiro.setVisible(False)
                if hasattr(self, "lbl_prateleiras"):
                    self.lbl_prateleiras.setVisible(False)
                self.sp_prateleiras.setVisible(False)

                if hasattr(self, "_fundo_sidebar_widgets"):
                    for w in self._fundo_sidebar_widgets:
                        w.setVisible(False)
                if hasattr(self, "_travessa_sidebar_widgets"):
                    for w in self._travessa_sidebar_widgets:
                        w.setVisible(False)
                if hasattr(self, "_gaveta_sidebar_widgets"):
                    for w in self._gaveta_sidebar_widgets:
                        w.setVisible(False)

                if hasattr(self, "lbl_furacao"):
                    self.lbl_furacao.setVisible(False)
                if hasattr(self, "chk_gerar_furacao"):
                    self.chk_gerar_furacao.setVisible(False)
                if hasattr(self, "lbl_dispositivo_fixacao"):
                    self.lbl_dispositivo_fixacao.setVisible(False)
                if hasattr(self, "cb_dispositivo_fixacao"):
                    self.cb_dispositivo_fixacao.setVisible(False)

                # Carrega parâmetros específicos de bancada de pedra
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
                if hasattr(self, "lbl_canto_recorte"):
                    self.lbl_canto_recorte.setVisible(tem_cuba)
                    self.cb_canto_recorte.setVisible(tem_cuba)
                    self.lbl_tem_area_molhada.setVisible(tem_cuba)
                    self.chk_tem_area_molhada.setVisible(tem_cuba)

                if tem_cuba:
                    cuba_val = str(params.get("tipo_cuba", "inox_simples")).lower()
                    cuba_map = {"inox_simples": 0, "inox_dupla": 1, "esculpida": 2, "sem_cuba": 3}
                    self.cb_tipo_cuba.setCurrentIndex(cuba_map.get(cuba_val, 0))

                    pos_val = str(params.get("posicao_cuba", "centro")).lower()
                    pos_cuba_map = {"centro": 0, "esquerda": 1, "direita": 2}
                    self.cb_posicao_cuba.setCurrentIndex(pos_cuba_map.get(pos_val, 0))

                    self.chk_tem_torneira.setChecked(bool(params.get("tem_torneira", True)))

                    canto_val = str(params.get("canto_recorte", "arredondado")).lower()
                    if hasattr(self, "cb_canto_recorte"):
                        self.cb_canto_recorte.setCurrentIndex(1 if "reto" in canto_val else 0)
                    if hasattr(self, "chk_tem_area_molhada"):
                        self.chk_tem_area_molhada.setChecked(bool(params.get("tem_area_molhada", True)))
            else:
                # Restaura visibilidade para marcenaria tradicional
                if hasattr(self, "lbl_rodape"):
                    self.lbl_rodape.setVisible(True)
                self.sp_rodape.setVisible(True)

                if hasattr(self, "lbl_materiais_header"):
                    self.lbl_materiais_header.setVisible(True)
                if hasattr(self, "lbl_material_caixa"):
                    self.lbl_material_caixa.setText("Caixa:")
                if hasattr(self, "lbl_espessura_caixa"):
                    self.lbl_espessura_caixa.setText("Esp. Caixa:")

                if hasattr(self, "lbl_fita_caixa"):
                    self.lbl_fita_caixa.setVisible(True)
                if hasattr(self, "cb_fita_caixa"):
                    self.cb_fita_caixa.setVisible(True)
                if hasattr(self, "lbl_material_fita_caixa"):
                    self.lbl_material_fita_caixa.setVisible(True)
                if hasattr(self, "cb_material_fita_caixa"):
                    self.cb_material_fita_caixa.setVisible(True)

                if hasattr(self, "lbl_material_frentes"):
                    self.lbl_material_frentes.setVisible(True)
                if hasattr(self, "cb_material_frentes"):
                    self.cb_material_frentes.setVisible(True)
                if hasattr(self, "lbl_espessura_frentes"):
                    self.lbl_espessura_frentes.setVisible(True)
                if hasattr(self, "cb_espessura_frentes"):
                    self.cb_espessura_frentes.setVisible(True)

                if hasattr(self, "lbl_puxadores_header"):
                    self.lbl_puxadores_header.setVisible(True)
                if hasattr(self, "lbl_puxador_tipo"):
                    self.lbl_puxador_tipo.setVisible(True)
                self.cb_puxador_tipo.setVisible(True)
                if hasattr(self, "lbl_puxador_cor"):
                    self.lbl_puxador_cor.setVisible(True)
                self.cb_puxador_cor.setVisible(True)
                if hasattr(self, "lbl_puxador_pos"):
                    self.lbl_puxador_pos.setVisible(True)
                self.cb_puxador_pos.setVisible(True)

                if hasattr(self, "lbl_estrutura_header"):
                    self.lbl_estrutura_header.setVisible(True)
                if hasattr(self, "lbl_qtd_elem"):
                    self.lbl_qtd_elem.setVisible(True)
                self.sp_qtd_elem.setVisible(True)
                if hasattr(self, "lbl_prateleiras"):
                    self.lbl_prateleiras.setVisible(True)
                self.sp_prateleiras.setVisible(True)

                if hasattr(self, "_fundo_sidebar_widgets"):
                    for w in self._fundo_sidebar_widgets:
                        w.setVisible(True)

                if hasattr(self, "lbl_furacao"):
                    self.lbl_furacao.setVisible(True)
                if hasattr(self, "chk_gerar_furacao"):
                    self.chk_gerar_furacao.setVisible(True)
                if hasattr(self, "lbl_dispositivo_fixacao"):
                    self.lbl_dispositivo_fixacao.setVisible(True)
                if hasattr(self, "cb_dispositivo_fixacao"):
                    self.cb_dispositivo_fixacao.setVisible(True)

            # ── Troca Dinâmica para Tampo Engrossado (peca_tampo_engrossado) ──
            is_tampo = (tipo in ("peca_tampo_engrossado", "tampo_engrossado"))
            if hasattr(self, "sec_frentes") and is_tampo:
                self.sec_frentes.setVisible(False)
            if hasattr(self, "sec_puxadores") and is_tampo:
                self.sec_puxadores.setVisible(False)
            if hasattr(self, "_tampo_sidebar_widgets"):
                for w in self._tampo_sidebar_widgets:
                    w.setVisible(is_tampo)

            if is_tampo:
                # Tampo Engrossado não possui rodapé, puxadores, portas/gavetas, prateleiras, fundo, furações
                if hasattr(self, "lbl_rodape"):
                    self.lbl_rodape.setVisible(False)
                self.sp_rodape.setVisible(False)

                if hasattr(self, "lbl_material_caixa"):
                    self.lbl_material_caixa.setText("Padrão MDF:")
                if hasattr(self, "lbl_espessura_caixa"):
                    self.lbl_espessura_caixa.setVisible(False)
                if hasattr(self, "cb_espessura"):
                    self.cb_espessura.setVisible(False)

                if hasattr(self, "lbl_fita_caixa"):
                    self.lbl_fita_caixa.setVisible(False)
                if hasattr(self, "cb_fita_caixa"):
                    self.cb_fita_caixa.setVisible(False)
                if hasattr(self, "lbl_material_fita_caixa"):
                    self.lbl_material_fita_caixa.setText("Fita de Borda:")

                if hasattr(self, "lbl_material_frentes"):
                    self.lbl_material_frentes.setVisible(False)
                if hasattr(self, "cb_material_frentes"):
                    self.cb_material_frentes.setVisible(False)
                if hasattr(self, "lbl_espessura_frentes"):
                    self.lbl_espessura_frentes.setVisible(False)
                if hasattr(self, "cb_espessura_frentes"):
                    self.cb_espessura_frentes.setVisible(False)

                if hasattr(self, "lbl_puxadores_header"):
                    self.lbl_puxadores_header.setVisible(False)
                if hasattr(self, "lbl_puxador_tipo"):
                    self.lbl_puxador_tipo.setVisible(False)
                self.cb_puxador_tipo.setVisible(False)
                if hasattr(self, "lbl_puxador_cor"):
                    self.lbl_puxador_cor.setVisible(False)
                self.cb_puxador_cor.setVisible(False)
                if hasattr(self, "lbl_puxador_pos"):
                    self.lbl_puxador_pos.setVisible(False)
                self.cb_puxador_pos.setVisible(False)
                if hasattr(self, "frame_perfil"):
                    self.frame_perfil.setVisible(False)

                if hasattr(self, "lbl_estrutura_header"):
                    self.lbl_estrutura_header.setVisible(False)
                if hasattr(self, "lbl_qtd_elem"):
                    self.lbl_qtd_elem.setVisible(False)
                self.sp_qtd_elem.setVisible(False)
                if hasattr(self, "lbl_largura_gaveteiro"):
                    self.lbl_largura_gaveteiro.setVisible(False)
                if hasattr(self, "sp_largura_gaveteiro"):
                    self.sp_largura_gaveteiro.setVisible(False)
                if hasattr(self, "lbl_prateleiras"):
                    self.lbl_prateleiras.setVisible(False)
                self.sp_prateleiras.setVisible(False)

                if hasattr(self, "_fundo_sidebar_widgets"):
                    for w in self._fundo_sidebar_widgets:
                        w.setVisible(False)
                if hasattr(self, "_travessa_sidebar_widgets"):
                    for w in self._travessa_sidebar_widgets:
                        w.setVisible(False)
                if hasattr(self, "_gaveta_sidebar_widgets"):
                    for w in self._gaveta_sidebar_widgets:
                        w.setVisible(False)

                if hasattr(self, "lbl_furacao"):
                    self.lbl_furacao.setVisible(False)
                if hasattr(self, "chk_gerar_furacao"):
                    self.chk_gerar_furacao.setVisible(False)
                if hasattr(self, "lbl_dispositivo_fixacao"):
                    self.lbl_dispositivo_fixacao.setVisible(False)
                if hasattr(self, "cb_dispositivo_fixacao"):
                    self.cb_dispositivo_fixacao.setVisible(False)

                # Carrega valores do tampo nos widgets da sidebar
                esp_ch = int(round(float(params.get("esp_chapa", 18.0))))
                idx_esp_ch = self.cb_tampo_esp_chapa.findText(f"{esp_ch} mm")
                self.cb_tampo_esp_chapa.setCurrentIndex(idx_esp_ch if idx_esp_ch >= 0 else 0)

                larg_eng = int(round(float(params.get("larg_engrosso", 70.0))))
                self.sp_tampo_larg_engrosso.setValue(larg_eng)

                qtd_eng = int(params.get("qtd_engrosso", 1))
                self.sp_tampo_qtd_engrosso.setValue(max(1, qtd_eng))

                self.chk_tampo_fechar_embaixo.setChecked(bool(params.get("fechar_embaixo", False)))

                tipo_eng = str(params.get("tipo_engrosso", "3_lados")).lower()
                tipo_eng_map = {"3_lados": 0, "4_lados": 1, "1_lado": 2, "apenas_frontal": 2}
                self.cb_tampo_tipo_engrosso.setCurrentIndex(tipo_eng_map.get(tipo_eng, 0))
        finally:
            self._updating_ui = False
            self._update_badges()

    def _update_badges(self) -> None:
        """Atualiza dinamicamente as pílulas de resumo (badges) nos cabeçalhos das seções."""
        if not hasattr(self, "sec_dimensoes"):
            return

        # 1. Dimensões
        l = self.sp_largura.value()
        a = self.sp_altura.value()
        p = self.sp_prof.value()
        self.sec_dimensoes.set_badge(f"{l}x{a}x{p} mm")

        # 2. Frentes & Estrutura
        qtd = self.sp_qtd_elem.value()
        lbl_elem = self.lbl_qtd_elem.text().replace(":", "").strip()
        prat = self.sp_prateleiras.value()
        badge_frentes = f"{qtd} {lbl_elem}"
        if prat > 0:
            badge_frentes += f" | {prat} prat."
        self.sec_frentes.set_badge(badge_frentes)

        # 3. Puxadores
        pux = self.cb_puxador_tipo.currentText()
        if pux.lower() == "sem puxador":
            self.sec_puxadores.set_badge("Nenhum")
        else:
            self.sec_puxadores.set_badge(pux)

        # 4. Materiais
        mat_caixa = self.cb_material.currentText().split("(")[0].strip()
        self.sec_materiais.set_badge(mat_caixa)

    def _apply_changes_to_selected(self) -> None:
        """Aplica as alterações dimensionais e estéticas no módulo selecionado no 3D com Undo/Redo."""
        mod = self._selected_module or self.find_selected_module()
        if mod is None:
            return

        viewport = self._get_viewport()
        scene = self._get_scene()
        if viewport is None or scene is None:
            return

        old_params = mod.ext.get("trazomob_module", {})
        tipo = old_params.get("tipo", "balcao")
        new_params = extract_ui_module_params(self, base_params=old_params)

        if "num_gavetas" in old_params or tipo in ("gaveteiro", "balcao_misto"):
            new_params["num_gavetas"] = self.sp_qtd_elem.value()
        if tipo == "balcao_misto":
            new_params["largura_gaveteiro"] = float(self.sp_largura_gaveteiro.value()) if hasattr(self, "sp_largura_gaveteiro") else float(old_params.get("largura_gaveteiro", 450.0))
        if tipo == "balcao_canto_l":
            new_params["larg_asa"] = float(self.sp_larg_asa.value()) if hasattr(self, "sp_larg_asa") else float(old_params.get("larg_asa", 550.0))
        # IDs com portas estruturalmente fixas não devem ter num_portas sobrescrito pelo spinbox
        _FIXED_PORTAS_IDS = {"armario_2p_divisao", "armario_3p_divisao"}
        if tipo in _FIXED_PORTAS_IDS:
            # Preserva o valor original já salvo nos params (sem tocar no spinbox)
            pass
        elif "num_portas" in old_params or tipo in ("balcao", "balcao_pia", "balcao_canto", "balcao_canto_l", "aereo", "aereo_basculante", "aereo_basculante_duplo", "roupeiro", "armario_prateleiras", "armario_1p_prat", "armario_1p_cabide", "armario_2p_prat"):
            new_params["num_portas"] = self.sp_qtd_elem.value()
        new_params["num_prateleiras"] = self.sp_prateleiras.value()
        if hasattr(self, "sp_divisoes"):
            new_params["num_divisoes"] = self.sp_divisoes.value()

        # Parâmetros de travessas (apenas para módulos de cozinha inferiores)
        _IDS_COZINHA_INFERIORES = {
            "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
            "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
        }
        if tipo in _IDS_COZINHA_INFERIORES and hasattr(self, "chk_travessa_frontal_em_pe"):
            tf_em_pe = self.chk_travessa_frontal_em_pe.isChecked()
            tt_em_pe = self.chk_travessa_traseira_em_pe.isChecked()
            new_params["travessa_frontal_em_pe"] = tf_em_pe
            new_params["travessa_traseira_em_pe"] = tt_em_pe
            new_params["larg_travessa_frontal_mm"] = float(self.sp_larg_travessa_frontal.value())
            new_params["larg_travessa_traseira_mm"] = float(self.sp_larg_travessa_traseira.value())
            new_params["recuo_porta_topo_mm"] = float(self.sp_recuo_porta_topo.value())
            # Compatibilidade legada
            new_params["larg_travessa_mm"] = float(self.sp_larg_travessa_frontal.value())
            new_params["recuo_porta_pia_mm"] = float(self.sp_recuo_porta_topo.value())

            # Material e espessura das travessas
            if hasattr(self, "cb_material_travessas"):
                mat_tr_txt = self.cb_material_travessas.currentText()
                esp_tr_txt = self.cb_espessura_travessas.currentText()
                esp_mm_caixa = float(new_params.get("espessura", 15.0))
                esp_tr_mm = esp_mm_caixa if esp_tr_txt.startswith("(") else float(esp_tr_txt.split()[0])
                if mat_tr_txt.startswith("("):
                    new_params["material_travessas"] = None
                else:
                    new_params["material_travessas"] = f"{mat_tr_txt} {int(esp_tr_mm)}mm"
                new_params["esp_travessas_mm"] = None if esp_tr_txt.startswith("(") else esp_tr_mm
                new_params["espessura_travessas"] = new_params["esp_travessas_mm"]

            # Fita de borda das travessas
            if hasattr(self, "cb_fita_travessas"):
                fita_modos = ["frontal_1L", "2L", "4L", "sem_fita"]
                f_idx = self.cb_fita_travessas.currentIndex()
                new_params["fita_travessas_modo"] = fita_modos[f_idx] if 0 <= f_idx < len(fita_modos) else "frontal_1L"

            if hasattr(self, "cb_material_fita_travessas"):
                mat_ftr_txt = self.cb_material_fita_travessas.currentText()
                new_params["material_fita_travessas"] = None if mat_ftr_txt.startswith("(") else mat_ftr_txt

        # Parâmetros de Forno (balcao_forno)
        if tipo == "balcao_forno":
            new_params["tem_gaveta"] = bool(self.chk_forno_tem_gaveta.isChecked())
            new_params["alt_gaveta_mm"] = float(self.sp_forno_alt_gaveta.value())

        # Parâmetros de Geladeira (caixa_geladeira)
        if tipo == "caixa_geladeira":
            new_params["alt_nicho_geladeira_mm"] = float(self.sp_geladeira_alt_nicho.value())
            is_basc = (self.cb_geladeira_tipo_porta.currentIndex() == 1)
            new_params["tipo_porta_superior"] = "basculante" if is_basc else "duas_portas"
            new_params["num_portas"] = 1 if is_basc else 2

        # Parâmetros de Aéreo Micro-ondas (aereo_microondas)
        if tipo == "aereo_microondas":
            is_basc_m = (self.cb_micro_tipo_porta.currentIndex() == 0)
            new_params["tipo_porta_superior"] = "basculante" if is_basc_m else "duas_portas"
            new_params["num_portas"] = 1 if is_basc_m else 2

        # Parâmetros de Caixa de Gaveta
        has_gav = ("num_gavetas" in new_params) or (tipo in ("gaveteiro", "balcao_misto", "torre_quente", "gabinete_banheiro")) or (tipo == "balcao_forno" and new_params.get("tem_gaveta", True))
        if has_gav and hasattr(self, "cb_tipo_fundo_gaveta"):
            new_params["tipo_fundo_gaveta"] = "por_baixo" if self.cb_tipo_fundo_gaveta.currentIndex() == 1 else "rasgo"
            new_params["folga_corredica_mm"] = float(self.sp_folga_corredica.value())

            mat_g_txt = self.cb_material_gaveta.currentText()
            esp_g_txt = self.cb_espessura_gaveta.currentText()
            esp_g_mm = float(esp_g_txt.split()[0])
            new_params["material_gaveta"] = None if mat_g_txt.startswith("(") else f"{mat_g_txt} {int(esp_g_mm)}mm"
            new_params["esp_gaveta_mm"] = esp_g_mm

            mat_fg_txt = self.cb_material_fita_gaveta.currentText()
            new_params["material_fita_gaveta"] = None if mat_fg_txt.startswith("(") else mat_fg_txt

            mat_fd_txt = self.cb_material_fundo_gaveta.currentText()
            esp_fd_txt = self.cb_esp_fundo_gaveta.currentText()
            esp_fd_mm = float(esp_fd_txt.split()[0])
            if mat_fd_txt.startswith("("):
                new_params["material_fundo_gaveta"] = f"MDF Fundo {int(esp_fd_mm)}mm" if esp_fd_mm <= 6.0 else f"MDF Branco TX {int(esp_fd_mm)}mm"
            else:
                new_params["material_fundo_gaveta"] = f"{mat_fd_txt} {int(esp_fd_mm)}mm"
            new_params["esp_fundo_gaveta_mm"] = esp_fd_mm

        # Parâmetros de Marmoraria / Bancada de Pedra
        if "bancada" in str(tipo):
            new_params["esp_pedra"] = float(self.sp_esp_pedra.value())
            new_params["altura_saia"] = float(self.sp_altura_saia.value())
            new_params["altura_frontao"] = float(self.sp_altura_frontao.value())
            new_params["tem_saia_esq"] = bool(self.chk_tem_saia_esq.isChecked())
            new_params["tem_saia_dir"] = bool(self.chk_tem_saia_dir.isChecked())
            if tipo in ("bancada_canto_l", "bancada_canto"):
                new_params["larg_asa"] = float(self.sp_larg_asa.value())

            tem_cuba = bool(old_params.get("has_cuba", (tipo == "bancada_pia")))
            if tem_cuba:
                cuba_tipos = ["inox_simples", "inox_dupla", "esculpida", "sem_cuba"]
                idx_cb = self.cb_tipo_cuba.currentIndex()
                new_params["tipo_cuba"] = cuba_tipos[idx_cb] if 0 <= idx_cb < len(cuba_tipos) else "inox_simples"

                cuba_posicoes = ["centro", "esquerda", "direita"]
                idx_cp = self.cb_posicao_cuba.currentIndex()
                new_params["posicao_cuba"] = cuba_posicoes[idx_cp] if 0 <= idx_cp < len(cuba_posicoes) else "centro"

                new_params["tem_torneira"] = bool(self.chk_tem_torneira.isChecked())
                new_params["canto_recorte"] = "arredondado" if self.cb_canto_recorte.currentIndex() == 0 else "reto"
                new_params["raio_canto_mm"] = 20.0 if new_params["canto_recorte"] == "arredondado" else 0.0
                new_params["tem_area_molhada"] = bool(self.chk_tem_area_molhada.isChecked())
                new_params["has_cuba"] = (new_params["tipo_cuba"] != "sem_cuba")

        # Parâmetros de Tampo Engrossado (peca_tampo_engrossado)
        if tipo in ("peca_tampo_engrossado", "tampo_engrossado"):
            if hasattr(self, "cb_tampo_esp_chapa"):
                txt_esp_ch = self.cb_tampo_esp_chapa.currentText()
                new_params["esp_chapa"] = float(txt_esp_ch.split()[0])
            if hasattr(self, "sp_tampo_larg_engrosso"):
                new_params["larg_engrosso"] = float(self.sp_tampo_larg_engrosso.value())
            if hasattr(self, "sp_tampo_qtd_engrosso"):
                new_params["qtd_engrosso"] = int(self.sp_tampo_qtd_engrosso.value())
            if hasattr(self, "chk_tampo_fechar_embaixo"):
                new_params["fechar_embaixo"] = bool(self.chk_tampo_fechar_embaixo.isChecked())
            if hasattr(self, "cb_tampo_tipo_engrosso"):
                idx_te = self.cb_tampo_tipo_engrosso.currentIndex()
                tipo_eng_list = ["3_lados", "4_lados", "1_lado"]
                new_params["tipo_engrosso"] = tipo_eng_list[idx_te] if idx_te < len(tipo_eng_list) else "3_lados"

        # RotateGroupCommand (ferramenta Q) e RotateTrazoMobModuleCommand já mantêm
        # o parâmetro 'rot_z' e 'rot_matrix_3d' atualizados em old_params!
        rot_z_eff = float(new_params.get("rot_z", old_params.get("rot_z", 0.0)) or 0.0) % 360.0
        new_params["rot_z"] = rot_z_eff
        if "rot_matrix_3d" in old_params and isinstance(old_params["rot_matrix_3d"], (list, tuple)):
            new_params["rot_matrix_3d"] = list(old_params["rot_matrix_3d"])

        # Usa o offset salvo nos parâmetros (ponto de inserção original do módulo).
        offset = old_params.get("offset", (0.0, 0.0, 0.0))
        if not isinstance(offset, (list, tuple)) or len(offset) < 3:
            offset = (0.0, 0.0, 0.0)
        offset = tuple(float(v) for v in offset)

        from .magnetic_drag import get_module_bounds
        from .module_ribbon import get_module_carcass_bounds, preserve_module_back_alignment
        b_old = get_module_carcass_bounds(mod) or get_module_bounds(mod)

        # Reconstrói o módulo já com a rotação efetiva consolidada nos vértices (e xform = Identidade)
        new_module_group = CabinetBuilder.build_module_group(new_params, offset=offset)
        b_new = get_module_carcass_bounds(new_module_group) or get_module_bounds(new_module_group)

        # ── PRESERVAÇÃO RIGOROSA DA POSIÇÃO E ROTAÇÃO ──────────────────
        has_3d_rot = isinstance(new_params.get("rot_matrix_3d"), (list, tuple)) and len(new_params["rot_matrix_3d"]) == 16
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
            preserve_module_back_alignment(mod, new_module_group, rot_z_eff)

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
                L_m = float(new_params.get("largura", 800.0)) / 1000.0
                P_m = float(new_params.get("profundidade", 550.0)) / 1000.0
                mod_ext["offset"] = (
                    cx_final - L_m * 0.5,
                    cy_final - P_m * 0.5,
                    b_final[4],
                )

        # Matriz xform do novo módulo permanece limpa (identidade),
        # pois a rotação 'rot_z' e a posição espacial já estão consolidadas na geometria dos vértices.

        # Transação segura no Histórico
        old_mod = mod

        def apply_transaction(sc):
            target_layer = getattr(new_module_group, 'layer', None)
            if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            if old_mod in sc.groups:
                sc.groups.remove(old_mod)
            sc.groups.append(new_module_group)
            sc.selection = {new_module_group}

        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(SnapshotImport(apply_transaction))
        else:
            apply_transaction(scene)

        self._selected_module = new_module_group
        # Invalida caches do renderer
        for _cn in ("_group_chunks", "_inst_chunks"):
            _c = getattr(viewport, _cn, None)
            if isinstance(_c, dict):
                _c.clear()
        if hasattr(viewport, "_placements_memo"):
            viewport._placements_memo = None
        viewport.update()

        self.lbl_status.setText(f"✅ Atualizado: {new_module_group.name}")

    def _on_apply_puxadores_to_all_modules(self) -> None:
        """Aplica o modelo, cor e posição de puxador selecionados a todos os armários da cena (estilo Promob)."""
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None:
            return

        # Coleta os parâmetros de puxador atuais da interface
        pux_params = extract_ui_module_params(self)
        pux_tipo = pux_params.get("puxador_tipo", "alca")
        pux_cor = pux_params.get("puxador_cor", "preto")
        pux_pos = pux_params.get("puxador_pos", "padrao")
        perfil_mod = pux_params.get("perfil_modelo", "gola")
        desc_perfil = pux_params.get("desconto_perfil", 35.0)

        # Localiza todos os grupos de módulos TrazoMob na cena que possuem portas ou gavetas
        all_modules = [
            g for g in getattr(scene, "groups", [])
            if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext
        ]

        if not all_modules:
            self.lbl_status.setText("ℹ️ Nenhum módulo TrazoMob encontrado na cena.")
            return

        from .builder import CabinetBuilder
        from .magnetic_drag import get_module_bounds
        from .module_ribbon import get_module_carcass_bounds, preserve_module_back_alignment
        from core.history import SnapshotImport

        replacements = []
        for mod in all_modules:
            old_params = mod.ext.get("trazomob_module", {})
            tipo = str(old_params.get("tipo", "")).lower()

            # Pula bancadas/tampos/pedras sem portas ou gavetas
            if any(k in tipo for k in ("bancada", "tampo_engrossado", "peca_")):
                continue

            # Clona parâmetros e injeta as novas configurações de puxador
            new_params = dict(old_params)
            new_params["puxador_tipo"] = pux_tipo
            new_params["puxador_cor"] = pux_cor
            new_params["puxador_pos"] = pux_pos
            new_params["perfil_modelo"] = perfil_mod
            new_params["desconto_perfil"] = desc_perfil

            offset = old_params.get("offset", (0.0, 0.0, 0.0))
            if not isinstance(offset, (list, tuple)) or len(offset) < 3:
                offset = (0.0, 0.0, 0.0)
            offset = tuple(float(v) for v in offset)

            rot_z_eff = float(new_params.get("rot_z", 0.0) or 0.0) % 360.0

            # Reconstrói com os novos puxadores
            new_mod_group = CabinetBuilder.build_module_group(new_params, offset=offset)
            preserve_module_back_alignment(mod, new_mod_group, rot_z_eff)

            b_final = get_module_carcass_bounds(new_mod_group) or get_module_bounds(new_mod_group)
            if b_final and "trazomob_module" in new_mod_group.ext:
                mod_ext = new_mod_group.ext["trazomob_module"]
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

            replacements.append((mod, new_mod_group))

        if not replacements:
            self.lbl_status.setText("ℹ️ Nenhum armário com portas/gavetas encontrado.")
            return

        def apply_batch_transaction(sc):
            for old_m, new_m in replacements:
                target_layer = getattr(new_m, 'layer', None)
                if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                    if sc.layer(target_layer) is None:
                        from core.layers import Layer
                        sc.layers.append(Layer(target_layer))
                if old_m in sc.groups:
                    sc.groups.remove(old_m)
                sc.groups.append(new_m)
            # Mantém selecionado o primeiro
            if replacements:
                sc.selection = {replacements[0][1]}

        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(SnapshotImport(apply_batch_transaction))
        else:
            apply_batch_transaction(scene)

        # Invalida caches do renderer
        for _cn in ("_group_chunks", "_inst_chunks"):
            _c = getattr(viewport, _cn, None)
            if isinstance(_c, dict):
                _c.clear()
        if hasattr(viewport, "_placements_memo"):
            viewport._placements_memo = None
        viewport.update()

        pux_label = self.cb_puxador_tipo.currentText()
        self.lbl_status.setText(f"✨ Puxadores aplicados a {len(replacements)} armários ({pux_label})!")

    def _on_apply_frentes_to_all_modules(self) -> None:
        """Troca o material e cor das frentes (portas e gavetas) de todos os módulos da cena (estilo Promob)."""
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None or viewport is None:
            return

        mat_frente_txt = self.cb_material_frentes.currentText()
        esp_frente_txt = self.cb_espessura_frentes.currentText()

        all_modules = [
            g for g in getattr(scene, "groups", [])
            if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext
        ]

        if not all_modules:
            self.lbl_status.setText("ℹ️ Nenhum módulo TrazoMob encontrado na cena.")
            return

        from .builder import CabinetBuilder
        from .magnetic_drag import get_module_bounds
        from .module_ribbon import get_module_carcass_bounds, preserve_module_back_alignment
        from core.history import SnapshotImport

        replacements = []
        for mod in all_modules:
            old_params = mod.ext.get("trazomob_module", {})
            tipo = str(old_params.get("tipo", "")).lower()

            if any(k in tipo for k in ("bancada", "tampo_engrossado", "peca_")):
                continue

            new_params = dict(old_params)

            # Resolve material de frentes
            mat_caixa = new_params.get("material", "MDF Branco TX 15mm")
            esp_caixa = float(new_params.get("espessura", 15.0))
            if mat_frente_txt.startswith("("):
                chosen_mat_frente = mat_caixa.rsplit(" ", 1)[0]
            else:
                chosen_mat_frente = mat_frente_txt

            if esp_frente_txt.startswith("("):
                chosen_esp_frente = esp_caixa
            else:
                chosen_esp_frente = float(esp_frente_txt.split()[0])

            new_params["material_frentes"] = f"{chosen_mat_frente} {int(chosen_esp_frente)}mm"
            new_params["espessura_frentes"] = chosen_esp_frente

            offset = old_params.get("offset", (0.0, 0.0, 0.0))
            if not isinstance(offset, (list, tuple)) or len(offset) < 3:
                offset = (0.0, 0.0, 0.0)
            offset = tuple(float(v) for v in offset)

            rot_z_eff = float(new_params.get("rot_z", 0.0) or 0.0) % 360.0

            new_mod_group = CabinetBuilder.build_module_group(new_params, offset=offset)
            preserve_module_back_alignment(mod, new_mod_group, rot_z_eff)

            b_final = get_module_carcass_bounds(new_mod_group) or get_module_bounds(new_mod_group)
            if b_final and "trazomob_module" in new_mod_group.ext:
                mod_ext = new_mod_group.ext["trazomob_module"]
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

            replacements.append((mod, new_mod_group))

        if not replacements:
            self.lbl_status.setText("ℹ️ Nenhum armário com frentes encontrado.")
            return

        def apply_batch_frentes(sc):
            for old_m, new_m in replacements:
                target_layer = getattr(new_m, 'layer', None)
                if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                    if sc.layer(target_layer) is None:
                        from core.layers import Layer
                        sc.layers.append(Layer(target_layer))
                if old_m in sc.groups:
                    sc.groups.remove(old_m)
                sc.groups.append(new_m)
            if replacements:
                sc.selection = {replacements[0][1]}

        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(SnapshotImport(apply_batch_frentes))
        else:
            apply_batch_frentes(scene)

        for _cn in ("_group_chunks", "_inst_chunks"):
            _c = getattr(viewport, _cn, None)
            if isinstance(_c, dict):
                _c.clear()
        if hasattr(viewport, "_placements_memo"):
            viewport._placements_memo = None

        # Salva nas preferências globais para novos módulos
        from .preferences import TrazoMobPreferencesManager
        prefs = TrazoMobPreferencesManager.get_instance()
        if not mat_frente_txt.startswith("("):
            prefs.set_global("material_frentes", mat_frente_txt)
        if not esp_frente_txt.startswith("("):
            prefs.set_global("espessura_frentes_mm", float(esp_frente_txt.split()[0]))
        prefs.save()

        viewport.notify_scene_changed()
        viewport.update()
        self.lbl_status.setText(f"🎨 Padrão de frentes atualizado em {len(replacements)} armário(s) ({mat_frente_txt})!")

    def _on_apply_caixa_to_all_modules(self) -> None:
        """Troca o material e cor da caixaria de todos os módulos da cena (estilo Promob)."""
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None or viewport is None:
            return

        mat_caixa_txt = self.cb_material.currentText()
        esp_caixa_txt = self.cb_espessura.currentText()
        esp_caixa_val = float(esp_caixa_txt.split()[0])

        all_modules = [
            g for g in getattr(scene, "groups", [])
            if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext
        ]

        if not all_modules:
            self.lbl_status.setText("ℹ️ Nenhum módulo TrazoMob encontrado na cena.")
            return

        from .builder import CabinetBuilder
        from .magnetic_drag import get_module_bounds
        from .module_ribbon import get_module_carcass_bounds, preserve_module_back_alignment
        from core.history import SnapshotImport

        replacements = []
        for mod in all_modules:
            old_params = mod.ext.get("trazomob_module", {})
            tipo = str(old_params.get("tipo", "")).lower()

            if any(k in tipo for k in ("bancada", "tampo_engrossado", "peca_")):
                continue

            new_params = dict(old_params)
            new_params["material"] = f"{mat_caixa_txt} {int(esp_caixa_val)}mm"
            new_params["espessura"] = esp_caixa_val

            offset = old_params.get("offset", (0.0, 0.0, 0.0))
            if not isinstance(offset, (list, tuple)) or len(offset) < 3:
                offset = (0.0, 0.0, 0.0)
            offset = tuple(float(v) for v in offset)

            rot_z_eff = float(new_params.get("rot_z", 0.0) or 0.0) % 360.0

            new_mod_group = CabinetBuilder.build_module_group(new_params, offset=offset)
            preserve_module_back_alignment(mod, new_mod_group, rot_z_eff)

            b_final = get_module_carcass_bounds(new_mod_group) or get_module_bounds(new_mod_group)
            if b_final and "trazomob_module" in new_mod_group.ext:
                mod_ext = new_mod_group.ext["trazomob_module"]
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

            replacements.append((mod, new_mod_group))

        if not replacements:
            self.lbl_status.setText("ℹ️ Nenhum armário encontrado.")
            return

        def apply_batch_caixa(sc):
            for old_m, new_m in replacements:
                target_layer = getattr(new_m, 'layer', None)
                if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                    if sc.layer(target_layer) is None:
                        from core.layers import Layer
                        sc.layers.append(Layer(target_layer))
                if old_m in sc.groups:
                    sc.groups.remove(old_m)
                sc.groups.append(new_m)
            if replacements:
                sc.selection = {replacements[0][1]}

        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(SnapshotImport(apply_batch_caixa))
        else:
            apply_batch_caixa(scene)

        for _cn in ("_group_chunks", "_inst_chunks"):
            _c = getattr(viewport, _cn, None)
            if isinstance(_c, dict):
                _c.clear()
        if hasattr(viewport, "_placements_memo"):
            viewport._placements_memo = None

        # Salva nas preferências globais para novos módulos
        from .preferences import TrazoMobPreferencesManager
        prefs = TrazoMobPreferencesManager.get_instance()
        prefs.set_global("material_caixa", mat_caixa_txt)
        prefs.set_global("espessura_caixa_mm", esp_caixa_val)
        prefs.save()

        viewport.notify_scene_changed()
        viewport.update()
        self.lbl_status.setText(f"🪵 Padrão de caixaria atualizado em {len(replacements)} armário(s) ({mat_caixa_txt})!")

    def _on_apply_travessas_to_all_modules(self) -> None:
        """Aplica a orientação (em pé/deitada), larguras e materiais de travessa a todos os balcões da cena."""
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None:
            return

        curr_params = extract_ui_module_params(self)
        _IDS_COZINHA_INFERIORES = {
            "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
            "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
        }

        all_modules = [
            g for g in getattr(scene, "groups", [])
            if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext
        ]

        if not all_modules:
            self.lbl_status.setText("ℹ️ Nenhum módulo TrazoMob encontrado na cena.")
            return

        from .builder import CabinetBuilder
        from .magnetic_drag import get_module_bounds
        from .module_ribbon import get_module_carcass_bounds, preserve_module_back_alignment
        from core.history import SnapshotImport

        replacements = []
        for mod in all_modules:
            old_params = mod.ext.get("trazomob_module", {})
            tipo = str(old_params.get("tipo", "")).lower()

            if tipo not in _IDS_COZINHA_INFERIORES:
                continue

            new_params = dict(old_params)
            new_params["travessa_frontal_em_pe"] = bool(curr_params.get("travessa_frontal_em_pe", False))
            new_params["travessa_traseira_em_pe"] = bool(curr_params.get("travessa_traseira_em_pe", False))
            new_params["larg_travessa_frontal_mm"] = float(curr_params.get("larg_travessa_frontal_mm", 70.0))
            new_params["larg_travessa_traseira_mm"] = float(curr_params.get("larg_travessa_traseira_mm", 70.0))
            new_params["recuo_porta_topo_mm"] = float(curr_params.get("recuo_porta_topo_mm", 50.0))
            new_params["material_travessas"] = curr_params.get("material_travessas")
            new_params["esp_travessas_mm"] = curr_params.get("esp_travessas_mm")
            new_params["espessura_travessas"] = new_params["esp_travessas_mm"]
            new_params["fita_travessas_modo"] = curr_params.get("fita_travessas_modo", "frontal_1L")
            new_params["material_fita_travessas"] = curr_params.get("material_fita_travessas")

            offset = old_params.get("offset", (0.0, 0.0, 0.0))
            if not isinstance(offset, (list, tuple)) or len(offset) < 3:
                offset = (0.0, 0.0, 0.0)
            offset = tuple(float(v) for v in offset)

            rot_z_eff = float(new_params.get("rot_z", 0.0) or 0.0) % 360.0

            new_mod_group = CabinetBuilder.build_module_group(new_params, offset=offset)
            preserve_module_back_alignment(mod, new_mod_group, rot_z_eff)

            b_final = get_module_carcass_bounds(new_mod_group) or get_module_bounds(new_mod_group)
            if b_final and "trazomob_module" in new_mod_group.ext:
                mod_ext = new_mod_group.ext["trazomob_module"]
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

            replacements.append((mod, new_mod_group))

        if not replacements:
            self.lbl_status.setText("ℹ️ Nenhum balcão inferior de cozinha encontrado na cena.")
            return

        def apply_batch_transaction(sc):
            for old_m, new_m in replacements:
                target_layer = getattr(new_m, 'layer', None)
                if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                    if sc.layer(target_layer) is None:
                        from core.layers import Layer
                        sc.layers.append(Layer(target_layer))
                if old_m in sc.groups:
                    sc.groups.remove(old_m)
                sc.groups.append(new_m)
            if replacements:
                sc.selection = {replacements[0][1]}

        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(SnapshotImport(apply_batch_transaction))
        else:
            apply_batch_transaction(scene)

        for _cn in ("_group_chunks", "_inst_chunks"):
            _c = getattr(viewport, _cn, None)
            if isinstance(_c, dict):
                _c.clear()
        if hasattr(viewport, "_placements_memo"):
            viewport._placements_memo = None

        # Salva também nas preferências globais para novos módulos
        from .preferences import TrazoMobPreferencesManager
        prefs = TrazoMobPreferencesManager.get_instance()
        prefs.set_global("travessa_frontal_em_pe", bool(curr_params.get("travessa_frontal_em_pe", False)))
        prefs.set_global("travessa_traseira_em_pe", bool(curr_params.get("travessa_traseira_em_pe", False)))
        prefs.set_global("larg_travessa_frontal_mm", float(curr_params.get("larg_travessa_frontal_mm", 70.0)))
        prefs.set_global("larg_travessa_traseira_mm", float(curr_params.get("larg_travessa_traseira_mm", 70.0)))
        prefs.save()

        viewport.notify_scene_changed()
        viewport.update()
        self.lbl_status.setText(f"✅ Travessas atualizadas em {len(replacements)} balcão(ões)!")

    def _on_encaixar_bancada_sobre_balcoes(self) -> None:
        """Gera e encaixa perfeitamente uma bancada de pedra/tampo sobre todos os balcões da parede selecionada."""
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None or viewport is None:
            return

        from .wall_selection import WallSelectionManager
        wall_mgr = WallSelectionManager.get_instance(viewport)
        sel_wf = wall_mgr.selected_wall_face
        if sel_wf is None or sel_wf.face is None:
            self.lbl_status.setText("⚠️ Nenhuma face de parede selecionada para referenciar os balcões.")
            return

        norm = sel_wf.normal
        n_dir = QVector3D(norm.x(), norm.y(), 0.0).normalized()
        u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()

        from .magnetic_drag import get_module_bounds, get_bounds_min_projection
        from .module_ribbon import get_module_carcass_bounds

        _IDS_BALCOES = {
            "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
            "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
        }

        # Localiza os balcões da cena encostados nesta parede
        balcoes_na_parede = []
        xf = getattr(sel_wf.wall_group, "xform", None)
        c_wall = xf.map(sel_wf.center) if xf is not None else sel_wf.center
        wall_n = QVector3D.dotProduct(c_wall, n_dir)

        for g in getattr(scene, "groups", []):
            ext = getattr(g, "ext", {})
            if isinstance(ext, dict) and "trazomob_module" in ext:
                tipo = str(ext["trazomob_module"].get("tipo", "")).lower()
                if tipo in _IDS_BALCOES:
                    b = get_module_carcass_bounds(g) or get_module_bounds(g)
                    if b is not None:
                        # Verifica se a base Z é compatível com balcão (<= 1.10m)
                        if b[4] <= 1.10:
                            # Verifica se as costas estão encostadas nesta parede
                            cur_min_n = get_bounds_min_projection(b, n_dir)
                            if abs(cur_min_n - wall_n) < 0.05:  # tolerância de 5cm
                                balcoes_na_parede.append((g, b))

        if not balcoes_na_parede:
            self.lbl_status.setText("ℹ️ Nenhum balcão inferior encontrado encostado nesta parede.")
            return

        # Calcula a extensão total ao longo de u_dir, profundidade e altura de apoio (top_z)
        all_bounds = [b for _, b in balcoes_na_parede]
        top_z = max(b[5] for b in all_bounds)
        max_depth = max(b[3] - b[2] if abs(n_dir.y()) > 0.5 else b[1] - b[0] for b in all_bounds)

        u_projs = []
        for b in all_bounds:
            corners = [
                QVector3D(b[0], b[2], 0.0), QVector3D(b[1], b[2], 0.0),
                QVector3D(b[0], b[3], 0.0), QVector3D(b[1], b[3], 0.0)
            ]
            for c in corners:
                u_projs.append(QVector3D.dotProduct(c, u_dir))

        min_u = min(u_projs)
        max_u = max(u_projs)
        total_larg_m = max_u - min_u
        center_u = (min_u + max_u) * 0.5

        import math
        angle_deg = math.degrees(math.atan2(n_dir.y(), n_dir.x())) + 90.0
        rot_z = (round(angle_deg / 90.0) * 90.0) % 360.0

        from .preferences import TrazoMobPreferencesManager
        prefs = TrazoMobPreferencesManager.get_instance()
        esp_pedra = float(prefs.get_module_default("bancada", "esp_pedra", 20.0))
        altura_saia = float(prefs.get_module_default("bancada", "altura_saia", 40.0))
        altura_frontao = float(prefs.get_module_default("bancada", "altura_frontao", 100.0))

        params_tampo = {
            "tipo": "bancada_reta",
            "largura": round(total_larg_m * 1000.0),
            "profundidade": round(max_depth * 1000.0),
            "altura": altura_saia,
            "esp_pedra": esp_pedra,
            "altura_saia": altura_saia,
            "altura_frontao": altura_frontao,
            "balanco_frontal_mm": 20.0,
            "tem_frontao_traseiro": True,
            "tem_saia_esq": True,
            "tem_saia_dir": True,
            "material": "Granito Preto São Gabriel 20mm",
            "rot_z": rot_z,
        }

        from .builder import CabinetBuilder
        g_tampo = CabinetBuilder.build_module_group(params_tampo, offset=(0.0, 0.0, 0.0))
        b_t = get_module_carcass_bounds(g_tampo) or get_module_bounds(g_tampo)

        if b_t is not None:
            cur_min_n = get_bounds_min_projection(b_t, n_dir)
            shift_n = (wall_n - cur_min_n) + 0.001

            cur_center_u = QVector3D.dotProduct(QVector3D((b_t[0] + b_t[1]) * 0.5, (b_t[2] + b_t[3]) * 0.5, 0.0), u_dir)
            shift_u = center_u - cur_center_u
            shift_z = top_z - b_t[4]

            shift = n_dir * shift_n + u_dir * shift_u + QVector3D(0.0, 0.0, shift_z)

            targets = getattr(g_tampo, "children", []) or [g_tampo]
            for t in targets:
                m_sub = getattr(t, "mesh", None)
                if m_sub and hasattr(m_sub, "vertices"):
                    for v in m_sub.vertices:
                        v.position += shift
                    m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
            if "trazomob_module" in g_tampo.ext:
                g_tampo.ext["trazomob_module"]["offset"] = (float(shift.x()), float(shift.y()), float(shift.z()))

        from core.history import SnapshotImport
        def apply_insert_tampo(sc):
            target_layer = getattr(g_tampo, 'layer', None)
            if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            sc.groups.append(g_tampo)
            sc.selection = {g_tampo}

        viewport.history.execute(SnapshotImport(apply_insert_tampo))
        viewport.notify_scene_changed()
        viewport.update()

        larg_cm = int(round(total_larg_m * 100.0))
        self.lbl_status.setText(f"🪨 Bancada contínua encaixada com sucesso ({larg_cm} cm) cobrindo {len(balcoes_na_parede)} balcão(ões)!")


    def _on_abrir_elevacao_parede(self) -> None:
        """Abre a janela de Eleva??o T?cnica 2D da parede com todas as cotas milim?tricas."""
        vp = self._get_viewport()
        win = self.window()
        from .wall_elevation_dialog import WallElevationDialog
        dlg = WallElevationDialog(viewport=vp, parent=win)
        dlg.exec()

    def _on_fechar_vao_canto(self) -> None:
        """Calcula a sobra residual entre o ?ltimo m?dulo e a quina da parede e insere o arremate com sarrafo."""
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None or viewport is None:
            return

        from .wall_selection import WallSelectionManager
        wall_mgr = WallSelectionManager.get_instance(viewport)
        sel_wf = wall_mgr.selected_wall_face
        if sel_wf is None or sel_wf.face is None:
            self.lbl_status.setText("?? Selecione uma face de parede para calcular o arremate.")
            return

        norm = sel_wf.normal
        n_dir = QVector3D(norm.x(), norm.y(), 0.0).normalized()
        u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()

        xf = getattr(sel_wf.wall_group, "xform", None)
        c_wall = xf.map(sel_wf.center) if xf is not None else sel_wf.center
        raw_pts = [xf.map(p) if xf is not None else p for p in getattr(sel_wf.face, "vertices", [])]
        if not raw_pts:
            return

        projs_u = [QVector3D.dotProduct(p, u_dir) for p in raw_pts]
        min_u, max_u = min(projs_u), max(projs_u)

        # Determina o ponto de ancoragem do ?ltimo m?dulo
        slot = wall_mgr.active_placement_slot
        anchor_u = slot.get("anchor_u") if slot else None

        from .magnetic_drag import get_module_bounds
        from .module_ribbon import get_module_carcass_bounds

        # Se n?o h? anchor_u no slot, busca na cena o m?vel encostado mais ? direita
        last_u = anchor_u
        ref_mod_bounds = None
        if last_u is None:
            wall_n = QVector3D.dotProduct(c_wall, n_dir)
            max_found_u = -float("inf")
            for g in getattr(scene, "groups", []):
                ext = getattr(g, "ext", {})
                if isinstance(ext, dict) and "trazomob_module" in ext:
                    b = get_module_carcass_bounds(g) or get_module_bounds(g)
                    if b is not None:
                        corners = [
                            QVector3D(b[0], b[2], 0.0), QVector3D(b[1], b[2], 0.0),
                            QVector3D(b[0], b[3], 0.0), QVector3D(b[1], b[3], 0.0),
                        ]
                        projs_g_n = [QVector3D.dotProduct(p, n_dir) for p in corners]
                        if abs(min(projs_g_n) - wall_n) < 0.06:
                            projs_g_u = [QVector3D.dotProduct(p, u_dir) for p in corners]
                            cur_max_u = max(projs_g_u)
                            if cur_max_u > max_found_u:
                                max_found_u = cur_max_u
                                ref_mod_bounds = b
            if max_found_u > -float("inf") and max_found_u < max_u - 0.01:
                last_u = max_found_u

        if last_u is None:
            self.lbl_status.setText("?? Insira ao menos um m?dulo na parede antes de gerar o arremate.")
            return

        # V?o residual at? o final da parede
        vao_residual_m = max_u - last_u
        vao_mm = round(vao_residual_m * 1000.0)

        if vao_residual_m < 0.015:
            self.lbl_status.setText("?? N?o h? v?o residual significativo para arremate (< 15mm).")
            return

        # Altura e profundidade herdados do ?ltimo m?dulo ou do slot ativo
        if ref_mod_bounds is not None:
            alt_m = ref_mod_bounds[5] - ref_mod_bounds[4]
            prof_m = ref_mod_bounds[3] - ref_mod_bounds[2] if abs(n_dir.y()) > 0.5 else ref_mod_bounds[1] - ref_mod_bounds[0]
            z_base = ref_mod_bounds[4]
        elif slot is not None:
            alt_m = slot.get("z_top", 0.85) - slot.get("z_base", 0.0)
            prof_m = slot.get("depth_m", 0.55)
            z_base = slot.get("z_base", 0.0)
        else:
            alt_m = 0.72
            prof_m = 0.55
            z_base = 0.10

        # Rota??o do m?dulo na parede
        rot_z = math.degrees(math.atan2(-n_dir.x(), n_dir.y()))

        # Centro do fechamento
        center_u = last_u + (vao_residual_m * 0.5)
        p_wall_center = c_wall + u_dir * (center_u - QVector3D.dotProduct(c_wall, u_dir))
        p_origin = p_wall_center - u_dir * (vao_residual_m * 0.5)
        p_origin = QVector3D(p_origin.x(), p_origin.y(), z_base)

        from .builder_fechamento import FechamentoBuilder
        from .preferences import PreferencesManager
        prefs = PreferencesManager.get_instance().get_all()
        mat_frentes = prefs.get("default_material_frentes", "MDF Branco TX 15mm")

        g_arremate = FechamentoBuilder.build_fechamento_group(
            largura_mm=vao_mm,
            altura_mm=round(alt_m * 1000.0),
            prof_mm=round(prof_m * 1000.0),
            material=mat_frentes,
            offset=(p_origin.x(), p_origin.y(), p_origin.z()),
            rot_z=rot_z,
        )

        from core.history import SnapshotImport
        def apply_insert_arremate(sc):
            target_layer = getattr(g_arremate, 'layer', None)
            if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            sc.groups.append(g_arremate)
            sc.selection = {g_arremate}

        viewport.history.execute(SnapshotImport(apply_insert_arremate))
        viewport.notify_scene_changed()
        viewport.update()

        # Atualiza slot para o final da parede
        if slot is not None:
            slot["anchor_u"] = max_u

        self.lbl_status.setText(f"?? R?gua de arremate inserida com sucesso ({vao_mm} mm) com sarrafo de recuo!")

    def _on_abrir_menu_esquadrias(self) -> None:
        """Abre o menu categorizado da biblioteca de esquadrias reais (.igz) para inserção na parede."""
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: palette(base); border: 1px solid palette(mid); } "
            "QMenu::item { padding: 6px 14px; font-size: 11px; color: palette(text); } "
            "QMenu::item:selected { background: palette(highlight); color: palette(highlighted-text); } "
            "QMenu::separator { height: 1px; background: palette(midlight); margin: 3px 6px; }"
        )

        from .catalog import MODULE_CATALOG
        esquadrias = MODULE_CATALOG.get("Portas & Janelas", [])

        # Submenu: Portas
        menu_portas = menu.addMenu("🚪 Portas Reais")
        # Submenu: Janelas
        menu_janelas = menu.addMenu("🪟 Janelas & Basculantes")

        actions_map = {}
        for item in esquadrias:
            item_id = item.get("id", "")
            nome = item.get("nome", item_id)
            larg = float(item.get("largura", 800))
            alt = float(item.get("altura", 2100))
            peit = float(item.get("peitoril", 0))

            if item_id.startswith("porta_"):
                act = menu_portas.addAction(f"🚪 {nome}")
            else:
                peit_label = f" (Peitoril {int(peit)}mm)" if peit > 0 else ""
                act = menu_janelas.addAction(f"🪟 {nome}{peit_label}")
            actions_map[act] = (item_id, larg, alt, peit)

        # Acesso rápido aos favoritos diretamente no menu raiz
        menu.addSeparator()
        act_quick_p80 = menu.addAction("⚡ Porta Giro 80x215 cm")
        act_quick_j130 = menu.addAction("⚡ Janela Correr 2F 130x120 cm (Peitoril 100cm)")
        actions_map[act_quick_p80] = ("porta_giro_80", 800.0, 2150.0, 0.0)
        actions_map[act_quick_j130] = ("janela_correr_2f_130", 1300.0, 1200.0, 1000.0)

        action = menu.exec(self.btn_inserir_esquadria.mapToGlobal(self.btn_inserir_esquadria.rect().bottomLeft()))
        if not action or action not in actions_map:
            return

        tipo_sel, larg_sel, alt_sel, peit_sel = actions_map[action]
        self._inserir_esquadria_na_parede(tipo_sel, largura_mm=larg_sel, altura_mm=alt_sel, peitoril_mm=peit_sel)

    def _inserir_esquadria_na_parede(self, tipo: str, largura_mm: float, altura_mm: float, peitoril_mm: float = 0.0) -> None:
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None or viewport is None:
            return

        from .wall_selection import WallSelectionManager
        wall_mgr = WallSelectionManager.get_instance(viewport)
        sel_wf = wall_mgr.selected_wall_face
        if sel_wf is None or sel_wf.face is None:
            self.lbl_status.setText("?? Selecione uma parede para posicionar a esquadria.")
            return

        norm = sel_wf.normal
        n_dir = QVector3D(norm.x(), norm.y(), 0.0).normalized()
        u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()

        xf = getattr(sel_wf.wall_group, "xform", None)
        c_wall = xf.map(sel_wf.center) if xf is not None else sel_wf.center

        # Espessura da parede
        params_w = getattr(sel_wf.wall_group, "ext", {}).get("trazomob_wall", {})
        esp_parede_mm = round(float(params_w.get("espessura", 0.15)) * 1000.0)

        # Rota??o Z
        rot_z = math.degrees(math.atan2(-n_dir.x(), n_dir.y()))

        # Posicionamento horizontal: usa anchor_u se houver, ou centralizado
        slot = wall_mgr.active_placement_slot
        anchor_u = slot.get("anchor_u") if slot else None

        raw_pts = [xf.map(p) if xf is not None else p for p in getattr(sel_wf.face, "vertices", [])]
        projs_u = [QVector3D.dotProduct(p, u_dir) for p in raw_pts] if raw_pts else [0.0]
        min_u, max_u = min(projs_u), max(projs_u)

        larg_m = largura_mm / 1000.0
        if anchor_u is not None and anchor_u + larg_m <= max_u:
            start_u = anchor_u
        else:
            # Centraliza no v?o restante ou na parede
            start_u = (min_u + max_u - larg_m) * 0.5

        center_u = start_u + (larg_m * 0.5)
        p_center = c_wall + u_dir * (center_u - QVector3D.dotProduct(c_wall, u_dir))
        p_origin = p_center - u_dir * (larg_m * 0.5)
        p_origin = QVector3D(p_origin.x(), p_origin.y(), 0.0)

        from .builder_esquadrias import EsquadriaBuilder
        # Carrega o modelo com fallback inteligente e alta fidelidade
        g_esq = EsquadriaBuilder.load_esquadria_igz(
            item_id=tipo,
            largura_mm=largura_mm,
            altura_mm=altura_mm,
            esp_parede_mm=esp_parede_mm,
            peitoril_mm=peitoril_mm,
            offset=(p_origin.x(), p_origin.y(), p_origin.z()),
            rot_z=rot_z,
        )

        from core.history import SnapshotImport
        def apply_insert_esq(sc):
            target_layer = getattr(g_esq, 'layer', None)
            if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            sc.groups.append(g_esq)
            sc.selection = {g_esq}

            # ── ABERTURA / RECORTE DO VÃO NA PAREDE HOSPEDEIRA ──
            wall_grp = getattr(sel_wf, "wall_group", None)
            if wall_grp is not None and hasattr(wall_grp, "ext") and isinstance(wall_grp.ext, dict) and "trazomob_wall" in wall_grp.ext:
                w_ext = wall_grp.ext["trazomob_wall"]
                pts_data = w_ext.get("pontos", [])
                is_closed = w_ext.get("is_closed", False)
                seg_idx = getattr(sel_wf, "segment_index", 0)
                n_pts = len(pts_data)
                n_segs = n_pts if is_closed else max(0, n_pts - 1)

                if 0 <= seg_idx < n_segs:
                    p0 = QVector3D(*pts_data[seg_idx])
                    p1 = QVector3D(*pts_data[(seg_idx + 1) % n_pts])
                    seg_v = p1 - p0
                    seg_len = seg_v.length()

                    if seg_len > 0.05:
                        seg_u_dir = seg_v.normalized()
                        # Projeta o centro da esquadria no segmento
                        proj_c = QVector3D.dotProduct(p_center - p0, seg_u_dir)
                        half_w = (largura_mm / 1000.0) * 0.5
                        u0_m = max(0.0, proj_c - half_w)
                        u1_m = min(seg_len, proj_c + half_w)

                        u0_frac = u0_m / seg_len
                        u1_frac = u1_m / seg_len

                        openings = w_ext.setdefault("openings", [])
                        openings.append({
                            "segment_index": seg_idx,
                            "u0": u0_frac,
                            "u1": u1_frac,
                            "altura_m": float(altura_mm) / 1000.0,
                            "peitoril_m": float(peitoril_mm) / 1000.0,
                        })

                        # Reconstrói a malha da parede com o recorte aplicado
                        from .wall_builder import WallBuilderTool
                        pts_vec = [QVector3D(p[0], p[1], p[2]) for p in pts_data]
                        new_mesh, face_map = WallBuilderTool.compute_wall_mesh(
                            pts=pts_vec,
                            is_closed=is_closed,
                            altura_m=w_ext.get("alturas", w_ext.get("altura", 2.6)),
                            espessura_m=w_ext.get("espessura", 0.15),
                            alinhamento=w_ext.get("alinhamento", "interno"),
                            open_quinas=w_ext.get("open_quinas"),
                            open_side_a=w_ext.get("open_side_a"),
                            open_side_b=w_ext.get("open_side_b"),
                            openings=openings,
                        )
                        wall_grp.mesh = new_mesh
                        wall_grp.mesh._chunk_dirty = True
                        w_ext["face_segment_map"] = face_map

        viewport.history.execute(SnapshotImport(apply_insert_esq))
        viewport.notify_scene_changed()
        viewport.update()

        # Atualiza ancoragem cont?gua
        if slot is not None:
            slot["anchor_u"] = start_u + larg_m

        self.lbl_status.setText(f"?? {g_esq.name} inserida na parede com sucesso!")
    def _rotate_selected(self, deg: float) -> None:
        mod = self._selected_module or self.find_selected_module()
        viewport = self._get_viewport()
        if mod is None or viewport is None:
            return
        cmd = RotateTrazoMobModuleCommand(mod, deg, viewport=viewport)
        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(cmd)
        else:
            cmd.do(self._get_scene())
        viewport.update()
        self.load_module(mod)

    def _on_dynamic_slider_changed(self, value: int) -> None:
        """Atualiza a cinemática de abertura em tempo real de acordo com o slider."""
        pct = int(value)
        self.lbl_open_pct.setText(f"{pct}%")
        frac = pct / 100.0
        scene = self._get_scene()
        viewport = self._get_viewport()
        if scene is None:
            return

        # Se houver um módulo selecionado, abre prioritariamente ele; caso contrário, abre toda a cena
        mod = self._selected_module or self.find_selected_module()
        if mod is not None:
            CabinetInteract.set_module_open_fraction(mod, frac, scene, viewport)
        else:
            CabinetInteract.set_scene_open_fraction(scene, frac, viewport)

        # Se ultrapassar 40% de abertura, executa checagem de colisão sutil
        if pct >= 40:
            self._check_dynamic_collisions(silent=True)
        else:
            if hasattr(self, "lbl_collision_warn"):
                self.lbl_collision_warn.setVisible(False)

    def _check_dynamic_collisions(self, silent: bool = False) -> None:
        """Verifica colisões entre portas/gavetas abertas e objetos adjacentes."""
        scene = self._get_scene()
        if scene is None:
            return
        from .collision import check_opening_collisions
        colisoes = check_opening_collisions(scene)

        if hasattr(self, "lbl_collision_warn"):
            if colisoes:
                primeira = colisoes[0]["desc"]
                qtd = len(colisoes)
                mais_txt = f" (+{qtd - 1} outros contatos)" if qtd > 1 else ""
                self.lbl_collision_warn.setText(f"{primeira}{mais_txt}")
                self.lbl_collision_warn.setVisible(True)
            else:
                if not silent:
                    self.lbl_collision_warn.setText("✅ Nenhuma colisão detectada! Abertura livre.")
                    self.lbl_collision_warn.setStyleSheet(
                        "background-color: #ecfdf5; color: #047857; font-size: 10px; font-weight: bold; "
                        "padding: 4px; border: 1px solid #a7f3d0; border-radius: 3px;"
                    )
                    self.lbl_collision_warn.setVisible(True)
                else:
                    self.lbl_collision_warn.setVisible(False)

    def _activate_interact_tool(self) -> None:
        """Ativa a ferramenta interativa de clique individual no 3D."""
        win = self._get_window()
        viewport = self._get_viewport()
        key = "plugin_trazomob_CabinetInteractTool"
        if win is not None and hasattr(win, "_activate_plugin_tool") and key in getattr(win, "_tools", {}):
            win._activate_plugin_tool(key)
        elif viewport is not None and hasattr(viewport, "set_active_tool"):
            viewport.set_active_tool(CabinetInteractTool())

    def _toggle_interact(self) -> None:
        mod = self._selected_module or self.find_selected_module()
        viewport = self._get_viewport()
        scene = self._get_scene()
        if mod is None or viewport is None or scene is None:
            return
        CabinetInteract.toggle_all(mod, scene, viewport)

    def _open_full_dialog(self) -> None:
        viewport = self._get_viewport()
        if viewport is None:
            return
        from .dialog import TrazoMobDialog
        win = self._get_window()
        dlg = getattr(win, "_trazomob_dialog", None)
        if dlg is None or not dlg.isVisible():
            dlg = TrazoMobDialog(viewport, parent=win)
            if win is not None:
                win._trazomob_dialog = dlg
            dlg.show()
        else:
            dlg.raise_()
            dlg.activateWindow()

    def _duplicate_selected(self) -> None:
        """Duplica o módulo selecionado na cena ao lado com Undo/Redo."""
        mod = self._selected_module or self.find_selected_module()
        viewport = self._get_viewport()
        if mod is None or viewport is None or not hasattr(mod, "ext") or "trazomob_module" not in mod.ext:
            return

        params = dict(mod.ext["trazomob_module"])
        orig_off = params.get("offset", (0.0, 0.0, 0.0))
        L_m = float(params.get("largura", 800.0)) / 1000.0
        offset = (orig_off[0] + L_m, orig_off[1], orig_off[2])

        new_module = CabinetBuilder.build_module_group(params, offset=offset)

        def apply_dup(sc):
            target_layer = getattr(new_module, 'layer', None)
            if target_layer and hasattr(sc, 'layer') and hasattr(sc, 'layers'):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            sc.groups.append(new_module)
            sc.selection = {new_module}

        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(SnapshotImport(apply_dup))
        else:
            apply_dup(self._get_scene())

        viewport.update()
        self.load_module(new_module)
        self.lbl_status.setText(f"📋 Módulo '{new_module.name}' duplicado!")

    def _delete_selected(self) -> None:
        """Exclui o módulo selecionado da cena com Undo/Redo."""
        mod = self._selected_module or self.find_selected_module()
        viewport = self._get_viewport()
        scene = self._get_scene()
        if mod is None or viewport is None or scene is None:
            return

        reply = QMessageBox.question(
            self,
            "Excluir Módulo",
            f"Deseja excluir o módulo '{mod.name}'?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        def apply_del(sc):
            if mod in sc.groups:
                sc.groups.remove(mod)
            if hasattr(sc, "selection") and mod in sc.selection:
                sc.selection.discard(mod)

        if hasattr(viewport, "history") and viewport.history:
            viewport.history.execute(SnapshotImport(apply_del))
        else:
            apply_del(scene)

        viewport.update()
        self._selected_module = None
        self._set_editor_enabled(False)
        self.lbl_status.setText("🗑️ Módulo excluído com sucesso.")

    # ── MÉTODOS DE EDIÇÃO DE ILUMINAÇÃO NA BARRA LATERAL ───────────────────────
    def load_light_group(self, light_grp: Group) -> None:
        """Carrega e exibe a edição da luz a partir do Group 3D nativo selecionado no viewport."""
        if not light_grp or not getattr(light_grp, "ext", None):
            self.clear_light_selection()
            return
        ext = light_grp.ext
        if not isinstance(ext, dict) or "trazomob_light" not in ext:
            self.clear_light_selection()
            return

        self._selected_light_grp = light_grp
        vp = self._get_viewport()
        from .light_tools import _get_document_lights, sync_scene_lights_to_document, TrazoMobLightVisualizer
        if vp is not None:
            sync_scene_lights_to_document(vp)
        lights = _get_document_lights(vp) if vp else []
        lt = ext["trazomob_light"]

        # Encontra o índice correspondente
        found_idx = None
        for i, l_item in enumerate(lights):
            if l_item.get("pos") == lt.get("pos") and l_item.get("kind") == lt.get("kind"):
                found_idx = i
                break
        self._selected_light_idx = found_idx
        if vp is not None:
            TrazoMobLightVisualizer.set_selected_index(found_idx, vp)

        self._display_light_data(lt, light_grp.name)

    def load_light(self, light_idx: int) -> None:
        """Carrega e exibe a edição da luz selecionada por índice na barra lateral."""
        from .light_tools import _get_document_lights
        vp = self._get_viewport()
        lights = _get_document_lights(vp) if vp else []
        if not (0 <= light_idx < len(lights)):
            self.clear_light_selection()
            return

        self._selected_light_idx = light_idx
        lt = lights[light_idx]

        # Localiza o Group correspondente na cena, se houver
        self._selected_light_grp = None
        scene = self._get_scene()
        if scene:
            for g in getattr(scene, "groups", []):
                ext = getattr(g, "ext", None)
                if isinstance(ext, dict) and "trazomob_light" in ext:
                    g_lt = ext["trazomob_light"]
                    if g_lt.get("pos") == lt.get("pos") and g_lt.get("kind") == lt.get("kind"):
                        self._selected_light_grp = g
                        break

        self._display_light_data(lt)

    def _display_light_data(self, lt: dict, custom_name: str | None = None) -> None:
        """Preenche os controles da barra lateral com os dados da luz."""
        self._ensure_form_built()
        self.focus_panel()

        # Oculta outros cards e exibe o card de luz
        if hasattr(self, "card_paredes"):
            self.card_paredes.setVisible(False)
        if hasattr(self, "card_align"):
            self.card_align.setVisible(False)
        if hasattr(self, "scroll_area"):
            self.scroll_area.setVisible(False)
        if hasattr(self, "btn_apply"):
            self.btn_apply.setVisible(False)
        if hasattr(self, "btn_save_defaults"):
            self.btn_save_defaults.setVisible(False)
        if hasattr(self, "btn_delete"):
            self.btn_delete.setVisible(False)
        if hasattr(self, "btn_apply_wall"):
            self.btn_apply_wall.setVisible(False)
        if hasattr(self, "btn_hide_selected_wall"):
            self.btn_hide_selected_wall.setVisible(False)

        self.card_luz.setVisible(True)

        kind = lt.get("kind", "point")
        is_on = lt.get("on", True)
        name = custom_name or lt.get("name") or ("Spot Direcionável" if kind == "spot" else ("Fita LED Linear" if kind == "led_strip" else "Luz Ponto/Omni"))
        idx_txt = f" (#{self._selected_light_idx + 1})" if self._selected_light_idx is not None else ""

        self.lbl_title.setText(f"💡 {name}")
        self.lbl_status.setText(f"Tipo: {kind.upper()} | Objeto 3D Nativo na Cena")
        self.lbl_luz_nome.setText(f"{name}{idx_txt}")

        # Botão Ligar/Desligar
        self.btn_luz_toggle.setText("Desligar Luz" if is_on else "Ligar Luz")
        self.btn_luz_toggle.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; font-weight: bold; padding: 5px; border-radius: 4px; }"
            if is_on else
            "QPushButton { background-color: #6B7280; color: white; font-weight: bold; padding: 5px; border-radius: 4px; }"
        )

        # Distribuição (Omni vs Spot)
        is_spot = (kind == "spot")
        is_led = (kind == "led_strip")
        if hasattr(self, "cb_luz_tipo"):
            self.cb_luz_tipo.setVisible(not is_led)
            self.cb_luz_tipo.blockSignals(True)
            self.cb_luz_tipo.setCurrentIndex(1 if is_spot else 0)
            self.cb_luz_tipo.blockSignals(False)

        # Potência
        self.sp_luz_power.blockSignals(True)
        self.sp_luz_power.setValue(int(lt.get("power", 400)))
        self.sp_luz_power.blockSignals(False)

        # Kelvin
        k = int(lt.get("kelvin", 2700))
        self.sl_luz_kelvin.blockSignals(True)
        self.sl_luz_kelvin.setValue(k)
        self.lbl_luz_kelvin.setText(f"{k}K")
        self.sl_luz_kelvin.blockSignals(False)

        # Altura Z
        pos = lt.get("pos") or [0, 0, 0]
        self.sp_luz_z.blockSignals(True)
        self.sp_luz_z.setValue(float(pos[2]))
        self.sp_luz_z.blockSignals(False)

        # Ângulo e Mira (Spot)
        self.row_luz_ang.setVisible(is_spot)
        self.btn_luz_aim.setVisible(is_spot)
        if is_spot:
            self.sp_luz_ang.blockSignals(True)
            self.sp_luz_ang.setValue(int(lt.get("angle", 45)))
            self.sp_luz_ang.blockSignals(False)

    def clear_light_selection(self) -> None:
        """Limpa a seleção de luz e restaura o card correspondente."""
        self._selected_light_idx = None
        self._selected_light_grp = None
        if hasattr(self, "card_luz"):
            self.card_luz.setVisible(False)
        if self._selected_module is not None:
            if hasattr(self, "scroll_area"):
                self.scroll_area.setVisible(True)
            if hasattr(self, "btn_apply"):
                self.btn_apply.setVisible(True)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setVisible(True)

    def _toggle_light_on_off(self) -> None:
        if self._selected_light_grp is not None:
            lt = self._selected_light_grp.ext.get("trazomob_light", {})
            cur = lt.get("on", True)
            lt["on"] = not cur
            self._selected_light_grp.ext["trazomob_light"] = lt
            self.btn_luz_toggle.setText("Desligar Luz" if not cur else "Ligar Luz")
            self.btn_luz_toggle.setStyleSheet(
                "QPushButton { background-color: #059669; color: white; font-weight: bold; padding: 5px; border-radius: 4px; }"
                if not cur else
                "QPushButton { background-color: #6B7280; color: white; font-weight: bold; padding: 5px; border-radius: 4px; }"
            )
            vp = self._get_viewport()
            if vp:
                from .light_tools import sync_scene_lights_to_document
                sync_scene_lights_to_document(vp)
                vp.update()
            return

        if self._selected_light_idx is None:
            return
        from .light_tools import _get_document_lights, _save_document_lights
        vp = self._get_viewport()
        lights = _get_document_lights(vp) if vp else []
        idx = self._selected_light_idx
        if 0 <= idx < len(lights):
            cur = lights[idx].get("on", True)
            lights[idx]["on"] = not cur
            _save_document_lights(vp, lights)
            self.btn_luz_toggle.setText("Desligar Luz" if not cur else "Ligar Luz")
            self.btn_luz_toggle.setStyleSheet(
                "QPushButton { background-color: #059669; color: white; font-weight: bold; padding: 5px; border-radius: 4px; }"
                if not cur else
                "QPushButton { background-color: #6B7280; color: white; font-weight: bold; padding: 5px; border-radius: 4px; }"
            )

    def _on_sidebar_light_tipo_changed(self) -> None:
        """Alterna a distribuição entre Omni (360° todas as direções) e Spot (Foco para baixo)."""
        new_kind = self.cb_luz_tipo.currentData() or ("spot" if self.cb_luz_tipo.currentIndex() == 1 else "point")
        is_spot = (new_kind == "spot")
        self.row_luz_ang.setVisible(is_spot)
        self.btn_luz_aim.setVisible(is_spot)

        vp = self._get_viewport()
        if self._selected_light_grp is not None:
            lt = self._selected_light_grp.ext.get("trazomob_light", {})
            lt["kind"] = new_kind
            if is_spot:
                lt.setdefault("angle", float(self.sp_luz_ang.value()))
                lt.setdefault("dir", [0.0, 0.0, -1.0])
            self._selected_light_grp.ext["trazomob_light"] = lt
            if vp:
                from .light_tools import sync_scene_lights_to_document
                sync_scene_lights_to_document(vp)
                vp.update()
        elif self._selected_light_idx is not None:
            from .light_tools import _get_document_lights, _save_document_lights
            lights = _get_document_lights(vp) if vp else []
            if 0 <= self._selected_light_idx < len(lights):
                lights[self._selected_light_idx]["kind"] = new_kind
                _save_document_lights(vp, lights)

        self.lbl_status.setText(f"Distribuição: {'SPOT (Foco direcionado)' if is_spot else 'OMNI (360° todas as direções)'}")

    def _on_sidebar_light_prop_changed(self) -> None:
        from .light_tools import kelvin_to_rgb, sync_scene_lights_to_document, _get_document_lights, _save_document_lights
        vp = self._get_viewport()
        k = int(self.sl_luz_kelvin.value())
        pwr = float(self.sp_luz_power.value())
        ang = float(self.sp_luz_ang.value()) if hasattr(self, "sp_luz_ang") and self.row_luz_ang.isVisible() else 45.0
        rgb = list(kelvin_to_rgb(k))
        self.lbl_luz_kelvin.setText(f"{k}K")

        if self._selected_light_grp is not None:
            lt = self._selected_light_grp.ext.get("trazomob_light", {})
            lt["power"] = pwr
            lt["kelvin"] = k
            lt["color"] = rgb
            if lt.get("kind") == "spot":
                lt["angle"] = ang
            self._selected_light_grp.ext["trazomob_light"] = lt
            # Atualiza cor emissiva na malha do grupo 3D
            mesh = getattr(self._selected_light_grp, "mesh", None)
            if mesh:
                for f in getattr(mesh, "faces", []):
                    m_name = f.attrs.get("mat", "")
                    if "Difusor" in m_name or "Lente" in m_name or "Vidro" in m_name:
                        f.attrs["color"] = (rgb[0], rgb[1], rgb[2])
                mesh._chunk_dirty = True
            if vp:
                sync_scene_lights_to_document(vp)
                vp.update()
            return

        if self._selected_light_idx is None:
            return
        lights = _get_document_lights(vp) if vp else []
        idx = self._selected_light_idx
        if 0 <= idx < len(lights):
            lt = lights[idx]
            lt["power"] = pwr
            lt["kelvin"] = k
            lt["color"] = rgb
            if hasattr(self, "sp_luz_ang") and self.row_luz_ang.isVisible():
                lt["angle"] = ang
            _save_document_lights(vp, lights)

    def _on_sidebar_light_z_changed(self) -> None:
        new_z = round(float(self.sp_luz_z.value()), 4)
        vp = self._get_viewport()

        if self._selected_light_grp is not None:
            lt = self._selected_light_grp.ext.get("trazomob_light", {})
            pos = lt.get("pos") or [0, 0, 0]
            dz = new_z - pos[2]
            pos[2] = new_z
            lt["pos"] = pos
            if lt.get("kind") == "spot" and "target" in lt and lt["target"]:
                lt["target"][2] = round(lt["target"][2] + dz, 4)
            if lt.get("kind") == "led_strip" and "p1" in lt and "p2" in lt:
                lt["p1"][2] = round(lt["p1"][2] + dz, 4)
                lt["p2"][2] = round(lt["p2"][2] + dz, 4)
            self._selected_light_grp.ext["trazomob_light"] = lt

            # Desloca a malha 3D real no eixo Z
            shift = QVector3D(0.0, 0.0, dz)
            mesh = getattr(self._selected_light_grp, "mesh", None)
            if mesh and hasattr(mesh, "vertices"):
                for v in mesh.vertices:
                    v.position += shift
                mesh._chunk_dirty = True
            if vp:
                from .light_tools import sync_scene_lights_to_document
                sync_scene_lights_to_document(vp)
                vp.update()
            return

        if self._selected_light_idx is None:
            return
        from .light_tools import _get_document_lights, _save_document_lights
        lights = _get_document_lights(vp) if vp else []
        idx = self._selected_light_idx
        if 0 <= idx < len(lights):
            lt = lights[idx]
            pos = lt.get("pos") or [0, 0, 0]
            dz = new_z - pos[2]
            pos[2] = new_z
            lt["pos"] = pos
            if lt.get("kind") == "spot" and "target" in lt and lt["target"]:
                lt["target"][2] = round(lt["target"][2] + dz, 4)
            if lt.get("kind") == "led_strip" and "p1" in lt and "p2" in lt:
                lt["p1"][2] = round(lt["p1"][2] + dz, 4)
                lt["p2"][2] = round(lt["p2"][2] + dz, 4)
            _save_document_lights(vp, lights)

    def _aim_selected_light(self) -> None:
        idx = self._selected_light_idx or 0
        from .light_tools import AimLightTool
        vp = self._get_viewport()
        if vp:
            tool = AimLightTool(idx, on_aimed=lambda: vp.update())
            vp.set_active_tool(tool)

    def _reposition_selected_light(self) -> None:
        idx = self._selected_light_idx or 0
        from .light_tools import MoveLightTool
        vp = self._get_viewport()
        if vp:
            tool = MoveLightTool(idx, on_moved=lambda: self.load_light(idx))
            vp.set_active_tool(tool)

    def _delete_selected_light(self) -> None:
        reply = QMessageBox.question(
            self,
            "Excluir Luz",
            "Deseja realmente remover esta luminária do projeto?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        vp = self._get_viewport()
        scene = self._get_scene()

        # Remove o Group 3D nativo da cena com Undo/Redo
        grp = self._selected_light_grp
        if grp is not None and scene is not None:
            from core.history import SnapshotImport
            def _remove_light_group(sc):
                if grp in sc.groups:
                    sc.groups.remove(grp)
                if hasattr(sc, "selection") and grp in sc.selection:
                    sc.selection.discard(grp)
            if hasattr(vp, "history") and vp.history:
                vp.history.execute(SnapshotImport(_remove_light_group))
            else:
                _remove_light_group(scene)

        if vp is not None:
            from .light_tools import sync_scene_lights_to_document, TrazoMobLightVisualizer
            sync_scene_lights_to_document(vp)
            TrazoMobLightVisualizer.set_selected_index(None, vp)
            vp.update()

        self.clear_light_selection()
        self.lbl_status.setText("🗑️ Luminária removida com sucesso.")

    def _delete_all_lights(self) -> None:
        """Remove todas as luminárias do projeto: tanto os grupos 3D quanto os dados do documento legados."""
        reply = QMessageBox.question(
            self,
            "Remover Todas as Luzes",
            "Deseja remover TODAS as luzes do projeto (incluindo luzes legadas antigas e objetos 3D)?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        vp = self._get_viewport()
        scene = self._get_scene()

        # Remove todos os grupos 3D de luz da cena
        if scene is not None:
            light_grps = [
                g for g in getattr(scene, "groups", [])
                if getattr(g, "ext", None) and isinstance(g.ext, dict) and "trazomob_light" in g.ext
            ]
            if light_grps:
                from core.history import SnapshotImport
                def _remove_all_light_groups(sc):
                    for g in light_grps:
                        if g in sc.groups:
                            sc.groups.remove(g)
                        if hasattr(sc, "selection") and g in sc.selection:
                            sc.selection.discard(g)
                if hasattr(vp, "history") and vp.history:
                    vp.history.execute(SnapshotImport(_remove_all_light_groups))
                else:
                    _remove_all_light_groups(scene)

        # Limpa completamente a lista de luzes no documento (render_blender)
        if vp is not None:
            from .light_tools import _save_document_lights, TrazoMobLightVisualizer
            _save_document_lights(vp, [])
            TrazoMobLightVisualizer.set_selected_index(None, vp)
            vp.update()

        self.clear_light_selection()
        self.lbl_status.setText("🧹 Todas as luzes foram removidas com sucesso.")


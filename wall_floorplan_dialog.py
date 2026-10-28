# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Diálogo de Planta Baixa 2D Interativa para Paredes (Estilo AutoCAD / Revit / Promob)."""
from __future__ import annotations

import math
from typing import Optional, List, Dict, Tuple, Any

from PySide6.QtCore import Qt, QPointF
from PySide6.QtGui import QColor, QFont, QVector3D
from PySide6.QtWidgets import (
    QDialog,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QToolButton,
    QDoubleSpinBox,
    QSpinBox,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QMessageBox,
    QFrame,
    QSplitter,
    QListWidget,
    QListWidgetItem,
    QScrollArea,
    QButtonGroup,
    QSlider,
    QFileDialog,
)

from core.group import Group
from core.history import SnapshotImport
from core.image_plane import ImagePlane

from .wall_floorplan_canvas import WallFloorplanCanvas
from .wall_plan_2d import WallGraph2D, WallNode2D, dist_2d
from .wall_mesh_builder import WallMeshBuilder
from core.units import format_length, model_unit, model_precision, bare_number_scale

class WallFloorplanDialog(QDialog):
    """Janela de Diálogo para Desenhar Paredes em Planta Baixa 2D com Extrusão 3D Direta."""

    def __init__(self, viewport, existing_group: Optional[Group] = None, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.viewport = viewport
        self.existing_group = existing_group
        self.setWindowTitle("Planta Baixa 2D — Construtor de Paredes (TrazoMob)")
        self.resize(1000, 680)

        # Carrega o grafo 2D de grupo existente na cena se fornecido ou se houver parede selecionada
        loaded_graph = None
        if self.existing_group is not None:
            loaded_graph = WallGraph2D.from_group(self.existing_group)
        elif self.viewport is not None and hasattr(self.viewport, "scene"):
            # Tenta carregar do grupo de parede selecionado na cena
            for g in getattr(self.viewport.scene, "selection", set()):
                g_ext = getattr(g, "ext", None)
                if isinstance(g_ext, dict) and g_ext.get("trazomob_wall"):
                    self.existing_group = g
                    loaded_graph = WallGraph2D.from_group(g)
                    break
            # Se não há seleção, procura se existe algum grupo de parede existente na cena
            if loaded_graph is None:
                for g in getattr(self.viewport.scene, "groups", []):
                    g_ext = getattr(g, "ext", None)
                    if isinstance(g_ext, dict) and g_ext.get("trazomob_wall"):
                        self.existing_group = g
                        loaded_graph = WallGraph2D.from_group(g)
                        break

        if loaded_graph is not None:
            self.graph = loaded_graph
        else:
            self.graph = WallGraph2D(default_thickness=0.15, default_height=2.60)

        self._setup_ui()
        scale = bare_number_scale()
        p = model_precision()
        self.sp_thickness.setValue(round(self.graph.default_thickness / scale, p))
        self.sp_height.setValue(round(self.graph.default_height / scale, p))
        if self.graph.segments:
            self.lbl_status.setText(f"Paredes carregadas: {len(self.graph.segments)}")

        # Restaura imagem de referência previamente salva no documento se houver
        self._restore_reference_image_from_scene()

        # Guarda o snapshot inicial para detecção de alterações pendentes
        self._initial_graph_dict = self.graph.to_dict()

    def has_unsaved_changes(self) -> bool:
        """Verifica se houve alterações no traçado de paredes em relação ao início."""
        return self.graph.to_dict() != self._initial_graph_dict

    def _setup_ui(self) -> None:
        root_layout = QHBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Canvas 2D
        self.canvas = WallFloorplanCanvas(self.graph, parent=self)
        self.canvas.wall_count_changed.connect(self._on_wall_count_changed)
        self.canvas.wall_selected.connect(self._on_wall_selected)
        self.canvas.current_length_changed.connect(self._on_current_length_changed)

        # 2. Painel Lateral de Controle dentro de QScrollArea (evita esticar para fora da tela)
        side_container = QFrame(self)
        side_container.setFixedWidth(295)
        side_container_layout = QVBoxLayout(side_container)
        side_container_layout.setContentsMargins(0, 0, 0, 0)
        side_container_layout.setSpacing(0)

        scroll_area = QScrollArea(side_container)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1e222b;
                border-left: 1px solid #2e3544;
            }
            QScrollBar:vertical {
                background: #181c24;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #3e4a63;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #00b0ff;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        side_panel = QFrame()
        side_panel.setStyleSheet("""
            QFrame {
                background-color: #1e222b;
                border: none;
                color: #e0e0e0;
            }
            QLabel {
                font-weight: bold;
                font-size: 11px;
                color: #9aa4b2;
            }
            QDoubleSpinBox {
                background-color: #13171f;
                border: 1px solid #363f52;
                border-radius: 4px;
                color: #ffffff;
                padding: 4px 6px;
                font-weight: bold;
            }
            QPushButton {
                background-color: #2b3345;
                border: 1px solid #3e4a63;
                border-radius: 4px;
                color: #ffffff;
                padding: 6px 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #38435c;
            }
            QPushButton:checked {
                background-color: #00b0ff;
                border: 1px solid #40c4ff;
                color: #000000;
            }
            QPushButton.tool-btn {
                font-size: 16px;
                padding: 6px 0px;
                min-width: 44px;
                min-height: 36px;
            }
            QGroupBox {
                border: 1px solid #2e3544;
                border-radius: 6px;
                margin-top: 6px;
                padding-top: 10px;
                font-weight: bold;
                color: #40c4ff;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 8px;
                padding: 0 4px;
            }
        """)

        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(12, 14, 12, 14)
        side_layout.setSpacing(9)

        # Título
        title_lbl = QLabel("📐 Parâmetros da Parede", side_panel)
        title_lbl.setStyleSheet("font-size: 14px; color: #ffffff;")
        side_layout.addWidget(title_lbl)

        # Ferramentas de desenho e seleção (ícones compactos com hint/tooltip)
        tool_box = QHBoxLayout()
        tool_box.setSpacing(6)

        self.btn_tool_line = QPushButton("📏", side_panel)
        self.btn_tool_line.setProperty("class", "tool-btn")
        self.btn_tool_line.setCheckable(True)
        self.btn_tool_line.setChecked(True)
        self.btn_tool_line.setToolTip("Desenhar Parede contínua (Linha por linha)")
        self.btn_tool_line.clicked.connect(lambda: self._set_mode("linha"))

        self.btn_tool_rect = QPushButton("🔲", side_panel)
        self.btn_tool_rect.setProperty("class", "tool-btn")
        self.btn_tool_rect.setCheckable(True)
        self.btn_tool_rect.setToolTip("Desenhar Cômodo Retangular fechado")
        self.btn_tool_rect.clicked.connect(lambda: self._set_mode("retangulo"))

        self.btn_tool_select = QPushButton("👆", side_panel)
        self.btn_tool_select.setProperty("class", "tool-btn")
        self.btn_tool_select.setCheckable(True)
        self.btn_tool_select.setToolTip("Selecionar ou mover paredes e nós")
        self.btn_tool_select.clicked.connect(lambda: self._set_mode("selecionar"))

        self.btn_tool_cota = QPushButton("📐", side_panel)
        self.btn_tool_cota.setProperty("class", "tool-btn")
        self.btn_tool_cota.setCheckable(True)
        self.btn_tool_cota.setToolTip("Adicionar Cota entre dois pontos quaisquer (faces, cantos ou centros)")
        self.btn_tool_cota.clicked.connect(lambda: self._set_mode("cota"))

        self.btn_group = QButtonGroup(self)
        self.btn_group.addButton(self.btn_tool_line)
        self.btn_group.addButton(self.btn_tool_rect)
        self.btn_group.addButton(self.btn_tool_select)
        self.btn_group.addButton(self.btn_tool_cota)

        tool_box.addWidget(self.btn_tool_line)
        tool_box.addWidget(self.btn_tool_rect)
        tool_box.addWidget(self.btn_tool_select)
        tool_box.addWidget(self.btn_tool_cota)
        side_layout.addLayout(tool_box)

        # Unidade do documento
        u_name = model_unit()
        p = model_precision()
        scale = bare_number_scale()

        # Comprimento da Parede - Entrada numérica direta ou edição
        self.lbl_length = QLabel(f"Comprimento da Parede ({u_name}):", side_panel)
        side_layout.addWidget(self.lbl_length)
        len_box = QHBoxLayout()
        self.sp_length = QDoubleSpinBox(side_panel)
        # Limites escalados conforme a unidade
        self.sp_length.setRange(0.01, 100000.0)
        self.sp_length.setDecimals(p)
        step = 100.0 if u_name == "mm" else (10.0 if u_name == "cm" else 0.10)
        self.sp_length.setSingleStep(step)
        self.sp_length.setValue(2.0 / scale)
        self.sp_length.setToolTip("Digite o comprimento desejado e clique em Aplicar ou aperte Enter")
        if self.sp_length.lineEdit():
            self.sp_length.lineEdit().returnPressed.connect(self._on_apply_length_clicked)
        len_box.addWidget(self.sp_length)

        self.btn_apply_len = QPushButton("✔️ Aplicar", side_panel)
        self.btn_apply_len.setFixedWidth(70)
        self.btn_apply_len.clicked.connect(self._on_apply_length_clicked)
        len_box.addWidget(self.btn_apply_len)
        side_layout.addLayout(len_box)

        # Espessura
        self.lbl_thickness = QLabel(f"Espessura da Parede ({u_name}):", side_panel)
        side_layout.addWidget(self.lbl_thickness)
        self.sp_thickness = QDoubleSpinBox(side_panel)
        self.sp_thickness.setRange(0.01, 10000.0)
        self.sp_thickness.setDecimals(p)
        self.sp_thickness.setSingleStep(step)
        self.sp_thickness.setValue(0.15 / scale)
        self.sp_thickness.valueChanged.connect(self._on_params_changed)
        side_layout.addWidget(self.sp_thickness)

        # Altura / Pé-direito
        self.lbl_height = QLabel(f"Pé-Direito / Altura ({u_name}):", side_panel)
        side_layout.addWidget(self.lbl_height)
        self.sp_height = QDoubleSpinBox(side_panel)
        self.sp_height.setRange(0.1, 10000.0)
        self.sp_height.setDecimals(p)
        self.sp_height.setSingleStep(step)
        self.sp_height.setValue(2.60 / scale)
        self.sp_height.valueChanged.connect(self._on_params_changed)
        side_layout.addWidget(self.sp_height)

        # Opções automáticas de piso e teto
        # Se estivermos editando um ambiente existente que já possui piso/teto na cena,
        # desmarca por padrão para não recriar desnecessariamente, a menos que o usuário queira.
        has_existing_floor = False
        has_existing_ceiling = False
        if self.existing_group is not None and getattr(self.viewport, "scene", None) is not None:
            scene_groups = getattr(self.viewport.scene, "groups", [])
            existing_name = getattr(self.existing_group, "name", "")
            for g in scene_groups:
                g_ext = getattr(g, "ext", None)
                if isinstance(g_ext, dict):
                    if g_ext.get("trazomob_floor") and (g_ext.get("associated_wall_name") == existing_name or g.name.startswith("Piso")):
                        has_existing_floor = True
                    if g_ext.get("trazomob_ceiling") and (g_ext.get("associated_wall_name") == existing_name or g.name.startswith("Teto")):
                        has_existing_ceiling = True

        self.chk_floor = QCheckBox("Gerar Piso Automaticamente", side_panel)
        self.chk_floor.setChecked(not has_existing_floor)
        side_layout.addWidget(self.chk_floor)

        self.chk_ceiling = QCheckBox("Gerar Teto / Forro", side_panel)
        self.chk_ceiling.setChecked(False)
        side_layout.addWidget(self.chk_ceiling)

        # Status / Contador
        self.lbl_status = QLabel("Paredes desenhadas: 0", side_panel)
        self.lbl_status.setStyleSheet("color: #00e676; font-size: 11px;")
        side_layout.addWidget(self.lbl_status)

        # Grupo Imagem de Referência / Planta de Fundo
        grp_ref = QGroupBox("🖼️ Referência", side_panel)
        grp_ref_layout = QVBoxLayout(grp_ref)
        grp_ref_layout.setContentsMargins(6, 6, 6, 6)
        grp_ref_layout.setSpacing(4)

        btn_load_ref = QPushButton("📁 Carregar Imagem...", grp_ref)
        btn_load_ref.setToolTip("Carrega uma planta baixa em JPG/PNG para desenhar por cima")
        btn_load_ref.clicked.connect(self._on_load_reference_image)
        grp_ref_layout.addWidget(btn_load_ref)

        box_ref_tools = QHBoxLayout()
        box_ref_tools.setSpacing(4)
        self.btn_calib_ref = QPushButton("📏", grp_ref)
        self.btn_calib_ref.setToolTip("Calibrar escala: clique em dois pontos com medida conhecida")
        self.btn_calib_ref.setCheckable(True)
        self.btn_calib_ref.clicked.connect(self._on_calib_ref_clicked)
        box_ref_tools.addWidget(self.btn_calib_ref)

        self.btn_move_ref = QPushButton("✋", grp_ref)
        self.btn_move_ref.setToolTip("Mover imagem de referência: arraste para posicionar")
        self.btn_move_ref.setCheckable(True)
        self.btn_move_ref.clicked.connect(self._on_move_ref_clicked)
        box_ref_tools.addWidget(self.btn_move_ref)

        btn_rot_ref = QPushButton("🔄", grp_ref)
        btn_rot_ref.setToolTip("Rotacionar imagem em 90°")
        btn_rot_ref.clicked.connect(self._on_rotate_ref_clicked)
        box_ref_tools.addWidget(btn_rot_ref)

        btn_remove_ref = QPushButton("❌", grp_ref)
        btn_remove_ref.setToolTip("Remover imagem de referência")
        btn_remove_ref.clicked.connect(self._on_remove_reference_image)
        box_ref_tools.addWidget(btn_remove_ref)
        grp_ref_layout.addLayout(box_ref_tools)

        # Opacidade / Transparência
        box_opac = QHBoxLayout()
        box_opac.addWidget(QLabel("Opacidade:", grp_ref))
        self.slider_opac = QSlider(Qt.Horizontal, grp_ref)
        self.slider_opac.setRange(10, 100)
        self.slider_opac.setValue(50)
        self.slider_opac.valueChanged.connect(self._on_ref_opacity_changed)
        box_opac.addWidget(self.slider_opac)
        grp_ref_layout.addLayout(box_opac)

        self.chk_ref_vis = QCheckBox("Exibir Imagem", grp_ref)
        self.chk_ref_vis.setChecked(True)
        self.chk_ref_vis.toggled.connect(self._on_ref_visibility_toggled)
        grp_ref_layout.addWidget(self.chk_ref_vis)

        side_layout.addWidget(grp_ref)

        # Botões de Visualização e Ações em Grade Compacta com Ícones
        box_actions = QHBoxLayout()
        box_actions.setSpacing(4)

        btn_zoom_fit = QPushButton("📐", side_panel)
        btn_zoom_fit.setToolTip("Enquadrar todas as paredes desenhadas na tela")
        btn_zoom_fit.clicked.connect(self.canvas.zoom_extents)
        box_actions.addWidget(btn_zoom_fit)

        btn_reset_cam = QPushButton("🎯", side_panel)
        btn_reset_cam.setToolTip("Centralizar na Origem (0, 0)")
        btn_reset_cam.clicked.connect(self.canvas.reset_view)
        box_actions.addWidget(btn_reset_cam)

        btn_undo = QPushButton("↩️", side_panel)
        btn_undo.setToolTip("Desfazer última alteração (Ctrl+Z)")
        btn_undo.clicked.connect(self.canvas.undo)
        box_actions.addWidget(btn_undo)

        btn_clear = QPushButton("🗑️", side_panel)
        btn_clear.setToolTip("Limpar todas as paredes")
        btn_clear.clicked.connect(self.canvas.clear_all)
        box_actions.addWidget(btn_clear)

        side_layout.addLayout(box_actions)

        # Dicas de uso compactas
        hints = QLabel("💡 <b>Dicas:</b> Digite a medida e aperte Enter. Duplo clique na cota para editar. Delete remove.", side_panel)
        hints.setStyleSheet("color: #788599; font-weight: normal; font-size: 10px;")
        hints.setWordWrap(True)
        side_layout.addWidget(hints)

        side_layout.addStretch()

        scroll_area.setWidget(side_panel)
        side_container_layout.addWidget(scroll_area, 1)

        # Botão Concluir em destaque fixo no rodapé
        bottom_box = QFrame(side_container)
        bottom_box.setStyleSheet("""
            QFrame {
                background-color: #181c24;
                border-top: 1px solid #2e3544;
                padding: 4px;
            }
            QPushButton#btn_build {
                background-color: #00b0ff;
                border: 1px solid #40c4ff;
                color: #000000;
                font-size: 13px;
                font-weight: bold;
                padding: 10px;
                border-radius: 5px;
            }
            QPushButton#btn_build:hover {
                background-color: #40c4ff;
            }
        """)
        bottom_layout = QVBoxLayout(bottom_box)
        bottom_layout.setContentsMargins(10, 8, 10, 8)
        self.btn_build = QPushButton("🧱 Concluir e Gerar no 3D", bottom_box)
        self.btn_build.setObjectName("btn_build")
        self.btn_build.clicked.connect(self._build_3d_and_close)
        bottom_layout.addWidget(self.btn_build)
        side_container_layout.addWidget(bottom_box)

        for btn in self.findChildren(QPushButton):
            btn.setAutoDefault(False)
            btn.setDefault(False)
        root_layout.addWidget(self.canvas, 1)
        root_layout.addWidget(side_container)

    def _set_mode(self, mode: str) -> None:
        self.canvas.mode = mode
        self.canvas._start_pt = None
        self.canvas._cota_points.clear()
        if hasattr(self, 'btn_calib_ref'):
            self.btn_calib_ref.setChecked(mode == "calibrar_ref")
        if hasattr(self, 'btn_move_ref'):
            self.btn_move_ref.setChecked(mode == "mover_ref")
        if hasattr(self, 'btn_tool_cota'):
            self.btn_tool_cota.setChecked(mode == "cota")
        self.canvas.update_cursor()
        self.canvas.update()

    def _on_params_changed(self) -> None:
        scale = bare_number_scale()
        new_th = self.sp_thickness.value() * scale
        new_h = self.sp_height.value() * scale
        if self.canvas._selected_seg_id is not None and self.canvas._selected_seg_id in self.graph.segments:
            seg = self.graph.segments[self.canvas._selected_seg_id]
            seg.thickness = new_th
            seg.height = new_h
        else:
            self.graph.default_thickness = new_th
            self.graph.default_height = new_h
            # Atualiza também todas as paredes existentes para a nova espessura padrão global
            for s in self.graph.segments.values():
                s.thickness = new_th
                s.height = new_h
        self.canvas.update()

    def _on_wall_count_changed(self, count: int) -> None:
        self.lbl_status.setText(f"Paredes desenhadas: {count}")

    def _on_wall_selected(self, seg_id: int, length_m: float) -> None:
        """Quando o usuário clica ou seleciona uma parede, atualiza os campos de espessura e comprimento na unidade do documento."""
        scale = bare_number_scale()
        p = model_precision()

        seg = self.graph.segments.get(seg_id)
        if seg:
            self.sp_length.blockSignals(True)
            self.sp_length.setValue(round(length_m / scale, p))
            self.sp_length.blockSignals(False)

            th_val = seg.thickness if seg.thickness is not None else self.graph.default_thickness
            self.sp_thickness.blockSignals(True)
            self.sp_thickness.setValue(round(th_val / scale, p))
            self.sp_thickness.blockSignals(False)

            h_val = seg.height if seg.height is not None else self.graph.default_height
            self.sp_height.blockSignals(True)
            self.sp_height.setValue(round(h_val / scale, p))
            self.sp_height.blockSignals(False)
        else:
            # Nenhuma parede selecionada: exibe valores padrão globais
            self.sp_thickness.blockSignals(True)
            self.sp_thickness.setValue(round(self.graph.default_thickness / scale, p))
            self.sp_thickness.blockSignals(False)

            self.sp_height.blockSignals(True)
            self.sp_height.setValue(round(self.graph.default_height / scale, p))
            self.sp_height.blockSignals(False)
    def _on_current_length_changed(self, length_m: float) -> None:
        """Atualiza a caixa de comprimento dinamicamente enquanto o mouse se move na tela."""
        if not self.sp_length.hasFocus():
            scale = bare_number_scale()
            p = model_precision()
            self.sp_length.blockSignals(True)
            self.sp_length.setValue(round(length_m / scale, p))
            self.sp_length.blockSignals(False)

    def _on_apply_length_clicked(self) -> None:
        """Aplica o comprimento digitado no campo de texto para a parede selecionada ou traço ativo."""
        scale = bare_number_scale()
        new_len_m = self.sp_length.value() * scale
        if new_len_m <= 0.01:
            return

        # 1. Se houver uma parede selecionada, altera seu comprimento diretamente
        if self.canvas._selected_seg_id is not None:
            self.canvas._save_history()
            self.canvas.graph.set_segment_length(self.canvas._selected_seg_id, new_len_m)
            self.canvas.update()
            return

        # 2. Se estiver desenhando (iniciou o traço com _start_pt), traça na direção atual com o comprimento exato
        if self.canvas._start_pt is not None:
            p0 = self.canvas._start_pt
            p1 = self.canvas._current_mouse_world
            dx = p1[0] - p0[0]
            dy = p1[1] - p0[1]
            dist = math.hypot(dx, dy)
            if dist < 1e-4:
                dx, dy = 1.0, 0.0
                dist = 1.0
            ux, uy = dx / dist, dy / dist
            ext = self.canvas.graph.get_start_extension(p0, (ux, uy))
            eff_len = new_len_m + ext
            end_x = p0[0] + ux * eff_len
            end_y = p0[1] + uy * eff_len

            self.canvas._save_history()
            self.canvas.graph.add_segment(p0[0], p0[1], end_x, end_y)
            self.canvas.graph.merge_close_nodes(threshold=0.25)
            self.canvas.wall_count_changed.emit(len(self.canvas.graph.segments))

            # Verifica se fechou um ciclo
            end_nid = self.canvas.graph.find_node_at(end_x, end_y, threshold=0.25)
            deg = 0
            if end_nid is not None:
                deg = sum(1 for s in self.canvas.graph.segments.values() if s.node_a_id == end_nid or s.node_b_id == end_nid)

            if deg >= 2:
                self.canvas._start_pt = None
            else:
                self.canvas._start_pt = (end_x, end_y)

            self.canvas.update()

    def _on_load_reference_image(self) -> None:
        """Abre seletor de arquivos para carregar imagem de referência."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Imagem de Referência / Planta Baixa",
            "",
            "Imagens (*.png *.jpg *.jpeg *.bmp *.webp);;Todos os Arquivos (*)"
        )
        if path:
            if self.canvas.set_reference_image(path):
                self.chk_ref_vis.setChecked(True)
                self.slider_opac.setValue(50)
                self._sync_reference_image_to_scene()

    def _sync_reference_image_to_scene(self) -> None:
        """Persiste a imagem de referência no documento 3D (Scene.image_planes e Scene.plugin_data)."""
        scene = getattr(self.viewport, "scene", None)
        if scene is None:
            return

        ref_planes_name = "Planta Baixa Referencia (TrazoMob)"
        # 1. Remove qualquer ImagePlane anterior com este nome
        if hasattr(scene, "image_planes"):
            scene.image_planes = [im for im in scene.image_planes if getattr(im, "name", "") != ref_planes_name]

        # 2. Se a imagem foi removida no canvas, limpa também os dados persistidos
        if self.canvas._ref_original_pixmap is None or not self.canvas._ref_image_path:
            if hasattr(scene, "plugin_data") and isinstance(scene.plugin_data, dict):
                scene.plugin_data.pop("trazomob_floorplan_ref", None)
            if hasattr(self.viewport, "update"):
                self.viewport.update()
            return

        # 3. Salva os metadados completos no plugin_data
        if not hasattr(scene, "plugin_data") or not isinstance(scene.plugin_data, dict):
            scene.plugin_data = {}

        pdata = {
            "path": self.canvas._ref_image_path,
            "pos_world": list(self.canvas._ref_pos_world),
            "width_m": float(self.canvas._ref_width_m),
            "opacity": float(self.canvas._ref_opacity),
            "rotation": int(self.canvas._ref_rotation),
            "visible": bool(self.canvas._ref_visible),
        }
        scene.plugin_data["trazomob_floorplan_ref"] = pdata

        # 4. Cria ImagePlane nativo na cena 3D (para embutir automaticamente no arquivo .igz)
        if hasattr(scene, "image_planes") and self.canvas._ref_visible:
            # Salva uma cópia orientada temporária se a imagem estiver rotacionada
            eff_path = self.canvas._ref_image_path
            if self.canvas._ref_rotation % 360 != 0 and self.canvas._ref_pixmap is not None:
                import tempfile, os
                tmp_dir = os.path.join(tempfile.gettempdir(), "trazomob_ref")
                os.makedirs(tmp_dir, exist_ok=True)
                rot_deg = self.canvas._ref_rotation % 360
                base_name = os.path.splitext(os.path.basename(self.canvas._ref_image_path))[0]
                eff_path = os.path.join(tmp_dir, f"{base_name}_rot{rot_deg}.png")
                self.canvas._ref_pixmap.save(eff_path, "PNG")

            rx, ry = self.canvas._ref_pos_world
            rw = self.canvas._ref_width_m
            rh = rw * (self.canvas._ref_pixmap.height() / max(1, self.canvas._ref_pixmap.width()))

            # Vetores u e v horizontais na mesa Z=0
            origin = QVector3D(rx, ry, 0.0)
            u = QVector3D(rw, 0.0, 0.0)
            v = QVector3D(0.0, rh, 0.0)

            try:
                plane = ImagePlane(
                    path=eff_path,
                    origin=origin,
                    u=u,
                    v=v,
                    aspect=(rh / max(1e-4, rw)),
                    name=ref_planes_name,
                    opacity=float(self.canvas._ref_opacity),
                )
                scene.image_planes.append(plane)
            except Exception:
                pass

        if hasattr(self.viewport, "update"):
            self.viewport.update()

    def _restore_reference_image_from_scene(self) -> None:
        """Restaura a imagem de referência previamente salva no documento."""
        scene = getattr(self.viewport, "scene", None)
        if scene is None:
            return

        ref_data = None
        # 1. Tenta carregar do plugin_data (fonte rica)
        if hasattr(scene, "plugin_data") and isinstance(scene.plugin_data, dict):
            ref_data = scene.plugin_data.get("trazomob_floorplan_ref")

        # 2. Se não encontrou no plugin_data, tenta resgatar de ImagePlane existente
        if not ref_data and hasattr(scene, "image_planes"):
            ref_planes_name = "Planta Baixa Referencia (TrazoMob)"
            for im in scene.image_planes:
                if getattr(im, "name", "") == ref_planes_name:
                    ref_data = {
                        "path": im.path,
                        "pos_world": [im.origin.x(), im.origin.y()],
                        "width_m": im.u.length(),
                        "opacity": getattr(im, "opacity", 0.5),
                        "rotation": 0,
                        "visible": True,
                    }
                    break

        if isinstance(ref_data, dict) and ref_data.get("path"):
            path = ref_data["path"]
            import os
            if os.path.exists(path):
                pos = tuple(ref_data.get("pos_world", (0.0, 0.0)))
                w_m = float(ref_data.get("width_m", 10.0))
                opac = float(ref_data.get("opacity", 0.5))
                rot = int(ref_data.get("rotation", 0))
                vis = bool(ref_data.get("visible", True))

                if self.canvas.set_reference_image(path, pos_world=pos, width_m=w_m,
                                                   opacity=opac, rotation=rot, visible=vis):
                    self.slider_opac.setValue(int(opac * 100))
                    self.chk_ref_vis.setChecked(vis)

    def _on_rotate_ref_clicked(self) -> None:
        self.canvas.rotate_reference_image(90)
        self._sync_reference_image_to_scene()

    def _on_calib_ref_clicked(self) -> None:
        if self.btn_calib_ref.isChecked():
            self.btn_move_ref.setChecked(False)
            self.btn_tool_line.setChecked(False)
            self.btn_tool_rect.setChecked(False)
            self.btn_tool_select.setChecked(False)
            self.canvas.mode = "calibrar_ref"
            self.canvas._calib_points.clear()
            self.canvas.update_cursor()
        else:
            self._set_mode("linha")
            self.btn_tool_line.setChecked(True)

    def _on_move_ref_clicked(self) -> None:
        if self.btn_move_ref.isChecked():
            self.btn_calib_ref.setChecked(False)
            self.btn_tool_line.setChecked(False)
            self.btn_tool_rect.setChecked(False)
            self.btn_tool_select.setChecked(False)
            self.canvas.mode = "mover_ref"
            self.canvas.update_cursor()
        else:
            self._set_mode("linha")
            self.btn_tool_line.setChecked(True)

    def _on_ref_opacity_changed(self, value: int) -> None:
        self.canvas._ref_opacity = float(value) / 100.0
        self.canvas.update()
        self._sync_reference_image_to_scene()

    def _on_ref_visibility_toggled(self, checked: bool) -> None:
        self.canvas._ref_visible = checked
        self.canvas.update()
        self._sync_reference_image_to_scene()

    def _on_remove_reference_image(self) -> None:
        self.canvas.remove_reference_image()
        self.btn_calib_ref.setChecked(False)
        self.btn_move_ref.setChecked(False)
        self._set_mode("linha")
        self.btn_tool_line.setChecked(True)
        self._sync_reference_image_to_scene()

    def _confirm_discard_changes(self) -> bool:
        """Exibe diálogo de confirmação se houver alterações não geradas no 3D."""
        if not self.has_unsaved_changes():
            return True

        res = QMessageBox.question(
            self,
            "Descartar Alterações?",
            "Você possui alterações não salvas na planta das paredes.\n\n"
            "Deseja descartar as alterações e fechar sem gerar no 3D?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return res == QMessageBox.Yes

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Trata tecla ESC no nível do diálogo evitando fechar acidentalmente se houver traço ou alterações."""
        if event.key() == Qt.Key_Escape:
            # 1. Se o canvas estiver desenhando ou com algo selecionado, cancela apenas a ação do canvas
            if (self.canvas._start_pt is not None or
                self.canvas._selected_seg_id is not None or
                self.canvas._selected_node_id is not None or
                self.canvas._type_buffer or
                self.canvas.mode in ("calibrar_ref", "mover_ref")):
                self.canvas.keyPressEvent(event)
                return

            # 2. Se não houver nada ativo no canvas, confirma descarte se houver alterações
            if not self._confirm_discard_changes():
                event.ignore()
                return

        super().keyPressEvent(event)

    def closeEvent(self, event) -> None:
        """Solicita confirmação antes de fechar a janela se houver alterações não salvas."""
        if not self._confirm_discard_changes():
            event.ignore()
            return
        self._sync_reference_image_to_scene()
        super().closeEvent(event)

    def reject(self) -> None:
        """Cancela/fecha o diálogo solicitando confirmação caso haja alterações."""
        if not self._confirm_discard_changes():
            return
        self._sync_reference_image_to_scene()
        super().reject()

    def _build_3d_and_close(self) -> None:
        self._sync_reference_image_to_scene()
        if self.graph.is_empty():
            self.reject()
            return

        scene = getattr(self.viewport, "scene", None)
        if scene is not None:
            group_name = self.existing_group.name if self.existing_group else "Ambiente Paredes"
            scale = bare_number_scale()
            altura = self.sp_height.value() * scale

            res = {"wall": None, "floors": 0, "ceilings": 0}

            # Toda a alteracao do modelo em UMA transacao do historico (Ctrl+Z desfaz tudo),
            # como pede docs/plugins.md ("Mutating the document").
            def _apply(scene):
                # Constrói o sólido extrudado contínuo a partir do grafo 2D
                wall_grp = self.graph.build_3d_group(
                    scene,
                    altura_m=altura,
                    name=group_name,
                )
                if wall_grp is not None:
                    # Preserva a matriz de posicionamento 3D (xform) caso a parede tenha sido movida,
                    # rotacionada ou copiada/colada em outro documento com deslocamento.
                    if self.existing_group is not None and getattr(self.existing_group, "xform", None) is not None:
                        from PySide6.QtGui import QMatrix4x4
                        wall_grp.xform = QMatrix4x4(self.existing_group.xform)

                    if self.existing_group is not None and self.existing_group in scene.groups:
                        idx = scene.groups.index(self.existing_group)
                        scene.groups[idx] = wall_grp
                    else:
                        scene.groups.append(wall_grp)

                    # Identifica ciclos fechados (cômodos) formados pelas paredes
                    cycles = self.graph.find_closed_cycles()
                    floor_created = 0
                    ceiling_created = 0

                    # Remove pisos/tetos anteriores associados a este ambiente se já existiam
                    # Evita multiplicação de pisos/tetos cada vez que o usuário clica em Concluir
                    groups_to_remove = []
                    prev_wall_name = self.existing_group.name if self.existing_group is not None else None

                    for g in list(scene.groups):
                        if g is wall_grp or g is self.existing_group:
                            continue
                        g_ext = getattr(g, "ext", None)
                        if not isinstance(g_ext, dict):
                            continue

                        # Verifica se o grupo é piso ou teto associado a esta parede
                        is_floor = bool(g_ext.get("trazomob_floor"))
                        is_ceiling = bool(g_ext.get("trazomob_ceiling"))
                        assoc_wall = g_ext.get("associated_wall_name")

                        if is_floor or is_ceiling:
                            # Se possui vínculo explícito pelo nome da parede
                            if prev_wall_name and assoc_wall == prev_wall_name:
                                groups_to_remove.append(g)
                            elif prev_wall_name and not assoc_wall:
                                # Caso retroativo: piso/teto da mesma camada gerado sem metadados
                                if (is_floor and self.chk_floor.isChecked()) or (is_ceiling and self.chk_ceiling.isChecked()):
                                    groups_to_remove.append(g)

                    for g in groups_to_remove:
                        if g in scene.groups:
                            scene.groups.remove(g)

                    for cycle_pts in cycles:
                        vec_pts = [QVector3D(p[0], p[1], 0.0) for p in cycle_pts]

                        # 1. Gera Piso automaticamente
                        if self.chk_floor.isChecked():
                            floor_grp = WallMeshBuilder.build_floor_group(scene, vec_pts)
                            if floor_grp is not None:
                                if not isinstance(floor_grp.ext, dict):
                                    floor_grp.ext = {}
                                floor_grp.ext["associated_wall_name"] = wall_grp.name
                                scene.groups.append(floor_grp)
                                res["floors"] += 1

                        # 2. Gera Teto / Forro automaticamente no pé-direito
                        if self.chk_ceiling.isChecked():
                            ceiling_grp = WallMeshBuilder.build_ceiling_group(scene, vec_pts, altura_m=altura)
                            if ceiling_grp is not None:
                                if not isinstance(ceiling_grp.ext, dict):
                                    ceiling_grp.ext = {}
                                ceiling_grp.ext["associated_wall_name"] = wall_grp.name
                                scene.groups.append(ceiling_grp)
                                res["ceilings"] += 1

                    res["wall"] = wall_grp

            from core.history import SnapshotImport
            history = getattr(self.viewport, "history", None)
            if history is not None:
                history.execute(SnapshotImport(_apply))
            else:
                _apply(scene)
                scene.version += 1
            if hasattr(self.viewport, "notify_scene_changed"):
                self.viewport.notify_scene_changed()
            wall_grp = res["wall"]
            floor_created, ceiling_created = res["floors"], res["ceilings"]
            if wall_grp is not None:
                if hasattr(self.viewport, "flash_status"):
                    detalhes = []
                    if floor_created > 0:
                        detalhes.append(f"{floor_created} piso(s)")
                    if ceiling_created > 0:
                        detalhes.append(f"{ceiling_created} teto(s)")
                    extra_str = f" com {' e '.join(detalhes)}" if detalhes else ""
                    self.viewport.flash_status(f"🧱 Paredes geradas com sucesso{extra_str}! ({len(self.graph.segments)} paredes)")
                self.viewport.update()

        self.accept()

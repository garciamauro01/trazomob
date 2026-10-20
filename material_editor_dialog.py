# SPDX-License-Identifier: GPL-3.0-or-later
"""Editor e Gerenciador de Materiais PBR do TrazoMob para Renderização no Blender.

Permite listar todos os materiais da cena atual e configurar:
- Tipo PBR: Madeira/MDF, Mármore/Pedra, Tecido/Estofado, Metal, Vidro, Couro, Tinta de Parede
- Subtipos e Acabamentos: Laca Brilhante, Acetinada, Fosca, Polida, Levigada, Veludo, Escovado
- Sliders: Rugosidade (Roughness), Especular/Verniz (Clearcoat) e Intensidade de Relevo (Bump)
"""
from __future__ import annotations

from typing import Dict, Any, List
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPixmap, QPainter, QIcon
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSplitter, QListWidget, QListWidgetItem,
    QGroupBox, QLabel, QComboBox, QSlider, QDoubleSpinBox, QPushButton,
    QWidget, QFrame, QFormLayout
)

# Presets predefinidos de shaders PBR
MATERIAL_PBR_TYPES = {
    "auto": {
        "label": "Auto-Detectar (Padrão Inteligente)",
        "roughness": 0.35,
        "bump": 0.02,
        "subtypes": ["Padrão"]
    },
    "madeira": {
        "label": "Madeira / MDF / Marcenaria",
        "roughness": 0.32,
        "bump": 0.035,
        "subtypes": ["MDF Madeirado (Textura Natural)", "Laca Fosca / Acetinada", "Laca Alto Brilho (High Gloss)"]
    },
    "pedra": {
        "label": "Mármore / Granito / Quartzo",
        "roughness": 0.06,
        "bump": 0.015,
        "subtypes": ["Polido (Espelhado com Verniz)", "Levigado / Escovado (Fosco)"]
    },
    "tecido": {
        "label": "Tecido / Estofado / Cortina",
        "roughness": 0.85,
        "bump": 0.04,
        "subtypes": ["Linho / Trama Fina", "Veludo Aveludado (Sheen)", "Algodão / Lona"]
    },
    "metal": {
        "label": "Metal / Inox / Perfis Alumínio",
        "roughness": 0.22,
        "bump": 0.005,
        "subtypes": ["Alumínio / Inox Escovado", "Metal Polido (Cromado/Gold)", "Preto Fosco Microtexturizado"]
    },
    "vidro": {
        "label": "Vidro / Espelho / Reflecta",
        "roughness": 0.02,
        "bump": 0.0,
        "subtypes": ["Vidro Incolor Transparente", "Vidro Reflecta Bronze/Fumê", "Espelho 100% Reflexivo"]
    },
    "couro": {
        "label": "Couro / Couro Ecológico",
        "roughness": 0.45,
        "bump": 0.04,
        "subtypes": ["Couro Natural Poroso", "Couro Liso Acetinado"]
    },
    "parede": {
        "label": "Tinta de Parede / Drywall / Cimento",
        "roughness": 0.85,
        "bump": 0.015,
        "subtypes": ["Tinta Acrílica Fosca / Acetinada", "Cimento Queimado / Concreto"]
    }
}


def extract_scene_materials(scene) -> List[str]:
    """Extrai os nomes de todos os materiais usados nos objetos/malhas da cena."""
    mat_names = set()
    for grp in getattr(scene, "groups", []) or []:
        def _walk(node):
            m = getattr(node, "mesh", None)
            if m is not None:
                for mat in getattr(m, "materials", []) or []:
                    name = getattr(mat, "name", "")
                    if name:
                        mat_names.add(name)
            for c in getattr(node, "children", []) or []:
                _walk(c)
        _walk(grp)
    return sorted(list(mat_names))


class MaterialEditorDialog(QDialog):
    """Diálogo visual para editar e atribuir shaders PBR aos materiais da cena."""

    materials_updated = Signal(dict)

    def __init__(self, scene, current_overrides: dict | None = None, parent=None):
        super().__init__(parent)
        self.scene = scene
        self._overrides = dict(current_overrides or {})
        self.setWindowTitle("🎨 TrazoMob — Configuração de Materiais & Shaders PBR (Blender)")
        self.setMinimumSize(780, 520)

        self._scene_materials = extract_scene_materials(scene)
        self._current_mat: str | None = None

        self._build_ui()
        self._load_materials_list()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Cabeçalho
        lbl_head = QLabel(
            "<b>Definição de Shaders PBR Fotorrealistas para o Blender (Cycles / EEVEE)</b><br>"
            "<span style='color: palette(mid); font-size: 11px;'>"
            "Configure como cada material ou chapa do projeto reage à luz (tecidos aveludados, pedras polidas com verniz, veios de madeira, metais e couros).</span>"
        )
        lbl_head.setWordWrap(True)
        layout.addWidget(lbl_head)

        splitter = QSplitter(Qt.Horizontal)

        # ── ESQUERDA: LISTA DE MATERIAIS ENCONTRADOS ──
        w_left = QWidget()
        l_left = QVBoxLayout(w_left)
        l_left.setContentsMargins(0, 0, 0, 0)
        l_left.setSpacing(6)

        lbl_mats = QLabel("<b>Materiais no Projeto:</b>")
        l_left.addWidget(lbl_mats)

        self.list_mats = QListWidget()
        self.list_mats.currentRowChanged.connect(self._on_material_selected)
        l_left.addWidget(self.list_mats, 1)

        splitter.addWidget(w_left)

        # ── DIREITA: PROPRIEDADES DO MATERIAL SELECIONADO ──
        self.box_props = QGroupBox("Propriedades do Shader")
        l_right = QVBoxLayout(self.box_props)
        l_right.setSpacing(10)

        form = QFormLayout()
        form.setSpacing(8)

        # Tipo PBR
        self.cb_type = QComboBox()
        for k, v in MATERIAL_PBR_TYPES.items():
            self.cb_type.addItem(v["label"], k)
        self.cb_type.currentIndexChanged.connect(self._on_type_changed)
        form.addRow("Tipo de Shader:", self.cb_type)

        # Subtipo / Acabamento
        self.cb_subtype = QComboBox()
        self.cb_subtype.currentIndexChanged.connect(self._on_subtype_changed)
        form.addRow("Acabamento:", self.cb_subtype)

        l_right.addLayout(form)

        # Sliders de Ajuste Fino
        l_right.addSpacing(6)
        lbl_adj = QLabel("<b>Ajustes de Reação à Luz:</b>")
        l_right.addWidget(lbl_adj)

        # 1. Rugosidade (Roughness)
        h_rough = QHBoxLayout()
        h_rough.addWidget(QLabel("Rugosidade:"))
        self.sl_rough = QSlider(Qt.Horizontal)
        self.sl_rough.setRange(0, 100)
        self.sl_rough.valueChanged.connect(self._on_slider_changed)
        h_rough.addWidget(self.sl_rough, 1)
        self.lbl_rough_val = QLabel("35%")
        h_rough.addWidget(self.lbl_rough_val)
        l_right.addLayout(h_rough)

        # 2. Relevo / Rugosidade Tátil (Bump Map)
        h_bump = QHBoxLayout()
        h_bump.addWidget(QLabel("Relevo Tátil (Bump):"))
        self.sl_bump = QSlider(Qt.Horizontal)
        self.sl_bump.setRange(0, 100)
        self.sl_bump.valueChanged.connect(self._on_slider_changed)
        h_bump.addWidget(self.sl_bump, 1)
        self.lbl_bump_val = QLabel("20%")
        h_bump.addWidget(self.lbl_bump_val)
        l_right.addLayout(h_bump)

        # Descrição explicativa do preset
        self.lbl_desc = QLabel()
        self.lbl_desc.setWordWrap(True)
        self.lbl_desc.setStyleSheet("background-color: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 6px; font-size: 11px;")
        l_right.addWidget(self.lbl_desc)

        l_right.addStretch()

        btn_reset_mat = QPushButton("Restaurar Padrão Deste Material")
        btn_reset_mat.clicked.connect(self._reset_current_material)
        l_right.addWidget(btn_reset_mat)

        splitter.addWidget(self.box_props)
        layout.addWidget(splitter, 1)

        # Rodapé
        h_bot = QHBoxLayout()
        h_bot.addStretch()
        btn_cancel = QPushButton("Cancelar")
        btn_cancel.clicked.connect(self.reject)
        h_bot.addWidget(btn_cancel)

        btn_ok = QPushButton("Aplicar ao Render")
        btn_ok.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 6px 14px;")
        btn_ok.clicked.connect(self._save_and_close)
        h_bot.addWidget(btn_ok)
        layout.addLayout(h_bot)

    def _load_materials_list(self):
        self.list_mats.blockSignals(True)
        self.list_mats.clear()
        for name in self._scene_materials:
            cfg = self._overrides.get(name, {})
            p_type = cfg.get("type")
            prefix = "✨ " if p_type else "▫️ "
            lbl = f"{prefix}{name}"
            if p_type:
                t_label = MATERIAL_PBR_TYPES.get(p_type, {}).get("label", p_type)
                lbl += f"  [{t_label}]"
            self.list_mats.addItem(lbl)
        self.list_mats.blockSignals(False)

        if self._scene_materials:
            self.list_mats.setCurrentRow(0)
        else:
            self.box_props.setEnabled(False)

    def _on_material_selected(self, row: int):
        if not (0 <= row < len(self._scene_materials)):
            self.box_props.setEnabled(False)
            self._current_mat = None
            return

        self.box_props.setEnabled(True)
        mat_name = self._scene_materials[row]
        self._current_mat = mat_name
        self.box_props.setTitle(f"Propriedades de: {mat_name}")

        cfg = self._overrides.get(mat_name, {})
        cur_type = cfg.get("type", "auto")

        # Seleciona o tipo no combobox
        idx = self.cb_type.findData(cur_type)
        self.cb_type.blockSignals(True)
        self.cb_type.setCurrentIndex(max(0, idx))
        self.cb_type.blockSignals(False)

        self._populate_subtypes(cur_type)

        rough = float(cfg.get("roughness", MATERIAL_PBR_TYPES.get(cur_type, {}).get("roughness", 0.35)))
        bump = float(cfg.get("bump", MATERIAL_PBR_TYPES.get(cur_type, {}).get("bump", 0.02)))

        self.sl_rough.blockSignals(True)
        self.sl_rough.setValue(int(rough * 100))
        self.lbl_rough_val.setText(f"{int(rough * 100)}%")
        self.sl_rough.blockSignals(False)

        self.sl_bump.blockSignals(True)
        self.sl_bump.setValue(int(bump * 1000))
        self.lbl_bump_val.setText(f"{int(bump * 1000)}%")
        self.sl_bump.blockSignals(False)

        self._update_desc(cur_type)

    def _populate_subtypes(self, cur_type: str):
        self.cb_subtype.blockSignals(True)
        self.cb_subtype.clear()
        subtypes = MATERIAL_PBR_TYPES.get(cur_type, {}).get("subtypes", ["Padrão"])
        for st in subtypes:
            self.cb_subtype.addItem(st)
        self.cb_subtype.blockSignals(False)

    def _on_type_changed(self):
        if not self._current_mat:
            return
        new_type = self.cb_type.currentData()
        self._populate_subtypes(new_type)
        def_info = MATERIAL_PBR_TYPES.get(new_type, {})
        rough = def_info.get("roughness", 0.35)
        bump = def_info.get("bump", 0.02)

        self.sl_rough.setValue(int(rough * 100))
        self.sl_bump.setValue(int(bump * 1000))

        if new_type == "auto":
            if self._current_mat in self._overrides:
                del self._overrides[self._current_mat]
        else:
            self._overrides[self._current_mat] = {
                "type": new_type,
                "sub_type": self.cb_subtype.currentText(),
                "roughness": rough,
                "bump": bump,
            }

        self._update_desc(new_type)
        row = self.list_mats.currentRow()
        self._load_materials_list()
        self.list_mats.setCurrentRow(row)

    def _on_subtype_changed(self):
        if not self._current_mat or self._current_mat not in self._overrides:
            return
        self._overrides[self._current_mat]["sub_type"] = self.cb_subtype.currentText()

    def _on_slider_changed(self):
        if not self._current_mat:
            return
        r_val = self.sl_rough.value() / 100.0
        b_val = self.sl_bump.value() / 1000.0
        self.lbl_rough_val.setText(f"{self.sl_rough.value()}%")
        self.lbl_bump_val.setText(f"{self.sl_bump.value() / 10.0:.1f}%")

        if self._current_mat in self._overrides:
            self._overrides[self._current_mat]["roughness"] = r_val
            self._overrides[self._current_mat]["bump"] = b_val

    def _update_desc(self, cur_type: str):
        descs = {
            "auto": "O motor analisa o nome da peça e textura para aplicar relevo e brilho ideais automaticamente.",
            "madeira": "Aplica shader de MDF com veios táteis e opção de laca fosca, acetinada ou alto brilho.",
            "pedra": "Gera camada vitrificada de verniz límpido (Clearcoat) e especularidade de mármores e granitos.",
            "tecido": "Ativa sombreamento micro-têxtil com penugem nas bordas (Sheen / Velvet) para sofás e cortinas.",
            "metal": "Simula condutividade metálica (Metallic 1.0) e reflexo estriado/escovado em alumínios e puxadores.",
            "vidro": "Aplica refração pura (IOR 1.52) ou refletividade reflecta sem distorção óptica.",
            "couro": "Cria células orgânicas procedurais com toque acetinado suave.",
            "parede": "Micro-textura suave simulando tinta fosca e rolo de massa acrílica."
        }
        self.lbl_desc.setText(descs.get(cur_type, ""))

    def _reset_current_material(self):
        if self._current_mat and self._current_mat in self._overrides:
            del self._overrides[self._current_mat]
            row = self.list_mats.currentRow()
            self._load_materials_list()
            self.list_mats.setCurrentRow(row)

    def _save_and_close(self):
        self.materials_updated.emit(self._overrides)
        self.accept()

    def get_overrides(self) -> dict:
        return dict(self._overrides)

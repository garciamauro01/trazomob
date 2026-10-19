# SPDX-License-Identifier: GPL-3.0-or-later
"""Gerenciador visual e ferramenta de inserção e controle de luzes físicas do TrazoMob.

Permite inserir e controlar:
- Spot Embutido (Dicroica / AR70 / PAR20) com mira direcionável e ângulo do facho
- Fita LED de Marcenaria / Perfil Linear (iluminação indireta sob armários)
- Ponto de Luz Difuso / Plafon / Pendente
- Controle de Temperatura de Cor em Kelvin (2200K quente a 6500K frio)
- Potência em Watts
- Liga/Desliga individual (se todas forem apagadas num quarto fechado, o render fica preto como no Kerkythea/V-Ray)
"""
from __future__ import annotations

import math
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, QPointF, QSize
from PySide6.QtGui import (
    QColor, QPixmap, QPainter, QBrush, QPen, QFont, QIcon, QVector3D
)
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QSlider, QSpinBox, QDoubleSpinBox,
    QComboBox, QFrame, QGroupBox, QMessageBox, QSplitter, QWidget
)

from core.group import Group
from core.render_blender import (
    clean_lights, kelvin_to_rgb, aim_from_angles, angles_from_aim,
    MIN_KELVIN, MAX_KELVIN, DEFAULT_KELVIN
)
from tools.base import Tool, ToolContext


# ── Presets Prontos de Iluminação Residencial / Marcenaria ─────────────
LIGHT_PRESETS = {
    "spot_quente": {
        "name": "Spot Dicroica Aconchegante (2700K)",
        "kind": "spot",
        "power": 450.0,
        "kelvin": 2700,
        "angle": 45.0,
        "dir": [0.0, 0.0, -1.0],
    },
    "spot_neutro": {
        "name": "Spot Neutro / Cozinha (4000K)",
        "kind": "spot",
        "power": 600.0,
        "kelvin": 4000,
        "angle": 60.0,
        "dir": [0.0, 0.0, -1.0],
    },
    "fita_led": {
        "name": "Fita LED Marcenaria (3000K Suave)",
        "kind": "point",
        "power": 250.0,
        "kelvin": 3000,
        "angle": 120.0,
        "dir": [0.0, 0.0, -1.0],
    },
    "plafon_geral": {
        "name": "Plafon Difuso Central (3500K)",
        "kind": "point",
        "power": 1200.0,
        "kelvin": 3500,
        "angle": 90.0,
        "dir": [0.0, 0.0, -1.0],
    },
}


def _lights_app(viewport):
    """Handle on the native Render plugin's document data (key 'render_blender'),
    so the lights are shared with IngeTrazo's viewport bulbs and its render."""
    from views.extension_api import ExtensionApp
    return ExtensionApp(viewport.window(), "render_blender")


def _get_document_lights(viewport) -> list[dict]:
    """Recupera a lista de luzes do documento."""
    raw = _lights_app(viewport).document_data({}) or {}
    if not isinstance(raw, dict):
        raw = {}
    return clean_lights(raw.get("lights", []))


def _save_document_lights(viewport, lights: list[dict]) -> None:
    """Salva as luzes no documento (um passo de undo)."""
    app = _lights_app(viewport)
    raw = app.document_data({}) or {}
    if not isinstance(raw, dict):
        raw = {}
    raw.setdefault("ambience", "night")
    raw.setdefault("sun_scale", 1.0)
    raw["lights"] = clean_lights(lights)
    app.set_document_data(raw)
    viewport.update()


def _lights_from_any_window() -> list[dict]:
    from PySide6.QtWidgets import QApplication
    for w in QApplication.topLevelWidgets():
        vp = getattr(w, "viewport", None)
        if vp is not None and hasattr(vp, "scene"):
            return _get_document_lights(vp)
    return []


def _flash(viewport, msg: str) -> None:
    fn = getattr(viewport, "flash_status", None)
    if callable(fn):
        fn(msg)


class InsertLightTool(Tool):
    """Ferramenta interativa para posicionar luzes com o clique do mouse."""

    name = "Inserir Luz"
    shortcut = None
    uses_snap = True
    description = "Clique sobre o teto, móvel ou parede para posicionar a luz."

    def __init__(self, light_data: dict, on_placed=None):
        super().__init__()
        self.light_data = dict(light_data)
        self.on_placed = on_placed
        self.hover_point: Optional[QVector3D] = None

    def on_activate(self, viewport) -> None:
        self.hover_point = None
        if True:
            _flash(viewport, f"💡 Clique no modelo para fixar a luz [{self.light_data.get('name', 'Spot')}]. Esc cancela.")

    def on_deactivate(self, viewport) -> None:
        self.hover_point = None
        if True:
            _flash(viewport, "")

    def on_hover(self, ctx: ToolContext) -> None:
        self.hover_point = ctx.world
        ctx.viewport.update()

    def on_click(self, ctx: ToolContext) -> None:
        pos = [ctx.world.x(), ctx.world.y(), ctx.world.z()]
        # Se clicou em uma face de teto ou prateleira virada para baixo, afasta levemente
        is_face = ctx.snap is not None and ctx.snap.kind == "on_face"
        new_light = dict(self.light_data)
        new_light["pos"] = pos
        new_light["on"] = True
        
        # Adiciona na cena
        lights = _get_document_lights(ctx.viewport)
        lights.append(new_light)
        _save_document_lights(ctx.viewport, lights)

        if True:
            _flash(ctx.viewport, f"✅ Luz inserida com sucesso em X:{pos[0]:.2f} Y:{pos[1]:.2f} Z:{pos[2]:.2f}")

        if callable(self.on_placed):
            self.on_placed(new_light)

        # Volta para a ferramenta de seleção padrão se existir
        if hasattr(ctx.viewport, "set_active_tool"):
            from tools.base import Tool
            # Procura select no app se disponível
            app = getattr(ctx.viewport, "app", None)
            if app and hasattr(app, "select_tool"):
                ctx.viewport.set_active_tool(app.select_tool)


    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Escape:
            cb = getattr(self, 'on_placed', None) or getattr(self, 'on_aimed', None)
            if callable(cb):
                cb(None) if hasattr(self, 'on_placed') else cb()
            return True
        return False

class AimLightTool(Tool):
    """Ferramenta para direcionar a mira do cone de um Spot com o mouse."""

    name = "Mirar Spot"
    shortcut = None
    uses_snap = True
    description = "Clique no ponto ou superfície onde o Spot deve iluminar."

    def __init__(self, light_index: int, on_aimed=None):
        super().__init__()
        self.light_index = light_index
        self.on_aimed = on_aimed

    def on_activate(self, viewport) -> None:
        if True:
            _flash(viewport, "🎯 Clique no móvel ou ponto para onde o Spot deve apontar. Esc cancela.")

    def on_deactivate(self, viewport) -> None:
        if True:
            _flash(viewport, "")

    def on_click(self, ctx: ToolContext) -> None:
        lights = _get_document_lights(ctx.viewport)
        if 0 <= self.light_index < len(lights):
            lt = lights[self.light_index]
            pos = lt.get("pos", [0, 0, 0])
            dir_vec = [ctx.world.x() - pos[0], ctx.world.y() - pos[1], ctx.world.z() - pos[2]]
            dist = math.hypot(*dir_vec)
            if dist > 1e-4:
                lt["dir"] = [dir_vec[0] / dist, dir_vec[1] / dist, dir_vec[2] / dist]
                _save_document_lights(ctx.viewport, lights)
                if True:
                    _flash(ctx.viewport, "✅ Direção do Spot atualizada.")

        if callable(self.on_aimed):
            self.on_aimed()


    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Escape:
            cb = getattr(self, 'on_placed', None) or getattr(self, 'on_aimed', None)
            if callable(cb):
                cb(None) if hasattr(self, 'on_placed') else cb()
            return True
        return False

class LightManagerDialog(QDialog):
    """Diálogo visual para gerenciamento completo das luzes físicas da cena."""

    def __init__(self, viewport, parent=None):
        super().__init__(parent)
        self.viewport = viewport
        self.setWindowTitle("💡 TrazoMob — Gerenciador de Iluminação & Spots Físicos")
        self.setMinimumSize(680, 520)

        self._lights: list[dict] = []
        self._current_index: int = -1

        self._build_ui()
        self._reload_lights()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Cabeçalho Explicativo
        lbl_head = QLabel(
            "<b>Controle Físico de Iluminação para Render Foto-Realista (Blender Cycles)</b><br>"
            "<span style='color: palette(text); font-size: 11px;'>"
            "Igual ao SketchUp + Kerkythea / V-Ray: as lâmpadas e spots inseridos iluminam fisicamente o ambiente.<br>"
            "Se todas as luzes forem desligadas e a cena for fechada, o render ficará no escuro real.</span>"
        )
        lbl_head.setWordWrap(True)
        layout.addWidget(lbl_head)

        # Corpo dividido em Lista (esquerda) e Propriedades (direita)
        splitter = QSplitter(Qt.Horizontal)

        # ── ESQUERDA: LISTA DE LUZES E PRESETS ──
        w_left = QWidget()
        l_left = QVBoxLayout(w_left)
        l_left.setContentsMargins(0, 0, 0, 0)
        l_left.setSpacing(8)

        lbl_list = QLabel("<b>Luzes no Projeto:</b>")
        l_left.addWidget(lbl_list)

        self.list_lights = QListWidget()
        self.list_lights.currentRowChanged.connect(self._on_light_selected)
        self.list_lights.itemChanged.connect(self._on_item_checked)
        l_left.addWidget(self.list_lights, 1)

        # Ações de adição rápida
        lbl_add = QLabel("<b>+ Adicionar Nova Luz:</b>")
        l_left.addWidget(lbl_add)

        h_add = QHBoxLayout()
        btn_add_spot = QPushButton("🔦 + Spot / Dicroica")
        btn_add_spot.setToolTip("Adiciona um spot com cone de luz direcionável")
        btn_add_spot.clicked.connect(lambda: self._start_placement("spot_quente"))
        h_add.addWidget(btn_add_spot)

        btn_add_led = QPushButton("✨ + Fita LED")
        btn_add_led.setToolTip("Adiciona iluminação difusa para nichos e sob armários")
        btn_add_led.clicked.connect(lambda: self._start_placement("fita_led"))
        h_add.addWidget(btn_add_led)

        l_left.addLayout(h_add)

        btn_del = QPushButton("🗑️ Excluir Luz Selecionada")
        btn_del.clicked.connect(self._delete_current_light)
        l_left.addWidget(btn_del)

        splitter.addWidget(w_left)

        # ── DIREITA: PROPRIEDADES DA LUZ SELECIONADA ──
        self.w_right = QGroupBox("Propriedades da Luz")
        l_right = QVBoxLayout(self.w_right)
        l_right.setSpacing(10)

        # Nome
        h_name = QHBoxLayout()
        h_name.addWidget(QLabel("Nome / Identificação:"))
        self.txt_name = QPushButton()
        self.txt_name.setEnabled(False)
        h_name.addWidget(self.txt_name, 1)
        l_right.addLayout(h_name)

        # Tipo (Spot vs Difusa)
        h_kind = QHBoxLayout()
        h_kind.addWidget(QLabel("Tipo de Emissão:"))
        self.cb_kind = QComboBox()
        self.cb_kind.addItems(["Spot Direcionável (Cone de Foco)", "Ponto Difuso (Omnidirecional)"])
        self.cb_kind.currentIndexChanged.connect(self._on_prop_changed)
        h_kind.addWidget(self.cb_kind, 1)
        l_right.addLayout(h_kind)

        # Potência (Watts)
        h_pwr = QHBoxLayout()
        h_pwr.addWidget(QLabel("Potência:"))
        self.spin_power = QDoubleSpinBox()
        self.spin_power.setRange(10.0, 10000.0)
        self.spin_power.setSingleStep(50.0)
        self.spin_power.setSuffix(" W")
        self.spin_power.valueChanged.connect(self._on_prop_changed)
        h_pwr.addWidget(self.spin_power, 1)
        l_right.addLayout(h_pwr)

        # Temperatura de Cor (Kelvin)
        lbl_k = QLabel("Temperatura de Cor (Kelvin):")
        l_right.addWidget(lbl_k)

        h_k = QHBoxLayout()
        self.slider_kelvin = QSlider(Qt.Horizontal)
        self.slider_kelvin.setRange(MIN_KELVIN, MAX_KELVIN)
        self.slider_kelvin.setSingleStep(100)
        self.spin_kelvin = QSpinBox()
        self.spin_kelvin.setRange(MIN_KELVIN, MAX_KELVIN)
        self.spin_kelvin.setSingleStep(100)
        self.spin_kelvin.setSuffix(" K")

        self.slider_kelvin.valueChanged.connect(self.spin_kelvin.setValue)
        self.spin_kelvin.valueChanged.connect(self.slider_kelvin.setValue)
        self.slider_kelvin.sliderReleased.connect(self._on_prop_changed)
        self.spin_kelvin.editingFinished.connect(self._on_prop_changed)

        h_k.addWidget(self.slider_kelvin, 1)
        h_k.addWidget(self.spin_kelvin)
        l_right.addLayout(h_k)

        self.lbl_kelvin_desc = QLabel("2700K — Amarela Quente Aconchegante")
        self.lbl_kelvin_desc.setStyleSheet("color: palette(mid); font-style: italic;")
        l_right.addWidget(self.lbl_kelvin_desc)

        # Ângulo de Abertura (para Spots)
        self.w_spot_group = QWidget()
        l_spot = QVBoxLayout(self.w_spot_group)
        l_spot.setContentsMargins(0, 0, 0, 0)
        l_spot.setSpacing(8)

        h_ang = QHBoxLayout()
        h_ang.addWidget(QLabel("Abertura do Facho:"))
        self.spin_angle = QDoubleSpinBox()
        self.spin_angle.setRange(10.0, 120.0)
        self.spin_angle.setSingleStep(5.0)
        self.spin_angle.setSuffix(" °")
        self.spin_angle.valueChanged.connect(self._on_prop_changed)
        h_ang.addWidget(self.spin_angle, 1)
        l_spot.addLayout(h_ang)

        self.btn_aim = QPushButton("🎯 Mirar Spot no 3D (Clique onde iluminar)")
        self.btn_aim.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 6px;")
        self.btn_aim.clicked.connect(self._start_aim)
        l_spot.addWidget(self.btn_aim)

        l_right.addWidget(self.w_spot_group)

        # Botão Reposicionar
        self.btn_reposition = QPushButton("📍 Reposicionar Luz no 3D")
        self.btn_reposition.clicked.connect(self._reposition_current_light)
        l_right.addWidget(self.btn_reposition)

        l_right.addStretch()
        splitter.addWidget(self.w_right)

        layout.addWidget(splitter, 1)

        # Rodapé
        h_bot = QHBoxLayout()
        h_bot.addStretch()
        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.accept)
        h_bot.addWidget(btn_close)
        layout.addLayout(h_bot)

    def _reload_lights(self):
        """Atualiza a lista visual com os dados das luzes salvas."""
        self._lights = _get_document_lights(self.viewport)
        self.list_lights.blockSignals(True)
        self.list_lights.clear()

        for i, lt in enumerate(self._lights):
            kind = "Spot" if lt.get("kind") == "spot" else "Difusa"
            name = lt.get("name") or f"Luz {i+1} ({kind})"
            power = int(lt.get("power", 400.0))
            k = int(lt.get("kelvin", 2700))
            icon_char = "🔦" if kind == "Spot" else "💡"

            item = QListWidgetItem(f"{icon_char} {name} — {power}W ({k}K)")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if lt.get("on", True) else Qt.Unchecked)
            self.list_lights.addItem(item)

        self.list_lights.blockSignals(False)

        if self._lights:
            sel_idx = min(max(self._current_index, 0), len(self._lights) - 1)
            self.list_lights.setCurrentRow(sel_idx)
        else:
            self._current_index = -1
            self.w_right.setEnabled(False)

    def _on_light_selected(self, row: int):
        self._current_index = row
        if not (0 <= row < len(self._lights)):
            self.w_right.setEnabled(False)
            return

        self.w_right.setEnabled(True)
        lt = self._lights[row]

        kind = lt.get("kind", "spot")
        self.cb_kind.blockSignals(True)
        self.cb_kind.setCurrentIndex(0 if kind == "spot" else 1)
        self.cb_kind.blockSignals(False)

        self.txt_name.setText(lt.get("name") or f"Luz #{row+1}")

        self.spin_power.blockSignals(True)
        self.spin_power.setValue(float(lt.get("power", 400.0)))
        self.spin_power.blockSignals(False)

        k = int(lt.get("kelvin", 2700))
        self.slider_kelvin.blockSignals(True)
        self.spin_kelvin.blockSignals(True)
        self.slider_kelvin.setValue(k)
        self.spin_kelvin.setValue(k)
        self.slider_kelvin.blockSignals(False)
        self.spin_kelvin.blockSignals(False)
        self._update_kelvin_desc(k)

        self.w_spot_group.setVisible(kind == "spot")
        self.spin_angle.blockSignals(True)
        self.spin_angle.setValue(float(lt.get("angle", 45.0)))
        self.spin_angle.blockSignals(False)

    def _update_kelvin_desc(self, k: int):
        if k < 2500:
            desc = "Luz de Vela / Fogo (Muito Quente)"
        elif k < 3200:
            desc = "Luz Quente Aconchegante (Ideal para quartos e salas)"
        elif k < 4500:
            desc = "Luz Neutra de Trabalho (Ideal para cozinhas e escritórios)"
        else:
            desc = "Luz Fria / Luz do Dia (LED 6500K)"
        self.lbl_kelvin_desc.setText(f"{k}K — {desc}")

    def _on_item_checked(self, item: QListWidgetItem):
        row = self.list_lights.row(item)
        if 0 <= row < len(self._lights):
            self._lights[row]["on"] = item.checkState() == Qt.Checked
            _save_document_lights(self.viewport, self._lights)

    def _on_prop_changed(self):
        row = self._current_index
        if not (0 <= row < len(self._lights)):
            return

        lt = self._lights[row]
        is_spot = self.cb_kind.currentIndex() == 0
        lt["kind"] = "spot" if is_spot else "point"
        self.w_spot_group.setVisible(is_spot)

        lt["power"] = float(self.spin_power.value())
        k = int(self.spin_kelvin.value())
        lt["kelvin"] = k
        lt["color"] = list(kelvin_to_rgb(k))
        lt["angle"] = float(self.spin_angle.value())

        self._update_kelvin_desc(k)
        _save_document_lights(self.viewport, self._lights)

        # Atualiza o texto do item da lista
        kind_label = "Spot" if is_spot else "Difusa"
        icon_char = "🔦" if is_spot else "💡"
        name = lt.get("name") or f"Luz {row+1} ({kind_label})"
        self.list_lights.item(row).setText(f"{icon_char} {name} — {int(lt['power'])}W ({k}K)")

    def _start_placement(self, preset_key: str):
        preset = LIGHT_PRESETS.get(preset_key, LIGHT_PRESETS["spot_quente"])
        new_light = dict(preset)
        new_light["color"] = list(kelvin_to_rgb(new_light["kelvin"]))

        self.hide()

        def _on_done(_placed):
            self._reload_lights()
            self.show()

        tool = InsertLightTool(new_light, on_placed=_on_done)
        self.viewport.set_active_tool(tool)

    def _reposition_current_light(self):
        if not (0 <= self._current_index < len(self._lights)):
            return
        lt = self._lights[self._current_index]
        self.hide()

        def _on_done(_placed):
            # O próprio insert colocou no final, mas se foi reposicionado removemos a antiga
            self._reload_lights()
            self.show()

        tool = InsertLightTool(lt, on_placed=_on_done)
        # Remove a antiga antes de repor
        del self._lights[self._current_index]
        _save_document_lights(self.viewport, self._lights)
        self.viewport.set_active_tool(tool)

    def _start_aim(self):
        if not (0 <= self._current_index < len(self._lights)):
            return
        self.hide()

        def _on_aimed():
            self._reload_lights()
            self.show()

        tool = AimLightTool(self._current_index, on_aimed=_on_aimed)
        self.viewport.set_active_tool(tool)

    def _delete_current_light(self):
        if 0 <= self._current_index < len(self._lights):
            del self._lights[self._current_index]
            _save_document_lights(self.viewport, self._lights)
            self._reload_lights()

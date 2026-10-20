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
        "kind": "led_strip",
        "power": 350.0,
        "kelvin": 3000,
        "angle": 120.0,
        "dir": [0.0, 0.0, -1.0],
    },
    "omni": {
        "name": "Luz Omni / Lâmpada Bulbo (2700K)",
        "kind": "point",
        "power": 600.0,
        "kelvin": 2700,
        "angle": 360.0,
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


def _surface_hit(ctx):
    """World point ON the surface under the cursor plus its normal.

    A free cursor point lies on the camera-dependent work plane, so a light
    placed there drifts when the view turns. Snapped points (endpoint,
    midpoint...) are real geometry and kept; otherwise the camera ray is
    intersected with the plane of the face actually under the mouse.
    Returns (QVector3D, QVector3D|None) or (None, None) over empty space."""
    vp = ctx.viewport
    kind = getattr(ctx.snap, "kind", None) if ctx.snap is not None else None
    x, y = ctx.screen.x(), ctx.screen.y()
    face, grp = (None, None)
    pick = getattr(vp, "pick_face_placement", None)
    if callable(pick):
        face, grp = pick(x, y)
    normal = None
    if face is not None:
        from core.snap import face_plane_world
        pt, n = face_plane_world(face, getattr(grp, "xform", None))
        if n.length() > 1e-9:
            normal = n.normalized()
            origin, direction = vp._pixel_to_ray(x, y)
            if origin is not None:
                hit = vp._ray_plane(origin, direction, pt, normal)
                if hit is not None:
                    # Face normal pointing back at the camera (the room side)
                    if QVector3D.dotProduct(normal, direction) > 0:
                        normal = -normal
                    if kind not in (None, "on_face", "free", "none"):
                        return QVector3D(ctx.world), normal
                    return hit, normal
    if kind not in (None, "on_face", "free", "none"):
        return QVector3D(ctx.world), normal
    return None, None


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
        _flash(viewport, f"💡 Clique no modelo para fixar a luz [{self.light_data.get('name', 'Luz')}]. Esc cancela.")

    def on_deactivate(self, viewport) -> None:
        self.hover_point = None
        _flash(viewport, "")

    def on_hover(self, ctx: ToolContext) -> None:
        self.hover_point = ctx.world
        ctx.viewport.update()

    def on_click(self, ctx: ToolContext) -> None:
        hit, normal = _surface_hit(ctx)
        if hit is None:
            _flash(ctx.viewport, "Clique sobre uma superfície (teto, móvel, parede) para fixar a luz.")
            return
        is_spot = self.light_data.get("kind") == "spot"
        off = 0.03 if is_spot else 0.15
        if normal is not None:
            hit = hit + normal * off
        pos = [hit.x(), hit.y(), hit.z()]
        new_light = dict(self.light_data)
        new_light["pos"] = pos
        new_light["on"] = True

        if is_spot:
            # Aponta para o chão/superfície oposta por padrão se não tiver target
            d = new_light.get("dir", [0.0, 0.0, -1.0])
            new_light["target"] = [pos[0] + d[0] * 1.5, pos[1] + d[1] * 1.5, pos[2] + d[2] * 1.5]

        # Adiciona na cena
        lights = _get_document_lights(ctx.viewport)
        lights.append(new_light)
        _save_document_lights(ctx.viewport, lights)

        _flash(ctx.viewport, f"✅ Luz inserida com sucesso em X:{pos[0]:.2f} Y:{pos[1]:.2f} Z:{pos[2]:.2f}")

        if callable(self.on_placed):
            self.on_placed(new_light)

        # Volta para a ferramenta de seleção padrão se existir
        if hasattr(ctx.viewport, "set_active_tool"):
            app = getattr(ctx.viewport, "app", None)
            if app and hasattr(app, "select_tool"):
                ctx.viewport.set_active_tool(app.select_tool)

    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Escape:
            cb = getattr(self, 'on_placed', None)
            if callable(cb):
                cb(None)
            return True
        return False


class InsertLedStripTool(Tool):
    """Ferramenta interativa de 2 cliques para desenhar fita LED contínua / perfil linear sob armários."""

    name = "Inserir Fita LED"
    shortcut = None
    uses_snap = True
    description = "Clique no ponto inicial e depois no ponto final do perfil de LED."

    def __init__(self, light_data: dict, on_placed=None):
        super().__init__()
        self.light_data = dict(light_data)
        self.on_placed = on_placed
        self.p1: Optional[QVector3D] = None
        self.p2_hover: Optional[QVector3D] = None
        self.normal: Optional[QVector3D] = None

    def on_activate(self, viewport) -> None:
        self.p1 = None
        self.p2_hover = None
        _flash(viewport, "✨ Fita LED (1/2): Clique no PONTO INICIAL da fita (ex: início do armário). Esc cancela.")

    def on_deactivate(self, viewport) -> None:
        self.p1 = None
        self.p2_hover = None
        _flash(viewport, "")

    def on_hover(self, ctx: ToolContext) -> None:
        hit, _n = _surface_hit(ctx)
        self.p2_hover = hit or ctx.world
        ctx.viewport.update()

    def on_click(self, ctx: ToolContext) -> None:
        hit, normal = _surface_hit(ctx)
        if hit is None:
            hit = ctx.world
        if hit is None:
            return

        if self.p1 is None:
            # 1º Clique: Ponto inicial
            self.p1 = QVector3D(hit)
            self.normal = normal
            _flash(ctx.viewport, "✨ Fita LED (2/2): Agora clique no PONTO FINAL da fita LED.")
            ctx.viewport.update()
        else:
            # 2º Clique: Ponto final
            p2 = QVector3D(hit)
            dist = (p2 - self.p1).length()
            if dist < 0.05:
                _flash(ctx.viewport, "⚠️ O comprimento da fita LED é muito curto (mínimo 5 cm). Clique mais distante.")
                return

            mid = (self.p1 + p2) * 0.5
            pos = [mid.x(), mid.y(), mid.z()]

            new_light = dict(self.light_data)
            new_light["kind"] = "led_strip"
            new_light["pos"] = pos
            new_light["p1"] = [self.p1.x(), self.p1.y(), self.p1.z()]
            new_light["p2"] = [p2.x(), p2.y(), p2.z()]
            new_light["length"] = float(dist)
            new_light["on"] = True
            # Direção de emissão (para baixo da superfície se normal existir)
            if self.normal is not None:
                new_light["dir"] = [self.normal.x(), self.normal.y(), self.normal.z()]
            else:
                new_light["dir"] = [0.0, 0.0, -1.0]

            lights = _get_document_lights(ctx.viewport)
            lights.append(new_light)
            _save_document_lights(ctx.viewport, lights)

            _flash(ctx.viewport, f"✅ Fita LED inserida com {dist*1000:.0f}mm ({new_light.get('power', 350):.0f}W)!")

            if callable(self.on_placed):
                self.on_placed(new_light)

            # Restaura ferramenta de seleção
            if hasattr(ctx.viewport, "set_active_tool"):
                app = getattr(ctx.viewport, "app", None)
                if app and hasattr(app, "select_tool"):
                    ctx.viewport.set_active_tool(app.select_tool)

    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Escape:
            cb = getattr(self, 'on_placed', None)
            if callable(cb):
                cb(None)
            return True
        return False


class MoveLightTool(Tool):
    """Ferramenta para mover / reposicionar uma luz no 3D com o mouse."""

    name = "Mover Luz"
    shortcut = None
    uses_snap = True
    description = "Clique na nova superfície ou posição onde a luz deve ser fixada."

    def __init__(self, light_index: int, on_moved=None):
        super().__init__()
        self.light_index = light_index
        self.on_moved = on_moved
        self.hover_point: Optional[QVector3D] = None

    def on_activate(self, viewport) -> None:
        self.hover_point = None
        _flash(viewport, "📍 Clique no teto, móvel, parede ou posição desejada para MOVER a luz. Esc cancela.")

    def on_deactivate(self, viewport) -> None:
        self.hover_point = None
        _flash(viewport, "")

    def on_hover(self, ctx: ToolContext) -> None:
        hit, _n = _surface_hit(ctx)
        self.hover_point = hit or ctx.world
        ctx.viewport.update()

    def on_click(self, ctx: ToolContext) -> None:
        lights = _get_document_lights(ctx.viewport)
        if not (0 <= self.light_index < len(lights)):
            return

        lt = lights[self.light_index]
        kind = lt.get("kind", "point")
        hit, normal = _surface_hit(ctx)
        if hit is None:
            hit = ctx.world
        if hit is None:
            _flash(ctx.viewport, "Clique sobre o modelo ou plano de trabalho para posicionar a luz.")
            return

        off = 0.03 if kind == "spot" else 0.12
        if normal is not None:
            hit = hit + normal * off

        new_pos = [round(hit.x(), 4), round(hit.y(), 4), round(hit.z(), 4)]
        old_pos = lt.get("pos", [0, 0, 0])
        dx = new_pos[0] - old_pos[0]
        dy = new_pos[1] - old_pos[1]
        dz = new_pos[2] - old_pos[2]

        lt["pos"] = new_pos

        # Se tiver target (spot), desloca o target junto com a luminária para manter o ângulo de mira
        if "target" in lt and lt["target"]:
            t = lt["target"]
            lt["target"] = [round(t[0] + dx, 4), round(t[1] + dy, 4), round(t[2] + dz, 4)]

        # Se for fita LED (p1 e p2), desloca ambos os terminais mantendo o comprimento e orientação
        if kind == "led_strip" and "p1" in lt and "p2" in lt:
            p1 = lt["p1"]
            p2 = lt["p2"]
            lt["p1"] = [round(p1[0] + dx, 4), round(p1[1] + dy, 4), round(p1[2] + dz, 4)]
            lt["p2"] = [round(p2[0] + dx, 4), round(p2[1] + dy, 4), round(p2[2] + dz, 4)]

        _save_document_lights(ctx.viewport, lights)
        _flash(ctx.viewport, f"✅ Luz movida com sucesso para X:{new_pos[0]:.2f} Y:{new_pos[1]:.2f} Z:{new_pos[2]:.2f}")

        if callable(self.on_moved):
            self.on_moved()

        if hasattr(ctx.viewport, "set_active_tool"):
            app = getattr(ctx.viewport, "app", None)
            if app and hasattr(app, "select_tool"):
                ctx.viewport.set_active_tool(app.select_tool)

    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Escape:
            cb = getattr(self, 'on_moved', None)
            if callable(cb):
                cb()
            return True

        # Setas Up / Down para ajuste fino de elevação Z (5cm normal, 10cm com Shift)
        if key in (Qt.Key_Up, Qt.Key_Down):
            step = 0.10 if (modifiers & Qt.ShiftModifier) else 0.05
            if key == Qt.Key_Down:
                step = -step
            lights = _get_document_lights(viewport)
            if 0 <= self.light_index < len(lights):
                lt = lights[self.light_index]
                pos = lt.get("pos") or [0, 0, 0]
                pos[2] = round(pos[2] + step, 4)
                lt["pos"] = pos
                if lt.get("kind") == "spot" and "target" in lt and lt["target"]:
                    lt["target"][2] = round(lt["target"][2] + step, 4)
                if lt.get("kind") == "led_strip" and "p1" in lt and "p2" in lt:
                    lt["p1"][2] = round(lt["p1"][2] + step, 4)
                    lt["p2"][2] = round(lt["p2"][2] + step, 4)
                _save_document_lights(viewport, lights)
                _flash(viewport, f"📏 Altura ajustada: Z={pos[2]:.2f}m (Setas ↑/↓)")
                if callable(self.on_moved):
                    self.on_moved()
                viewport.update()
                return True
        return False


class AimLightTool(Tool):
    """Ferramenta para direcionar a mira e ponto focal do Spot com o mouse."""

    name = "Mirar Spot"
    shortcut = None
    uses_snap = True
    description = "Clique no ponto ou superfície onde o Spot deve iluminar."

    def __init__(self, light_index: int, on_aimed=None):
        super().__init__()
        self.light_index = light_index
        self.on_aimed = on_aimed

    def on_activate(self, viewport) -> None:
        _flash(viewport, "🎯 Clique no móvel ou ponto para onde o Spot deve mirar. Esc cancela.")

    def on_deactivate(self, viewport) -> None:
        _flash(viewport, "")

    def on_click(self, ctx: ToolContext) -> None:
        lights = _get_document_lights(ctx.viewport)
        if 0 <= self.light_index < len(lights):
            lt = lights[self.light_index]
            pos = lt.get("pos", [0, 0, 0])
            target, _n = _surface_hit(ctx)
            if target is None:
                target = ctx.world
            if target is None:
                _flash(ctx.viewport, "Clique sobre uma superfície para mirar o spot.")
                return

            t_vec = [target.x(), target.y(), target.z()]
            dir_vec = [target.x() - pos[0], target.y() - pos[1], target.z() - pos[2]]
            dist = math.hypot(*dir_vec)
            if dist > 1e-4:
                lt["target"] = t_vec
                lt["dir"] = [dir_vec[0] / dist, dir_vec[1] / dist, dir_vec[2] / dist]
                _save_document_lights(ctx.viewport, lights)
                _flash(ctx.viewport, "✅ Ponto Focal do Spot atualizado com sucesso!")

        if callable(self.on_aimed):
            self.on_aimed()

        if hasattr(ctx.viewport, "set_active_tool"):
            app = getattr(ctx.viewport, "app", None)
            if app and hasattr(app, "select_tool"):
                ctx.viewport.set_active_tool(app.select_tool)

    def on_key(self, viewport, key, modifiers) -> bool:
        if key == Qt.Key_Escape:
            cb = getattr(self, 'on_aimed', None)
            if callable(cb):
                cb()
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

        h_add2 = QHBoxLayout()
        btn_add_omni = QPushButton("💡 + Luz Omni")
        btn_add_omni.setToolTip("Lâmpada que ilumina em todas as direções (bulbo, pendente, arandela)")
        btn_add_omni.clicked.connect(lambda: self._start_placement("omni"))
        h_add2.addWidget(btn_add_omni)
        btn_add_plafon = QPushButton("⬜ + Plafon")
        btn_add_plafon.setToolTip("Luz geral difusa de teto, mais forte")
        btn_add_plafon.clicked.connect(lambda: self._start_placement("plafon_geral"))
        h_add2.addWidget(btn_add_plafon)
        l_left.addLayout(h_add2)

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
        self.cb_kind.addItems(["Spot Direcionável (Cone de Foco)", "Omni / Ponto (todas as direções)"])
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

        # Altura / Elevação (Z)
        h_elev = QHBoxLayout()
        h_elev.addWidget(QLabel("Altura / Elevação (Z):"))
        self.spin_z = QDoubleSpinBox()
        self.spin_z.setRange(-10.0, 50.0)
        self.spin_z.setSingleStep(0.05)
        self.spin_z.setDecimals(2)
        self.spin_z.setSuffix(" m")
        self.spin_z.valueChanged.connect(self._on_prop_changed)
        h_elev.addWidget(self.spin_z, 1)

        btn_elev_up = QPushButton("▲ +10cm")
        btn_elev_up.clicked.connect(lambda: self.spin_z.setValue(self.spin_z.value() + 0.10))
        h_elev.addWidget(btn_elev_up)

        btn_elev_dn = QPushButton("▼ -10cm")
        btn_elev_dn.clicked.connect(lambda: self.spin_z.setValue(self.spin_z.value() - 0.10))
        h_elev.addWidget(btn_elev_dn)

        l_right.addLayout(h_elev)

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

        pos = lt.get("pos") or [0, 0, 0]
        self.spin_z.blockSignals(True)
        self.spin_z.setValue(float(pos[2]))
        self.spin_z.blockSignals(False)

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

        # Atualiza Z e desloca target/fitas de acordo
        new_z = round(float(self.spin_z.value()), 4)
        pos = lt.get("pos") or [0, 0, 0]
        dz = new_z - pos[2]
        pos[2] = new_z
        lt["pos"] = pos

        if lt.get("kind") == "spot" and "target" in lt and lt["target"]:
            lt["target"][2] = round(lt["target"][2] + dz, 4)
        if lt.get("kind") == "led_strip" and "p1" in lt and "p2" in lt:
            lt["p1"][2] = round(lt["p1"][2] + dz, 4)
            lt["p2"][2] = round(lt["p2"][2] + dz, 4)

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

        if preset.get("kind") == "led_strip" or preset_key == "fita_led":
            tool = InsertLedStripTool(new_light, on_placed=_on_done)
        else:
            tool = InsertLightTool(new_light, on_placed=_on_done)
        self.viewport.set_active_tool(tool)


    def _reposition_current_light(self):
        if not (0 <= self._current_index < len(self._lights)):
            return
        self.hide()

        def _on_done():
            self._reload_lights()
            self.show()

        tool = MoveLightTool(self._current_index, on_moved=_on_done)
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


# ── Mini Popup Flutuante de Edição Rápida da Luz (HUD) ─────────────────────────
class LightQuickPopupHUD(QFrame):
    """Mini painel flutuante de edição rápida ao clicar numa luz no 3D."""

    def __init__(self, viewport, light_index: int, on_changed=None, parent=None):
        super().__init__(parent or viewport)
        self.viewport = viewport
        self.light_index = light_index
        self.on_changed = on_changed
        self.setWindowFlags(Qt.SubWindow | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(30, 30, 35, 235);
                border: 1px solid #0284C7;
                border-radius: 8px;
                color: #FFFFFF;
                font-size: 11px;
            }
            QLabel { background: transparent; color: #FFFFFF; }
            QPushButton {
                background-color: #374151;
                border: 1px solid #4B5563;
                border-radius: 4px;
                padding: 4px 8px;
                color: white;
            }
            QPushButton:hover { background-color: #4B5563; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        lights = _get_document_lights(self.viewport)
        if not (0 <= self.light_index < len(lights)):
            self.close()
            return
        lt = lights[self.light_index]

        kind = lt.get("kind", "point")
        kind_label = "Spot Direcionável" if kind == "spot" else ("Fita LED Linear" if kind == "led_strip" else "Luz Ponto/Omni")

        # Cabeçalho
        h_top = QHBoxLayout()
        lbl_title = QLabel(f"<b>💡 {lt.get('name') or kind_label}</b>")
        h_top.addWidget(lbl_title, 1)

        btn_close = QPushButton("✕")
        btn_close.setFixedSize(20, 20)
        btn_close.clicked.connect(self.close)
        h_top.addWidget(btn_close)
        layout.addLayout(h_top)

        # Ligar / Desligar
        h_on = QHBoxLayout()
        self.btn_toggle = QPushButton("Desligar Luz" if lt.get("on", True) else "Ligar Luz")
        self.btn_toggle.setStyleSheet("background-color: #059669;" if lt.get("on", True) else "background-color: #6B7280;")
        self.btn_toggle.clicked.connect(self._toggle_on)
        h_on.addWidget(self.btn_toggle, 1)
        layout.addLayout(h_on)

        # Potência
        h_pwr = QHBoxLayout()
        h_pwr.addWidget(QLabel("Potência:"))
        self.sp_pwr = QSpinBox()
        self.sp_pwr.setRange(10, 10000)
        self.sp_pwr.setSingleStep(50)
        self.sp_pwr.setSuffix(" W")
        self.sp_pwr.setValue(int(lt.get("power", 400)))
        self.sp_pwr.valueChanged.connect(self._on_prop_change)
        h_pwr.addWidget(self.sp_pwr, 1)
        layout.addLayout(h_pwr)

        # Kelvin
        h_k = QHBoxLayout()
        h_k.addWidget(QLabel("Kelvin:"))
        self.sl_k = QSlider(Qt.Horizontal)
        self.sl_k.setRange(MIN_KELVIN, MAX_KELVIN)
        self.sl_k.setSingleStep(100)
        self.sl_k.setValue(int(lt.get("kelvin", 2700)))
        self.sl_k.valueChanged.connect(self._on_prop_change)
        h_k.addWidget(self.sl_k, 1)
        self.lbl_k_val = QLabel(f"{int(lt.get('kelvin', 2700))}K")
        h_k.addWidget(self.lbl_k_val)
        layout.addLayout(h_k)

        # Se for spot: botão para mirar ponto focal e ângulo
        if kind == "spot":
            h_ang = QHBoxLayout()
            h_ang.addWidget(QLabel("Ângulo Facho:"))
            self.sp_ang = QSpinBox()
            self.sp_ang.setRange(10, 120)
            self.sp_ang.setSuffix("°")
            self.sp_ang.setValue(int(lt.get("angle", 45)))
            self.sp_ang.valueChanged.connect(self._on_prop_change)
            h_ang.addWidget(self.sp_ang, 1)
            layout.addLayout(h_ang)

            btn_aim = QPushButton("🎯 Mirar no Ponto Focal (3D)")
            btn_aim.setStyleSheet("background-color: #0284C7; font-weight: bold;")
            btn_aim.clicked.connect(self._aim_spot)
            layout.addWidget(btn_aim)

        # Elevação / Altura Z
        pos = lt.get("pos") or [0, 0, 0]
        h_z = QHBoxLayout()
        h_z.addWidget(QLabel("Altura (Z):"))
        self.sp_z = QDoubleSpinBox()
        self.sp_z.setRange(-10.0, 50.0)
        self.sp_z.setSingleStep(0.05)
        self.sp_z.setDecimals(2)
        self.sp_z.setSuffix(" m")
        self.sp_z.setValue(float(pos[2]))
        self.sp_z.valueChanged.connect(self._on_z_change)
        h_z.addWidget(self.sp_z, 1)

        btn_z_up = QPushButton("▲")
        btn_z_up.setToolTip("Subir 10cm (+0.10m)")
        btn_z_up.setFixedWidth(24)
        btn_z_up.clicked.connect(lambda: self.sp_z.setValue(self.sp_z.value() + 0.10))
        h_z.addWidget(btn_z_up)

        btn_z_dn = QPushButton("▼")
        btn_z_dn.setToolTip("Descer 10cm (-0.10m)")
        btn_z_dn.setFixedWidth(24)
        btn_z_dn.clicked.connect(lambda: self.sp_z.setValue(self.sp_z.value() - 0.10))
        h_z.addWidget(btn_z_dn)

        layout.addLayout(h_z)

        # Ações inferiores: Mover e Excluir
        h_bot = QHBoxLayout()
        btn_move = QPushButton("📍 Mover Posição")
        btn_move.setStyleSheet("background-color: #2563EB; font-weight: bold;")
        btn_move.setToolTip("Clique na nova posição/superfície onde deseja fixar esta luz.")
        btn_move.clicked.connect(self._move_light)
        h_bot.addWidget(btn_move)

        btn_del = QPushButton("🗑️ Excluir")
        btn_del.setStyleSheet("background-color: #DC2626;")
        btn_del.clicked.connect(self._delete_light)
        h_bot.addWidget(btn_del)
        layout.addLayout(h_bot)

        self.adjustSize()

    def _move_light(self):
        self.close()
        tool = MoveLightTool(self.light_index, on_moved=self.on_changed)
        self.viewport.set_active_tool(tool)


    def _toggle_on(self):
        lights = _get_document_lights(self.viewport)
        if 0 <= self.light_index < len(lights):
            cur = lights[self.light_index].get("on", True)
            lights[self.light_index]["on"] = not cur
            _save_document_lights(self.viewport, lights)
            self.btn_toggle.setText("Desligar Luz" if not cur else "Ligar Luz")
            self.btn_toggle.setStyleSheet("background-color: #059669;" if not cur else "background-color: #6B7280;")
            if callable(self.on_changed):
                self.on_changed()

    def _on_prop_change(self):
        lights = _get_document_lights(self.viewport)
        if 0 <= self.light_index < len(lights):
            lt = lights[self.light_index]
            lt["power"] = float(self.sp_pwr.value())
            k = int(self.sl_k.value())
            lt["kelvin"] = k
            lt["color"] = list(kelvin_to_rgb(k))
            self.lbl_k_val.setText(f"{k}K")
            if hasattr(self, "sp_ang"):
                lt["angle"] = float(self.sp_ang.value())
            _save_document_lights(self.viewport, lights)
            if callable(self.on_changed):
                self.on_changed()

    def _on_z_change(self):
        lights = _get_document_lights(self.viewport)
        if 0 <= self.light_index < len(lights):
            lt = lights[self.light_index]
            new_z = round(float(self.sp_z.value()), 4)
            pos = lt.get("pos") or [0, 0, 0]
            dz = new_z - pos[2]
            pos[2] = new_z
            lt["pos"] = pos

            # Desloca target se for spot
            if lt.get("kind") == "spot" and "target" in lt and lt["target"]:
                lt["target"][2] = round(lt["target"][2] + dz, 4)

            # Desloca terminais se for fita LED
            if lt.get("kind") == "led_strip" and "p1" in lt and "p2" in lt:
                lt["p1"][2] = round(lt["p1"][2] + dz, 4)
                lt["p2"][2] = round(lt["p2"][2] + dz, 4)

            _save_document_lights(self.viewport, lights)
            if callable(self.on_changed):
                self.on_changed()

    def _aim_spot(self):
        self.close()
        tool = AimLightTool(self.light_index, on_aimed=self.on_changed)
        self.viewport.set_active_tool(tool)

    def _delete_light(self):
        lights = _get_document_lights(self.viewport)
        if 0 <= self.light_index < len(lights):
            del lights[self.light_index]
            _save_document_lights(self.viewport, lights)
        if callable(self.on_changed):
            self.on_changed()
        self.close()


# ── Overlay Gráfico e Seleção de Luzes no 3D ──────────────────────────────────
class TrazoMobLightVisualizer:
    """Gerencia a renderização dos cones de spot, alvos de mira, fitas LED e seleção no viewport."""

    _selected_light_idx: Optional[int] = None
    _active_hud: Optional[LightQuickPopupHUD] = None

    @classmethod
    def get_selected_index(cls) -> Optional[int]:
        return cls._selected_light_idx

    @classmethod
    def set_selected_index(cls, idx: Optional[int], viewport=None):
        cls._selected_light_idx = idx
        if viewport is not None:
            viewport.update()

    @classmethod
    def is_point_visible(cls, viewport, world_pt: QVector3D) -> bool:
        """Verifica se o ponto 3D está desobstruído na visão da câmera (sem objetos/móveis à frente)."""
        cam = getattr(viewport, "camera", None)
        eye = cam.eye() if (cam is not None and hasattr(cam, "eye") and callable(cam.eye)) else None
        if eye is None:
            return True

        delta = world_pt - eye
        dist_pt = delta.length()
        if dist_pt < 0.05:
            return True

        dir_ray = delta / dist_pt
        ray_dist_fn = getattr(viewport, "ray_distance", None)
        if callable(ray_dist_fn):
            try:
                t_hit = ray_dist_fn(eye, dir_ray)
                if t_hit is not None and (t_hit < dist_pt - 0.05):
                    # Há um objeto opaco (móvel, parede, porta) à frente
                    return False
            except Exception:
                pass
        return True

    @classmethod
    def pick_light_or_target(cls, viewport, px: float, py: float) -> Optional[tuple[str, int]]:
        """Verifica se o clique pegou a lâmpada/spot, fita LED ou o ponto focal de um spot.
        Retorna ('bulb', idx), ('target', idx), ('led_p1', idx), ('led_p2', idx) ou None.
        Ignora luzes que estejam obstruídas por móveis ou paredes.
        """
        lights = _get_document_lights(viewport)
        best, best_d = None, 35.0

        for i, lt in enumerate(lights):
            kind = lt.get("kind", "point")
            pos = lt.get("pos")

            # 1. Ponto focal / Target de Spot
            if kind == "spot":
                t_pos = lt.get("target")
                if not t_pos and "dir" in lt and pos:
                    d = lt["dir"]
                    t_pos = [pos[0] + d[0] * 1.5, pos[1] + d[1] * 1.5, pos[2] + d[2] * 1.5]
                if t_pos:
                    vec_t = QVector3D(*t_pos)
                    if cls.is_point_visible(viewport, vec_t):
                        p = viewport._world_to_pixel(vec_t)
                        if p is not None:
                            dist = math.hypot(p[0] - px, p[1] - py)
                            if dist <= best_d:
                                best, best_d = ("target", i), dist

            # 2. Extremidades da Fita LED (P1 / P2)
            if kind == "led_strip" and "p1" in lt and "p2" in lt:
                for k_name, pt_vec in (("led_p1", lt["p1"]), ("led_p2", lt["p2"])):
                    vec_p = QVector3D(*pt_vec)
                    if cls.is_point_visible(viewport, vec_p):
                        p = viewport._world_to_pixel(vec_p)
                        if p is not None:
                            dist = math.hypot(p[0] - px, p[1] - py)
                            if dist <= best_d:
                                best, best_d = (k_name, i), dist

            # 3. Bulbo principal / Posição da Luz
            if pos:
                vec_pos = QVector3D(*pos)
                if cls.is_point_visible(viewport, vec_pos):
                    p = viewport._world_to_pixel(vec_pos)
                    if p is not None:
                        dist = math.hypot(p[0] - px, p[1] - py)
                        if dist <= best_d:
                            best, best_d = ("bulb", i), dist

        return best

    @classmethod
    def on_light_clicked(cls, pick_result: Optional[tuple[str, int]], viewport, click_pos=None):
        if pick_result is None:
            cls.set_selected_index(None, viewport)
            if cls._active_hud:
                cls._active_hud.close()
                cls._active_hud = None
            return

        action, idx = pick_result
        cls.set_selected_index(idx, viewport)

        if action == "target":
            # Clicou diretamente no alvo de mira do Spot: ativa a ferramenta de mirar imediatamente
            tool = AimLightTool(idx, on_aimed=lambda: viewport.update())
            viewport.set_active_tool(tool)
            return

        if action in ("bulb", "led_p1", "led_p2"):
            # O Gizmo 3D e o destaque são ativados automaticamente na cena
            viewport.update()


    @classmethod
    def draw_trazomob_lights(cls, viewport, painter) -> None:
        """Desenha a representação 3D das luzes, fita LED e cones/mira de spots."""
        lights = _get_document_lights(viewport)
        if not lights:
            return

        sel_idx = cls._selected_light_idx
        painter.setRenderHint(QPainter.Antialiasing)
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)

        for i, lt in enumerate(lights):
            kind = lt.get("kind", "point")
            is_on = lt.get("on", True)
            color_rgb = lt.get("color", [1.0, 0.9, 0.8])
            tint = QColor.fromRgbF(*color_rgb) if is_on else QColor(140, 140, 140)
            is_selected = (i == sel_idx)

            # ── 1. DESENHO DE FITA LED LINEAR ──
            if kind == "led_strip" and "p1" in lt and "p2" in lt:
                vec_p1 = QVector3D(*lt["p1"])
                vec_p2 = QVector3D(*lt["p2"])
                # Se ambos os pontos estiverem completamente obstruídos, não desenha
                if not (cls.is_point_visible(viewport, vec_p1) or cls.is_point_visible(viewport, vec_p2)):
                    continue

                p1_px = viewport._world_to_pixel(vec_p1)
                p2_px = viewport._world_to_pixel(vec_p2)
                if p1_px is not None and p2_px is not None:
                    pt1 = QPointF(p1_px[0], p1_px[1])
                    pt2 = QPointF(p2_px[0], p2_px[1])

                    # Brilho / Halo exterior
                    glow_col = QColor(tint)
                    glow_col.setAlpha(60 if is_on else 20)
                    painter.setPen(QPen(glow_col, 8.0, Qt.SolidLine, Qt.RoundCap))
                    painter.drawLine(pt1, pt2)

                    # Linha do perfil de alumínio com LED
                    pen_strip = QPen(tint, 3.5, Qt.SolidLine, Qt.RoundCap)
                    painter.setPen(pen_strip)
                    painter.drawLine(pt1, pt2)

                    # Nós nas pontas (P1 e P2)
                    for pt in (pt1, pt2):
                        painter.setPen(QPen(QColor(30, 30, 30), 1.5))
                        painter.setBrush(tint)
                        painter.drawEllipse(pt, 4.0, 4.0)

                    # Se selecionada: anel azul de seleção
                    if is_selected:
                        mid_px = QPointF((pt1.x() + pt2.x()) * 0.5, (pt1.y() + pt2.y()) * 0.5)
                        painter.setPen(QPen(QColor(2, 132, 199), 2.0, Qt.DashLine))
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(mid_px, 12.0, 12.0)
                        painter.setPen(QPen(QColor(240, 240, 240)))
                        l_mm = lt.get("length", 1.0) * 1000.0
                        painter.drawText(mid_px + QPointF(14, 4), f"Fita LED {l_mm:.0f}mm ({int(lt.get('power', 350))}W)")
                continue

            # ── 2. DESENHO DE SPOT COM CONE E PONTO FOCAL ──
            pos = lt.get("pos")
            if not pos:
                continue
            vec_pos = QVector3D(*pos)
            # Luzes obstruídas por móveis ou paredes não são desenhadas na tela
            if not cls.is_point_visible(viewport, vec_pos) and not is_selected:
                continue

            pos_px = viewport._world_to_pixel(vec_pos)
            if pos_px is None:
                continue
            c = QPointF(pos_px[0], pos_px[1])

            if kind == "spot":
                # Alvo de mira (Target)
                t_pos = lt.get("target")
                if not t_pos:
                    d = lt.get("dir", [0.0, 0.0, -1.0])
                    t_pos = [pos[0] + d[0] * 1.5, pos[1] + d[1] * 1.5, pos[2] + d[2] * 1.5]

                t_px = viewport._world_to_pixel(QVector3D(*t_pos))
                if t_px is not None:
                    target_pt = QPointF(t_px[0], t_px[1])

                    # Eixo central de mira (Linha pontilhada)
                    pen_axis = QPen(tint.lighter(120), 1.6, Qt.DashLine)
                    painter.setPen(pen_axis)
                    painter.drawLine(c, target_pt)

                    # Cone lateral do facho de luz (abertura angular)
                    ang_deg = float(lt.get("angle", 45.0))
                    rad = math.radians(ang_deg / 2.0)
                    dist_3d = math.hypot(t_pos[0] - pos[0], t_pos[1] - pos[1], t_pos[2] - pos[2]) or 1.5
                    cone_r = dist_3d * math.tan(rad)

                    # Alvo Focal (Target Gizmo 🎯)
                    painter.setBrush(Qt.NoBrush)
                    pen_target = QPen(QColor(2, 132, 199) if is_selected else tint.lighter(130), 2.0)
                    painter.setPen(pen_target)
                    painter.drawEllipse(target_pt, 8.0, 8.0)
                    painter.drawEllipse(target_pt, 3.0, 3.0)
                    painter.drawLine(QPointF(target_pt.x() - 12, target_pt.y()), QPointF(target_pt.x() + 12, target_pt.y()))
                    painter.drawLine(QPointF(target_pt.x(), target_pt.y() - 12), QPointF(target_pt.x(), target_pt.y() + 12))

                    if is_selected:
                        painter.setPen(QPen(QColor(240, 240, 240)))
                        painter.drawText(target_pt + QPointF(14, 4), "🎯 Ponto Focal (Mirar)")

            # ── 3. BULBO PRINCIPAL ──
            # Se selecionado ou hover, desenha auréola brilhante ao redor
            if is_selected:
                painter.setBrush(QBrush(QColor(0, 212, 255, 50)))
                painter.setPen(QPen(QColor(0, 212, 255, 180), 1.5, Qt.DashLine))
                painter.drawEllipse(c, 24.0, 24.0)

            # Bulbo sólido com contorno nítido
            painter.setPen(QPen(QColor(20, 20, 20), 1.8))
            painter.setBrush(tint)
            painter.drawEllipse(c, 9.0, 9.0)

            # Raios solares / filamentos da lâmpada
            painter.setPen(QPen(tint.darker(140), 1.6))
            for k in range(8):
                a = k * math.pi / 4
                painter.drawLine(
                    QPointF(c.x() + 11.0 * math.cos(a), c.y() + 11.0 * math.sin(a)),
                    QPointF(c.x() + 16.0 * math.cos(a), c.y() + 16.0 * math.sin(a)),
                )

            # Se a luz estiver selecionada: desenha o Gizmo 3D de Eixos (X, Y, Z) e Cota de Altura
            if is_selected and pos:
                p_base = QVector3D(*pos)

                # Eixo Z (Azul - Vertical / Elevação)
                pz_top = p_base + QVector3D(0.0, 0.0, 0.40)
                pz_px = viewport._world_to_pixel(pz_top)
                if pz_px is not None:
                    pt_z = QPointF(pz_px[0], pz_px[1])
                    painter.setPen(QPen(QColor(37, 99, 235), 2.8))  # Azul
                    painter.drawLine(c, pt_z)
                    # Ponta da seta Z
                    painter.setBrush(QColor(37, 99, 235))
                    painter.drawPolygon([pt_z, pt_z + QPointF(-4, 7), pt_z + QPointF(4, 7)])
                    painter.setPen(QPen(QColor(240, 240, 255)))
                    painter.drawText(pt_z + QPointF(6, -4), f"Z (Altura: {pos[2]:.2f}m)")

                # Eixo X (Vermelho)
                px_tip = p_base + QVector3D(0.35, 0.0, 0.0)
                px_px = viewport._world_to_pixel(px_tip)
                if px_px is not None:
                    pt_x = QPointF(px_px[0], px_px[1])
                    painter.setPen(QPen(QColor(220, 38, 38), 2.4))  # Vermelho
                    painter.drawLine(c, pt_x)
                    painter.setBrush(QColor(220, 38, 38))
                    painter.drawEllipse(pt_x, 3.5, 3.5)

                # Eixo Y (Verde)
                py_tip = p_base + QVector3D(0.0, 0.35, 0.0)
                py_px = viewport._world_to_pixel(py_tip)
                if py_px is not None:
                    pt_y = QPointF(py_px[0], py_px[1])
                    painter.setPen(QPen(QColor(16, 185, 129), 2.4))  # Verde
                    painter.drawLine(c, pt_y)
                    painter.setBrush(QColor(16, 185, 129))
                    painter.drawEllipse(pt_y, 3.5, 3.5)

                # Rótulo de identificação da luz
                name_lbl = lt.get("name") or ("Spot" if kind == "spot" else "Luz")
                painter.setPen(QPen(QColor(255, 255, 255)))
                painter.drawText(c + QPointF(20, -14), f"💡 {name_lbl} · {int(lt.get('power', 400))}W")


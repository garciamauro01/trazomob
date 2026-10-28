# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Gerenciador de Réguas de Altura e Linhas-Guia Paramétricas de Parede (WallGuideRulerManager).

Permite:
1. Definir réguas pré-configuradas de marcenaria por ambiente (Cozinha, Quarto, Banheiro, Personalizado);
2. Projetar linhas-guia com cotas nítidas ao longo da face de parede selecionada;
3. Fornecer atração magnética (snap) vertical exata para posicionamento e arraste de móveis.
"""
from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple, NamedTuple

from PySide6.QtCore import QPointF, Qt, QRectF
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QVector3D


class LevelSnapResult(tuple):
    """Resultado do snap a uma linha-guia da régua.
    Compatível com tupla de 2 elementos (z_snapped, name) para código legado,
    mas expondo .z, .name e .diff.
    """
    def __new__(cls, z: float, name: str, diff: float = 0.0):
        obj = super().__new__(cls, (z, name))
        obj.z = z
        obj.name = name
        obj.diff = diff
        return obj

    def __repr__(self) -> str:
        return f"LevelSnapResult(z={self.z}, name='{self.name}', diff={self.diff})"


# Presets de alturas de referência por ambiente (em milímetros)
DEFAULT_RULER_PRESETS: Dict[str, List[Dict[str, any]]] = {
    "Cozinha": [
        {"name": "Rodapé / Base Alvenaria", "z_mm": 150, "color": (234, 179, 8)},       # Amarelo
        {"name": "Bancada Inferior", "z_mm": 900, "color": (16, 185, 129)},             # Esmeralda
        {"name": "Início Armários Aéreos", "z_mm": 1500, "color": (14, 165, 233)},       # Sky
        {"name": "Topo Aéreos / Torres", "z_mm": 2200, "color": (168, 85, 247)},        # Roxo
        {"name": "Pé-Direito Superior", "z_mm": 2600, "color": (239, 68, 68)},           # Vermelho
    ],
    "Quarto": [
        {"name": "Mesa de Cabeceira / Baixo", "z_mm": 450, "color": (234, 179, 8)},
        {"name": "Bancada Estudo / Make", "z_mm": 750, "color": (16, 185, 129)},
        {"name": "Cabideiro Superior", "z_mm": 1900, "color": (14, 165, 233)},
        {"name": "Maleiro Superior", "z_mm": 2200, "color": (168, 85, 247)},
        {"name": "Teto / Sanca", "z_mm": 2600, "color": (239, 68, 68)},
    ],
    "Banheiro": [
        {"name": "Base Suspenso", "z_mm": 300, "color": (234, 179, 8)},
        {"name": "Bancada Pia / Cuba", "z_mm": 850, "color": (16, 185, 129)},
        {"name": "Base Espelheira", "z_mm": 1200, "color": (14, 165, 233)},
        {"name": "Topo Espelheira / Armário", "z_mm": 2000, "color": (168, 85, 247)},
    ],
    "Escritório": [
        {"name": "Gaveteiro / Apoio Baixo", "z_mm": 650, "color": (234, 179, 8)},       # Amarelo
        {"name": "Mesa / Estação de Trabalho", "z_mm": 750, "color": (16, 185, 129)},   # Esmeralda (ergonomia padrão NBR)
        {"name": "Prateleira Baixa / Apoio", "z_mm": 1400, "color": (14, 165, 233)},     # Sky
        {"name": "Armário Alto / Nichos", "z_mm": 1800, "color": (168, 85, 247)},       # Roxo
        {"name": "Teto / Fechamento", "z_mm": 2600, "color": (239, 68, 68)},             # Vermelho
    ],
    "Personalizado": [
        {"name": "Nível 1", "z_mm": 900, "color": (16, 185, 129)},
        {"name": "Nível 2", "z_mm": 1500, "color": (14, 165, 233)},
        {"name": "Nível 3", "z_mm": 2200, "color": (168, 85, 247)},
    ],
}


class WallGuideRulerManager:
    """Gerencia as réguas ativas, configurações de altura e renderização das guias."""

    _instance: Optional[WallGuideRulerManager] = None

    def __init__(self) -> None:
        from .preferences import TrazoMobPreferencesManager
        prefs_mgr = TrazoMobPreferencesManager.get_instance()
        wg_cfg = prefs_mgr.get_wall_guides_config()

        self.presets = dict(DEFAULT_RULER_PRESETS)
        custom_presets = wg_cfg.get("custom_presets")
        if isinstance(custom_presets, dict):
            for k, v in custom_presets.items():
                if isinstance(v, list):
                    self.presets[k] = v

        self.active_preset_name = wg_cfg.get("active_preset", "Cozinha")
        if self.active_preset_name not in self.presets:
            self.active_preset_name = "Cozinha"
        self.visible = bool(wg_cfg.get("visible", True))
        self.show_labels = bool(wg_cfg.get("show_labels", False))
        self.snap_enabled = bool(wg_cfg.get("snap_enabled", True))

    @classmethod
    def get_instance(cls) -> WallGuideRulerManager:
        if cls._instance is None:
            cls._instance = WallGuideRulerManager()
        return cls._instance

    def save_preferences(self) -> None:
        """Salva as configurações atuais de régua nas preferências persistentes do usuário."""
        from .preferences import TrazoMobPreferencesManager
        prefs_mgr = TrazoMobPreferencesManager.get_instance()
        # Preserva apenas presets que diferem do padrão para não inflar o JSON
        custom = {k: v for k, v in self.presets.items() if k not in DEFAULT_RULER_PRESETS or v != DEFAULT_RULER_PRESETS[k]}
        prefs_mgr.save_wall_guides_config(
            active_preset=self.active_preset_name,
            visible=self.visible,
            show_labels=self.show_labels,
            snap_enabled=self.snap_enabled,
            custom_presets=custom,
        )

    def get_active_levels(self) -> List[Dict[str, any]]:
        """Retorna a lista de níveis de altura da régua ativa."""
        return self.presets.get(self.active_preset_name, self.presets.get("Cozinha", []))

    def set_active_preset(self, name: str) -> None:
        if name in self.presets:
            self.active_preset_name = name
            self.save_preferences()

    def create_preset(self, name: str, levels: Optional[List[Dict[str, any]]] = None, base_preset: Optional[str] = None) -> bool:
        """Cria um novo preset de régua com nome único."""
        name = name.strip()
        if not name or name in self.presets:
            return False
        if levels is not None:
            self.presets[name] = [dict(lv) for lv in levels]
        elif base_preset and base_preset in self.presets:
            self.presets[name] = [dict(lv) for lv in self.presets[base_preset]]
        else:
            self.presets[name] = [
                {"name": "Nível 1", "z_mm": 900, "color": (16, 185, 129)},
                {"name": "Nível 2", "z_mm": 1500, "color": (14, 165, 233)},
            ]
        self.active_preset_name = name
        self.save_preferences()
        return True

    def delete_preset(self, name: str) -> bool:
        """Exclui um preset. Não permite excluir se for o único restante."""
        if len(self.presets) <= 1 or name not in self.presets:
            return False
        del self.presets[name]
        if self.active_preset_name == name:
            self.active_preset_name = next(iter(self.presets.keys()))
        self.save_preferences()
        return True

    def rename_preset(self, old_name: str, new_name: str) -> bool:
        """Renomeia um preset existente."""
        new_name = new_name.strip()
        if not new_name or old_name not in self.presets or (new_name != old_name and new_name in self.presets):
            return False
        if new_name == old_name:
            return True
        levels = self.presets.pop(old_name)
        self.presets[new_name] = levels
        if self.active_preset_name == old_name:
            self.active_preset_name = new_name
        self.save_preferences()
        return True

    def update_preset_levels(self, name: str, levels: List[Dict[str, any]]) -> bool:
        """Atualiza a lista completa de níveis de um preset."""
        if name not in self.presets:
            return False
        # Ordena os níveis por altura (z_mm) crescente
        sorted_levels = sorted([dict(lv) for lv in levels], key=lambda x: int(x.get("z_mm", 0)))
        self.presets[name] = sorted_levels
        self.save_preferences()
        return True

    def reset_preset_to_default(self, name: str) -> bool:
        """Restaura um preset de fábrica para sua configuração original."""
        if name in DEFAULT_RULER_PRESETS:
            self.presets[name] = [dict(lv) for lv in DEFAULT_RULER_PRESETS[name]]
            self.save_preferences()
            return True
        return False

    def compute_wall_face_guide_segments(
        self,
        wall_face_info,
        margin_m: float = 0.05,
    ) -> List[Dict[str, any]]:
        """Calcula as coordenadas 3D (p0, p1) de cada linha-guia na face da parede selecionada."""
        if wall_face_info is None or not getattr(wall_face_info, "face", None):
            return []

        pts = getattr(wall_face_info.face, "vertices", [])
        if len(pts) < 2:
            return []

        xf = getattr(wall_face_info.wall_group, "xform", None)
        raw_pts = [xf.map(p) if xf is not None else p for p in pts]

        # Encontra os limites horizontais da face (extremos no plano XY)
        normal = wall_face_info.normal
        n_dir = QVector3D(normal.x(), normal.y(), 0.0).normalized()
        u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()

        projs = [QVector3D.dotProduct(p, u_dir) for p in raw_pts]
        min_u, max_u = min(projs), max(projs)

        # Pontos de referência nas duas extremidades horizontais
        c_pt = wall_face_info.center
        center_u = QVector3D.dotProduct(c_pt, u_dir)
        p_base_left = c_pt + u_dir * (min_u - center_u - margin_m)
        p_base_right = c_pt + u_dir * (max_u - center_u + margin_m)

        # Projeta um leve deslocamento (offset) na direção da normal para desenhar na face da parede
        p_base_left = p_base_left + n_dir * 0.002
        p_base_right = p_base_right + n_dir * 0.002

        levels = self.get_active_levels()
        guides = []
        for lv in levels:
            z_m = float(lv["z_mm"]) / 1000.0
            p0 = QVector3D(p_base_left.x(), p_base_left.y(), z_m)
            p1 = QVector3D(p_base_right.x(), p_base_right.y(), z_m)
            guides.append({
                "name": lv["name"],
                "z_mm": lv["z_mm"],
                "z_m": z_m,
                "color": lv["color"],
                "p0": p0,
                "p1": p1,
            })

        return guides

    def draw_ruler_overlay(self, vp, painter: QPainter, wall_face_info) -> None:
        """Renderiza as linhas-guia com traçado moderno e badges com cotas em milímetros."""
        if not self.visible or wall_face_info is None or not wall_face_info.face:
            return

        # Se a face ou o grupo de parede estiverem ocultos, não desenha as réguas/linhas-guia
        if getattr(wall_face_info.wall_group, "hidden", False) or bool(getattr(wall_face_info.face, "attrs", {}).get("hidden")):
            return

        # Back-face culling para as linhas-guia
        cam = getattr(vp, "camera", None)
        if cam is not None:
            xf = getattr(wall_face_info.wall_group, "xform", None)
            c_world = xf.map(wall_face_info.center) if xf is not None else wall_face_info.center
            if hasattr(cam, "eye") and callable(cam.eye):
                eye_pos = cam.eye()
            elif hasattr(cam, "target") and hasattr(cam, "distance"):
                fwd = cam.forward() if (hasattr(cam, "forward") and callable(cam.forward)) else QVector3D(0, 1, 0)
                eye_pos = cam.target - fwd * cam.distance
            else:
                eye_pos = None

            if eye_pos is not None:
                view_dir = (eye_pos - c_world).normalized()
                world_norm = xf.mapVector(wall_face_info.normal).normalized() if (xf is not None and hasattr(xf, "mapVector")) else wall_face_info.normal
                if QVector3D.dotProduct(world_norm, view_dir) < -0.1:
                    return

        guides = self.compute_wall_face_guide_segments(wall_face_info)
        if not guides:
            return

        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)

            font = QFont()
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            fm = painter.fontMetrics()

            # Filtro de oclusão: verifica se há móveis/módulos à frente da parede
            idx = None
            mask_no_wall = None
            cam_eye = None
            if hasattr(vp, "_pick_index") and hasattr(vp, "_ray_hits") and cam is not None:
                try:
                    idx = vp._pick_index()
                    cam_eye = vp.camera.eye() if (hasattr(vp.camera, "eye") and callable(vp.camera.eye)) else None
                    if idx is not None and getattr(idx, "entities", None) and cam_eye is not None:
                        w_grp = wall_face_info.wall_group
                        import numpy as np
                        mask_no_wall = np.array([(grp is not w_grp) for (face, grp) in idx.entities], dtype=bool) & idx.ent_vis
                        # Se não há outros objetos visíveis na cena além da parede, dispensa o teste
                        if not np.any(mask_no_wall):
                            mask_no_wall = None
                except Exception:
                    mask_no_wall = None

            for g in guides:
                p0, p1 = g["p0"], g["p1"]
                
                # Se temos como testar oclusão contra os armários/móveis na frente:
                sub_segs: List[Tuple[QVector3D, QVector3D]] = []
                if mask_no_wall is not None and cam_eye is not None and idx is not None:
                    # Amostra a linha em pequenos segmentos de ~10cm para desenhar apenas as partes livres
                    import numpy as np
                    total_len = (p1 - p0).length()
                    n_steps = max(2, min(40, int(total_len / 0.10)))
                    sample_pts = [p0 + (p1 - p0) * (float(s) / n_steps) for s in range(n_steps + 1)]
                    
                    # Testa cada subsegmento pelo seu ponto médio
                    for s_i in range(n_steps):
                        sp_a = sample_pts[s_i]
                        sp_b = sample_pts[s_i + 1]
                        mid_pt = (sp_a + sp_b) * 0.5
                        delta = mid_pt - cam_eye
                        dist = delta.length()
                        if dist > 1e-4:
                            dir_ray = delta / dist
                            hits = vp._ray_hits(idx, cam_eye, dir_ray, mask_no_wall)
                            is_occ = (hits is not None) and np.any(np.isfinite(hits) & (hits < dist - 0.015))
                            if not is_occ:
                                sub_segs.append((sp_a, sp_b))
                else:
                    sub_segs.append((p0, p1))

                if not sub_segs:
                    continue

                r, gr, b = g["color"]
                line_color = QColor(r, gr, b, 230)
                pen = QPen(line_color, 1.8, Qt.DashLine)
                painter.setPen(pen)

                first_vis_pt = None

                for sa, sb in sub_segs:
                    seg = vp._clip_segment_front(sa, sb)
                    if seg is None:
                        continue
                    s0, s1 = seg
                    px0 = vp.world_to_pixel(s0)
                    px1 = vp.world_to_pixel(s1)
                    if px0 is None or px1 is None:
                        continue
                    vis = vp._clip_pixel_line(px0, px1, margin=32.0)
                    if vis is None:
                        continue
                    p_start = QPointF(*vis[0])
                    p_end = QPointF(*vis[1])
                    painter.drawLine(p_start, p_end)
                    if first_vis_pt is None:
                        first_vis_pt = p_start if p_start.x() <= p_end.x() else p_end

                # Badge de cota e nome da linha-guia (apenas se configurado para exibir)
                if self.show_labels and first_vis_pt is not None:
                    txt = f"{g['name']} ({g['z_mm']} mm)"
                    tw, th = fm.horizontalAdvance(txt), fm.height()
                    pad_x, pad_y = 6, 3

                    badge_x = first_vis_pt.x() + 10
                    badge_y = first_vis_pt.y() - th - pad_y

                    badge_rect = QRectF(badge_x, badge_y, tw + pad_x * 2, th + pad_y * 2)

                    painter.setPen(QPen(line_color, 1.0))
                    painter.setBrush(QColor(24, 28, 36, 230))
                    painter.drawRoundedRect(badge_rect, 4.0, 4.0)

                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(badge_rect, Qt.AlignCenter, txt)

        finally:
            painter.restore()

    def snap_to_levels(self, current_z: float, threshold_m: float = 0.08) -> Optional[LevelSnapResult]:
        """Retorna LevelSnapResult(z_snapped, guide_name, diff) se o current_z estiver dentro do threshold de atração.
        Compatível com desempacotamento de 2 itens: (snapped_z, guide_name) = res.
        """
        if not self.snap_enabled:
            return None

        best_z = None
        best_name = None
        min_diff = threshold_m

        for lv in self.get_active_levels():
            z_m = float(lv["z_mm"]) / 1000.0
            diff = abs(current_z - z_m)
            if diff <= min_diff:
                min_diff = diff
                best_z = z_m
                best_name = lv["name"]

        if best_z is not None:
            return LevelSnapResult(best_z, best_name, min_diff)
        return None

    def get_slot_between_guides(self, z_world: float) -> Dict[str, any]:
        """Detecta a faixa vertical RIGOROSA entre as duas linhas-guia adjacentes onde o usuário clicou.

        Obedece estritamente às linhas-guia da régua:
        - z_base: cota Z exata da linha-guia inferior do vão (ou piso 0.0 se clicou abaixo da primeira guia)
        - z_top: cota Z exata da linha-guia superior do vão
        - height_mm: altura exata do vão (z_top - z_base) em milímetros
        """
        levels = self.get_active_levels()
        if not levels:
            if z_world <= 1.10:
                z_b, z_t = 0.0, 0.90
            else:
                z_b, z_t = 1.50, 2.20
            h_mm = round((z_t - z_b) * 1000.0)
            return {
                "z_base": z_b,
                "z_top": z_t,
                "height_mm": float(h_mm),
                "category": "inferior" if z_b < 1.0 else "aereo",
                "default_depth_mm": 550.0 if z_b < 1.0 else 350.0,
                "label": f"Vão ({int(z_b * 1000)} a {int(z_t * 1000)} mm)",
                "lower_guide": f"{int(z_b * 1000)}mm",
                "upper_guide": f"{int(z_t * 1000)}mm",
            }

        sorted_levels = sorted(levels, key=lambda x: float(x.get("z_mm", 0)))
        z_vals = [float(lv["z_mm"]) / 1000.0 for lv in sorted_levels]
        names = [lv.get("name", f"{lv.get('z_mm')}mm") for lv in sorted_levels]

        # 1. Clique abaixo da primeira linha-guia: entre o Piso (0.0) e a 1ª Linha-Guia
        if z_world < z_vals[0]:
            z_base = 0.0
            z_top = z_vals[0]
            name_lo = "Piso (0 mm)"
            name_hi = names[0]
        # 2. Clique acima da última linha-guia: entre a última Linha-Guia e o Teto (estimado em +400mm ou 2.60m)
        elif z_world >= z_vals[-1]:
            z_base = z_vals[-1]
            z_top = max(z_base + 0.40, 2.60)
            name_lo = names[-1]
            name_hi = "Teto"
        # 3. Clique entre duas linhas-guia adjacentes: z_base = guia inferior, z_top = guia superior
        else:
            lower_idx = 0
            for i in range(len(z_vals) - 1):
                if z_vals[i] <= z_world < z_vals[i + 1]:
                    lower_idx = i
                    break
            z_base = z_vals[lower_idx]
            z_top = z_vals[lower_idx + 1]
            name_lo = names[lower_idx]
            name_hi = names[lower_idx + 1]

        # Altura exata e rígida entre as duas linhas-guia selecionadas
        h_mm = round((z_top - z_base) * 1000.0)

        # Categoria e profundidade sugerida
        if z_base < 0.20 and z_top <= 1.05:
            cat = "inferior"
            p_mm = 550.0
        elif z_base >= 1.20 and z_top <= 2.30:
            cat = "aereo"
            p_mm = 350.0
        elif z_top > 2.20:
            cat = "fechamento"
            p_mm = 350.0
        elif z_base >= 0.70 and z_top <= 1.60:
            cat = "nicho"
            p_mm = 300.0
        else:
            cat = "aereo" if z_base >= 1.10 else "inferior"
            p_mm = 350.0 if cat == "aereo" else 550.0

        lbl = f"{name_lo} a {name_hi} ({h_mm} mm)"

        return {
            "z_base": z_base,
            "z_top": z_top,
            "height_mm": float(h_mm),
            "category": cat,
            "default_depth_mm": p_mm,
            "label": lbl,
            "lower_guide": name_lo,
            "upper_guide": name_hi,
        }

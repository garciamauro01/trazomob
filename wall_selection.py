# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Gerenciador e visualizador de seleção de faces de parede (WallSelectionManager).

Permite:
1. Detectar o clique numa face de parede no 3D;
2. Destacar visualmente a face selecionada com feedback de cor/highlight translúcido;
3. Fornecer plano, segmento e orientação de referência para encaixe automático de módulos.
"""
from __future__ import annotations

import math
from typing import Optional, Tuple, List, Dict, Any

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF, QVector3D

from core.group import Group
from core.mesh import Face


class WallFaceInfo:
    """Informações geométricas e semânticas da face de parede selecionada."""

    def __init__(
        self,
        wall_group: Group,
        face: Face,
        segment_index: int,
        face_type: str,  # 'interna', 'externa', 'topo', 'base', 'topo_degrau', 'topo_termino'
        normal: QVector3D,
        center: QVector3D,
    ) -> None:
        self.wall_group = wall_group
        self.face = face
        self.segment_index = segment_index
        self.face_type = face_type
        self.normal = normal
        self.center = center


class WallSelectionManager:
    """Singleton/Gerenciador de estado para a face de parede ativa no viewport."""

    _instance: Optional[WallSelectionManager] = None

    def __init__(self, viewport=None, sidebar_panel=None) -> None:
        self.viewport = viewport
        self.sidebar_panel = sidebar_panel
        self.selected_wall_face: Optional[WallFaceInfo] = None
        self._saved_face_color = None
        self._overlay_installed = False

    @classmethod
    def get_instance(cls, viewport=None, sidebar_panel=None) -> WallSelectionManager:
        if cls._instance is None:
            cls._instance = WallSelectionManager(viewport, sidebar_panel)
        else:
            if viewport is not None:
                cls._instance.viewport = viewport
            if sidebar_panel is not None:
                cls._instance.sidebar_panel = sidebar_panel
        return cls._instance

    def install_overlay(self) -> None:
        """Garante registro do callback de overlay na passagem de pintura do viewport."""
        if self._overlay_installed or self.viewport is None:
            return
        if not hasattr(self.viewport, "_ext_overlays") or self.viewport._ext_overlays is None:
            self.viewport._ext_overlays = []
        if self.draw_selection_overlay not in self.viewport._ext_overlays:
            self.viewport._ext_overlays.append(self.draw_selection_overlay)
        self._overlay_installed = True

    def clear_selection(self) -> None:
        """Limpa a face de parede selecionada e restaura sua aparência original."""
        if self.selected_wall_face is not None:
            old_face = self.selected_wall_face.face
            if old_face is not None:
                if self._saved_face_color is not None:
                    old_face.attrs["color"] = self._saved_face_color
                else:
                    old_face.attrs.pop("color", None)
            
            # Notifica a cena para atualizar os chunks de malha no OpenGL
            if self.viewport is not None and hasattr(self.viewport, "scene"):
                try:
                    from core.history import _dirty_group_chunks
                    _dirty_group_chunks(self.viewport.scene)
                except Exception:
                    pass

            self.selected_wall_face = None
            self._saved_face_color = None
            if self.viewport is not None:
                self.viewport.update()

    def set_selected_face(self, wall_group: Group, face: Face, notify_sidebar: bool = True) -> Optional[WallFaceInfo]:
        """Analisa a face e registra como face ativa de parede."""
        if not hasattr(wall_group, "mesh") or not wall_group.mesh or face not in wall_group.mesh.faces:
            return None

        # Se a face ou o grupo estiverem ocultos, não permite seleção
        if getattr(wall_group, "hidden", False) or bool(getattr(face, "attrs", {}).get("hidden")):
            return None

        ext = getattr(wall_group, "ext", {})
        if not isinstance(ext, dict) or ("trazomob_wall" not in ext and "corte_cloud_wall" not in ext):
            return None

        from .migration import migrate_legacy_group
        migrate_legacy_group(wall_group)
        ext = getattr(wall_group, "ext", {})

        # Se já havia outra face selecionada anteriormente, restaura sua cor
        if self.selected_wall_face is not None and self.selected_wall_face.face is not face:
            old_face = self.selected_wall_face.face
            if old_face is not None:
                if self._saved_face_color is not None:
                    old_face.attrs["color"] = self._saved_face_color
                else:
                    old_face.attrs.pop("color", None)
            self._saved_face_color = None

        params = ext.get("trazomob_wall", {})
        face_map: Dict[int, int] = params.get("face_segment_map", {})
        f_idx = wall_group.mesh.faces.index(face)
        seg_idx = face_map.get(f_idx, 0)

        # Salva a cor original da face (se ainda não salva)
        if face is not None:
            self._saved_face_color = face.attrs.get("color")

        # Calcula a normal e o centro da face
        normal = face.normal()
        pts = face.vertices
        if not pts:
            return None

        cx = sum(p.x() for p in pts) / len(pts)
        cy = sum(p.y() for p in pts) / len(pts)
        cz = sum(p.z() for p in pts) / len(pts)
        center = QVector3D(cx, cy, cz)

        # Determina o tipo de face baseado na normal
        if normal.z() > 0.7:
            face_type = "topo"
        elif normal.z() < -0.7:
            face_type = "base"
        else:
            # Face vertical (parede)
            # Verifica com a direção do segmento para saber se é lado interno ou externo
            pontos = params.get("pontos", [])
            alinhamento = params.get("alinhamento", "interno")
            if len(pontos) >= 2 and seg_idx < len(pontos):
                p0 = QVector3D(*pontos[seg_idx])
                nxt_idx = (seg_idx + 1) % len(pontos) if params.get("is_closed") else min(seg_idx + 1, len(pontos) - 1)
                p1 = QVector3D(*pontos[nxt_idx])
                d = (p1 - p0).normalized()
                seg_norm = QVector3D(-d.y(), d.x(), 0.0).normalized()

                dot = QVector3D.dotProduct(normal, seg_norm)
                if alinhamento == "interno":
                    face_type = "interna" if dot < 0 else "externa"
                else:
                    face_type = "externa" if dot > 0 else "interna"
            else:
                face_type = "lateral"

        # Aplica a cor de highlight na face nativa do OpenGL (GPU Z-Buffer automático)
        # Amarelo bem clarinho e discreto (pastel suave)
        if face_type == "interna":
            face.attrs["color"] = (0.98, 0.96, 0.78)   # Amarelo suave/creme bem discreto
        elif face_type == "externa":
            face.attrs["color"] = (0.95, 0.93, 0.82)   # Tom areia/amarelo pálido
        else:
            face.attrs["color"] = (0.96, 0.94, 0.80)

        info = WallFaceInfo(
            wall_group=wall_group,
            face=face,
            segment_index=seg_idx,
            face_type=face_type,
            normal=normal,
            center=center,
        )
        self.selected_wall_face = info

        # Marca os chunks como sujos para o OpenGL atualizar a malha 3D com a nova cor da face
        if self.viewport is not None and hasattr(self.viewport, "scene"):
            try:
                from core.history import _dirty_group_chunks
                _dirty_group_chunks(self.viewport.scene)
            except Exception:
                pass

        # Atualiza metadados na parede
        params["selected_segment"] = seg_idx
        params["selected_face_idx"] = f_idx
        params["selected_face_type"] = face_type

        # Notifica o painel lateral se disponível e solicitado
        if notify_sidebar and self.sidebar_panel is not None:
            try:
                self.sidebar_panel.load_wall(wall_group, segment_index=seg_idx, face_type=face_type)
            except Exception:
                pass

        if self.viewport is not None:
            if hasattr(self.viewport, "flash_status"):
                desc_lado = "Face Interna" if face_type == "interna" else ("Face Externa" if face_type == "externa" else f"Face ({face_type})")
                self.viewport.flash_status(f"🧱 Parede Selecionada: Segmento #{seg_idx + 1} — {desc_lado}")
            if hasattr(self.viewport, "update"):
                self.viewport.update()

        return info

    def handle_click(self, px: float, py: float) -> bool:
        """Tenta selecionar uma face de parede nas coordenadas de tela dadas. Retorna True se atingiu uma parede."""
        if self.viewport is None or not hasattr(self.viewport, "pick_face_any"):
            return False

        face, grp = self.viewport.pick_face_any(px, py)
        if grp is not None and hasattr(grp, "ext") and isinstance(grp.ext, dict) and "trazomob_wall" in grp.ext:
            if face is not None:
                self.set_selected_face(grp, face)
                return True

        return False

    def draw_selection_overlay(self, vp, painter: QPainter) -> None:
        """Renderiza o destaque visual colorido (highlight) sobre a face de parede selecionada."""
        info = self.selected_wall_face
        if info is None or info.face is None:
            return

        # Verifica se a parede ainda existe na cena ou se foi ocultada
        scene = getattr(vp, "scene", None)
        if scene is not None:
            if info.wall_group not in getattr(scene, "groups", []) or getattr(info.wall_group, "hidden", False):
                self.selected_wall_face = None
                return
            if bool(getattr(info.face, "attrs", {}).get("hidden")):
                self.selected_wall_face = None
                return

        pts_3d = getattr(info.face, "vertices", [])
        if not pts_3d:
            return

        # Aplica a transformação do grupo, se houver
        xf = getattr(info.wall_group, "xform", None)
        raw_pts = [xf.map(p) if xf is not None else p for p in pts_3d]

        # ── BACK-FACE CULLING ROBUSTO ──────────────────────────────────────────
        # Se a câmera estiver olhando para as costas da parede (ex: orbitou para o outro lado),
        # a seleção e as linhas-guia NÃO devem ser desenhadas pelo lado oposto!
        cam = getattr(vp, "camera", None)
        if cam is not None:
            # Posição da câmera no mundo
            if hasattr(cam, "eye") and callable(cam.eye):
                eye_pos = cam.eye()
            elif hasattr(cam, "target") and hasattr(cam, "distance"):
                fwd = cam.forward() if (hasattr(cam, "forward") and callable(cam.forward)) else QVector3D(0, 1, 0)
                eye_pos = cam.target - fwd * cam.distance
            else:
                eye_pos = None

            if eye_pos is not None:
                c_world = xf.map(info.center) if xf is not None else info.center
                view_dir = (eye_pos - c_world).normalized()
                # Calcula a normal real dos vértices da face
                if len(raw_pts) >= 3:
                    n_calc = QVector3D.crossProduct(raw_pts[1] - raw_pts[0], raw_pts[2] - raw_pts[0]).normalized()
                else:
                    n_calc = info.normal

                # Se a normal estiver apontando para longe da câmera (dot < 0), a face está de costas
                # Testamos com uma margem de segurança de -0.05
                dot = QVector3D.dotProduct(n_calc, view_dir)
                # Verifica também com a normal original
                dot_orig = QVector3D.dotProduct(info.normal, view_dir)
                # Se ambas estiverem apontando para trás, descarta
                if dot < -0.1 and dot_orig < -0.1:
                    return

        # Triangula a face ou usa as arestas e triângulos projetados no plano da câmera
        from core.triangulate import triangulate
        tris = triangulate(raw_pts, normal=info.normal)
        if not tris and len(raw_pts) >= 3:
            # Fallback para fan trivial
            tris = [(raw_pts[0], raw_pts[i], raw_pts[i + 1]) for i in range(1, len(raw_pts) - 1)]

        mvp = vp.camera.projection_matrix() * vp.camera.view_matrix()
        from PySide6.QtGui import QVector4D

        # Contorno elegante e discreto em amarelo dourado suave
        stroke_color = QColor(217, 160, 40, 200)   # Dourado âmbar suave e refinado
        if info.face_type == "interna":
            stroke_color = QColor(220, 165, 30, 220)  # Amarelo âmbar suave
        elif info.face_type == "externa":
            stroke_color = QColor(190, 150, 45, 200)

        painter.save()
        try:
            painter.setRenderHint(QPainter.Antialiasing, True)
            painter.setRenderHint(QPainter.TextAntialiasing, True)

            # 1. O preenchimento da face agora é renderizado nativamente pelo OpenGL (GPU Z-buffer)
            # via face.attrs['color'], respeitando a oclusão física dos móveis e objetos na frente!
            pass

            # 2. Desenha o contorno da face (arestas do perímetro recortadas na frente da câmera)
            pen = QPen(stroke_color, 2.5)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)

            n_raw = len(raw_pts)
            for i in range(n_raw):
                pa = raw_pts[i]
                pb = raw_pts[(i + 1) % n_raw]
                seg = vp._clip_segment_front(pa, pb)
                if seg is not None:
                    s0, s1 = seg
                    px0 = vp._world_to_pixel(s0)
                    px1 = vp._world_to_pixel(s1)
                    if px0 and px1:
                        # Corta para o retângulo da viewport com margem segura
                        vis = vp._clip_pixel_line(px0, px1, margin=32.0)
                        if vis is not None:
                            painter.drawLine(QPointF(*vis[0]), QPointF(*vis[1]))

            # 3. Desenha um badge informativo no centro visível da face
            c_world = xf.map(info.center) if xf is not None else info.center
            c_screen = vp._world_to_pixel(c_world)
            if c_screen is not None:
                cx, cy = c_screen
                tag_tipo = "Face Interna" if info.face_type == "interna" else ("Face Externa" if info.face_type == "externa" else info.face_type.capitalize())
                tag_text = f"🧱 Parede #{info.segment_index + 1} • {tag_tipo}"

                font = QFont()
                font.setPointSize(9)
                font.setBold(True)
                painter.setFont(font)
                fm = painter.fontMetrics()
                tw = fm.horizontalAdvance(tag_text)
                th = fm.height()

                from PySide6.QtCore import QRectF
                pad_x, pad_y = 7, 4
                badge_rect = QRectF(cx - tw / 2.0 - pad_x, cy - th / 2.0 - pad_y, tw + pad_x * 2, th + pad_y * 2)

                painter.setPen(QPen(stroke_color, 1.2))
                painter.setBrush(QColor(24, 28, 36, 230))
                painter.drawRoundedRect(badge_rect, 4.0, 4.0)

                painter.setPen(QColor(255, 255, 255))
                painter.drawText(badge_rect, Qt.AlignCenter, tag_text)

            # 4. Renderiza as Linhas-Guia da Régua Paramétrica na Face Selecionada
            from .wall_guides import WallGuideRulerManager
            ruler_mgr = WallGuideRulerManager.get_instance()
            ruler_mgr.draw_ruler_overlay(vp, painter, info)

        finally:
            painter.restore()

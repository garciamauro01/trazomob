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

from PySide6.QtCore import QPointF, Qt, QRectF
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
        self.active_placement_slot: Optional[Dict[str, any]] = None

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
        if self.viewport is None:
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
            self.active_placement_slot = None
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

        self.install_overlay()
        if self.viewport is not None:
            if hasattr(self.viewport, "flash_status"):
                desc_lado = "Face Interna" if face_type == "interna" else ("Face Externa" if face_type == "externa" else f"Face ({face_type})")
                self.viewport.flash_status(f"🧱 Parede Selecionada: Segmento #{seg_idx + 1} — {desc_lado}")
            if hasattr(self.viewport, "update"):
                self.viewport.update()

        return info

    def arm_frame_from_click(self, px: float, py: float, target_width_m: Optional[float] = None) -> bool:
        """Arma o frame 3D entre as duas linhas-guia mais próximas onde o usuário clicou na parede."""
        if self.viewport is None or self.selected_wall_face is None:
            return False

        info = self.selected_wall_face
        if info.face is None:
            return False

        # Obtém o raio da câmera para as coordenadas de tela clicadas
        ray_orig, ray_dir = self.viewport._pixel_to_ray(px, py)
        if ray_orig is None or ray_dir is None:
            return False

        # Plano da face da parede: ponto = info.center, normal = info.normal
        # Se houver transformação do grupo, projeta no espaço global
        xf = getattr(info.wall_group, "xform", None)
        c_world = xf.map(info.center) if xf is not None else info.center
        n_world = info.normal

        hit_pt = self.viewport._ray_plane(ray_orig, ray_dir, c_world, n_world)
        if hit_pt is None:
            return False

        # Consulta a faixa vertical entre as linhas-guia da régua ativa
        from .wall_guides import WallGuideRulerManager
        ruler_mgr = WallGuideRulerManager.get_instance()
        slot = ruler_mgr.get_slot_between_guides(hit_pt.z())

        # Vetor normal e tangencial da parede
        n_dir = QVector3D(n_world.x(), n_world.y(), 0.0).normalized()
        u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()

        width_m = float(target_width_m) if target_width_m is not None else 0.80
        depth_m = float(slot.get("default_depth_mm", 550.0)) / 1000.0

        # Posição horizontal central do clique ao longo do eixo u_dir
        # Garante que o frame fique estritamente confinado dentro dos limites físicos da face da parede
        raw_pts = [xf.map(p) if xf is not None else p for p in getattr(info.face, "vertices", [])]
        if raw_pts:
            projs_u = [QVector3D.dotProduct(p, u_dir) for p in raw_pts]
            min_u, max_u = min(projs_u), max(projs_u)
            half_w = width_m * 0.5
            hit_u = QVector3D.dotProduct(hit_pt, u_dir)
            if max_u - min_u > width_m:
                clamped_u = max(min_u + half_w, min(max_u - half_w, hit_u))
            else:
                clamped_u = (min_u + max_u) * 0.5
        else:
            clamped_u = QVector3D.dotProduct(hit_pt, u_dir)

        # Ponto central da base do frame na face da parede
        center_u = QVector3D.dotProduct(c_world, u_dir)
        p_frame_wall_center = c_world + u_dir * (clamped_u - center_u)
        p_frame_wall_center = QVector3D(p_frame_wall_center.x(), p_frame_wall_center.y(), slot["z_base"])

        # Calcula os 8 vértices do paralelepípedo do frame (estilo Promob)
        z_b = slot["z_base"]
        z_t = slot["z_top"]
        half_w = width_m * 0.5

        p_bl_back = p_frame_wall_center - u_dir * half_w
        p_br_back = p_frame_wall_center + u_dir * half_w
        p_tl_back = QVector3D(p_bl_back.x(), p_bl_back.y(), z_t)
        p_tr_back = QVector3D(p_br_back.x(), p_br_back.y(), z_t)

        p_bl_front = p_bl_back + n_dir * depth_m
        p_br_front = p_br_back + n_dir * depth_m
        p_tl_front = p_tl_back + n_dir * depth_m
        p_tr_front = p_tr_back + n_dir * depth_m

        frame_box = {
            "bl_back": p_bl_back,
            "br_back": p_br_back,
            "tl_back": p_tl_back,
            "tr_back": p_tr_back,
            "bl_front": p_bl_front,
            "br_front": p_br_front,
            "tl_front": p_tl_front,
            "tr_front": p_tr_front,
        }

        # Armazena todas as informações do slot armado
        self.active_placement_slot = {
            **slot,
            "width_m": width_m,
            "depth_m": depth_m,
            "center_pt": p_frame_wall_center,
            "u_pos": clamped_u,
            "n_dir": n_dir,
            "u_dir": u_dir,
            "box_vertices": frame_box,
            "wall_face": info,
        }
        self.install_overlay()

    def update_frame_dimensions(self, width_m: float, depth_m: Optional[float] = None) -> None:
        """Atualiza a largura e profundidade do frame para casar exatamente com o módulo selecionado no catálogo.

        Se o frame estiver ancorado na quina de um móvel já inserido (anchor_u), ele expande ou contrai
        mantendo-se RIGOROSAMENTE colado na face lateral daquele móvel, sem deixar vão e sem sobrepor!
        """
        if self.active_placement_slot is None or self.selected_wall_face is None:
            return

        info = self.selected_wall_face
        slot = self.active_placement_slot
        u_dir = slot["u_dir"]
        n_dir = slot["n_dir"]
        if depth_m is None:
            depth_m = slot.get("depth_m", 0.55)

        half_w = width_m * 0.5
        anchor_u = slot.get("anchor_u")

        if anchor_u is not None:
            # Ancorado na borda do móvel anterior: o novo centro é exatamente a quina ancorada + metade da nova largura
            cur_u = anchor_u + half_w
        else:
            cur_u = slot["u_pos"]

        # Confinamento aos limites da parede
        xf = getattr(info.wall_group, "xform", None)
        raw_pts = [xf.map(p) if xf is not None else p for p in getattr(info.face, "vertices", [])]
        if raw_pts:
            projs_u = [QVector3D.dotProduct(p, u_dir) for p in raw_pts]
            min_u, max_u = min(projs_u), max(projs_u)
            if max_u - min_u > width_m:
                cur_u = max(min_u + half_w, min(max_u - half_w, cur_u))
            else:
                cur_u = (min_u + max_u) * 0.5

        c_world = xf.map(info.center) if xf is not None else info.center
        center_u = QVector3D.dotProduct(c_world, u_dir)
        p_frame_wall_center = c_world + u_dir * (cur_u - center_u)
        p_frame_wall_center = QVector3D(p_frame_wall_center.x(), p_frame_wall_center.y(), slot["z_base"])

        z_b = slot["z_base"]
        z_t = slot["z_top"]

        p_bl_back = p_frame_wall_center - u_dir * half_w
        p_br_back = p_frame_wall_center + u_dir * half_w
        p_tl_back = QVector3D(p_bl_back.x(), p_bl_back.y(), z_t)
        p_tr_back = QVector3D(p_br_back.x(), p_br_back.y(), z_t)

        p_bl_front = p_bl_back + n_dir * depth_m
        p_br_front = p_br_back + n_dir * depth_m
        p_tl_front = p_tl_back + n_dir * depth_m
        p_tr_front = p_tr_back + n_dir * depth_m

        slot["width_m"] = width_m
        slot["depth_m"] = depth_m
        slot["u_pos"] = cur_u
        slot["center_pt"] = p_frame_wall_center
        slot["box_vertices"] = {
            "bl_back": p_bl_back,
            "br_back": p_br_back,
            "tl_back": p_tl_back,
            "tr_back": p_tr_back,
            "bl_front": p_bl_front,
            "br_front": p_br_front,
            "tl_front": p_tl_front,
            "tr_front": p_tr_front,
        }

        if self.viewport is not None:
            self.viewport.update()

    def advance_slot_after_placement(self, placed_width_m: float) -> None:
        """Desloca o frame 3D armado para a posição imediatamente contígua ao módulo inserido (estilo Promob)."""
        if self.active_placement_slot is None or self.selected_wall_face is None:
            return

        info = self.selected_wall_face
        slot = self.active_placement_slot
        u_dir = slot["u_dir"]
        n_dir = slot["n_dir"]
        width_m = slot.get("width_m", 0.80)
        depth_m = slot.get("depth_m", 0.55)
        z_b = slot["z_base"]
        z_t = slot["z_top"]

        # Posição U da quina/lateral final do móvel recém-inserido
        # (o centro estava em u_pos e a metade era placed_width_m * 0.5)
        placed_right_edge_u = slot["u_pos"] + (placed_width_m * 0.5)

        # Salva o ponto de ancoragem: o próximo móvel começará EXATAMENTE nesta quina!
        slot["anchor_u"] = placed_right_edge_u

        # O centro do próximo frame fica na quina ancorada + metade da largura do próximo frame
        new_u = placed_right_edge_u + (width_m * 0.5)

        # Limites da parede para evitar que o frame saia para fora
        xf = getattr(info.wall_group, "xform", None)
        raw_pts = [xf.map(p) if xf is not None else p for p in getattr(info.face, "vertices", [])]
        if raw_pts:
            projs_u = [QVector3D.dotProduct(p, u_dir) for p in raw_pts]
            min_u, max_u = min(projs_u), max(projs_u)
            half_w = width_m * 0.5
            if new_u + half_w > max_u:
                new_u = max_u - half_w

        c_world = xf.map(info.center) if xf is not None else info.center
        center_u = QVector3D.dotProduct(c_world, u_dir)
        p_frame_wall_center = c_world + u_dir * (new_u - center_u)
        p_frame_wall_center = QVector3D(p_frame_wall_center.x(), p_frame_wall_center.y(), z_b)

        half_w = width_m * 0.5
        p_bl_back = p_frame_wall_center - u_dir * half_w
        p_br_back = p_frame_wall_center + u_dir * half_w
        p_tl_back = QVector3D(p_bl_back.x(), p_bl_back.y(), z_t)
        p_tr_back = QVector3D(p_br_back.x(), p_br_back.y(), z_t)

        p_bl_front = p_bl_back + n_dir * depth_m
        p_br_front = p_br_back + n_dir * depth_m
        p_tl_front = p_tl_back + n_dir * depth_m
        p_tr_front = p_tr_back + n_dir * depth_m

        slot["u_pos"] = new_u
        slot["center_pt"] = p_frame_wall_center
        slot["box_vertices"] = {
            "bl_back": p_bl_back,
            "br_back": p_br_back,
            "tl_back": p_tl_back,
            "tr_back": p_tr_back,
            "bl_front": p_bl_front,
            "br_front": p_br_front,
            "tl_front": p_tl_front,
            "tr_front": p_tr_front,
        }

        if self.viewport is not None:
            self.viewport.update()

        if hasattr(self.viewport, "flash_status"):
            h_mm = int(slot["height_mm"])
            p_mm = int(slot["default_depth_mm"])
            self.viewport.flash_status(f"🎯 Frame Armado: {slot['label']} — {int(width_m * 1000)}x{p_mm}x{h_mm} mm")

        self.viewport.update()
        return True

    def handle_click(self, px: float, py: float) -> bool:
        """Tenta selecionar uma face de parede ou, se ja selecionada, armar o frame entre linhas-guia."""
        if self.viewport is None or not hasattr(self.viewport, "pick_face_any"):
            return False

        face, grp = self.viewport.pick_face_any(px, py)
        if grp is not None and hasattr(grp, "ext") and isinstance(grp.ext, dict) and "trazomob_wall" in grp.ext:
            if face is not None:
                # Se clicou na mesma face ja selecionada, arma o frame estilo Promob na faixa clicada!
                if self.selected_wall_face is not None and self.selected_wall_face.face is face:
                    self.arm_frame_from_click(px, py)
                    return True
                # Caso contrario, seleciona a nova face e arma o frame na faixa clicada
                self.set_selected_face(grp, face)
                self.arm_frame_from_click(px, py)
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
                    px0 = vp.world_to_pixel(s0)
                    px1 = vp.world_to_pixel(s1)
                    if px0 and px1:
                        # Corta para o retângulo da viewport com margem segura
                        vis = vp._clip_pixel_line(px0, px1, margin=32.0)
                        if vis is not None:
                            painter.drawLine(QPointF(*vis[0]), QPointF(*vis[1]))

            # Badge da parede desativado
            # 4. Renderiza as Linhas-Guia da Régua Paramétrica na Face Selecionada
            from .wall_guides import WallGuideRulerManager
            ruler_mgr = WallGuideRulerManager.get_instance()
            ruler_mgr.draw_ruler_overlay(vp, painter, info)

            # 5. Renderiza o Frame 3D estilo Promob se houver slot armado entre guias
            if self.active_placement_slot is not None:
                self._draw_placement_frame_overlay(vp, painter, self.active_placement_slot)

        finally:
            painter.restore()

    def _draw_placement_frame_overlay(self, vp, painter: QPainter, slot: Dict[str, any]) -> None:
        """Renderiza o volume wireframe translúcido e cotas do frame 3D armado (estilo Promob)."""
        box = slot.get("box_vertices")
        if not box:
            return

        # 12 arestas do paralelepípedo do frame
        edges = [
            # Base inferior
            (box["bl_back"], box["br_back"]),
            (box["br_back"], box["br_front"]),
            (box["br_front"], box["bl_front"]),
            (box["bl_front"], box["bl_back"]),
            # Topo superior
            (box["tl_back"], box["tr_back"]),
            (box["tr_back"], box["tr_front"]),
            (box["tr_front"], box["tl_front"]),
            (box["tl_front"], box["tl_back"]),
            # 4 colunas verticais
            (box["bl_back"], box["tl_back"]),
            (box["br_back"], box["tr_back"]),
            (box["bl_front"], box["tl_front"]),
            (box["br_front"], box["tr_front"]),
        ]

        # Estilo do frame Promob: ciano/azul elétrico tecnológico vibrante com preenchimento suave
        frame_color = QColor(14, 165, 233, 230)      # Sky blue vibrante
        dash_color = QColor(56, 189, 248, 180)       # Azul claro tracejado
        fill_color = QColor(14, 165, 233, 40)        # Preenchimento translúcido

        # 1. Desenha as faces principais projetadas (frente e laterais)
        # Projeta os 4 vértices frontais
        pts_front = [box["bl_front"], box["br_front"], box["tr_front"], box["tl_front"]]
        px_front = [vp.world_to_pixel(p) for p in pts_front]
        if all(p is not None for p in px_front):
            from PySide6.QtGui import QPolygonF
            from PySide6.QtCore import QPointF
            poly = QPolygonF([QPointF(p[0], p[1]) for p in px_front])
            painter.setPen(Qt.NoPen)
            painter.setBrush(fill_color)
            painter.drawPolygon(poly)

        # 2. Desenha as 12 arestas wireframe do frame 3D
        pen_solid = QPen(frame_color, 2.0, Qt.SolidLine)
        pen_solid.setJoinStyle(Qt.RoundJoin)
        pen_dash = QPen(dash_color, 1.5, Qt.DashLine)

        for idx, (p0, p1) in enumerate(edges):
            seg = vp._clip_segment_front(p0, p1)
            if seg is None:
                continue
            s0, s1 = seg
            px0 = vp.world_to_pixel(s0)
            px1 = vp.world_to_pixel(s1)
            if px0 and px1:
                vis = vp._clip_pixel_line(px0, px1, margin=32.0)
                if vis is not None:
                    # Linhas da frente sólidas; linhas de trás tracejadas
                    is_back_edge = (idx == 0 or idx == 4 or idx == 8 or idx == 9)
                    painter.setPen(pen_dash if is_back_edge else pen_solid)
                    painter.drawLine(QPointF(*vis[0]), QPointF(*vis[1]))

        pass

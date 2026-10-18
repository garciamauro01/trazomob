# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Interatividade dinâmica: abertura e fechamento de portas e gavetas."""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtGui import QMatrix4x4, QVector3D

from core.group import Group
from tools.base import Tool, ToolContext


class CabinetInteract:
    """Controlador de abertura e fechamento interativo de portas e gavetas."""

    @staticmethod
    def is_interactive_piece(name: str) -> bool:
        if not name:
            return False
        n = name.lower()
        if "travessa" in n or "contra-frente" in n or "lateral" in n or "rodape" in n or "rodapé" in n or "divisoria" in n or "divisória" in n:
            return False
        return any(k in n for k in ["porta", "gaveta", "frente", "basc"])

    @classmethod
    def get_piece_interaction_type(cls, name: str) -> str | None:
        """Retorna 'drawer', 'door_flap', 'door_right', 'door_left' ou None."""
        if not name:
            return None
        n = name.lower()
        # Não confunde peças da estrutura externa (laterais, travessas, divisórias, rodapé) com portas ou gavetas
        if "travessa" in n or "divisoria" in n or "divisória" in n or "rodape" in n or "rodapé" in n:
            return None
        if "lateral" in n and "gaveta" not in n:
            return None
        if "base" in n and "gaveta" not in n:
            return None
        if "prateleira" in n:
            return None
        if "fundo" in n and "gaveta" not in n:
            return None

        # Identifica peças de gaveta (frente, laterais da caixa, contra-frentes, fundo da gaveta)
        if "gaveta" in n or "cf " in n or "contra-frente" in n or ("frente" in n and "porta" not in n):
            return "drawer"
        if "basc" in n or "basculante" in n:
            return "door_flap"
        if "canto" in n and "porta" in n:
            if "ala x" in n or "plano x" in n:
                return "door_canto_l_x"
            if "ala y" in n or "plano y" in n:
                return "door_canto_l_y"
        if "porta" in n:
            if "dir" in n or "direita" in n:
                return "door_right"
            return "door_left"
        return None

    @classmethod
    def get_drawer_id(cls, name: str) -> str | None:
        """Extrai um identificador da gaveta (ex: 'gaveta_1', 'gaveta_2') ou None se não pertencer a gaveta."""
        import re
        n = name.lower()
        if "gaveta" not in n and "frente" not in n and "contra-frente" not in n and "cf " not in n:
            return None
        m = re.search(r"(?:gaveta|frente)\s*(\d+)", n)
        if m:
            return f"gaveta_{m.group(1)}"
        return "gaveta_1"

    @classmethod
    def toggle_piece(cls, piece: Group, module_group: Group | None = None, scene=None, viewport=None) -> bool:
        """Alterna o estado de abertura (aberto <-> fechado) da peça clicada."""
        if piece is None or not hasattr(piece, "mesh") or not getattr(piece.mesh, "vertices", None):
            return False

        itype = cls.get_piece_interaction_type(getattr(piece, "name", ""))
        if not itype:
            return False

        if getattr(piece, "ext", None) is None:
            piece.ext = {}

        if itype == "drawer":
            # Gaveta: move todas as peças que compõem a mesma gaveta
            drawer_id = cls.get_drawer_id(piece.name)
            siblings = [piece]
            if drawer_id and module_group and hasattr(module_group, "children"):
                for child in module_group.children:
                    if child is not piece and cls.get_drawer_id(getattr(child, "name", "")) == drawer_id:
                        siblings.append(child)

            is_open = piece.ext.get("is_open", False)
            slide_dist = 0.35  # 35 cm para a frente

            for p in siblings:
                if getattr(p, "ext", None) is None:
                    p.ext = {}
                ov = p.ext.get("orig_vertices")
                if not isinstance(ov, list) or len(ov) != len(p.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):
                    p.ext["orig_vertices"] = [QVector3D(v.position) for v in p.mesh.vertices]

                if not is_open:
                    delta = p.ext.get("slide_delta")
                    if delta is None:
                        rot_z = 0.0
                        if module_group and hasattr(module_group, "ext") and "trazomob_module" in module_group.ext:
                            rot_z = float(module_group.ext["trazomob_module"].get("rot_z", 0.0))
                        rad = math.radians(rot_z)
                        delta = QVector3D(slide_dist * math.sin(rad), -slide_dist * math.cos(rad), 0.0)
                        p.ext["slide_delta"] = delta
                    for v in p.mesh.vertices:
                        v.position = v.position + delta
                    p.ext["is_open"] = True
                else:
                    for v, orig in zip(p.mesh.vertices, p.ext["orig_vertices"]):
                        v.position = QVector3D(orig)
                    p.ext["is_open"] = False
                if hasattr(p, "mesh") and p.mesh is not None:
                    p.mesh._mut_serial = getattr(p.mesh, "_mut_serial", 0) + 1

        elif itype == "door_flap":
            # Porta basculante: bascula para cima no topo traseiro da porta
            is_open = piece.ext.get("is_open", False)
            ov = piece.ext.get("orig_vertices")
            if not isinstance(ov, list) or len(ov) != len(piece.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):
                piece.ext["orig_vertices"] = [QVector3D(v.position) for v in piece.mesh.vertices]

            if not is_open:
                ys = [pt.y() for pt in piece.ext["orig_vertices"]]
                zs = [pt.z() for pt in piece.ext["orig_vertices"]]
                py = max(ys)
                pz = max(zs)
                angle_deg = -80.0
                rad = math.radians(angle_deg)
                cos_a, sin_a = math.cos(rad), math.sin(rad)
                for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):
                    dy = orig.y() - py
                    dz = orig.z() - pz
                    ny = py + dy * cos_a - dz * sin_a
                    nz = pz + dy * sin_a + dz * cos_a
                    v.position = QVector3D(orig.x(), ny, nz)
                piece.ext["is_open"] = True
            else:
                for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):
                    v.position = QVector3D(orig)
                piece.ext["is_open"] = False
            if hasattr(piece, "mesh") and piece.mesh is not None:
                piece.mesh._mut_serial = getattr(piece.mesh, "_mut_serial", 0) + 1

        elif itype in ("door_canto_l", "door_canto_l_y", "door_canto_l_x"):
            # Portas de Canto L com abertura divergente para lados opostos
            from core.history import rotation_matrix

            is_open = piece.ext.get("is_open", False)
            ov = piece.ext.get("orig_vertices")
            if not isinstance(ov, list) or len(ov) != len(piece.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):
                piece.ext["orig_vertices"] = [QVector3D(v.position) for v in piece.mesh.vertices]

            if not is_open:
                hp = piece.ext.get("hinge_pivot")
                if not isinstance(hp, QVector3D):
                    xs = [pt.x() for pt in piece.ext["orig_vertices"]]
                    ys = [pt.y() for pt in piece.ext["orig_vertices"]]
                    if itype == "door_canto_l_x":
                        # Porta Ala X (plano XZ): dobradiça na lateral direita externa (max_x, max_y)
                        # Gira +90° abrindo para fora (-Y)
                        px = max(xs)
                        py = max(ys)
                        ang = 90.0
                    else:
                        # Porta Ala Y (plano YZ): dobradiça na lateral frontal externa (min_x, min_y)
                        # Gira -90° abrindo para fora (+X)
                        px = min(xs)
                        py = min(ys)
                        ang = -90.0
                    piece.ext["hinge_pivot"] = QVector3D(px, py, 0.0)
                    piece.ext["door_angle"] = ang

                pivot = piece.ext["hinge_pivot"]
                ang = piece.ext.get("door_angle", 90.0 if itype == "door_canto_l_x" else -90.0)
                m_door = rotation_matrix(pivot, QVector3D(0.0, 0.0, 1.0), ang)

                for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):
                    v.position = m_door.map(orig)
                piece.ext["is_open"] = True
            else:
                for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):
                    v.position = QVector3D(orig)
                piece.ext["is_open"] = False
            if hasattr(piece, "mesh") and piece.mesh is not None:
                piece.mesh._mut_serial = getattr(piece.mesh, "_mut_serial", 0) + 1

        else:
            # Portas de abrir laterais (Z axis pivot com suporte a rotação)
            from core.history import rotation_matrix

            is_open = piece.ext.get("is_open", False)
            ov = piece.ext.get("orig_vertices")
            if not isinstance(ov, list) or len(ov) != len(piece.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):
                piece.ext["orig_vertices"] = [QVector3D(v.position) for v in piece.mesh.vertices]

            if not is_open:
                hp = piece.ext.get("hinge_pivot")
                if not isinstance(hp, QVector3D):
                    xs = [pt.x() for pt in piece.ext["orig_vertices"]]
                    ys = [pt.y() for pt in piece.ext["orig_vertices"]]
                    min_x, max_x = min(xs), max(xs)
                    py = max(ys)

                    if itype == "door_right":
                        px = max_x
                        ang = 90.0
                    else:
                        px = min_x
                        ang = -90.0
                    piece.ext["hinge_pivot"] = QVector3D(px, py, 0.0)
                    piece.ext["door_angle"] = ang

                pivot = piece.ext["hinge_pivot"]
                ang = piece.ext.get("door_angle", 90.0 if itype == "door_right" else -90.0)
                m_door = rotation_matrix(pivot, QVector3D(0.0, 0.0, 1.0), ang)

                for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):
                    v.position = m_door.map(orig)
                piece.ext["is_open"] = True
            else:
                for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):
                    v.position = QVector3D(orig)
                piece.ext["is_open"] = False
            if hasattr(piece, "mesh") and piece.mesh is not None:
                piece.mesh._mut_serial = getattr(piece.mesh, "_mut_serial", 0) + 1

        if scene is not None:
            scene.version += 1
        if viewport is not None:
            if hasattr(viewport, "_group_chunks"):
                viewport._group_chunks.clear()
            if hasattr(viewport, "_inst_chunks"):
                viewport._inst_chunks.clear()
            if hasattr(viewport, "_placement_proxies"):
                viewport._placement_proxies.clear()
            viewport._placements_memo = None
            viewport._pick_block = None
            viewport._pick_memo = None
            viewport._face_any_memo = None
            if hasattr(viewport, "_dirty"):
                viewport._dirty = True
            if hasattr(viewport, "notify_scene_changed"):
                viewport.notify_scene_changed()
            elif hasattr(viewport, "update"):
                viewport.update()

        return True

    @classmethod
    def toggle_all(cls, module_group: Group, scene=None, viewport=None) -> bool:
        """Abre ou fecha todas as portas e gavetas do módulo especificado."""
        if not module_group or not hasattr(module_group, "children"):
            return False

        interactive_children = [
            c for c in module_group.children if cls.is_interactive_piece(getattr(c, "name", ""))
        ]
        if not interactive_children:
            return False

        # Se alguma porta ou gaveta estiver aberta, a intenção de clicar no móvel/toggle_all é FECHAR tudo.
        # Caso tudo esteja fechado, abre tudo.
        any_open = any(bool(getattr(c, "ext", None) and c.ext.get("is_open")) for c in interactive_children)
        target_open = not any_open

        handled_drawers = set()
        for child in interactive_children:
            itype = cls.get_piece_interaction_type(child.name)
            curr_state = bool(getattr(child, "ext", None) and child.ext.get("is_open"))

            if itype == "drawer":
                did = cls.get_drawer_id(child.name)
                if did in handled_drawers:
                    continue
                handled_drawers.add(did)
                if curr_state != target_open:
                    cls.toggle_piece(child, module_group, scene, None)
            else:
                if curr_state != target_open:
                    cls.toggle_piece(child, module_group, scene, None)

        if scene is not None:
            scene.version += 1
        if viewport is not None:
            if hasattr(viewport, "_group_chunks"):
                viewport._group_chunks.clear()
            if hasattr(viewport, "_inst_chunks"):
                viewport._inst_chunks.clear()
            if hasattr(viewport, "_placement_proxies"):
                viewport._placement_proxies.clear()
            viewport._placements_memo = None
            viewport._pick_block = None
            viewport._pick_memo = None
            viewport._face_any_memo = None
            if hasattr(viewport, "_dirty"):
                viewport._dirty = True
            if hasattr(viewport, "notify_scene_changed"):
                viewport.notify_scene_changed()
            elif hasattr(viewport, "update"):
                viewport.update()

        return True


class CabinetInteractTool(Tool):
    """Ferramenta de clique interativo para abrir e fechar portas e gavetas no 3D."""
    name = "Interagir Módulo"
    shortcut = "I"
    description = "Clique nas portas ou gavetas para abrir e fechar no 3D."
    uses_snap = False

    def on_activate(self, viewport) -> None:
        if hasattr(viewport, "setCursor"):
            viewport.setCursor(Qt.PointingHandCursor)

    def on_deactivate(self, viewport) -> None:
        if hasattr(viewport, "unsetCursor"):
            viewport.unsetCursor()

    def on_hover(self, ctx: ToolContext) -> None:
        face, piece = ctx.viewport.pick_face_placement(ctx.screen.x(), ctx.screen.y())
        if piece is not None and CabinetInteract.is_interactive_piece(getattr(piece, "name", "")):
            ctx.viewport.setCursor(Qt.PointingHandCursor)
            return
        group = ctx.viewport.pick_group(ctx.screen.x(), ctx.screen.y())
        if group is not None and hasattr(group, "ext") and isinstance(group.ext, dict):
            if "trazomob_module" in group.ext or "corte_cloud_module" in group.ext or "hellomob_module" in group.ext:
                ctx.viewport.setCursor(Qt.PointingHandCursor)
                return
        ctx.viewport.setCursor(Qt.ArrowCursor)

    def on_click(self, ctx: ToolContext) -> None:
        face, piece = ctx.viewport.pick_face_placement(ctx.screen.x(), ctx.screen.y())
        group = ctx.viewport.pick_group(ctx.screen.x(), ctx.screen.y())

        # Encontra o móvel dono da peça clicada
        module_owner = None
        if piece is not None:
            module_owner = getattr(piece, "owner", None)
            if module_owner is None and hasattr(ctx.viewport, "scene"):
                for g in getattr(ctx.viewport.scene, "groups", []):
                    if hasattr(g, "children"):
                        if piece in g.children or any(getattr(c, "mesh", None) is getattr(piece, "mesh", None) for c in g.children):
                            module_owner = g
                            break
        if module_owner is None:
            module_owner = group

        # Se clicou em uma porta ou gaveta interativa específica:
        if piece is not None and CabinetInteract.is_interactive_piece(getattr(piece, "name", "")):
            real_piece = piece
            if module_owner is not None and hasattr(module_owner, "children"):
                for child in module_owner.children:
                    if child is piece or getattr(child, "mesh", None) is getattr(piece, "mesh", None):
                        real_piece = child
                        break
            CabinetInteract.toggle_piece(real_piece, module_owner, ctx.viewport.scene, ctx.viewport)
            return

        # Se clicou no corpo/carcaça do armário (lateral, rodapé, topo, travessa, etc.):
        if module_owner is not None and hasattr(module_owner, "ext"):
            is_mod = (
                "trazomob_module" in module_owner.ext
                or "corte_cloud_module" in module_owner.ext
                or "hellomob_module" in module_owner.ext
            )
            if is_mod:
                CabinetInteract.toggle_all(module_owner, ctx.viewport.scene, ctx.viewport)
        elif piece is not None and module_owner is not None:
            CabinetInteract.toggle_all(module_owner, ctx.viewport.scene, ctx.viewport)




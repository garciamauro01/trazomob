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

        if "marco" in n or "alisar" in n or "trilho" in n or "batente" in n:

            return False

        if "puxador" in n or "fechadura" in n or "maçaneta" in n or "macaneta" in n or "braçadeira" in n or "bracadeira" in n:

            return False

        return any(k in n for k in ["porta", "gaveta", "frente", "basc", "folha"])



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

        if "puxador" in n or "fechadura" in n or "maçaneta" in n or "macaneta" in n or "braçadeira" in n or "bracadeira" in n:

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

        if "porta" in n or "folha" in n:

            if "correr" in n or "slide" in n:

                return "door_slide"

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

    def set_piece_open_fraction(

        cls,

        piece: Group,

        fraction: float,

        module_group: Group | None = None,

        scene=None,

        viewport=None,

    ) -> bool:

        """Define o percentual contínuo de abertura (0.0 = fechado, 1.0 = 100% aberto) da peça."""

        if piece is None or not hasattr(piece, "mesh") or not getattr(piece.mesh, "vertices", None):

            return False



        itype = cls.get_piece_interaction_type(getattr(piece, "name", ""))

        if not itype:

            return False



        if getattr(piece, "ext", None) is None:

            piece.ext = {}



        frac = max(0.0, min(1.0, float(fraction)))



        # Resgata rotação e transformação do módulo pai

        rot_z = 0.0

        if module_group and hasattr(module_group, "ext") and isinstance(module_group.ext, dict):

            from .schema import module_params

            rot_z = float(module_params(module_group).get("rot_z", 0.0) or 0.0)



        from core.group import _remap_uvws



        def _init_uvws_if_needed(target_piece):

            """Garante que todas as faces com textura possuam 'uvw' ancorado antes de qualquer movimento."""

            if not hasattr(target_piece, "mesh") or not getattr(target_piece.mesh, "faces", None):

                return

            from core.texture import face_uv_axes

            for f in target_piece.mesh.faces:

                tex = f.attrs.get("texture") if f.attrs else None

                if tex and "uvw" not in tex:

                    gu, cu, gv, cv = face_uv_axes(tex, f.normal())

                    tex["uvw"] = [

                        gu.x(), gu.y(), gu.z(), cu,

                        gv.x(), gv.y(), gv.z(), cv

                    ]



        def _restore_orig_uvws(target_piece):

            """Restaura os UVWs originais da peça a partir do backup em ext."""

            orig_uvws = target_piece.ext.get("orig_uvws")

            if not orig_uvws or not hasattr(target_piece, "mesh") or not getattr(target_piece.mesh, "faces", None):

                return

            for f, u_saved in zip(target_piece.mesh.faces, orig_uvws):

                if u_saved is not None and f.attrs and "texture" in f.attrs:

                    f.attrs["texture"]["uvw"] = list(u_saved)



        def _backup_orig_uvws(target_piece):

            """Gera backup dos UVWs se ainda não existir."""

            if "orig_uvws" not in target_piece.ext:

                _init_uvws_if_needed(target_piece)

                target_piece.ext["orig_uvws"] = [

                    list(f.attrs["texture"]["uvw"]) if (f.attrs and f.attrs.get("texture") and "uvw" in f.attrs["texture"]) else None

                    for f in target_piece.mesh.faces

                ]



        if itype == "drawer":

            drawer_id = cls.get_drawer_id(piece.name)

            siblings = [piece]

            if drawer_id and module_group and hasattr(module_group, "children"):

                for child in module_group.children:

                    if child is not piece and cls.get_drawer_id(getattr(child, "name", "")) == drawer_id:

                        siblings.append(child)



            slide_dist = 0.35 * frac

            rad = math.radians(rot_z)

            delta = QVector3D(slide_dist * math.sin(rad), -slide_dist * math.cos(rad), 0.0)



            m_slide = QMatrix4x4()

            m_slide.translate(delta)



            for p in siblings:

                if getattr(p, "ext", None) is None:

                    p.ext = {}

                ov = p.ext.get("orig_vertices")

                if not isinstance(ov, list) or len(ov) != len(p.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):

                    p.ext["orig_vertices"] = [QVector3D(v.position) for v in p.mesh.vertices]



                _backup_orig_uvws(p)

                _restore_orig_uvws(p)



                for v, orig in zip(p.mesh.vertices, p.ext["orig_vertices"]):

                    v.position = orig + delta

                _remap_uvws(p.mesh, m_slide)



                p.ext["is_open"] = (frac > 0.05)

                p.ext["open_fraction"] = frac

                if hasattr(p, "mesh") and p.mesh is not None:

                    p.mesh._mut_serial = getattr(p.mesh, "_mut_serial", 0) + 1



        elif itype == "door_flap":

            ov = piece.ext.get("orig_vertices")

            if not isinstance(ov, list) or len(ov) != len(piece.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):

                piece.ext["orig_vertices"] = [QVector3D(v.position) for v in piece.mesh.vertices]



            from core.history import rotation_matrix

            hp = piece.ext.get("hinge_pivot")

            flap_axis = piece.ext.get("flap_axis")

            if not isinstance(hp, QVector3D) or not isinstance(flap_axis, QVector3D):

                zs = [pt.z() for pt in piece.ext["orig_vertices"]]

                pz = max(zs)

                rad = math.radians(rot_z)

                axis_x = math.cos(rad)

                axis_y = math.sin(rad)

                cand = [pt for pt in piece.ext["orig_vertices"] if abs(pt.z() - pz) < 0.01]

                if cand:

                    px = sum(pt.x() for pt in cand) / len(cand)

                    py = sum(pt.y() for pt in cand) / len(cand)

                else:

                    px, py = piece.ext["orig_vertices"][0].x(), piece.ext["orig_vertices"][0].y()

                hp = QVector3D(px, py, pz)

                flap_axis = QVector3D(axis_x, axis_y, 0.0).normalized()

                piece.ext["hinge_pivot"] = hp

                piece.ext["flap_axis"] = flap_axis



            angle_deg = -80.0 * frac

            m_door = rotation_matrix(piece.ext["hinge_pivot"], piece.ext["flap_axis"], angle_deg)



            _backup_orig_uvws(piece)

            _restore_orig_uvws(piece)



            for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):

                v.position = m_door.map(orig)

            _remap_uvws(piece.mesh, m_door)



            piece.ext["is_open"] = (frac > 0.05)

            piece.ext["open_fraction"] = frac

            if hasattr(piece, "mesh") and piece.mesh is not None:

                piece.mesh._mut_serial = getattr(piece.mesh, "_mut_serial", 0) + 1



        elif itype == "door_slide":

            # Porta de correr (deslizamento horizontal)

            axis = piece.ext.get("slide_axis", QVector3D(1.0, 0.0, 0.0))

            dist = float(piece.ext.get("slide_distance", 0.70))

            delta = axis * (dist * frac)



            siblings = [piece]

            linked = piece.ext.get("linked_pieces", [])

            if linked and module_group and hasattr(module_group, "children"):

                for child in module_group.children:

                    if child is not piece and any(name_k in getattr(child, "name", "") for name_k in linked):

                        siblings.append(child)



            for p in siblings:

                if getattr(p, "ext", None) is None:

                    p.ext = {}

                ov = p.ext.get("orig_vertices")

                if not isinstance(ov, list) or len(ov) != len(p.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):

                    p.ext["orig_vertices"] = [QVector3D(v.position) for v in p.mesh.vertices]



                _backup_orig_uvws(p)

                _restore_orig_uvws(p)



                for v, orig in zip(p.mesh.vertices, p.ext["orig_vertices"]):

                    v.position = orig + delta



                p.ext["is_open"] = (frac > 0.05)

                p.ext["open_fraction"] = frac

                if hasattr(p, "mesh") and p.mesh is not None:

                    p.mesh._mut_serial = getattr(p.mesh, "_mut_serial", 0) + 1



        elif itype in ("door_canto_l", "door_canto_l_y", "door_canto_l_x"):

            from core.history import rotation_matrix

            ov = piece.ext.get("orig_vertices")

            if not isinstance(ov, list) or len(ov) != len(piece.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):

                piece.ext["orig_vertices"] = [QVector3D(v.position) for v in piece.mesh.vertices]



            hp = piece.ext.get("hinge_pivot")

            if not isinstance(hp, QVector3D):

                xs = [pt.x() for pt in piece.ext["orig_vertices"]]

                ys = [pt.y() for pt in piece.ext["orig_vertices"]]

                if itype == "door_canto_l_x":

                    px, py = max(xs), max(ys)

                    ang = 90.0

                else:

                    px, py = min(xs), min(ys)

                    ang = -90.0

                piece.ext["hinge_pivot"] = QVector3D(px, py, 0.0)

                piece.ext["door_angle"] = ang



            total_ang = piece.ext.get("door_angle", 90.0 if itype == "door_canto_l_x" else -90.0)

            ang = total_ang * frac

            m_door = rotation_matrix(piece.ext["hinge_pivot"], QVector3D(0.0, 0.0, 1.0), ang)



            _backup_orig_uvws(piece)

            _restore_orig_uvws(piece)



            for v, orig in zip(piece.mesh.vertices, piece.ext["orig_vertices"]):

                v.position = m_door.map(orig)

            _remap_uvws(piece.mesh, m_door)



            piece.ext["is_open"] = (frac > 0.05)

            piece.ext["open_fraction"] = frac

            if hasattr(piece, "mesh") and piece.mesh is not None:

                piece.mesh._mut_serial = getattr(piece.mesh, "_mut_serial", 0) + 1



        else:

            # Portas de giro laterais

            from core.history import rotation_matrix



            # Coleta peças vinculadas à folha (maçanetas, puxadores, frisos)

            siblings = [piece]

            linked = piece.ext.get("linked_pieces", [])

            if linked and module_group and hasattr(module_group, "children"):

                for child in module_group.children:

                    if child is not piece and any(name_k in getattr(child, "name", "") for name_k in linked):

                        siblings.append(child)



            hp = piece.ext.get("hinge_pivot")

            if not isinstance(hp, QVector3D):

                ov_test = piece.ext.get("orig_vertices")

                if not isinstance(ov_test, list) or len(ov_test) != len(piece.mesh.vertices):

                    ov_test = [QVector3D(v.position) for v in piece.mesh.vertices]

                pts = ov_test

                rad = math.radians(rot_z)

                u_x, u_y = math.cos(rad), math.sin(rad)

                f_x, f_y = math.sin(rad), -math.cos(rad)



                proj_u = [pt.x() * u_x + pt.y() * u_y for pt in pts]

                proj_f = [pt.x() * f_x + pt.y() * f_y for pt in pts]



                meta_side = getattr(piece, "ext", {}).get("trazomob", {}).get("door_side")

                is_right = (itype == "door_right" or meta_side == "right")



                target_u = max(proj_u) if is_right else min(proj_u)

                target_f = max(proj_f)



                best_pt = min(pts, key=lambda pt: (

                    ((pt.x() * u_x + pt.y() * u_y) - target_u) ** 2 +

                    ((pt.x() * f_x + pt.y() * f_y) - target_f) ** 2

                ))



                ang = 95.0 if is_right else -95.0

                piece.ext["hinge_pivot"] = QVector3D(best_pt.x(), best_pt.y(), 0.0)

                piece.ext["door_angle"] = ang



            total_ang = piece.ext.get("door_angle", 95.0 if itype == "door_right" else -95.0)

            ang = total_ang * frac

            m_door = rotation_matrix(piece.ext["hinge_pivot"], QVector3D(0.0, 0.0, 1.0), ang)



            for p in siblings:

                if getattr(p, "ext", None) is None:

                    p.ext = {}

                ov = p.ext.get("orig_vertices")

                if not isinstance(ov, list) or len(ov) != len(p.mesh.vertices) or not all(isinstance(pt, QVector3D) for pt in ov):

                    p.ext["orig_vertices"] = [QVector3D(v.position) for v in p.mesh.vertices]



                _backup_orig_uvws(p)

                _restore_orig_uvws(p)



                for v, orig in zip(p.mesh.vertices, p.ext["orig_vertices"]):

                    v.position = m_door.map(orig)

                _remap_uvws(p.mesh, m_door)



                p.ext["is_open"] = (frac > 0.05)

                p.ext["open_fraction"] = frac

                if hasattr(p, "mesh") and p.mesh is not None:

                    p.mesh._mut_serial = getattr(p.mesh, "_mut_serial", 0) + 1



        return True



    @classmethod

    def toggle_piece(cls, piece: Group, module_group: Group | None = None, scene=None, viewport=None) -> bool:

        """Alterna o estado de abertura (aberto <-> fechado) da peça clicada."""

        if piece is None or not hasattr(piece, "ext"):

            return False

        curr_open = bool(getattr(piece, "ext", None) and piece.ext.get("is_open"))

        target_frac = 0.0 if curr_open else 1.0

        ok = cls.set_piece_open_fraction(piece, target_frac, module_group, scene, viewport)

        if ok:

            cls._notify_scene(scene, viewport)

        return ok



    @classmethod

    def set_module_open_fraction(cls, module_group: Group, fraction: float, scene=None, viewport=None) -> bool:

        """Define o percentual de abertura de todas as portas e gavetas do módulo especificado."""

        if not module_group or not hasattr(module_group, "children"):

            return False



        interactive_children = [

            c for c in module_group.children if cls.is_interactive_piece(getattr(c, "name", ""))

        ]

        if not interactive_children:

            return False



        handled_drawers = set()

        for child in interactive_children:

            itype = cls.get_piece_interaction_type(child.name)

            if itype == "drawer":

                did = cls.get_drawer_id(child.name)

                if did in handled_drawers:

                    continue

                handled_drawers.add(did)

            cls.set_piece_open_fraction(child, fraction, module_group, scene, None)



        cls._notify_scene(scene, viewport)

        return True



    @classmethod

    def set_scene_open_fraction(cls, scene, fraction: float, viewport=None) -> list[dict[str, Any]]:

        """Abertura Dinâmica Global: abre todas as portas e gavetas de todos os armários da cena 3D."""

        if scene is None:

            return []



        for g in getattr(scene, "groups", []):

            if hasattr(g, "ext") and isinstance(g.ext, dict) and any(

                k in g.ext for k in ("trazomob_module", "corte_cloud_module", "hellomob_module")

            ):

                cls.set_module_open_fraction(g, fraction, scene, None)



        cls._notify_scene(scene, viewport)



        from .collision import check_opening_collisions

        return check_opening_collisions(scene)



    @staticmethod

    def _notify_scene(scene, viewport) -> None:

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



        # Se clicou diretamente em uma peça acessória vinculada (puxador, maçaneta, braçadeira),
        # redireciona o clique para a folha de porta ou frente correspondente:
        if piece is not None and module_owner is not None and hasattr(module_owner, "children"):
            p_name = getattr(piece, "name", "")
            for child in module_owner.children:
                if child is not piece and hasattr(child, "ext") and isinstance(child.ext, dict):
                    linked = child.ext.get("linked_pieces", [])
                    if any(k in p_name for k in linked):
                        piece = child
                        break

        # Se clicou em uma porta ou gaveta interativa específica:

        if piece is not None and CabinetInteract.is_interactive_piece(getattr(piece, "name", "")):

            real_piece = piece

            if module_owner is not None and hasattr(module_owner, "children"):

                for child in module_owner.children:

                    if child is piece or getattr(child, "mesh", None) is getattr(piece, "mesh", None):

                        real_piece = child

                        break

                p_name = getattr(real_piece, 'name', '')

                for child in module_owner.children:

                    if child is not real_piece and hasattr(child, 'ext') and isinstance(child.ext, dict):

                        linked = child.ext.get('linked_pieces', [])

                        if any(k in p_name for k in linked):

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








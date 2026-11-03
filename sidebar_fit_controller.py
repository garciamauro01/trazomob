# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Mixin para o painel lateral do TrazoMob especializado no encaixe paramétrico sobre paredes:
bancadas de pedra contínuas, rodapés contínuos em lote e fechamento de vãos residuais (arremates).
"""
from __future__ import annotations

import math
from typing import Any
from PySide6.QtGui import QVector3D
from core.group import Group
from .schema import module_params


class SidebarFitMixin:
    """Encapsula encaixe automático de bancada de pedra, rodapé contínuo e arremate de canto."""

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
        from .module_geometry import get_module_carcass_bounds

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
                tipo = str(module_params(g).get("tipo", "")).lower()
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
            target_layer = getattr(g_tampo, "layer", None)
            if target_layer and hasattr(sc, "layer") and hasattr(sc, "layers"):
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

    def _on_encaixar_rodape_sobre_balcoes(self) -> None:
        """Gera e encaixa perfeitamente uma régua única de rodapé contínuo em lote sobre todos os balcões da parede selecionada."""
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
        from .module_geometry import get_module_carcass_bounds

        _IDS_BALCOES = {
            "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
            "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
        }

        balcoes_na_parede = []
        xf = getattr(sel_wf.wall_group, "xform", None)
        c_wall = xf.map(sel_wf.center) if xf is not None else sel_wf.center
        wall_n = QVector3D.dotProduct(c_wall, n_dir)

        for g in getattr(scene, "groups", []):
            ext = getattr(g, "ext", {})
            if isinstance(ext, dict) and "trazomob_module" in ext:
                tipo = str(module_params(g).get("tipo", "")).lower()
                if tipo in _IDS_BALCOES:
                    b = get_module_carcass_bounds(g) or get_module_bounds(g)
                    if b is not None and b[4] <= 1.10:
                        cur_min_n = get_bounds_min_projection(b, n_dir)
                        if abs(cur_min_n - wall_n) < 0.05:
                            balcoes_na_parede.append((g, b))

        if not balcoes_na_parede:
            self.lbl_status.setText("ℹ️ Nenhum balcão inferior encontrado encostado nesta parede.")
            return

        all_bounds = [b for _, b in balcoes_na_parede]
        min_z = min(b[4] for b in all_bounds)
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

        angle_deg = math.degrees(math.atan2(n_dir.y(), n_dir.x())) + 90.0
        rot_z = (round(angle_deg / 90.0) * 90.0) % 360.0

        from .preferences import TrazoMobPreferencesManager
        prefs = TrazoMobPreferencesManager.get_instance()
        mat_caixa = str(prefs.get_module_default("inferior", "material_caixa", "Branco TX 15mm"))

        params_rodape = {
            "tipo": "peca_travessa_em_pe",
            "largura": round(total_larg_m * 1000.0),
            "altura": 100,
            "profundidade": 15,
            "material": mat_caixa,
            "rot_z": rot_z,
        }

        from .builder import CabinetBuilder
        g_rodape = CabinetBuilder.build_module_group(params_rodape, offset=(0.0, 0.0, 0.0))
        g_rodape.name = f"Rodapé Contínuo {round(total_larg_m * 1000.0)}x100"

        b_r = get_module_carcass_bounds(g_rodape) or get_module_bounds(g_rodape)
        if b_r is not None:
            target_front_n = wall_n + max_depth - 0.05
            cur_min_n = get_bounds_min_projection(b_r, n_dir)
            shift_n = target_front_n - cur_min_n

            cur_center_u = QVector3D.dotProduct(QVector3D((b_r[0] + b_r[1]) * 0.5, (b_r[2] + b_r[3]) * 0.5, 0.0), u_dir)
            shift_u = center_u - cur_center_u
            shift_z = min_z - b_r[4]

            shift = n_dir * shift_n + u_dir * shift_u + QVector3D(0.0, 0.0, shift_z)

            targets = getattr(g_rodape, "children", []) or [g_rodape]
            for t in targets:
                m_sub = getattr(t, "mesh", None)
                if m_sub and hasattr(m_sub, "vertices"):
                    for v in m_sub.vertices:
                        v.position += shift
                    m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
            if "trazomob_module" in g_rodape.ext:
                g_rodape.ext["trazomob_module"]["offset"] = (float(shift.x()), float(shift.y()), float(shift.z()))

        from core.history import SnapshotImport
        def apply_insert_rodape(sc):
            target_layer = getattr(g_rodape, "layer", None)
            if target_layer and hasattr(sc, "layer") and hasattr(sc, "layers"):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            sc.groups.append(g_rodape)
            sc.selection = {g_rodape}

        viewport.history.execute(SnapshotImport(apply_insert_rodape))
        viewport.notify_scene_changed()
        viewport.update()

        larg_cm = int(round(total_larg_m * 100.0))
        self.lbl_status.setText(f"🪵 Rodapé contínuo de {larg_cm} cm encaixado cobrindo {len(balcoes_na_parede)} balcão(ões)!")

    def _on_abrir_elevacao_parede(self) -> None:
        """Abre a janela de Elevação Técnica 2D da parede com todas as cotas milimétricas."""
        vp = self._get_viewport()
        win = self.window()
        from .wall_elevation_dialog import WallElevationDialog
        dlg = WallElevationDialog(viewport=vp, parent=win)
        dlg.exec()

    def _on_fechar_vao_canto(self) -> None:
        """Calcula a sobra residual entre o último módulo e a quina da parede e insere o arremate com sarrafo."""
        viewport = self._get_viewport()
        scene = getattr(viewport, "scene", None) if viewport else None
        if scene is None or viewport is None:
            return

        from .wall_selection import WallSelectionManager
        wall_mgr = WallSelectionManager.get_instance(viewport)
        sel_wf = wall_mgr.selected_wall_face
        if sel_wf is None or sel_wf.face is None:
            self.lbl_status.setText("⚠️ Selecione uma face de parede para calcular o arremate.")
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

        slot = wall_mgr.active_placement_slot
        anchor_u = slot.get("anchor_u") if slot else None

        from .magnetic_drag import get_module_bounds
        from .module_geometry import get_module_carcass_bounds

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
            self.lbl_status.setText("⚠️ Insira ao menos um módulo na parede antes de gerar o arremate.")
            return

        vao_residual_m = max_u - last_u
        vao_mm = round(vao_residual_m * 1000.0)

        if vao_residual_m < 0.015:
            self.lbl_status.setText("ℹ️ Não há vão residual significativo para arremate (< 15mm).")
            return

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

        rot_z = math.degrees(math.atan2(-n_dir.x(), n_dir.y()))

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
            target_layer = getattr(g_arremate, "layer", None)
            if target_layer and hasattr(sc, "layer") and hasattr(sc, "layers"):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            sc.groups.append(g_arremate)
            sc.selection = {g_arremate}

        viewport.history.execute(SnapshotImport(apply_insert_arremate))
        viewport.notify_scene_changed()
        viewport.update()

        if slot is not None:
            slot["anchor_u"] = max_u

        self.lbl_status.setText(f"✅ Régua de arremate inserida com sucesso ({vao_mm} mm) com sarrafo de recuo!")


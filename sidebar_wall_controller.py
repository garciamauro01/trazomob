# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Mixin para o painel lateral do TrazoMob especializado em paredes 3D (SidebarWallMixin)."""
from __future__ import annotations

from typing import Optional
from PySide6.QtGui import QVector3D
from core.group import Group
from .wall_builder import WallBuilderTool, ReplaceWallGroupCommand


class SidebarWallMixin:
    """Mixin que encapsula o modo de parede, carregamento, alteração e ferramenta interativa."""

    def set_wall_mode(self, active: bool = True) -> None:
        """Configura a barra lateral em modo exclusivo de parede ou modo de marcenaria."""
        if hasattr(self, "_ensure_form_built"):
            self._ensure_form_built()
        if active:
            self.focus_panel()
            self.card_paredes.setVisible(True)
            self.scroll_area.setVisible(False)
            self.btn_apply.setVisible(False)
            if hasattr(self, "btn_duplicate"):
                self.btn_duplicate.setVisible(False)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setVisible(False)
            if hasattr(self, "btn_open_dialog"):
                self.btn_open_dialog.setVisible(False)

            self.lbl_title.setText("🧱 Construtor de Paredes")
            self.lbl_status.setText("💡 Clique no 3D para traçar os cantos das paredes. Feche no início para criar o piso.")
            self.card_header.setStyleSheet(
                "QFrame { background-color: palette(base); border: 1px solid palette(highlight); border-radius: 4px; padding: 2px 4px; }"
            )
            self.btn_toggle_wall_tool.setVisible(True)
            self.btn_toggle_wall_tool.setChecked(True)
            self.btn_toggle_wall_tool.setText("⏹️ Finalizar Paredes (Esc)")
            self.btn_apply_wall.setVisible(False)
        else:
            self.card_paredes.setVisible(False)
            self.scroll_area.setVisible(self._selected_module is not None)
            self.btn_apply.setVisible(self._selected_module is not None)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setVisible(self._selected_module is not None)

            self.btn_toggle_wall_tool.setVisible(True)
            self.btn_toggle_wall_tool.setChecked(False)
            self.btn_toggle_wall_tool.setText("✏️ Construir Paredes no 3D")
            self.btn_apply_wall.setVisible(False)
            self._set_editor_enabled(self._selected_module is not None)

    def load_wall(self, wall: Group, segment_index: Optional[int] = None, face_type: Optional[str] = None) -> None:
        """Carrega os parâmetros da parede selecionada no painel de paredes da barra lateral."""
        if hasattr(self, "_ensure_form_built"):
            self._ensure_form_built()
        if hasattr(self, "focus_panel"):
            self.focus_panel()
        from .migration import migrate_legacy_group
        migrate_legacy_group(wall)
        self._updating_ui = True
        try:
            self._selected_wall = wall
            params = wall.ext.get("trazomob_wall", {})
            seg_idx = segment_index if segment_index is not None else params.get("selected_segment")
            alturas = params.get("alturas", [])

            if seg_idx is not None and 0 <= seg_idx < len(alturas):
                current_alt = alturas[seg_idx]
            else:
                current_alt = params.get("altura", 2.6)

            alt_mm = int(round(current_alt * 1000.0))
            esp_mm = int(round(params.get("espessura", 0.15) * 1000.0))
            al = params.get("alinhamento", "interno")

            self.sp_parede_altura.setValue(alt_mm)
            self.sp_parede_esp.setValue(esp_mm)
            idx_al = 0 if al == "interno" else (1 if al == "centro" else 2)
            self.cb_parede_alinhar.setCurrentIndex(idx_al)

            # Armazena segmento ativo
            params["selected_segment"] = seg_idx
            if face_type:
                params["selected_face_type"] = face_type

            # Exibe painel de parede com o botão de atualizar
            self.card_paredes.setVisible(True)
            self.scroll_area.setVisible(False)
            self.btn_apply.setVisible(False)
            if hasattr(self, "btn_delete"):
                self.btn_delete.setVisible(False)

            f_desc = ""
            if face_type:
                f_desc = f" ({'Face Interna' if face_type == 'interna' else ('Face Externa' if face_type == 'externa' else face_type.capitalize())})"
            seg_desc = f" — Seg #{seg_idx + 1}{f_desc}" if seg_idx is not None else ""
            self.lbl_title.setText(f"🧱 {wall.name}{seg_desc}")
            if face_type:
                self.lbl_status.setText(f"🎯 Face ativa para referência e módulos: {f_desc.strip(' ()')}.")
            else:
                self.lbl_status.setText("💡 Altere o pé-direito ou espessura e clique em Atualizar Parede.")
            self.card_header.setStyleSheet(
                "QFrame { background-color: palette(base); border: 1px solid palette(highlight); border-radius: 4px; padding: 2px 4px; }"
            )
            self.btn_toggle_wall_tool.setVisible(False)
            self.btn_apply_wall.setVisible(True)
        finally:
            self._updating_ui = False

    def _apply_wall_changes(self) -> None:
        """Reconstrói a parede selecionada com as novas medidas configuradas na barra lateral."""
        if self._selected_wall is None:
            return

        viewport = self._get_viewport()
        scene = self._get_scene()
        if viewport is None or scene is None:
            return

        params = self._selected_wall.ext.get("trazomob_wall", {})
        raw_pts = params.get("pontos", [])
        if not raw_pts:
            return

        pts = [QVector3D(p[0], p[1], p[2]) for p in raw_pts]
        is_closed = params.get("is_closed", False)
        n_segs = len(pts) if is_closed else max(0, len(pts) - 1)

        alt_m = float(self.sp_parede_altura.value()) / 1000.0
        esp_m = float(self.sp_parede_esp.value()) / 1000.0
        idx_al = self.cb_parede_alinhar.currentIndex()
        alinhamento = "interno" if idx_al == 0 else ("centro" if idx_al == 1 else "externo")

        # Verifica se altera todas ou somente a parede selecionada
        apply_all = self.chk_parede_todas.isChecked()
        selected_seg = params.get("selected_segment")

        if apply_all or selected_seg is None or not (0 <= selected_seg < n_segs):
            alturas_to_apply: float | list[float] = alt_m
        else:
            old_alturas = params.get("alturas", [])
            if len(old_alturas) < n_segs:
                def_h = params.get("altura", 2.6)
                old_alturas = [def_h] * n_segs
            else:
                old_alturas = list(old_alturas)
            old_alturas[selected_seg] = alt_m
            alturas_to_apply = old_alturas

        new_grp = WallBuilderTool.build_chain_group(
            scene=scene,
            pts=pts,
            is_closed=is_closed,
            altura_m=alturas_to_apply,
            espessura_m=esp_m,
            alinhamento=alinhamento,
            name_override=self._selected_wall.name,
            segment_index=selected_seg,
        )

        cmd = ReplaceWallGroupCommand(self._selected_wall, new_grp)
        viewport.history.execute(cmd)
        self._selected_wall = new_grp
        scene.selection = {new_grp}
        viewport.update()

        alvo_txt = "Todas as paredes" if apply_all else f"Parede #{selected_seg + 1}"
        self.lbl_status.setText(f"✅ {alvo_txt} atualizada: {alt_m:.2f}m x {int(esp_m*1000)}mm.")

    def _toggle_wall_builder(self) -> None:
        """Ativa ou desativa a ferramenta interativa de Construtor de Paredes no Viewport."""
        viewport = self._get_viewport()
        if viewport is None:
            return

        is_checked = self.btn_toggle_wall_tool.isChecked()
        if not is_checked:
            if isinstance(getattr(viewport, "active_tool", None), WallBuilderTool):
                viewport.set_active_tool(None)
            self.set_wall_mode(False)
            return

        alt_m = float(self.sp_parede_altura.value()) / 1000.0
        esp_m = float(self.sp_parede_esp.value()) / 1000.0
        idx_al = self.cb_parede_alinhar.currentIndex()
        alinhamento = "interno" if idx_al == 0 else ("centro" if idx_al == 1 else "externo")

        def _on_wall_created(grp):
            self.lbl_status.setText(f"🧱 Parede adicionada: {grp.name}. Continue clicando ou feche no ponto inicial.")

        def _on_wall_deactivated():
            self.set_wall_mode(False)

        wall_tool = WallBuilderTool(
            altura_m=alt_m,
            espessura_m=esp_m,
            alinhamento=alinhamento,
            on_wall_added=_on_wall_created,
            on_deactivated=_on_wall_deactivated,
        )

        # Atualiza parâmetros se os spinboxes mudarem enquanto a ferramenta estiver ativa
        def _update_live_params():
            if isinstance(getattr(viewport, "active_tool", None), WallBuilderTool):
                a = float(self.sp_parede_altura.value()) / 1000.0
                e = float(self.sp_parede_esp.value()) / 1000.0
                i = self.cb_parede_alinhar.currentIndex()
                al = "interno" if i == 0 else ("centro" if i == 1 else "externo")
                viewport.active_tool.set_params(a, e, al)
                viewport.update()

        self.sp_parede_altura.valueChanged.connect(_update_live_params)
        self.sp_parede_esp.valueChanged.connect(_update_live_params)
        self.cb_parede_alinhar.currentIndexChanged.connect(_update_live_params)

        self.set_wall_mode(True)
        viewport.set_active_tool(wall_tool)

    def _toggle_walls_floor_lock(self, checked: bool = True) -> None:
        """Alterna a trava anti-movimento para paredes e pisos da cena."""
        scene = self._get_scene()
        vp = self._get_viewport()
        is_locked = bool(checked)

        if is_locked:
            self.btn_lock_walls_floor.setText("🔒 Trava de Posição: ATIVA")
            if vp and hasattr(vp, "flash_status"):
                vp.flash_status("🔒 Posição de Paredes e Piso travada (Snaps e Cotas 100% ativos).")
        else:
            self.btn_lock_walls_floor.setText("🔓 Trava de Posição: DESATIVADA")
            if vp and hasattr(vp, "flash_status"):
                vp.flash_status("🔓 Posição de Paredes e Piso liberada para movimentação.")

        if scene and hasattr(scene, "groups"):
            for g in scene.groups:
                ext = getattr(g, "ext", None)
                if not isinstance(ext, dict):
                    continue
                if "trazomob_wall" in ext or "trazomob_floor" in ext or getattr(g, "layer", "") in ("Parede", "Piso"):
                    ext["motion_locked"] = is_locked
                    g.motion_locked = is_locked
                    if "trazomob_wall" in ext and isinstance(ext["trazomob_wall"], dict):
                        ext["trazomob_wall"]["motion_locked"] = is_locked

        if vp:
            vp.update()

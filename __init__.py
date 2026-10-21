# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""TrazoMob plugin for IngeTrazo — componentes dinâmicos de marcenaria e plano de corte.

Fornece:
1. Módulos Paramétricos Dinâmicos (estilo TrazoMob):
   - Balcões inferiores, gaveteiros, armários aéreos e nichos;
   - Seleção e edição dinâmica em tempo real (redimensionar sem deformar chapas);
   - Ajustes dimensionais rápidos (+/- 50mm, +/- 100mm);
2. Extração inteligente de chapas (comprimento, largura, espessura, fitas e veio);
3. Envio direto para o TrazoMob (cópia com Ctrl+V, CSV e JSON);
4. Interatividade dinâmica: abrir/fechar portas e gavetas com clique no 3D.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar

from core.group import Group
from tools.base import Tool

from .builder import CabinetBuilder, _make_board_mesh, create_board_group, RotateTrazoMobModuleCommand
from .catalog import MODULE_CATALOG
from .dialog import TrazoMobDialog
from .export import export_trazomob_csv, export_trazomob_json, format_trazomob_text
from .icons import (
    get_module_thumbnail,
    make_cabinet_icon,
    make_trazomob_icon,
    make_cut_plan_icon,
    make_cutlist_icon,
    make_interact_icon,
    make_rotate_ccw_icon,
    make_rotate_cw_icon,
    make_perfil_diagram_pixmap,
    make_style_palette_icon,
    make_wall_icon,
    make_ruler_icon,
    make_render_icon,
    make_paint_icon,
    make_emoji_icon,
    make_light_icon,
)

from .cut_plan_viewer import CutPlanViewerDialog
from .interact import (
    CabinetInteract,
    CabinetInteractTool as _CabinetInteractToolImpl,
)
from .wall_builder import WallBuilderTool
from .parts import _get_entity_bbox, extract_parts, group_similar_parts
from .sidebar import TrazoMobSidebarPanel


class TrazoMobTool(Tool):
    """Ferramenta do menu Extensões para abrir o TrazoMob."""
    name = "TrazoMob"
    shortcut = None
    description = "Biblioteca de módulos paramétricos de marcenaria e gerador de corte para TrazoMob."
    uses_snap = False

    def on_activate(self, viewport) -> None:
        win = viewport.window() if viewport else None
        dlg = getattr(win, "_trazomob_dialog", None)
        if dlg is None or not dlg.isVisible():
            dlg = TrazoMobDialog(viewport, parent=win)
            if win is not None:
                win._trazomob_dialog = dlg
            dlg.show()
        else:
            dlg.raise_()
            dlg.activateWindow()

    def on_deactivate(self, viewport) -> None:
        pass



class CabinetInteractTool(_CabinetInteractToolImpl):
    """Ferramenta de clique interativo para abrir e fechar portas e gavetas no 3D."""
    pass


def setup(app) -> None:
    """Inicializa o plugin TrazoMob registrando barra lateral, toolbar e menus de contexto."""
    # Instala os interceptadores em tempo de execução (desacoplamento total do core do IngeTrazo)
    from .hooks import apply_runtime_hooks
    apply_runtime_hooks()

    main_window = getattr(app, "window", None)
    viewport = getattr(app, "viewport", None)

    # Instala o manipulador de Aderência Magnética e Arraste Direto no Viewport (100% contido no plugin)
    if viewport is not None:
        from .magnetic_drag import MagneticModuleDragFilter
        drag_filter = MagneticModuleDragFilter(viewport, parent=viewport)
        viewport.installEventFilter(drag_filter)
        setattr(viewport, "_trazomob_drag_filter", drag_filter)

    # 1. Painel de encaixe da barra lateral (Side Tray Dock)
    sidebar_panel = TrazoMobSidebarPanel(app)
    sidebar_dock = None
    if hasattr(app, "add_panel"):
        sidebar_dock = app.add_panel("TrazoMob", sidebar_panel)
    elif main_window is not None and hasattr(main_window, "_register_extension_dock"):
        from PySide6.QtWidgets import QDockWidget
        sidebar_dock = QDockWidget("TrazoMob", main_window)
        sidebar_dock.setObjectName("extension_trazomob")
        sidebar_dock.setWidget(sidebar_panel)
        main_window._register_extension_dock(sidebar_dock)
    elif main_window is not None and hasattr(main_window, "addDockWidget"):
        from PySide6.QtWidgets import QDockWidget
        sidebar_dock = QDockWidget("TrazoMob", main_window)
        sidebar_dock.setObjectName("extension_trazomob")
        sidebar_dock.setWidget(sidebar_panel)
        main_window.addDockWidget(Qt.RightDockWidgetArea, sidebar_dock)

    if sidebar_dock is not None:
        sidebar_panel.set_dock(sidebar_dock)

    # Inicializa o gerenciador de seleção de faces de paredes (WallSelectionManager)
    from .wall_selection import WallSelectionManager
    wall_mgr = WallSelectionManager.get_instance(viewport, sidebar_panel)
    wall_mgr.install_overlay()

    # Auto-Migração e Compatibilidade Retroativa (Backward-Compatibility)
    # Executa apenas UMA vez após carregar a cena, nunca no sinal recorrente sceneVersionChanged
    from .migration import migrate_scene_trazomob_entities
    if viewport is not None and hasattr(viewport, "scene"):
        QTimer.singleShot(250, lambda: migrate_scene_trazomob_entities(viewport.scene, viewport=viewport))

    # Inicializa o visualizador gráfico sutil de luzes (cones de spot e fitas LED)
    if hasattr(app, "add_overlay"):
        from .light_tools import TrazoMobLightVisualizer
        app.add_overlay(lambda vp, painter: TrazoMobLightVisualizer.draw_trazomob_lights(vp, painter))

    if hasattr(app, "add_menu_action") and sidebar_dock is not None:
        app.add_menu_action(
            "Painel Lateral do TrazoMob",
            sidebar_panel.focus_panel,
            tip="Abre o editor de módulos dinâmicos na barra lateral.",
        )

    # 2. Cria barra de ferramentas na interface principal
    if main_window is not None and hasattr(main_window, "addToolBar"):
        from PySide6.QtWidgets import QWidget
        parent_widget = main_window if isinstance(main_window, QWidget) else None
        tb = QToolBar("TrazoMob", parent_widget)
        tb.setObjectName("toolbar_trazomob")
        tb.setWindowTitle("TrazoMob")
        tb.setMovable(True)
        tb.setFloatable(True)
        tb.setIconSize(QSize(24, 24))
        tb.setToolButtonStyle(Qt.ToolButtonIconOnly)

        act_main = QAction(make_trazomob_icon(), "TrazoMob", main_window)
        act_main.setStatusTip("Abrir biblioteca de marcenaria e plano de corte do TrazoMob")
        act_main.setToolTip("TrazoMob — Marcenaria Inteligente")
        act_main.triggered.connect(lambda: TrazoMobTool().on_activate(viewport))
        tb.addAction(act_main)

        act_side = QAction(make_cabinet_icon(), "Editor Lateral", main_window)
        act_side.setStatusTip("Abrir e focar o editor do TrazoMob na barra lateral")
        act_side.setToolTip("Editor na Barra Lateral (TrazoMob)")
        act_side.triggered.connect(sidebar_panel.focus_panel)
        tb.addAction(act_side)

        # Botão direto para Construir Paredes (Design de Interiores)
        act_wall = QAction(make_wall_icon(), "Construir Paredes", main_window)
        act_wall.setStatusTip("Construir paredes contínuas no 3D com pé-direito e espessura automáticos (Atalho: W)")
        act_wall.setToolTip("🧱 Construir Paredes (Design de Interiores) — Atalho: W")

        def _activate_wall_tool():
            if viewport is not None and hasattr(viewport, "set_active_tool"):
                alt_m = float(getattr(sidebar_panel, "sp_parede_altura", None).value()) / 1000.0 if hasattr(sidebar_panel, "sp_parede_altura") else 2.60
                esp_m = float(getattr(sidebar_panel, "sp_parede_esp", None).value()) / 1000.0 if hasattr(sidebar_panel, "sp_parede_esp") else 0.15
                idx_al = getattr(sidebar_panel, "cb_parede_alinhar", None).currentIndex() if hasattr(sidebar_panel, "cb_parede_alinhar") else 0
                alinhamento = "interno" if idx_al == 0 else ("centro" if idx_al == 1 else "externo")

                def _on_wall_created(grp):
                    sidebar_panel.lbl_status.setText(f"🧱 Parede adicionada: {grp.name}. Continue clicando ou feche no ponto inicial.")

                def _on_wall_deactivated():
                    sidebar_panel.set_wall_mode(False)

                tool = WallBuilderTool(
                    altura_m=alt_m,
                    espessura_m=esp_m,
                    alinhamento=alinhamento,
                    on_wall_added=_on_wall_created,
                    on_deactivated=_on_wall_deactivated,
                )

                # Coloca a barra lateral no modo exclusivo de paredes (focada e limpa)
                sidebar_panel.set_wall_mode(True)
                viewport.set_active_tool(tool)
                if hasattr(viewport, "flash_status"):
                    viewport.flash_status(f"🧱 Construtor de Paredes: {alt_m:.2f}m x {esp_m*100:.0f}cm. Clique no chão.")

        act_wall.triggered.connect(_activate_wall_tool)
        tb.addAction(act_wall)

        # Botão direto para Configurar Réguas de Altura
        act_ruler = QAction(make_ruler_icon(), "Réguas de Altura", main_window)
        act_ruler.setStatusTip("Configurar, criar e personalizar réguas de altura e linhas-guia magnéticas de parede")
        act_ruler.setToolTip("📏 Réguas de Altura & Linhas-Guia (Personalizar / Criar)")
        def _open_ruler_config():
            from .ruler_editor_dialog import RulerEditorDialog
            from .wall_guides import WallGuideRulerManager
            ruler_mgr = WallGuideRulerManager.get_instance()
            dlg = RulerEditorDialog(parent=main_window, ruler_mgr=ruler_mgr)
            if dlg.exec():
                if hasattr(sidebar_panel, "cb_regua_ambiente"):
                    sidebar_panel.cb_regua_ambiente.blockSignals(True)
                    sidebar_panel.cb_regua_ambiente.clear()
                    sidebar_panel.cb_regua_ambiente.addItems(list(ruler_mgr.presets.keys()))
                    sidebar_panel.cb_regua_ambiente.setCurrentText(ruler_mgr.active_preset_name)
                    sidebar_panel.cb_regua_ambiente.blockSignals(False)
                if viewport is not None:
                    viewport.update()
        act_ruler.triggered.connect(_open_ruler_config)
        tb.addAction(act_ruler)

        # Barra de Ferramentas com Abas de Módulos (instanciada sob demanda no primeiro clique)
        setattr(main_window, "_trazomob_module_ribbon", None)

        def _toggle_module_ribbon():
            module_ribbon = getattr(main_window, "_trazomob_module_ribbon", None)
            if module_ribbon is None:
                from .module_ribbon import TrazoMobModuleRibbonBar
                module_ribbon = TrazoMobModuleRibbonBar(main_window, viewport, sidebar_panel)
                main_window.addToolBar(Qt.TopToolBarArea, module_ribbon)
                main_window.insertToolBarBreak(module_ribbon)
                setattr(main_window, "_trazomob_module_ribbon", module_ribbon)
                module_ribbon.show()
                act_mod.setChecked(True)
                if hasattr(viewport, "flash_status"):
                    viewport.flash_status("🧱 Catálogo de Módulos ativo. Escolha a aba e clique no móvel.")
                return

            if module_ribbon.isVisible():
                module_ribbon.hide()
                act_mod.setChecked(False)
            else:
                module_ribbon.show()
                act_mod.setChecked(True)
                if hasattr(viewport, "flash_status"):
                    viewport.flash_status("🧱 Catálogo de Módulos ativo. Escolha a aba e clique no móvel.")

        act_mod = QAction(make_cabinet_icon(), "Módulos", main_window)
        act_mod.setCheckable(True)
        act_mod.setStatusTip("Abrir/fechar barra superior de módulos por abas (Cozinha, Quarto, Banheiro...)")
        act_mod.setToolTip("🧱 Catálogo de Módulos (Abas por Ambiente) — TrazoMob")
        act_mod.triggered.connect(_toggle_module_ribbon)
        tb.addAction(act_mod)

        def _rotate_active(deg: float):
            if viewport is None or not hasattr(viewport, "scene"):
                return
            sel = list(getattr(viewport.scene, "selection", []))
            mod = None
            for item in sel:
                if hasattr(item, "ext") and isinstance(item.ext, dict) and "trazomob_module" in item.ext:
                    mod = item
                    break
            if mod is None:
                for g in getattr(viewport.scene, "groups", []):
                    if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext:
                        children = getattr(g, "children", [])
                        if any(c in sel for c in children):
                            mod = g
                            break
            if mod is None and getattr(viewport.scene, "groups", None):
                for g in reversed(viewport.scene.groups):
                    if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext:
                        mod = g
                        break
            if mod is not None:
                viewport.history.execute(RotateTrazoMobModuleCommand(mod, deg, viewport=viewport))
                viewport.notify_scene_changed()
                viewport.update()
                if hasattr(viewport, "flash_status"):
                    viewport.flash_status(f"Módulo '{mod.name}' girado {int(deg)}°")
            elif hasattr(viewport, "flash_status"):
                viewport.flash_status("Selecione um móvel para girar 90°")

        act_rot_ccw = QAction(make_rotate_ccw_icon(), "Girar 90° Anti-horário", main_window)
        act_rot_ccw.setStatusTip("Girar módulo selecionado 90° para a esquerda (anti-horário)")
        act_rot_ccw.setToolTip("Girar 90° Anti-horário (↺)")
        act_rot_ccw.triggered.connect(lambda: _rotate_active(-90.0))
        tb.addAction(act_rot_ccw)

        act_rot_cw = QAction(make_rotate_cw_icon(), "Girar 90° Horário", main_window)
        act_rot_cw.setStatusTip("Girar módulo selecionado 90° para a direita (horário)")
        act_rot_cw.setToolTip("Girar 90° Horário (↻)")
        act_rot_cw.triggered.connect(lambda: _rotate_active(90.0))
        tb.addAction(act_rot_cw)

        act_interact = QAction(make_interact_icon(), "Interagir", main_window)
        act_interact.setStatusTip("Clique nas portas e gavetas do armário para abrir ou fechar no 3D (Atalho: I)")
        act_interact.setToolTip("Interagir: Abrir/Fechar Portas e Gavetas (Atalho: I)")
        def _activate_interact():
            key = "plugin_trazomob_CabinetInteractTool"
            if hasattr(main_window, "_activate_plugin_tool") and key in getattr(main_window, "_tools", {}):
                main_window._activate_plugin_tool(key)
            elif viewport is not None and hasattr(viewport, "set_active_tool"):
                viewport.set_active_tool(CabinetInteractTool())
        act_interact.triggered.connect(_activate_interact)
        tb.addAction(act_interact)

        act_list = QAction(make_cutlist_icon(), "Lista de Peças", main_window)
        act_list.setStatusTip("Gerar lista de peças, fitas de borda e copiar para o TrazoMob")
        act_list.setToolTip("Lista de Peças & Fitas de Borda (Ctrl+V)")
        act_list.triggered.connect(lambda: _open_or_show_dialog(1))
        tb.addAction(act_list)

        act_plan = QAction(make_cut_plan_icon(), "Plano de Corte 2D", main_window)
        act_plan.setStatusTip("Abrir diagrama otimizado de corte de chapas (Nesting 2D)")
        act_plan.setToolTip("Plano de Corte Otimizado 2D (Nesting)")
        def _open_plan():
            if viewport is None or not hasattr(viewport, "scene"):
                return
            parts = extract_parts(viewport.scene)
            if not parts:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.information(
                    main_window,
                    "Plano de Corte 2D",
                    "Nenhuma peça de marcenaria encontrada na cena para gerar o plano de corte.\n"
                    "Insira módulos ou desenhe chapas antes de gerar o plano de corte."
                )
                return
            dlg = CutPlanViewerDialog(parts, parent=main_window)
            dlg.exec()
        act_plan.triggered.connect(_open_plan)
        tb.addAction(act_plan)

        # ── BOTÃO DROPDOWN DE ESTILOS DE VISUALIZAÇÃO (SUPLANTA A BARRA POLUÍDA) ──
        from PySide6.QtWidgets import QToolButton, QMenu, QWidgetAction
        from PySide6.QtGui import QActionGroup

        btn_styles = QToolButton(tb)
        btn_styles.setIcon(make_style_palette_icon())
        btn_styles.setToolTip("Estilos de Visualização (Modos de Face, Arestas, Raio-X)")
        btn_styles.setStatusTip("Alterar modo de exibição de faces, arestas e transparência")
        btn_styles.setPopupMode(QToolButton.InstantPopup)
        btn_styles.setStyleSheet("QToolButton::menu-indicator { image: none; }")

        menu_styles = QMenu(btn_styles)

        # 1. Modos de Estilo de Faces
        from core.style import BUILTIN_STYLES, style_by_name
        group_styles = QActionGroup(menu_styles)

        lbl_section1 = menu_styles.addAction("── Modos de Face ──")
        lbl_section1.setEnabled(False)

        for preset in BUILTIN_STYLES:
            act_preset = QAction(preset.name, menu_styles)
            act_preset.setCheckable(True)
            group_styles.addAction(act_preset)
            def _apply(_checked=False, p=preset):
                if hasattr(main_window, "_apply_display_style"):
                    main_window._apply_display_style(p)
                elif viewport is not None and hasattr(viewport, "scene"):
                    viewport.scene.display_style = p.copy()
                    if hasattr(main_window, "_sync_style_menu"):
                        main_window._sync_style_menu()
                    viewport.update()
            act_preset.triggered.connect(_apply)
            menu_styles.addAction(act_preset)


        menu_styles.addSeparator()

        # 2. Transparência / Raio-X
        act_xray = QAction("⚡ Alternar Raio-X (Alt+X)", menu_styles)
        act_xray.triggered.connect(lambda: getattr(main_window, "_toggle_xray", lambda: None)())
        menu_styles.addAction(act_xray)

        menu_styles.addSeparator()

        # 3. Arestas e Perfis
        lbl_section2 = menu_styles.addAction("── Arestas & Perfis ──")
        lbl_section2.setEnabled(False)

        act_edges = QAction("Arestas", menu_styles)
        act_edges.setCheckable(True)
        def _toggle_edges(val):
            if hasattr(main_window, "_set_style_field"):
                main_window._set_style_field("edges", val)
        act_edges.toggled.connect(_toggle_edges)
        menu_styles.addAction(act_edges)

        act_prof = QAction("Perfis de Contorno", menu_styles)
        act_prof.setCheckable(True)
        def _toggle_prof(val):
            if hasattr(main_window, "_set_style_field"):
                main_window._set_style_field("profiles", val)
        act_prof.toggled.connect(_toggle_prof)
        menu_styles.addAction(act_prof)

        act_back = QAction("Arestas Ocultas / Pontilhadas (K)", menu_styles)
        act_back.setCheckable(True)
        def _toggle_back(val):
            if hasattr(main_window, "_set_style_field"):
                main_window._set_style_field("back_edges", val)
        act_back.toggled.connect(_toggle_back)
        menu_styles.addAction(act_back)

        # Sincroniza estado das caixas ao abrir o menu
        def _sync_style_dropdown():
            st = getattr(getattr(viewport, "scene", None), "display_style", None)
            if st is None:
                return
            for a in group_styles.actions():
                a.blockSignals(True)
                a.setChecked(a.text() == st.name)
                a.blockSignals(False)
            act_edges.blockSignals(True)
            act_edges.setChecked(bool(getattr(st, "edges", True)))
            act_edges.blockSignals(False)
            act_prof.blockSignals(True)
            act_prof.setChecked(bool(getattr(st, "profiles", False)))
            act_prof.blockSignals(False)
            act_back.blockSignals(True)
            act_back.setChecked(bool(getattr(st, "back_edges", False)))
            act_back.blockSignals(False)

        menu_styles.aboutToShow.connect(_sync_style_dropdown)
        btn_styles.setMenu(menu_styles)
        tb.addWidget(btn_styles)

        # ── BOTÃO DE TINTAS & CORES DE PAREDES (TRAZOMOB) ──
        act_paint = QAction(make_paint_icon(), "Tintas de Parede (TrazoMob)", main_window)
        act_paint.setToolTip("Tintas & Cores de Parede (Suvinil, Coral, Cimento Queimado)")
        act_paint.setStatusTip("Clique para escolher uma cor e pintar paredes ou pisos no projeto")
        def _activate_paint_tool():
            from .wall_paint_tool import WallPaintTool, WallPaintPaletteDialog
            dlg = WallPaintPaletteDialog(parent=main_window)
            if dlg.exec():
                color, name = dlg.get_color()
                tool = WallPaintTool(color=color, paint_name=name)
                viewport.set_active_tool(tool)
        act_paint.triggered.connect(_activate_paint_tool)
        tb.addAction(act_paint)

        # ── BOTÃO DE ILUMINAÇÃO E SPOTS FÍSICOS (TRAZOMOB) ──
        act_light = QAction(make_light_icon(), "Iluminação e Spots Físicos (TrazoMob)", main_window)
        act_light.setToolTip("Gerenciador de Iluminação e Spots Físicos Profissionais")
        act_light.setStatusTip("Inserir e controlar spots, fitas LED, potência e cor da luz para o render")
        def _open_light_manager():
            from .light_tools import LightManagerDialog
            dlg = LightManagerDialog(viewport, parent=main_window)
            main_window._trazomob_light_dlg = dlg  # non-modal: viewport must get clicks
            dlg.show()
        act_light.triggered.connect(_open_light_manager)
        tb.addAction(act_light)

        # ── BOTÃO DE RENDER FOTO-REALISTA TRAZOMOB (BLENDER CYCLES / EEVEE) ──
        act_render = QAction(make_render_icon(), "Render Foto-Realista (TrazoMob)", main_window)
        act_render.setToolTip("Render Foto-Realista de Interiores (Blender Cycles / EEVEE)")
        act_render.setStatusTip("Gera imagem foto-realista com iluminação de estúdio e materiais PBR")
        def _open_render_dialog():
            from .render_dialog import TrazoMobRenderDialog
            dlg = TrazoMobRenderDialog(viewport, parent=main_window)
            dlg.exec()
        act_render.triggered.connect(_open_render_dialog)
        tb.addAction(act_render)

        # ── SUPRIME / ESCONDE A BARRA POLUÍDA igz_tb_style ──
        def _suppress_legacy_style_toolbar():
            if main_window is None:
                return
            for child in main_window.findChildren(QToolBar):
                if child.objectName() == "igz_tb_style":
                    child.hide()
                    child.setVisible(False)
                    child.setEnabled(False)

        QTimer.singleShot(200, _suppress_legacy_style_toolbar)
        QTimer.singleShot(1000, _suppress_legacy_style_toolbar)

        main_window.addToolBar(Qt.TopToolBarArea, tb)


    # 3. Menu de contexto no botão direito do mouse
    def _context(menu, selection):
        wall = None
        for item in selection:
            if hasattr(item, "ext") and isinstance(item.ext, dict) and ("trazomob_wall" in item.ext or "corte_cloud_wall" in item.ext):
                wall = item
                break
        if wall is None and hasattr(app, "viewport") and hasattr(app.viewport, "scene"):
            for g in getattr(app.viewport.scene, "groups", []):
                if hasattr(g, "ext") and isinstance(g.ext, dict) and ("trazomob_wall" in g.ext or "corte_cloud_wall" in g.ext):
                    children = getattr(g, "children", []) or []
                    if any(child in selection for child in children):
                        wall = g
                        break

        if wall is not None:
            # Tenta identificar qual segmento de parede específico foi clicado
            seg_index = None
            params = wall.ext.get("trazomob_wall") or wall.ext.get("corte_cloud_wall") or {}
            face_map = params.get("face_segment_map", {})
            if hasattr(app, "viewport") and hasattr(app.viewport, "_context_pixel"):
                px, py = app.viewport._context_pixel
                hit_face, hit_grp = app.viewport.pick_face_any(px, py)
                if hit_grp is wall and hit_face in getattr(wall.mesh, "faces", []):
                    f_idx = wall.mesh.faces.index(hit_face)
                    seg_index = face_map.get(f_idx)

            seg_text = f" #{seg_index + 1}" if seg_index is not None else ""
            act_wall = menu.addAction(f"🧱 Editar Parede{seg_text} na Barra Lateral")
            def _open_wall_side(s_idx=seg_index):
                if hasattr(app, "viewport") and hasattr(app.viewport, "scene"):
                    app.viewport.scene.selection = {wall}
                    app.viewport.update()
                sidebar_panel.focus_panel()
                sidebar_panel.load_wall(wall, segment_index=s_idx)
            act_wall.triggered.connect(lambda: QTimer.singleShot(0, _open_wall_side))

            is_locked = bool(getattr(wall, "motion_locked", False) or (hasattr(wall, "ext") and isinstance(wall.ext, dict) and wall.ext.get("motion_locked", False)))
            lock_label = "🔓 Destravar Posição das Paredes e Piso" if is_locked else "🔒 Travar Posição das Paredes e Piso"
            act_lock = menu.addAction(lock_label)
            def _toggle_lock_from_menu():
                new_state = not is_locked
                if hasattr(sidebar_panel, "btn_lock_walls_floor"):
                    sidebar_panel.btn_lock_walls_floor.setChecked(new_state)
                if hasattr(sidebar_panel, "_toggle_walls_floor_lock"):
                    sidebar_panel._toggle_walls_floor_lock(new_state)
            act_lock.triggered.connect(_toggle_lock_from_menu)
            menu.addSeparator()

        mod = None
        for item in selection:
            if hasattr(item, "ext") and isinstance(item.ext, dict):
                if "trazomob_module" in item.ext or "corte_cloud_module" in item.ext or "hellomob_module" in item.ext:
                    mod = item
                    break
        if mod is None and hasattr(app, "viewport") and hasattr(app.viewport, "scene"):
            for g in getattr(app.viewport.scene, "groups", []):
                if hasattr(g, "ext") and isinstance(g.ext, dict):
                    if "trazomob_module" in g.ext or "corte_cloud_module" in g.ext or "hellomob_module" in g.ext:
                        children = getattr(g, "children", [])
                        if any(child in selection for child in children):
                            mod = g
                            break
        if mod is not None:
            action_side = menu.addAction(f"📐 Editar na Barra Lateral: {mod.name}")
            def _open_side():
                if hasattr(app, "viewport") and hasattr(app.viewport, "scene"):
                    app.viewport.scene.selection = {mod}
                    app.viewport.update()
                sidebar_panel.focus_panel()
                sidebar_panel.load_module(mod)
            action_side.triggered.connect(lambda: QTimer.singleShot(0, _open_side))

            action = menu.addAction(f"Editar Módulo (Janela): {mod.name}…")
            def _open():
                app.viewport.scene.selection = {mod}
                app.viewport.update()
                TrazoMobTool().on_activate(app.viewport)
            action.triggered.connect(lambda: QTimer.singleShot(0, _open))

            act_tg = menu.addAction(f"🚪 Abrir / Fechar Portas e Gavetas")
            act_tg.triggered.connect(lambda: CabinetInteract.toggle_all(mod, app.viewport.scene, app.viewport))

            rot_menu = menu.addMenu("🔄 Girar 90° (TrazoMob)")
            rot_cw = rot_menu.addAction("↻ Girar 90° Horário")
            rot_cw.triggered.connect(lambda: app.viewport.history.execute(
                RotateTrazoMobModuleCommand(mod, 90.0, viewport=app.viewport)
            ))
            rot_ccw = rot_menu.addAction("↺ Girar 90° Anti-horário")
            rot_ccw.triggered.connect(lambda: app.viewport.history.execute(
                RotateTrazoMobModuleCommand(mod, -90.0, viewport=app.viewport)
            ))
            rot_180 = rot_menu.addAction("🔁 Girar 180°")
            rot_180.triggered.connect(lambda: app.viewport.history.execute(
                RotateTrazoMobModuleCommand(mod, 180.0, viewport=app.viewport)
            ))

        # ── Menu de Alinhamento e Centralização (TrazoMob) ──────────────────────
        sel_groups = [it for it in selection if isinstance(it, Group)]
        if len(sel_groups) >= 2:
            from .align_tools import center_objects
            # O último clicado ou selecionado serve de alvo, o primeiro é a base/referência
            alvo = sel_groups[-1]
            base = sel_groups[0]
            menu.addSeparator()
            align_menu = menu.addMenu(f"🎯 Centralizar / Alinhar ({alvo.name} ➔ {base.name})")

            act_c_xy = align_menu.addAction("✛ Centralizar no Centro (Largura e Profundidade - XY)")
            act_c_xy.triggered.connect(lambda: center_objects(alvo, base, axes="xy", viewport=getattr(app, "viewport", None)))

            act_c_x = align_menu.addAction("↔ Centralizar na Largura (Eixo X)")
            act_c_x.triggered.connect(lambda: center_objects(alvo, base, axes="x", viewport=getattr(app, "viewport", None)))

            act_c_y = align_menu.addAction("↕ Centralizar na Profundidade (Eixo Y)")
            act_c_y.triggered.connect(lambda: center_objects(alvo, base, axes="y", viewport=getattr(app, "viewport", None)))

            act_c_z = align_menu.addAction("⬍ Centralizar na Altura (Eixo Z)")
            act_c_z.triggered.connect(lambda: center_objects(alvo, base, axes="z", viewport=getattr(app, "viewport", None)))

            act_c_all = align_menu.addAction("🎯 Centralizar em Todos os Eixos (XYZ)")
            act_c_all.triggered.connect(lambda: center_objects(alvo, base, axes="xyz", viewport=getattr(app, "viewport", None)))

    app.add_context_menu(_context)


from .ruler_editor_dialog import RulerEditorDialog

__all__ = [
    "CabinetBuilder",
    "RotateTrazoMobModuleCommand",
    "_make_board_mesh",
    "create_board_group",
    "MODULE_CATALOG",
    "CabinetInteract",
    "CabinetInteractTool",
    "_get_entity_bbox",
    "extract_parts",
    "group_similar_parts",
    "format_trazomob_text",
    "export_trazomob_csv",
    "export_trazomob_json",
    "TrazoMobDialog",
    "TrazoMobSidebarPanel",
    "RulerEditorDialog",
    "get_module_thumbnail",
    "make_trazomob_icon",
    "make_cabinet_icon",
    "make_cutlist_icon",
    "make_interact_icon",
    "make_rotate_ccw_icon",
    "make_rotate_cw_icon",
    "make_cut_plan_icon",
    "make_perfil_diagram_pixmap",
    "make_ruler_icon",
    "CutPlanViewerDialog",
    "TrazoMobTool",
    "setup",
]

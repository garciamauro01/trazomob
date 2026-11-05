# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Construcao do card Construtor de Paredes da barra lateral."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
)


class SidebarWallsUIMixin:
    """Monta o card completo de edicao e referencia de paredes."""

    def _build_walls_card(self, layout) -> None:
        """Cria o card de paredes e o adiciona a ``layout``."""
        # ── Card: Construtor de Paredes (Design de Interiores) ───────────────────
        self.scroll_paredes = QScrollArea()
        self.scroll_paredes.setWidgetResizable(True)
        self.scroll_paredes.setFrameShape(QFrame.NoFrame)
        self.scroll_paredes.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.card_paredes = QFrame()
        self.card_paredes.setStyleSheet(
            "QFrame { background-color: palette(base); border: 1px solid palette(mid); border-radius: 4px; padding: 2px 4px; }"
        )
        l_paredes = QVBoxLayout(self.card_paredes)
        l_paredes.setContentsMargins(4, 4, 4, 4)
        l_paredes.setSpacing(3)

        lbl_par_title = QLabel("🧱 <b>Construtor de Paredes</b>")
        lbl_par_title.setStyleSheet("color: palette(text); font-size: 11px;")
        l_paredes.addWidget(lbl_par_title)

        form_paredes = QFormLayout()
        form_paredes.setContentsMargins(0, 2, 0, 2)
        form_paredes.setSpacing(4)

        # --- Segmento e Comprimento Paramétrico da Parede ---
        self.cb_parede_segmento = QComboBox()
        self.cb_parede_segmento.setToolTip("Selecione qual parede do cômodo você deseja consultar ou alterar o comprimento.")
        self.cb_parede_segmento.currentIndexChanged.connect(self._on_wall_segment_combobox_changed)
        form_paredes.addRow("Parede / Seg:", self.cb_parede_segmento)

        self.sp_parede_comprimento = QSpinBox()
        self.sp_parede_comprimento.setRange(200, 50000)
        self.sp_parede_comprimento.setValue(3000)
        self.sp_parede_comprimento.setSuffix(" mm")
        self.sp_parede_comprimento.setSingleStep(50)
        self.sp_parede_comprimento.setToolTip("Comprimento desta parede. Altere a medida em milímetros e clique em 'Atualizar Parede Selecionada'.")
        form_paredes.addRow("Comprimento:", self.sp_parede_comprimento)

        self.sp_parede_altura = QSpinBox()
        self.sp_parede_altura.setRange(1000, 6000)
        self.sp_parede_altura.setValue(2600)
        self.sp_parede_altura.setSuffix(" mm")
        self.sp_parede_altura.setSingleStep(50)
        form_paredes.addRow("Pé-Direito:", self.sp_parede_altura)

        self.sp_parede_esp = QSpinBox()
        self.sp_parede_esp.setRange(50, 500)
        self.sp_parede_esp.setValue(150)
        self.sp_parede_esp.setSuffix(" mm")
        self.sp_parede_esp.setSingleStep(10)
        form_paredes.addRow("Espessura:", self.sp_parede_esp)

        self.cb_parede_alinhar = QComboBox()
        self.cb_parede_alinhar.addItems([
            "Face Interna (Medida Livre)",
            "Centro da Parede",
            "Face Externa",
        ])
        form_paredes.addRow("Alinhamento:", self.cb_parede_alinhar)

        self.chk_parede_todas = QCheckBox("Aplicar a todas as paredes")
        self.chk_parede_todas.setChecked(True)
        self.chk_parede_todas.setToolTip(
            "Se marcado, altera o pé-direito de todas as paredes interligadas do cômodo.\n"
            "Se desmarcado, altera somente a parede selecionada."
        )
        form_paredes.addRow("", self.chk_parede_todas)

        self.chk_parede_teto = QCheckBox("Gerar Teto / Forro ao fechar")
        from PySide6.QtCore import QSettings
        _saved_teto = QSettings().value("trazomob_wall/gerar_teto", False, type=bool)
        self.chk_parede_teto.setChecked(_saved_teto)
        def _on_teto_toggled(chk):
            QSettings().setValue("trazomob_wall/gerar_teto", bool(chk))
        self.chk_parede_teto.toggled.connect(_on_teto_toggled)
        self.chk_parede_teto.setToolTip(
            "Se marcado, cria automaticamente a laje/forro de teto no pé-direito ao fechar o perímetro de paredes."
        )
        form_paredes.addRow("", self.chk_parede_teto)

        # --- Réguas Paramétricas de Alturas (Linhas-Guia) ---
        from ..wall.guides import WallGuideRulerManager, DEFAULT_RULER_PRESETS
        self._ruler_mgr = WallGuideRulerManager.get_instance()

        self.cb_regua_ambiente = QComboBox()
        self.cb_regua_ambiente.addItems(list(self._ruler_mgr.presets.keys()))
        self.cb_regua_ambiente.setCurrentText(self._ruler_mgr.active_preset_name)
        def _on_ruler_changed(preset_name):
            if preset_name:
                self._ruler_mgr.set_active_preset(preset_name)
                vp = self._get_viewport()
                if vp:
                    vp.update()
        self.cb_regua_ambiente.currentTextChanged.connect(_on_ruler_changed)

        self.btn_edit_reguas = QPushButton("⚙️")
        self.btn_edit_reguas.setMaximumWidth(32)
        self.btn_edit_reguas.setToolTip("Configurar, criar e editar réguas e alturas personalizadas...")
        def _open_ruler_dialog():
            from ..ui.ruler_editor_dialog import RulerEditorDialog
            dlg = RulerEditorDialog(parent=self.window(), ruler_mgr=self._ruler_mgr)
            if dlg.exec():
                # Atualiza a lista de presets na combobox
                self.cb_regua_ambiente.blockSignals(True)
                self.cb_regua_ambiente.clear()
                self.cb_regua_ambiente.addItems(list(self._ruler_mgr.presets.keys()))
                self.cb_regua_ambiente.setCurrentText(self._ruler_mgr.active_preset_name)
                self.cb_regua_ambiente.blockSignals(False)
                vp = self._get_viewport()
                if vp:
                    vp.update()
        self.btn_edit_reguas.clicked.connect(_open_ruler_dialog)

        h_ruler_row = QHBoxLayout()
        h_ruler_row.setContentsMargins(0, 0, 0, 0)
        h_ruler_row.setSpacing(4)
        h_ruler_row.addWidget(self.cb_regua_ambiente)
        h_ruler_row.addWidget(self.btn_edit_reguas)

        form_paredes.addRow("📏 Régua Alturas:", h_ruler_row)

        self.chk_regua_visivel = QCheckBox("Exibir Linhas-Guia e Snap 3D")
        self.chk_regua_visivel.setChecked(self._ruler_mgr.visible)
        def _on_ruler_toggle(checked):
            self._ruler_mgr.visible = bool(checked)
            self._ruler_mgr.snap_enabled = bool(checked)
            self._ruler_mgr.save_preferences()
            vp = self._get_viewport()
            if vp:
                vp.update()
        self.chk_regua_visivel.toggled.connect(_on_ruler_toggle)
        form_paredes.addRow("", self.chk_regua_visivel)

        self.chk_regua_labels = QCheckBox("Exibir Rótulos das Guias (Texto)")
        self.chk_regua_labels.setChecked(self._ruler_mgr.show_labels)
        def _on_ruler_labels_toggle(checked):
            self._ruler_mgr.show_labels = bool(checked)
            self._ruler_mgr.save_preferences()
            vp = self._get_viewport()
            if vp:
                vp.update()
        self.chk_regua_labels.toggled.connect(_on_ruler_labels_toggle)
        form_paredes.addRow("", self.chk_regua_labels)

        l_paredes.addLayout(form_paredes)

        self.btn_toggle_wall_tool = QPushButton("✏️ Construir Paredes no 3D")
        self.btn_toggle_wall_tool.setCheckable(True)
        self.btn_toggle_wall_tool.setStyleSheet(
            "QPushButton { background-color: palette(highlight); color: palette(highlighted-text); font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { opacity: 0.9; }"
            "QPushButton:checked { background-color: palette(dark); border: 2px solid palette(highlight); }"
        )
        self.btn_toggle_wall_tool.clicked.connect(self._toggle_wall_builder)
        l_paredes.addWidget(self.btn_toggle_wall_tool)

        self.btn_apply_wall = QPushButton("🔄 Atualizar Parede Selecionada")
        self.btn_apply_wall.setVisible(False)
        self.btn_apply_wall.setStyleSheet(
            "QPushButton { background-color: palette(highlight); color: palette(highlighted-text); font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { opacity: 0.9; }"
        )
        self.btn_apply_wall.clicked.connect(self._apply_wall_changes)
        l_paredes.addWidget(self.btn_apply_wall)

        # Botão Inteligente: Encaixar Bancada / Tampo sobre Balcões desta Parede
        self.btn_encaixar_bancada = QPushButton("🪨 Encaixar Bancada sobre Balcões")
        self.btn_encaixar_bancada.setVisible(False)
        self.btn_encaixar_bancada.setToolTip("Cria e encaixa automaticamente uma bancada de pedra/tampo cobrindo com precisão todos os balcões encostados nesta parede.")
        self.btn_encaixar_bancada.setStyleSheet(
            "QPushButton { background-color: #0284C7; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0369A1; }"
        )
        self.btn_encaixar_bancada.clicked.connect(self._on_encaixar_bancada_sobre_balcoes)
        l_paredes.addWidget(self.btn_encaixar_bancada)

        # Botão Inteligente: Encaixar Rodapé Contínuo em Lote sobre Balcões desta Parede
        self.btn_encaixar_rodape = QPushButton("🪵 Encaixar Rodapé Contínuo")
        self.btn_encaixar_rodape.setVisible(False)
        self.btn_encaixar_rodape.setToolTip("Cria e encaixa uma régua única de rodapé contínuo cobrindo a base frontal de todos os balcões encostados nesta parede.")
        self.btn_encaixar_rodape.setStyleSheet(
            "QPushButton { background-color: #78350F; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #92400E; }"
        )
        self.btn_encaixar_rodape.clicked.connect(self._on_encaixar_rodape_sobre_balcoes)
        l_paredes.addWidget(self.btn_encaixar_rodape)

        # Botão Inteligente: Vista Frontal 3D da Parede
        self.btn_frente_parede = QPushButton("👁️ Posicionar de Frente (3D)")
        self.btn_frente_parede.setVisible(False)
        self.btn_frente_parede.setToolTip("Posiciona a câmera do 3D perfeitamente de frente para a parede selecionada (você também pode dar dois cliques rápidos nela no 3D).")
        self.btn_frente_parede.setStyleSheet(
            "QPushButton { background-color: #059669; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #047857; }"
        )
        def _on_clicar_frente_parede():
            from ..wall.selection import WallSelectionManager
            wall_mgr = WallSelectionManager.get_instance(self._get_viewport())
            wall_mgr.align_view_to_wall()
        self.btn_frente_parede.clicked.connect(_on_clicar_frente_parede)
        l_paredes.addWidget(self.btn_frente_parede)

        # Botão Inteligente: Elevação Técnica 2D da Parede com Cotas
        self.btn_elevacao_parede = QPushButton("📐 Elevação 2D com Cotas")
        self.btn_elevacao_parede.setVisible(False)
        self.btn_elevacao_parede.setToolTip("Abre a vista ortogonal t?cnica 2D da parede com todos os m?veis e cotas milim?tricas detalhadas.")
        self.btn_elevacao_parede.setStyleSheet(
            "QPushButton { background-color: #4338CA; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #3730A3; }"
        )
        self.btn_elevacao_parede.clicked.connect(self._on_abrir_elevacao_parede)
        l_paredes.addWidget(self.btn_elevacao_parede)

        # Bot?o Inteligente: R?gua de Fechamento / Arremate Autom?tico de Canto
        self.btn_fechar_vao = QPushButton("?? Inserir Arremate de Canto")
        self.btn_fechar_vao.setVisible(False)
        self.btn_fechar_vao.setToolTip("Detecta a folga residual entre o ?ltimo m?dulo e a parede de canto e insere uma r?gua de arremate sob medida.")
        self.btn_fechar_vao.setStyleSheet(
            "QPushButton { background-color: #0D9488; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0F766E; }"
        )
        self.btn_fechar_vao.clicked.connect(self._on_fechar_vao_canto)
        l_paredes.addWidget(self.btn_fechar_vao)

        # ── Preenchimento Automático de Parede ─────────────────────────
        self.lbl_auto_preencher = QLabel("🤖 <b>Preenchimento Automático</b>")
        self.lbl_auto_preencher.setStyleSheet(
            "color: palette(text); font-size: 11px; margin-top: 4px;")
        self.lbl_auto_preencher.setVisible(False)
        l_paredes.addWidget(self.lbl_auto_preencher)

        self.cb_auto_composicao = QComboBox()
        self.cb_auto_composicao.addItem("Balcões com portas", "portas")
        self.cb_auto_composicao.addItem("Balcões + gaveteiros", "misto")
        self.cb_auto_composicao.addItem("Somente gaveteiros", "gavetas")
        self.cb_auto_composicao.setToolTip(
            "Composição usada no preenchimento dos módulos inferiores.\n"
            "Para aéreos o preenchimento usa sempre armários com portas.")
        self.cb_auto_composicao.setVisible(False)
        l_paredes.addWidget(self.cb_auto_composicao)

        h_auto = QHBoxLayout()
        h_auto.setSpacing(4)
        self.btn_auto_inferiores = QPushButton("Preencher Inferiores")
        self.btn_auto_inferiores.setToolTip(
            "Gera e distribui módulos inferiores contíguos para fechar o vão "
            "informado em 'Comprimento', usando a parede selecionada como referência.")
        self.btn_auto_inferiores.setStyleSheet(
            "QPushButton { background-color: #7C3AED; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #6D28D9; }"
        )
        self.btn_auto_inferiores.clicked.connect(self._on_auto_preencher_inferiores)
        self.btn_auto_inferiores.setVisible(False)
        h_auto.addWidget(self.btn_auto_inferiores)

        self.btn_auto_aereos = QPushButton("Preencher Aéreos")
        self.btn_auto_aereos.setToolTip(
            "Gera e distribui armários aéreos contíguos para fechar o vão "
            "informado em 'Comprimento', usando a parede selecionada como referência.")
        self.btn_auto_aereos.setStyleSheet(
            "QPushButton { background-color: #0891B2; color: white; font-weight: bold; padding: 7px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0E7490; }"
        )
        self.btn_auto_aereos.clicked.connect(self._on_auto_preencher_aereos)
        self.btn_auto_aereos.setVisible(False)
        h_auto.addWidget(self.btn_auto_aereos)
        l_paredes.addLayout(h_auto)



        # Botão direto para ocultar a parede selecionada
        self.btn_hide_selected_wall = QPushButton("👁️ Ocultar Parede Selecionada")
        self.btn_hide_selected_wall.setVisible(False)
        self.btn_hide_selected_wall.setStyleSheet(
            "QPushButton { background-color: #64748B; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #475569; }"
        )
        def _on_click_hide_selected_wall():
            w = getattr(self, "_selected_wall", None)
            vp = self._get_viewport()
            if w and vp and hasattr(vp, "history"):
                from core.history import HideCommand
                from ..wall.selection import WallSelectionManager
                from ..wall.builder import WallBuilderTool, SplitWallGroupCommand

                params = getattr(w, "ext", {}).get("trazomob_wall") if isinstance(getattr(w, "ext", None), dict) else {}
                is_seg = bool(params.get("is_segmented", False))
                pts_count = len(params.get("pontos", []))

                # Se a parede já for um segmento seccionado independente
                if is_seg or pts_count <= 2:
                    vp.history.execute(HideCommand([w], hidden=True))
                    if hasattr(vp, "scene"):
                        vp.scene.selection.discard(w)
                    WallSelectionManager.get_instance().clear_selection()
                    self._selected_wall = None
                    self.btn_apply_wall.setVisible(False)
                    self.btn_hide_selected_wall.setVisible(False)
                    if hasattr(self, "btn_frente_parede"):
                        self.btn_frente_parede.setVisible(False)
                    if hasattr(self, "btn_split_walls"):
                        self.btn_split_walls.setVisible(False)
                    vp.update()
                    if hasattr(vp, "flash_status"):
                        vp.flash_status(f"👁️ {w.name} ocultada (use 'Reexibir Paredes' para mostrar novamente).")
                    return

                # Se for monólito contínuo antigo, secciona em paredes individuais e oculta a escolhida
                seg_idx = None
                if hasattr(self, "cb_parede_segmento"):
                    seg_idx = self.cb_parede_segmento.currentData()
                if seg_idx is None:
                    seg_idx = params.get("selected_segment", 0)

                subs = WallBuilderTool.split_wall_group_into_segments(w)
                if len(subs) > 1:
                    cmd_split = SplitWallGroupCommand(w, subs)
                    vp.history.execute(cmd_split)
                    target_sub = next((s for s in subs if s.ext.get("trazomob_wall", {}).get("segment_index") == int(seg_idx)), subs[0])
                    vp.history.execute(HideCommand([target_sub], hidden=True))
                    if hasattr(vp, "scene"):
                        vp.scene.selection.discard(w)
                    WallSelectionManager.get_instance().clear_selection()
                    self._selected_wall = None
                    self.btn_apply_wall.setVisible(False)
                    self.btn_hide_selected_wall.setVisible(False)
                    if hasattr(self, "btn_frente_parede"):
                        self.btn_frente_parede.setVisible(False)
                    if hasattr(self, "btn_split_walls"):
                        self.btn_split_walls.setVisible(False)
                    vp.update()
                    if hasattr(vp, "flash_status"):
                        vp.flash_status(f"👁️ Parede #{int(seg_idx) + 1} seccionada e ocultada com sucesso!")
                    return
        self.btn_hide_selected_wall.clicked.connect(_on_click_hide_selected_wall)
        l_paredes.addWidget(self.btn_hide_selected_wall)

        # Botão para seccionar monólito em paredes individuais independentes
        self.btn_split_walls = QPushButton("✂️ Seccionar em Paredes Individuais")
        self.btn_split_walls.setVisible(False)
        self.btn_split_walls.setToolTip("Divide o bloco contínuo de paredes em paredes independentes para ocultar, mover ou editar cada uma separadamente.")
        self.btn_split_walls.setStyleSheet(
            "QPushButton { background-color: #0284C7; color: white; font-weight: bold; padding: 6px; border-radius: 4px; }"
            "QPushButton:hover { background-color: #0369A1; }"
        )
        def _on_click_split_walls():
            w = getattr(self, "_selected_wall", None)
            vp = self._get_viewport()
            if w and vp and hasattr(vp, "history"):
                from ..wall.builder import WallBuilderTool, SplitWallGroupCommand
                subs = WallBuilderTool.split_wall_group_into_segments(w)
                if len(subs) > 1:
                    cmd = SplitWallGroupCommand(w, subs)
                    vp.history.execute(cmd)
                    if hasattr(vp, "scene"):
                        vp.scene.selection = {subs[0]}
                    self.load_wall(subs[0])
                    vp.update()
                    if hasattr(vp, "flash_status"):
                        vp.flash_status(f"✂️ Bloco dividido com sucesso em {len(subs)} paredes individuais independentes!")
        self.btn_split_walls.clicked.connect(_on_click_split_walls)
        l_paredes.addWidget(self.btn_split_walls)

        self.btn_lock_walls_floor = QPushButton("🔒 Trava de Posição: ATIVA")
        self.btn_lock_walls_floor.setCheckable(True)
        self.btn_lock_walls_floor.setChecked(True)
        self.btn_lock_walls_floor.setToolTip("Impede mover paredes e piso acidentalmente. Snaps, cotas e medições continuam funcionando normalmente!")
        self.btn_lock_walls_floor.setStyleSheet(
            "QPushButton { background-color: #2e7d32; color: white; font-weight: bold; padding: 6px; border-radius: 4px; border: 1px solid #1b5e20; }"
            "QPushButton:hover { background-color: #388e3c; }"
            "QPushButton:!checked { background-color: palette(button); color: palette(text); border: 1px solid palette(mid); font-weight: normal; }"
        )
        self.btn_lock_walls_floor.clicked.connect(self._toggle_walls_floor_lock)
        l_paredes.addWidget(self.btn_lock_walls_floor)

        # Botão de reexibir todas as paredes/tetos ocultos
        self.btn_unhide_all_walls = QPushButton("👁️ Reexibir Paredes e Tetos")
        self.btn_unhide_all_walls.setStyleSheet(
            "QPushButton { background-color: palette(button); color: palette(text); padding: 5px; border-radius: 4px; border: 1px solid palette(mid); }"
            "QPushButton:hover { background-color: palette(midlight); }"
        )
        def _on_click_unhide_all():
            vp = self._get_viewport()
            if vp and hasattr(vp, "scene") and hasattr(vp, "history"):
                arch_to_show = []
                for g in getattr(vp.scene, "groups", []):
                    ext = getattr(g, "ext", {})
                    if isinstance(ext, dict) and ("trazomob_wall" in ext or "trazomob_ceiling" in ext):
                        if getattr(g, "hidden", False) or vp.scene.entity_hidden(g):
                            arch_to_show.append(g)
                if arch_to_show:
                    from core.history import HideCommand
                    vp.history.execute(HideCommand(arch_to_show, hidden=False))
                    vp.update()
                    if hasattr(vp, "flash_status"):
                        vp.flash_status(f"👁️ {len(arch_to_show)} elemento(s) reexibido(s).")
                else:
                    if hasattr(vp, "flash_status"):
                        vp.flash_status("Nenhuma parede ou teto oculto.")
        self.btn_unhide_all_walls.clicked.connect(_on_click_unhide_all)
        l_paredes.addWidget(self.btn_unhide_all_walls)
        l_paredes.addStretch(1)

        self.scroll_paredes.setWidget(self.card_paredes)
        self.scroll_paredes.setVisible(False)
        layout.addWidget(self.scroll_paredes)


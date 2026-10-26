# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Componente de Seção Colapsável Padronizada (CollapsibleSection) para a Sidebar do TrazoMob.

Proporciona uma interface moderna em estilo Accordion / Cards:
- Cabeçalho clicável com ícone, título, indicador de expansão (▾ / ▸) e badge de status/resumo;
- Animação suave e alternância limpa de visibilidade do conteúdo interno;
- Design System unificado seguindo a paleta de cores nativa do Qt.
"""
from __future__ import annotations

from typing import Optional
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QFrame,
    QToolButton,
    QLayout,
)


class CollapsibleSection(QWidget):
    """Card colapsável com cabeçalho interativo, badge e container interno."""

    toggled = Signal(bool)

    def __init__(
        self,
        title: str,
        icon_text: str = "",
        parent: Optional[QWidget] = None,
        collapsed: bool = False,
    ) -> None:
        super().__init__(parent)
        self._is_collapsed = collapsed

        # Layout Principal do Card
        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 2, 0, 4)
        self._main_layout.setSpacing(0)

        # ─── CABEÇALHO DO CARD ───
        self._header_frame = QFrame(self)
        self._header_frame.setObjectName("collapsibleHeader")
        self._header_frame.setCursor(Qt.PointingHandCursor)
        self._header_frame.setStyleSheet(
            """
            QFrame#collapsibleHeader {
                background-color: palette(alternate-base);
                border: 1px solid palette(midlight);
                border-radius: 4px;
                padding: 4px 6px;
            }
            QFrame#collapsibleHeader:hover {
                background-color: palette(midlight);
                border: 1px solid palette(highlight);
            }
            """
        )

        h_layout = QHBoxLayout(self._header_frame)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(6)

        # Ícone de seta expansora (▾ / ▸)
        self._btn_toggle = QToolButton(self._header_frame)
        self._btn_toggle.setStyleSheet("QToolButton { border: none; background: transparent; font-size: 11px; font-weight: bold; }")
        self._btn_toggle.setText("▸" if self._is_collapsed else "▾")
        self._btn_toggle.clicked.connect(self.toggle)
        h_layout.addWidget(self._btn_toggle)

        # Ícone temático da seção (opcional)
        if icon_text:
            self._lbl_icon = QLabel(icon_text, self._header_frame)
            self._lbl_icon.setStyleSheet("font-size: 13px; font-weight: bold;")
            h_layout.addWidget(self._lbl_icon)

        # Título da seção
        self._lbl_title = QLabel(f"<b>{title}</b>", self._header_frame)
        self._lbl_title.setStyleSheet("color: palette(text); font-size: 11px;")
        h_layout.addWidget(self._lbl_title)

        h_layout.addStretch(1)

        # Badge de resumo rápido (ex: '800x720 mm', '2 Portas', 'Gola')
        self._lbl_badge = QLabel("", self._header_frame)
        self._lbl_badge.setStyleSheet(
            "color: palette(bright-text); background-color: palette(highlight); "
            "border-radius: 8px; padding: 1px 6px; font-size: 10px; font-weight: bold;"
        )
        self._lbl_badge.setVisible(False)
        h_layout.addWidget(self._lbl_badge)

        self._main_layout.addWidget(self._header_frame)

        # ─── CONTAINER DE CONTEÚDO ───
        self._content_area = QFrame(self)
        self._content_area.setObjectName("collapsibleContent")
        self._content_area.setStyleSheet(
            """
            QFrame#collapsibleContent {
                background-color: palette(base);
                border-left: 1px solid palette(midlight);
                border-right: 1px solid palette(midlight);
                border-bottom: 1px solid palette(midlight);
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
                padding: 4px 6px;
            }
            """
        )
        self._content_layout = QVBoxLayout(self._content_area)
        self._content_layout.setContentsMargins(6, 6, 6, 6)
        self._content_layout.setSpacing(4)

        # FormLayout embutido por conveniência para formulários rotulados
        self._form_layout = QFormLayout()
        self._form_layout.setContentsMargins(0, 0, 0, 0)
        self._form_layout.setSpacing(4)
        self._content_layout.addLayout(self._form_layout)

        self._main_layout.addWidget(self._content_area)

        # Conectar clique no frame do cabeçalho
        self._header_frame.mousePressEvent = lambda e: self.toggle()

        # Aplica estado inicial
        self._content_area.setVisible(not self._is_collapsed)

    @property
    def form_layout(self) -> QFormLayout:
        """Acesso direto ao QFormLayout interno do card."""
        return self._form_layout

    def add_row(self, *args) -> None:
        """Atalho conveniente para adicionar linhas diretamente ao QFormLayout interno."""
        self._form_layout.addRow(*args)

    def set_content_layout(self, layout: QLayout) -> None:
        """Define o layout interno de widgets do card."""
        QWidget().setLayout(self._content_layout) # Limpa se houver anterior
        self._content_layout = layout
        self._content_area.setLayout(layout)

    def add_widget(self, widget: QWidget) -> None:
        """Adiciona um widget ao corpo do card."""
        self._content_layout.addWidget(widget)

    def add_layout(self, layout: QLayout) -> None:
        """Adiciona um sub-layout ao corpo do card."""
        self._content_layout.addLayout(layout)

    def set_badge(self, text: str) -> None:
        """Atualiza o texto da pílula/badge de resumo."""
        if text:
            self._lbl_badge.setText(text)
            self._lbl_badge.setVisible(True)
        else:
            self._lbl_badge.setVisible(False)

    def is_collapsed(self) -> bool:
        """Retorna True se o card estiver recolhido."""
        return self._is_collapsed

    def set_collapsed(self, collapsed: bool) -> None:
        """Define o estado expandido/recolhido do card."""
        self._is_collapsed = collapsed
        self._btn_toggle.setText("▸" if self._is_collapsed else "▾")
        self._content_area.setVisible(not self._is_collapsed)
        self.toggled.emit(not self._is_collapsed)

    def toggle(self) -> None:
        """Alterna o estado entre expandido e recolhido."""
        self.set_collapsed(not self._is_collapsed)

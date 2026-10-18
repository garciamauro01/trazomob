# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Visualizador interativo 2D de Plano de Corte e Aproveitamento de Chapas."""
from __future__ import annotations

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QFont,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .optimizer import CutPiece, CutSheet, GuillotineOptimizer, SheetConfig


class SheetCanvasWidget(QWidget):
    """Área gráfica de desenho 2D da chapa de corte com peças e cotas."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._sheet: CutSheet | None = None
        self._config: SheetConfig = SheetConfig()
        self.setMinimumSize(700, 480)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_sheet(self, sheet: CutSheet | None, config: SheetConfig) -> None:
        self._sheet = sheet
        self._config = config
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)

        w_view = self.width()
        h_view = self.height()

        # Fundo do canvas (cinza blueprint moderno)
        painter.fillRect(0, 0, w_view, h_view, QColor("#1e2024"))

        if not self._sheet:
            painter.setPen(QColor("#94a3b8"))
            painter.setFont(QFont("Segoe UI", 12))
            painter.drawText(self.rect(), Qt.AlignCenter, "Nenhuma chapa gerada para visualização.")
            return

        sheet = self._sheet
        cfg = self._config

        # Margem de respiro no visualizador
        margin = 50.0
        avail_w = max(100.0, w_view - 2 * margin)
        avail_h = max(100.0, h_view - 2 * margin)

        # Escala uniforme para caber a chapa no canvas
        scale_x = avail_w / cfg.comprimento
        scale_y = avail_h / cfg.largura
        scale = min(scale_x, scale_y)

        draw_w = cfg.comprimento * scale
        draw_h = cfg.largura * scale

        ox = (w_view - draw_w) / 2.0
        oy = (h_view - draw_h) / 2.0

        # Sombra sutil sob a chapa
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawRoundedRect(QRectF(ox + 5, oy + 5, draw_w, draw_h), 4, 4)

        # 1. Desenho da chapa bruta
        chapa_rect = QRectF(ox, oy, draw_w, draw_h)
        painter.setBrush(QColor("#f8fafc"))
        painter.setPen(QPen(QColor("#475569"), 1.5))
        painter.drawRect(chapa_rect)

        # 2. Desenho das margens de refilo (linha pontilhada)
        if cfg.refilo > 0:
            ref_x = ox + (cfg.refilo * scale)
            ref_y = oy + (cfg.refilo * scale)
            ref_w = draw_w - (2 * cfg.refilo * scale)
            ref_h = draw_h - (2 * cfg.refilo * scale)
            pen_ref = QPen(QColor("#94a3b8"), 1.0, Qt.DashLine)
            painter.setPen(pen_ref)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(QRectF(ref_x, ref_y, ref_w, ref_h))

        # 3. Desenho das sobras aproveitáveis (hachurado verde claro)
        for sx, sy, sw, sh in sheet.sobras:
            r_sobra = QRectF(ox + sx * scale, oy + sy * scale, sw * scale, sh * scale)
            painter.setPen(QPen(QColor("#10b981"), 1.0, Qt.DotLine))
            painter.setBrush(QColor(16, 185, 129, 35))
            painter.drawRect(r_sobra)

            if r_sobra.width() > 50 and r_sobra.height() > 25:
                painter.setPen(QColor("#059669"))
                painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
                painter.drawText(
                    r_sobra,
                    Qt.AlignCenter,
                    f"Sobra\n{int(sw)}x{int(sh)}",
                )

        # Paleta de cores harmoniosas para as peças
        cores_pecas = [
            QColor("#e0e7ff"),  # Índigo suave
            QColor("#dcfce7"),  # Verde suave
            QColor("#fef3c7"),  # Âmbar suave
            QColor("#fee2e2"),  # Rosa/coral suave
            QColor("#f3e8ff"),  # Roxo suave
            QColor("#e0f2fe"),  # Ciano suave
            QColor("#ffedd5"),  # Laranja suave
        ]

        # 4. Desenho das peças cortadas
        for i, p in enumerate(sheet.pecas):
            px = ox + p.x * scale
            py = oy + p.y * scale
            pw = p.w_aloc * scale
            ph = p.h_aloc * scale
            rect_peca = QRectF(px, py, pw, ph)

            cor = cores_pecas[i % len(cores_pecas)]
            painter.setPen(QPen(QColor("#334155"), 1.2))
            painter.setBrush(cor)
            painter.drawRect(rect_peca)

            # Fita de borda (arestas destacadas com fita vermelha/laranja grossa)
            pen_fita = QPen(QColor("#dc2626"), 3.0, Qt.SolidLine, Qt.RoundCap)
            painter.setPen(pen_fita)

            # C1 e C2: arestas de comprimento
            # L1 e L2: arestas de largura
            if not p.rotacionada:
                # Comprimento na horizontal (topo/base), Largura na vertical (esq/dir)
                if p.fita_c1: painter.drawLine(QPointF(px, py + ph), QPointF(px + pw, py + ph))  # Base
                if p.fita_c2: painter.drawLine(QPointF(px, py), QPointF(px + pw, py))            # Topo
                if p.fita_l1: painter.drawLine(QPointF(px, py), QPointF(px, py + ph))            # Esquerda
                if p.fita_l2: painter.drawLine(QPointF(px + pw, py), QPointF(px + pw, py + ph))  # Direita
            else:
                # Rotacionada 90°: Comprimento na vertical, Largura na horizontal
                if p.fita_c1: painter.drawLine(QPointF(px, py), QPointF(px, py + ph))
                if p.fita_c2: painter.drawLine(QPointF(px + pw, py), QPointF(px + pw, py + ph))
                if p.fita_l1: painter.drawLine(QPointF(px, py + ph), QPointF(px + pw, py + ph))
                if p.fita_l2: painter.drawLine(QPointF(px, py), QPointF(px + pw, py))

            # Rótulo de texto da peça
            if pw >= 30 and ph >= 18:
                painter.setPen(QColor("#0f172a"))
                rot_tag = " 🔄" if p.rotacionada else ""
                txt_dim = f"{int(p.comprimento)}x{int(p.largura)}"

                font_size = 9 if (pw > 70 and ph > 40) else 7
                painter.setFont(QFont("Segoe UI", font_size, QFont.Bold))

                if ph > 35:
                    txt_full = f"{p.nome}{rot_tag}\n{txt_dim}"
                else:
                    txt_full = f"{txt_dim}"

                painter.drawText(rect_peca.adjusted(2, 2, -2, -2), Qt.AlignCenter, txt_full)

            # 4.1. Marcações visuais de furação e usinagem (canecos, cavilhas, rasgos)
            ops = getattr(p, "operacoes", []) or []
            if ops and pw >= 20 and ph >= 15:
                for op in ops:
                    op_tipo = op.get("tipo", "furo")
                    op_x = float(op.get("x", 0.0))
                    op_y = float(op.get("y", 0.0))
                    diam = float(op.get("diametro", 5.0))

                    # Converte coordenadas locais da peça para o canvas da chapa
                    if not p.rotacionada:
                        pt_x = px + (op_x / max(1.0, p.comprimento)) * pw
                        pt_y = py + (op_y / max(1.0, p.largura)) * ph
                    else:
                        pt_x = px + (op_y / max(1.0, p.largura)) * pw
                        pt_y = py + (op_x / max(1.0, p.comprimento)) * ph

                    if op_tipo == "furo":
                        r_px = max(2.0, min(8.0, (diam / 2.0) * scale))
                        painter.setPen(QPen(QColor("#0284c7"), 1.0))
                        painter.setBrush(QBrush(QColor(2, 132, 199, 140)))
                        painter.drawEllipse(QPointF(pt_x, pt_y), r_px, r_px)
                        # Cruz central técnica do furo
                        painter.setPen(QPen(QColor("#ffffff"), 0.8))
                        painter.drawLine(QPointF(pt_x - r_px, pt_y), QPointF(pt_x + r_px, pt_y))
                        painter.drawLine(QPointF(pt_x, pt_y - r_px), QPointF(pt_x, pt_y + r_px))
                    elif op_tipo in ("rasgo", "rebaixo"):
                        # Desenha linha tracejada representando o canal
                        painter.setPen(QPen(QColor("#ea580c"), 1.5, Qt.DashLine))
                        if not p.rotacionada:
                            painter.drawLine(QPointF(px, pt_y), QPointF(px + pw, pt_y))
                        else:
                            painter.drawLine(QPointF(pt_x, py), QPointF(pt_x, py + ph))


        # 5. Cotas da Chapa Bruta no Rodapé e Lateral
        painter.setPen(QColor("#cbd5e1"))
        painter.setFont(QFont("Segoe UI", 9, QFont.Bold))
        # Cota horizontal
        painter.drawText(
            QRectF(ox, oy + draw_h + 8, draw_w, 25),
            Qt.AlignCenter,
            f"↔ {int(cfg.comprimento)} mm",
        )
        # Cota vertical
        painter.save()
        painter.translate(ox - 18, oy + (draw_h / 2.0))
        painter.rotate(-90)
        painter.drawText(QRectF(-60, -10, 120, 20), Qt.AlignCenter, f"↕ {int(cfg.largura)} mm")
        painter.restore()


class CutPlanViewerDialog(QDialog):
    """Janela completa de visualização, navegação e exportação do Plano de Corte."""

    def __init__(self, raw_parts: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("📐 Plano de Corte Otimizado 2D — IngeTrazo / TrazoMob")
        self.resize(1150, 750)
        self._raw_parts = raw_parts
        self._config = SheetConfig()
        self._optimizer = GuillotineOptimizer(self._config)
        self._sheets_by_material: dict[str, list[CutSheet]] = {}
        self._current_material: str = ""
        self._current_sheet_idx: int = 0

        self._build_ui()
        self._run_optimization()

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(10)

        # Barra Superior: Parâmetros e Configuração da Chapa
        top_box = QGroupBox("Configurações da Chapa e Corte")
        top_box.setStyleSheet("font-weight: bold;")
        h_top = QHBoxLayout(top_box)
        h_top.setSpacing(12)

        h_top.addWidget(QLabel("Chapa (mm):"))
        self.sp_chapa_comp = QSpinBox()
        self.sp_chapa_comp.setRange(500, 4000)
        self.sp_chapa_comp.setValue(int(self._config.comprimento))
        self.sp_chapa_comp.setSuffix(" L")
        h_top.addWidget(self.sp_chapa_comp)

        self.sp_chapa_larg = QSpinBox()
        self.sp_chapa_larg.setRange(500, 4000)
        self.sp_chapa_larg.setValue(int(self._config.largura))
        self.sp_chapa_larg.setSuffix(" A")
        h_top.addWidget(self.sp_chapa_larg)

        h_top.addWidget(QLabel("Serra / Kerf:"))
        self.sp_kerf = QDoubleSpinBox()
        self.sp_kerf.setRange(1.0, 10.0)
        self.sp_kerf.setSingleStep(0.5)
        self.sp_kerf.setValue(self._config.espessura_corte)
        self.sp_kerf.setSuffix(" mm")
        h_top.addWidget(self.sp_kerf)

        h_top.addWidget(QLabel("Refilo:"))
        self.sp_refilo = QDoubleSpinBox()
        self.sp_refilo.setRange(0.0, 50.0)
        self.sp_refilo.setValue(self._config.refilo)
        self.sp_refilo.setSuffix(" mm")
        h_top.addWidget(self.sp_refilo)

        btn_recalc = QPushButton("⚡ Re-otimizar")
        btn_recalc.setStyleSheet("background-color: #2563eb; color: white; padding: 6px 14px; border-radius: 4px;")
        btn_recalc.clicked.connect(self._run_optimization)
        h_top.addWidget(btn_recalc)

        h_top.addStretch()

        btn_export_img = QPushButton("📷 Salvar Imagem da Chapa")
        btn_export_img.clicked.connect(self._export_sheet_image)
        h_top.addWidget(btn_export_img)

        main_layout.addWidget(top_box)

        # Barra de Navegação de Chapas e Estatísticas
        nav_bar = QHBoxLayout()
        nav_bar.setSpacing(14)

        nav_bar.addWidget(QLabel("Material:"))
        self.cb_material = QComboBox()
        self.cb_material.setMinimumWidth(220)
        self.cb_material.currentIndexChanged.connect(self._on_material_changed)
        nav_bar.addWidget(self.cb_material)

        self.btn_prev_sheet = QPushButton("◀ Anterior")
        self.btn_prev_sheet.clicked.connect(self._prev_sheet)
        nav_bar.addWidget(self.btn_prev_sheet)

        self.lbl_sheet_nav = QLabel("Chapa 1 de 1")
        self.lbl_sheet_nav.setStyleSheet("font-size: 13px; font-weight: bold; color: #1e293b;")
        nav_bar.addWidget(self.lbl_sheet_nav)

        self.btn_next_sheet = QPushButton("Próxima ▶")
        self.btn_next_sheet.clicked.connect(self._next_sheet)
        nav_bar.addWidget(self.btn_next_sheet)

        nav_bar.addStretch()

        # Banner de Indicadores / Estatísticas
        self.lbl_sheet_stats = QLabel("Aproveitamento: 0% | Área Útil: 0.00 m² | Fita de Borda: 0.0 m")
        self.lbl_sheet_stats.setStyleSheet(
            "background-color: #ecfdf5; color: #047857; font-weight: bold; padding: 6px 12px; "
            "border: 1px solid #a7f3d0; border-radius: 6px; font-size: 12px;"
        )
        nav_bar.addWidget(self.lbl_sheet_stats)

        main_layout.addLayout(nav_bar)

        # Canvas Gráfico 2D
        self.canvas = SheetCanvasWidget(self)
        main_layout.addWidget(self.canvas, stretch=1)

        # Rodapé com Resumo Geral do Projeto
        foot_layout = QHBoxLayout()
        self.lbl_total_summary = QLabel("Total do Projeto: 0 chapas | 0.00 m²")
        self.lbl_total_summary.setStyleSheet("font-weight: 500; color: #64748b;")
        foot_layout.addWidget(self.lbl_total_summary)

        foot_layout.addStretch()

        btn_close = QPushButton("Fechar")
        btn_close.clicked.connect(self.close)
        foot_layout.addWidget(btn_close)

        main_layout.addLayout(foot_layout)

    def _run_optimization(self) -> None:
        """Executa o algoritmo com as configurações atuais."""
        self._config.comprimento = float(self.sp_chapa_comp.value())
        self._config.largura = float(self.sp_chapa_larg.value())
        self._config.espessura_corte = float(self.sp_kerf.value())
        self._config.refilo = float(self.sp_refilo.value())

        self._optimizer = GuillotineOptimizer(self._config)
        self._sheets_by_material = self._optimizer.optimize(self._raw_parts)

        # Atualiza combo de materiais
        self.cb_material.blockSignals(True)
        self.cb_material.clear()
        for mat in self._sheets_by_material.keys():
            chapas_count = len(self._sheets_by_material[mat])
            self.cb_material.addItem(f"{mat} ({chapas_count} chapa{'s' if chapas_count > 1 else ''})", mat)
        self.cb_material.blockSignals(False)

        if self._sheets_by_material:
            self._current_material = list(self._sheets_by_material.keys())[0]
            self._current_sheet_idx = 0
            self._update_view()
        else:
            self.canvas.set_sheet(None, self._config)
            self.lbl_sheet_stats.setText("Nenhuma peça para cortar.")

        self._update_total_summary()

    def _on_material_changed(self) -> None:
        mat_data = self.cb_material.currentData()
        if mat_data and mat_data in self._sheets_by_material:
            self._current_material = mat_data
            self._current_sheet_idx = 0
            self._update_view()

    def _prev_sheet(self) -> None:
        if self._current_sheet_idx > 0:
            self._current_sheet_idx -= 1
            self._update_view()

    def _next_sheet(self) -> None:
        chapas = self._sheets_by_material.get(self._current_material, [])
        if self._current_sheet_idx < len(chapas) - 1:
            self._current_sheet_idx += 1
            self._update_view()

    def _update_view(self) -> None:
        chapas = self._sheets_by_material.get(self._current_material, [])
        if not chapas:
            self.canvas.set_sheet(None, self._config)
            return

        total_chapas = len(chapas)
        sheet = chapas[self._current_sheet_idx]

        self.canvas.set_sheet(sheet, self._config)
        self.lbl_sheet_nav.setText(f"Chapa {self._current_sheet_idx + 1} de {total_chapas}")
        self.btn_prev_sheet.setEnabled(self._current_sheet_idx > 0)
        self.btn_next_sheet.setEnabled(self._current_sheet_idx < total_chapas - 1)

        area_util_m2 = sheet.area_util_mm2 / 1_000_000.0
        self.lbl_sheet_stats.setText(
            f"🎯 Aproveitamento: {sheet.aproveitamento_pct}%  |  "
            f"Área Útil: {area_util_m2:.2f} m²  |  "
            f"Peças: {len(sheet.pecas)}  |  "
            f"Fita de Borda: {sheet.metros_fita:.1f} m"
        )

    def _update_total_summary(self) -> None:
        total_chapas = sum(len(c) for c in self._sheets_by_material.values())
        total_pecas = sum(len(s.pecas) for c in self._sheets_by_material.values() for s in c)
        total_fita = sum(s.metros_fita for c in self._sheets_by_material.values() for s in c)

        self.lbl_total_summary.setText(
            f"📊 Total do Projeto: {total_chapas} chapa(s)  •  "
            f"{total_pecas} peças alocadas  •  "
            f"{total_fita:.1f} metros lineares de fita de borda"
        )

    def _export_sheet_image(self) -> None:
        """Salva uma imagem de alta resolução (PNG) da chapa atual."""
        chapas = self._sheets_by_material.get(self._current_material, [])
        if not chapas:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Diagrama de Corte",
            f"Plano_Corte_Chapa_{self._current_sheet_idx + 1}.png",
            "Imagens PNG (*.png)",
        )
        if not filepath:
            return

        pix = QPixmap(self.canvas.size())
        self.canvas.render(pix)
        if pix.save(filepath, "PNG"):
            QMessageBox.information(self, "Exportação", f"Diagrama salvo com sucesso em:\n{filepath}")

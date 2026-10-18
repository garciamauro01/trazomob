# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
# Miniaturas vetoriais dos m?dulos para o cat?logo TrazoMob do TrazoMob.
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

_THUMBNAIL_CACHE: dict[str, QIcon] = {}

def get_module_thumbnail(module_id: str) -> QIcon:
    """Gera uma miniatura isométrica vetorial de alta definição para o módulo."""
    if module_id in _THUMBNAIL_CACHE:
        return _THUMBNAIL_CACHE[module_id]

    pix = QPixmap(130, 130)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    # Cartão de fundo suave com borda arredondada
    p.setPen(QPen(QColor("#CBD5E1"), 1.2))
    p.setBrush(QBrush(QColor("#F8FAFC")))
    p.drawRoundedRect(4, 4, 122, 122, 8, 8)

    pen_dark = QPen(QColor("#334155"), 1.8)
    pen_detail = QPen(QColor("#94A3B8"), 1.2)
    brush_white = QBrush(QColor("#FFFFFF"))
    brush_shaded = QBrush(QColor("#F1F5F9"))
    brush_inner = QBrush(QColor("#E2E8F0"))
    brush_handle = QBrush(QColor("#475569"))
    brush_plinth = QBrush(QColor("#94A3B8"))

    p.setPen(pen_dark)

    if module_id == "balcao":
        # ── Balcão com 2 Portas ── Destaque: AZUL PETRÓLEO / Portas entreabertas + Prateleira ──
        accent = QColor("#0369A1")          # Sky 700
        accent_light = QColor("#F0F9FF")    # Sky 50
        p.setBrush(brush_plinth)
        p.drawRect(28, 100, 74, 10)  # rodapé
        p.setBrush(QBrush(accent_light))
        p.drawRect(26, 26, 78, 74)  # carcaça interna
        # Travessas superiores em destaque
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#BAE6FD")))
        p.drawRect(28, 27, 74, 5)
        # Prateleira interna com louças/panelas
        p.setPen(QPen(accent, 1.4))
        p.setBrush(QBrush(QColor("#BAE6FD")))
        p.drawRect(27, 60, 76, 4)
        # Objetos na prateleira
        p.fillRect(36, 51, 16, 9, QColor("#7DD3FC"))
        p.fillRect(58, 49, 22, 11, QColor("#38BDF8"))
        # Fundo inferior: pilhas de pratos
        p.fillRect(40, 85, 20, 8, QColor("#7DD3FC"))
        p.fillRect(66, 83, 18, 10, QColor("#38BDF8"))
        # Portas entreabertas em perspectiva
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(26, 26), QPoint(12, 33), QPoint(12, 97), QPoint(26, 94)])
        p.drawPolygon([QPoint(104, 26), QPoint(118, 33), QPoint(118, 97), QPoint(104, 94)])
        # Puxadores verticais modernos nas portas
        p.setBrush(QBrush(accent))
        p.drawRect(14, 52, 3, 16)
        p.drawRect(113, 52, 3, 16)
        # Badge "2 PORTAS"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(28, 101, 74, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(28, 101, 74, 11, Qt.AlignCenter, "2 PORTAS")

    elif module_id == "balcao_pia":
        # ── Balcão de Pia ── Destaque: CIANO / Cuba inox embutida + Torneira monocomando ──
        accent = QColor("#0E7490")          # Cyan 700
        accent_light = QColor("#ECFEFF")    # Cyan 50
        p.setBrush(brush_plinth)
        p.drawRect(28, 100, 74, 10)  # rodapé
        p.setBrush(QBrush(accent_light))
        p.drawRect(26, 26, 78, 74)  # carcaça interna
        # Cuba de inox embutida no topo
        p.setPen(QPen(QColor("#475569"), 1.2))
        p.setBrush(QBrush(QColor("#CBD5E1")))
        p.drawRoundedRect(36, 26, 58, 22, 3, 3)
        p.setBrush(QBrush(QColor("#94A3B8")))
        p.drawRoundedRect(42, 30, 46, 14, 2, 2)
        # Válvula / Ralo no centro da cuba
        p.setBrush(QBrush(QColor("#64748B")))
        p.drawEllipse(62, 35, 6, 4)
        # Torneira curva monocomando elegante sobre a cuba
        p.setPen(QPen(QColor("#334155"), 2.2))
        p.drawLine(65, 26, 65, 14)
        p.drawLine(65, 14, 57, 16)
        p.drawLine(57, 16, 57, 19)
        # Vão livre sob a pia para sifão / hidráulica
        p.setPen(QPen(QColor("#0891B2"), 1.4))
        p.drawLine(65, 48, 65, 66)
        p.drawArc(59, 64, 12, 12, 0, 180 * 16)
        p.drawLine(59, 70, 59, 82)
        # Portas entreabertas
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(26, 26), QPoint(12, 33), QPoint(12, 97), QPoint(26, 94)])
        p.drawPolygon([QPoint(104, 26), QPoint(118, 33), QPoint(118, 97), QPoint(104, 94)])
        p.setBrush(QBrush(accent))
        p.drawRect(14, 52, 3, 16)
        p.drawRect(113, 52, 3, 16)
        # Badge "PIA INOX"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(30, 101, 70, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(30, 101, 70, 11, Qt.AlignCenter, "PIA INOX")

    elif module_id == "gaveteiro":
        # ── Balcão Gaveteiro ── Destaque: LARANJA / 4 Gavetas com corrediças visíveis ──
        accent = QColor("#C2410C")          # Orange 700
        accent_light = QColor("#FFF7ED")    # Orange 50
        p.setBrush(brush_plinth)
        p.drawRect(34, 100, 62, 10)  # rodapé
        p.setBrush(QBrush(accent_light))
        p.drawRect(28, 22, 74, 78)   # carcaça
        # 4 Gavetas estilizadas com frentes em branco e puxadores horizontais largos
        p.setPen(pen_dark)
        for i in range(4):
            yg = 24 + (i * 18)
            p.setBrush(brush_white)
            p.drawRect(30, yg, 70, 16)
            # Puxador perfil/barra horizontal na cor de destaque
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(accent))
            p.drawRoundedRect(47, yg + 6, 36, 4, 1, 1)
            p.setPen(pen_dark)
        # Badge "GAVETEIRO"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(28, 101, 74, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(28, 101, 74, 11, Qt.AlignCenter, "GAVETEIRO")

    elif module_id == "balcao_misto":
        # ── Balcão Misto ── Destaque: VIOLETA / Gaveteiro 4G + 2 Portas conjugados ──
        accent = QColor("#7C3AED")          # Violet 600
        accent_light = QColor("#F5F3FF")    # Violet 50
        p.setBrush(brush_plinth)
        p.drawRect(18, 100, 94, 10)  # rodapé largo
        p.setBrush(QBrush(accent_light))
        p.drawRect(14, 24, 102, 76)  # carcaça total
        # Divisória vertical intermediária espessa
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#DDD6FE")))
        p.drawRect(51, 24, 4, 76)
        # Esquerda: 4 Gavetas
        p.setPen(pen_dark)
        for i in range(4):
            yg = 26 + (i * 17)
            p.setBrush(brush_white)
            p.drawRect(16, yg, 34, 15)
            p.setPen(Qt.NoPen)
            p.setBrush(QBrush(accent))
            p.drawRoundedRect(24, yg + 6, 18, 3, 1, 1)
            p.setPen(pen_dark)
        # Direita: 2 Portas com puxadores verticais
        p.setBrush(brush_white)
        p.drawRect(57, 26, 27, 72)
        p.drawRect(86, 26, 27, 72)
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRect(80, 48, 3, 16)
        p.drawRect(89, 48, 3, 16)
        # Badge "MISTO (4G+2P)"
        p.drawRoundedRect(22, 101, 86, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(22, 101, 86, 11, Qt.AlignCenter, "MISTO (4G+2P)")

    elif module_id == "balcao_canto":
        # ── Balcão Canto Reto (L Cego) ── Destaque: ÂMBAR / Montante cego frontal + Porta ──
        accent = QColor("#B45309")          # Amber 700
        accent_light = QColor("#FFFBEB")    # Amber 50
        p.setBrush(brush_plinth)
        p.drawRect(24, 100, 82, 10)  # rodapé
        p.setBrush(QBrush(accent_light))
        p.drawRect(20, 26, 90, 74)   # carcaça interna
        # Montante Cego frontal à direita (simbolizando encaixe perpendicular da outra bancada)
        p.setPen(pen_dark)
        p.setBrush(QBrush(QColor("#FDE68A")))
        p.drawRect(78, 26, 30, 74)
        p.setPen(QPen(accent, 1.2, Qt.DashLine))
        p.drawRect(81, 29, 24, 68)
        # Porta de acesso à esquerda aberta em ângulo
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(22, 26), QPoint(10, 33), QPoint(10, 97), QPoint(22, 94)])
        p.setBrush(QBrush(accent))
        p.drawRect(12, 52, 3, 16)
        # Prateleira interna no vão livre
        p.setPen(QPen(QColor("#F59E0B"), 1.4))
        p.drawLine(21, 62, 77, 62)
        p.fillRect(34, 52, 18, 10, QColor("#FCD34D"))
        # Badge "CANTO CEGO"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(26, 101, 78, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(26, 101, 78, 11, Qt.AlignCenter, "CANTO CEGO")

    elif module_id == "balcao_canto_l":
        # ── Balcão Canto L (90°) ── Destaque: ESMERALDA / Geometria em L com coluna de quina ──
        accent = QColor("#047857")          # Emerald 700
        accent_light = QColor("#ECFDF5")    # Emerald 50
        p.setBrush(brush_plinth)
        p.drawRect(24, 100, 82, 10)
        # Desenho isométrico esquemático das duas asas em L
        p.setBrush(QBrush(accent_light))
        p.setPen(pen_dark)
        p.drawRect(20, 26, 90, 74)
        # Coluna / Batente de quina 90° no encontro das asas
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#A7F3D0")))
        p.drawRect(61, 26, 8, 74)
        # Duas portas articuladas em 90° entreabertas
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        # Porta asa esquerda
        p.drawPolygon([QPoint(20, 26), QPoint(10, 33), QPoint(10, 97), QPoint(20, 94)])
        # Porta asa direita
        p.drawPolygon([QPoint(110, 26), QPoint(120, 33), QPoint(120, 97), QPoint(110, 94)])
        # Puxadores
        p.setBrush(QBrush(accent))
        p.drawRect(12, 52, 3, 16)
        p.drawRect(117, 52, 3, 16)
        # Prateleira contínua em L
        p.setPen(QPen(QColor("#10B981"), 1.4))
        p.drawLine(21, 62, 109, 62)
        p.fillRect(40, 52, 16, 10, QColor("#6EE7B7"))
        p.fillRect(74, 52, 16, 10, QColor("#6EE7B7"))
        # Badge "CANTO EM L"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(28, 101, 74, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(28, 101, 74, 11, Qt.AlignCenter, "CANTO EM L")

    elif module_id == "porta_tempero":
        # ── Porta-Tempero / Garrafeiro ── Destaque: ROSA / Estreito com aramado e garrafas ──
        accent = QColor("#BE185D")          # Pink 700
        accent_light = QColor("#FDF2F8")    # Pink 50
        p.setBrush(brush_plinth)
        p.drawRect(44, 100, 42, 10)  # rodapé estreito
        p.setBrush(QBrush(accent_light))
        p.drawRect(38, 22, 54, 78)   # carcaça estreita
        # Frente/Bandeja deslizante com corrediça
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawRect(40, 24, 50, 74)
        # Puxador perfil vertical proeminente
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(62, 34, 6, 32, 2, 2)
        # Prateleiras aramadas e garrafas/potes ilustrados
        p.setPen(QPen(QColor("#F472B6"), 1.4))
        p.drawLine(42, 72, 88, 72)
        p.drawLine(42, 90, 88, 90)
        # Garrafas/temperos
        p.fillRect(46, 75, 8, 14, QColor("#FBCFE8"))
        p.fillRect(58, 75, 8, 14, QColor("#F472B6"))
        p.fillRect(70, 75, 8, 14, QColor("#DB2777"))
        # Badge "TEMPEROS"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(30, 101, 70, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(30, 101, 70, 11, Qt.AlignCenter, "TEMPEROS")

    elif module_id == "balcao_forno":
        # ── Balcão Forno Embutido ── Destaque: VERMELHO FOGO / Nicho de forno com vidro + Gavetão ──
        accent = QColor("#DC2626")          # Red 600
        accent_light = QColor("#FEF2F2")    # Red 50
        p.setBrush(brush_plinth)
        p.drawRect(28, 100, 74, 10)  # rodapé
        p.setBrush(QBrush(accent_light))
        p.drawRect(26, 24, 78, 76)   # carcaça interna
        # Travessas superiores reforçadas
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#FECACA")))
        p.drawRect(28, 25, 74, 5)

        # Nicho do Forno de Embutir (painel de vidro escuro + visor + puxador metálico)
        p.setPen(pen_dark)
        p.setBrush(QBrush(QColor("#1E293B")))  # corpo escuro do forno
        p.drawRoundedRect(30, 31, 70, 42, 2, 2)
        # Visor central de vidro temperado
        p.setBrush(QBrush(QColor("#0F172A")))
        p.drawRect(36, 41, 58, 26)
        # Grelha interna iluminada (linhas douradas sutis)
        p.setPen(QPen(QColor("#F59E0B"), 1.0))
        p.drawLine(40, 52, 90, 52)
        p.drawLine(40, 58, 90, 58)
        # Puxador tubular largo do forno
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#E2E8F0")))
        p.drawRoundedRect(42, 34, 46, 3, 1, 1)

        # Base de apoio / Prateleira estrutural sob o forno
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#FCA5A5")))
        p.drawRect(28, 74, 74, 4)

        # Gavetão Inferior para formas e panelas
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawRect(28, 79, 74, 19)
        # Puxador horizontal do gavetão
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(48, 87, 34, 3, 1, 1)

        # Badge "FORNO EMBUT."
        p.drawRoundedRect(24, 101, 82, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(24, 101, 82, 11, Qt.AlignCenter, "FORNO EMBUT.")

    elif module_id == "aereo":
        p.setBrush(brush_inner)
        p.drawRect(26, 28, 78, 68)
        p.setPen(pen_detail)
        p.drawLine(27, 62, 103, 62)
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(26, 28), QPoint(14, 35), QPoint(14, 98), QPoint(26, 96)])
        p.drawPolygon([QPoint(104, 28), QPoint(116, 35), QPoint(116, 98), QPoint(104, 96)])

    elif module_id == "aereo_basculante":
        p.setBrush(brush_inner)
        p.drawRect(20, 52, 90, 46)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(20, 52), QPoint(22, 28), QPoint(108, 28), QPoint(110, 52)])
        p.setBrush(brush_handle)
        p.drawRect(55, 33, 20, 3)

    elif module_id == "aereo_basculante_duplo":
        p.setBrush(brush_shaded)
        p.drawRect(26, 22, 78, 80)
        p.setBrush(brush_white)
        p.drawRect(27, 23, 76, 38)
        p.drawRect(27, 63, 76, 38)
        p.setBrush(brush_handle)
        p.drawRect(55, 54, 20, 3)
        p.drawRect(55, 94, 20, 3)

    elif module_id == "aereo_microondas":
        p.setBrush(brush_shaded)
        p.drawRect(28, 20, 74, 84)
        p.setBrush(brush_white)
        p.drawRect(29, 21, 72, 36)
        p.setBrush(brush_handle)
        p.drawRect(55, 50, 20, 3)
        p.setBrush(brush_inner)
        p.drawRect(29, 60, 72, 43)
        p.setBrush(QBrush(QColor("#475569")))
        p.drawRect(37, 68, 42, 26)
        p.setBrush(QBrush(QColor("#94A3B8")))
        p.drawRect(81, 68, 14, 26)

    elif module_id == "torre_quente":
        p.setBrush(brush_plinth)
        p.drawRect(40, 110, 50, 8)
        p.setBrush(brush_shaded)
        p.drawRect(36, 12, 58, 98)
        p.setBrush(brush_white)
        p.drawRect(37, 13, 56, 26)
        p.setBrush(brush_inner)
        p.drawRect(37, 42, 56, 22)
        p.setBrush(QBrush(QColor("#334155")))
        p.drawRect(39, 67, 52, 24)
        p.setBrush(brush_white)
        p.drawRect(37, 94, 56, 8)
        p.drawRect(37, 102, 56, 8)

    elif module_id == "caixa_geladeira":
        # ── Caixa para Geladeira: Laterais até o chão, armário superior e silhueta de geladeira inox ──
        # Laterais e topo da caixa de marcenaria (contorno)
        p.setPen(pen_dark)
        p.setBrush(brush_shaded)
        p.drawRect(30, 10, 68, 108)

        # Armário superior (maleiro com 2 portas)
        p.setBrush(brush_white)
        p.drawRect(33, 13, 30, 24)
        p.drawRect(65, 13, 30, 24)
        # Puxadores do maleiro
        p.setBrush(brush_handle)
        p.drawRect(60, 22, 2, 7)
        p.drawRect(66, 22, 2, 7)

        # Divisória estrutural horizontal
        p.setBrush(brush_shaded)
        p.drawRect(31, 37, 66, 3)

        # Vão da geladeira (área de encaixe / silhueta de refrigerador inox)
        p.setBrush(QBrush(QColor("#E2E8F0")))
        p.drawRect(34, 42, 60, 76)
        # Corpo da geladeira (cinza inox metálico suave)
        p.setBrush(QBrush(QColor("#CBD5E1")))
        p.setPen(QPen(QColor("#94A3B8"), 1.2))
        p.drawRoundedRect(37, 45, 54, 73, 2, 2)
        # Divisão freezer / refrigerador duplex
        p.drawLine(37, 68, 91, 68)
        # Puxadores da geladeira
        p.setBrush(QBrush(QColor("#64748B")))
        p.setPen(Qt.NoPen)
        p.drawRoundedRect(40, 52, 2, 10, 1, 1)
        p.drawRoundedRect(40, 74, 2, 16, 1, 1)
        # Reset pen
        p.setPen(pen_dark)

    elif module_id == "roupeiro":
        # ── Armário Cabideiro ── Destaque: AZUL MARINHO / Varão proeminente ──
        accent = QColor("#1E40AF")
        accent_light = QColor("#DBEAFE")
        p.setBrush(brush_plinth)
        p.drawRect(28, 110, 74, 8)
        # Fundo interno azul-claro
        p.setBrush(QBrush(accent_light))
        p.drawRect(28, 12, 74, 98)
        # Maleiro superior com faixa de destaque
        p.setBrush(QBrush(QColor("#BFDBFE")))
        p.drawRect(29, 13, 72, 22)
        p.setPen(QPen(accent, 1.6))
        p.drawLine(29, 35, 101, 35)
        # Varão cabideiro GROSSO e visível (principal diferenciador)
        p.setPen(QPen(accent, 3.0))
        p.drawLine(34, 46, 96, 46)
        # Suportes do varão
        p.setPen(QPen(QColor("#3B82F6"), 2.0))
        p.drawLine(34, 38, 34, 46)
        p.drawLine(96, 38, 96, 46)
        # Cabides grandes e visíveis (triângulos)
        p.setPen(QPen(QColor("#2563EB"), 1.6))
        for x_cab in (44, 58, 72, 86):
            p.drawLine(x_cab, 46, x_cab - 7, 58)
            p.drawLine(x_cab - 7, 58, x_cab + 7, 58)
            p.drawLine(x_cab + 7, 58, x_cab, 46)
            # Roupas penduradas (retângulos coloridos)
            p.fillRect(x_cab - 5, 59, 10, 24, QColor("#93C5FD"))
        # Sapateira inferior
        p.setPen(QPen(accent, 1.4))
        p.drawLine(29, 92, 101, 92)
        p.fillRect(35, 94, 26, 6, QColor("#BFDBFE"))
        p.fillRect(67, 94, 26, 6, QColor("#BFDBFE"))
        # Portas entreabertas azuis
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(28, 12), QPoint(14, 18), QPoint(14, 112), QPoint(28, 106)])
        p.drawPolygon([QPoint(102, 12), QPoint(116, 18), QPoint(116, 112), QPoint(102, 106)])
        p.setBrush(QBrush(accent))
        p.drawRect(16, 56, 3, 14)
        p.drawRect(111, 56, 3, 14)
        # Badge "CABIDEIRO"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(30, 102, 70, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(30, 102, 70, 11, Qt.AlignCenter, "CABIDEIRO")

    elif module_id in ("armario_prateleiras", "armario_2p_prat"):
        # ── Armário Prateleiras ── Destaque: VERDE / Prateleiras grossas ──
        accent = QColor("#166534")
        accent_light = QColor("#DCFCE7")
        p.setBrush(brush_plinth)
        p.drawRect(28, 110, 74, 8)
        # Fundo interno verde-claro
        p.setBrush(QBrush(accent_light))
        p.drawRect(28, 12, 74, 98)
        # 5 Prateleiras GROSSAS e coloridas (principal diferenciador)
        p.setPen(QPen(accent, 1.4))
        for i, y_p in enumerate((26, 42, 58, 74, 90)):
            # Prateleira grossa
            p.setBrush(QBrush(QColor("#BBF7D0")))
            p.drawRect(29, y_p, 72, 4)
            # Objetos variados sobre cada prateleira
            if i % 2 == 0:
                p.fillRect(36, y_p - 10, 18, 10, QColor("#86EFAC"))
                p.fillRect(60, y_p - 8, 14, 8, QColor("#4ADE80"))
            else:
                p.fillRect(40, y_p - 12, 12, 12, QColor("#86EFAC"))
                p.fillRect(58, y_p - 9, 20, 9, QColor("#4ADE80"))
        # Portas entreabertas
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(28, 12), QPoint(14, 18), QPoint(14, 112), QPoint(28, 106)])
        p.drawPolygon([QPoint(102, 12), QPoint(116, 18), QPoint(116, 112), QPoint(102, 106)])
        p.setBrush(QBrush(accent))
        p.drawRect(16, 56, 3, 14)
        p.drawRect(111, 56, 3, 14)
        # Badge "PRATELEIRAS"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(26, 102, 78, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(26, 102, 78, 11, Qt.AlignCenter, "PRATELEIRAS")

    elif module_id == "armario_2p_divisao":
        # ── Armário 2P Divisória ── Destaque: LARANJA / Divisória central grossa ──
        accent = QColor("#9A3412")
        accent_light = QColor("#FFF7ED")
        p.setBrush(brush_plinth)
        p.drawRect(26, 110, 78, 8)
        # Fundo interno laranja-claro
        p.setBrush(QBrush(accent_light))
        p.drawRect(26, 12, 78, 98)
        # Divisória central GROSSA e colorida (principal diferenciador)
        p.setBrush(QBrush(QColor("#EA580C")))
        p.setPen(Qt.NoPen)
        p.drawRect(62, 12, 6, 98)
        # Lado esquerdo: prateleiras com roupas dobradas
        p.setPen(QPen(QColor("#FB923C"), 1.4))
        for y_p in (33, 53, 73, 91):
            p.drawLine(27, y_p, 62, y_p)
            p.fillRect(32, y_p - 7, 24, 6, QColor("#FED7AA"))
        # Lado direito: varão + cabides
        p.setPen(QPen(QColor("#FB923C"), 1.2))
        p.drawLine(68, 33, 103, 33)
        p.setPen(QPen(QColor("#EA580C"), 2.4))
        p.drawLine(68, 44, 103, 44)
        p.setPen(QPen(QColor("#C2410C"), 1.4))
        for x_cab in (76, 88, 98):
            p.drawLine(x_cab, 44, x_cab - 5, 54)
            p.drawLine(x_cab - 5, 54, x_cab + 5, 54)
            p.drawLine(x_cab + 5, 54, x_cab, 44)
            p.fillRect(x_cab - 4, 55, 8, 16, QColor("#FDBA74"))
        # Portas entreabertas
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(26, 12), QPoint(12, 18), QPoint(12, 112), QPoint(26, 106)])
        p.drawPolygon([QPoint(104, 12), QPoint(118, 18), QPoint(118, 112), QPoint(104, 106)])
        p.setBrush(QBrush(accent))
        p.drawRect(14, 56, 3, 14)
        p.drawRect(113, 56, 3, 14)
        # Badge "2P DIVISÃO"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(28, 102, 74, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(28, 102, 74, 11, Qt.AlignCenter, u"2P DIVIS\u00c3O")

    elif module_id == "armario_1p_prat":
        # ── Armário 1P Estreito Prateleiras ── Destaque: ROXO / Estreito ──
        accent = QColor("#6B21A8")
        accent_light = QColor("#F5F3FF")
        p.setBrush(brush_plinth)
        p.drawRect(44, 110, 42, 8)
        # Fundo interno roxo-claro
        p.setBrush(QBrush(accent_light))
        p.drawRect(44, 12, 42, 98)
        # 5 prateleiras roxas
        p.setPen(QPen(accent, 1.2))
        for y_p in (28, 44, 60, 76, 92):
            p.setBrush(QBrush(QColor("#E9D5FF")))
            p.drawRect(45, y_p, 40, 3)
            p.fillRect(52, y_p - 6, 20, 5, QColor("#D8B4FE"))
        # 1 Porta entreaberta à esquerda
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(44, 12), QPoint(24, 20), QPoint(24, 112), QPoint(44, 106)])
        p.setBrush(QBrush(accent))
        p.drawRect(41, 56, 3, 14)
        # Badge "1P PRAT"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(38, 102, 54, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(38, 102, 54, 11, Qt.AlignCenter, "1P PRAT")

    elif module_id == "armario_1p_cabide":
        # ── Armário 1P Estreito Cabideiro ── Destaque: CIANO / Varão + roupa ──
        accent = QColor("#0E7490")
        accent_light = QColor("#ECFEFF")
        p.setBrush(brush_plinth)
        p.drawRect(44, 110, 42, 8)
        # Fundo interno ciano-claro
        p.setBrush(QBrush(accent_light))
        p.drawRect(44, 12, 42, 98)
        # Maleiro superior
        p.setPen(QPen(accent, 1.4))
        p.drawLine(45, 34, 85, 34)
        p.fillRect(45, 14, 40, 19, QColor("#CFFAFE"))
        # Varão grosso
        p.setPen(QPen(accent, 3.0))
        p.drawLine(47, 46, 83, 46)
        # Cabide grande com roupa pendurada
        p.setPen(QPen(QColor("#0891B2"), 1.6))
        p.drawLine(65, 46, 55, 56)
        p.drawLine(55, 56, 75, 56)
        p.drawLine(75, 56, 65, 46)
        p.fillRect(57, 57, 16, 26, QColor("#67E8F9"))
        # Sapateira inferior
        p.setPen(QPen(accent, 1.2))
        p.drawLine(45, 92, 85, 92)
        p.fillRect(50, 94, 30, 6, QColor("#A5F3FC"))
        # 1 Porta entreaberta à direita
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(86, 12), QPoint(106, 20), QPoint(106, 112), QPoint(86, 106)])
        p.setBrush(QBrush(accent))
        p.drawRect(88, 56, 3, 14)
        # Badge "1P CABID"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(38, 102, 54, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(38, 102, 54, 11, Qt.AlignCenter, "1P CABID")

    elif module_id == "armario_3p_divisao":
        # ── Armário 3 Portas Misto ── Destaque: VERMELHO ESCURO / Largo com 2 divisórias ──
        accent = QColor("#991B1B")
        accent_light = QColor("#FEF2F2")
        p.setBrush(brush_plinth)
        p.drawRect(16, 110, 98, 8)
        # Fundo interno rosado-claro
        p.setBrush(QBrush(accent_light))
        p.drawRect(16, 12, 98, 98)
        # 2 divisórias verticais GROSSAS e vermelhas (principal diferenciador)
        p.setBrush(QBrush(QColor("#DC2626")))
        p.setPen(Qt.NoPen)
        p.drawRect(47, 12, 5, 98)
        p.drawRect(80, 12, 5, 98)
        # Esquerda: 3 prateleiras
        p.setPen(QPen(QColor("#F87171"), 1.2))
        for y_p in (34, 58, 82):
            p.drawLine(17, y_p, 47, y_p)
            p.fillRect(22, y_p - 8, 18, 7, QColor("#FECACA"))
        # Centro: maleiro + varão cabideiro + 2 gavetas
        p.setPen(QPen(QColor("#F87171"), 1.2))
        p.drawLine(52, 34, 80, 34)
        p.setPen(QPen(QColor("#DC2626"), 2.4))
        p.drawLine(52, 44, 80, 44)
        # Gavetas na base do centro
        p.setPen(pen_dark)
        p.setBrush(QBrush(QColor("#FEE2E2")))
        p.drawRect(52, 84, 28, 12)
        p.drawRect(52, 97, 28, 12)
        p.setBrush(QBrush(accent))
        p.drawRect(63, 89, 6, 2)
        p.drawRect(63, 102, 6, 2)
        # Direita: 3 prateleiras
        p.setPen(QPen(QColor("#F87171"), 1.2))
        for y_p in (34, 58, 82):
            p.drawLine(85, y_p, 113, y_p)
            p.fillRect(90, y_p - 8, 18, 7, QColor("#FECACA"))
        # 3 Portas entreabertas
        p.setPen(pen_dark)
        p.setBrush(brush_white)
        p.drawPolygon([QPoint(16, 12), QPoint(6, 18), QPoint(6, 112), QPoint(16, 106)])
        p.drawPolygon([QPoint(114, 12), QPoint(124, 18), QPoint(124, 112), QPoint(114, 106)])
        p.drawPolygon([QPoint(66, 12), QPoint(54, 18), QPoint(54, 112), QPoint(66, 106)])
        p.setBrush(QBrush(accent))
        p.drawRect(8, 56, 2, 14)
        p.drawRect(120, 56, 2, 14)
        p.drawRect(56, 56, 2, 14)
        # Badge "3P MISTO"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(accent))
        p.drawRoundedRect(24, 102, 82, 11, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(24, 102, 82, 11, Qt.AlignCenter, "3P MISTO")

    elif module_id == "gabinete_banheiro":
        p.setBrush(brush_white)
        p.drawRect(48, 28, 34, 9)  # cuba
        p.setBrush(brush_shaded)
        p.drawRect(26, 38, 78, 58)
        p.setBrush(brush_white)
        p.drawRect(27, 39, 76, 27)
        p.drawRect(27, 68, 76, 27)
        p.setBrush(brush_handle)
        p.drawRect(48, 60, 34, 3)
        p.drawRect(48, 89, 34, 3)

    elif module_id == "nicho":
        p.setBrush(QBrush(QColor("#E2E8F0")))
        p.drawRect(26, 34, 78, 60)
        p.setBrush(QBrush(QColor("#F8FAFC")))
        p.drawRect(32, 40, 66, 48)
        p.setPen(pen_detail)
        p.drawLine(32, 64, 98, 64)

    elif module_id == "bancada_reta":
        # ── Bancada Reta de Pedra ── Granito Preto / Mármore com Frontão e Saia ──
        p.setBrush(QBrush(QColor("#0F172A")))  # Frontão preto/grafite
        p.drawRect(24, 38, 82, 12)
        p.setBrush(QBrush(QColor("#1E293B")))  # Tampo superior
        p.drawRect(22, 50, 86, 18)
        p.setBrush(QBrush(QColor("#334155")))  # Saia frontal engrossada
        p.drawRect(22, 68, 86, 12)
        # Brilho de polimento no tampo
        p.setPen(QPen(QColor("#94A3B8"), 1.0))
        p.drawLine(26, 54, 104, 54)
        # Badge "PEDRA"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#475569")))
        p.drawRoundedRect(36, 96, 58, 12, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(36, 96, 58, 12, Qt.AlignCenter, "BANCADA")

    elif module_id == "bancada_pia":
        # ── Bancada de Pia com Cuba ── Tampo + Cuba Inox + Torneira ──
        p.setBrush(QBrush(QColor("#0F172A")))  # Frontão
        p.drawRect(24, 32, 82, 12)
        p.setBrush(QBrush(QColor("#1E293B")))  # Tampo
        p.drawRect(22, 44, 86, 26)
        # Cuba Inox no centro
        p.setBrush(QBrush(QColor("#94A3B8")))
        p.setPen(QPen(QColor("#CBD5E1"), 1.4))
        p.drawRoundedRect(44, 48, 42, 18, 2, 2)
        # Ralo da cuba
        p.setBrush(QBrush(QColor("#475569")))
        p.drawEllipse(62, 55, 6, 4)
        # Torneira
        p.setPen(QPen(QColor("#E2E8F0"), 2.2))
        p.drawLine(65, 34, 65, 46)
        p.drawLine(65, 34, 60, 37)
        # Saia
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#334155")))
        p.drawRect(22, 70, 86, 12)
        # Badge "PIA / CUBA"
        p.setBrush(QBrush(QColor("#0284C7")))
        p.drawRoundedRect(34, 96, 62, 12, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(34, 96, 62, 12, Qt.AlignCenter, "PIA CUBA")

    elif module_id in ("bancada_canto_l", "bancada_canto"):
        # ── Bancada de Canto em L ── Formato em L com frontão nas paredes ──
        p.setBrush(QBrush(QColor("#0F172A")))  # Frontão em L
        p.drawRect(24, 28, 80, 10)
        p.drawRect(24, 38, 10, 70)
        p.setBrush(QBrush(QColor("#1E293B")))  # Tampo em L
        # Asa horizontal
        p.drawRect(24, 38, 80, 26)
        # Asa vertical
        p.drawRect(24, 64, 32, 44)
        # Saias
        p.setBrush(QBrush(QColor("#334155")))
        p.drawRect(56, 64, 48, 10)
        p.drawRect(56, 74, 10, 34)
        # Badge "CANTO L"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#475569")))
        p.drawRoundedRect(36, 96, 58, 12, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(36, 96, 58, 12, Qt.AlignCenter, "CANTO L")

    elif module_id == "bancada_ilha":
        # ── Ilha Gourmet ── Ampla com saia 360 e efeito mármore ──
        p.setBrush(QBrush(QColor("#334155")))
        p.drawRect(20, 42, 90, 40)
        p.setBrush(QBrush(QColor("#F8FAFC")))  # Quartzo Calacatta claro
        p.setPen(QPen(QColor("#CBD5E1"), 1.2))
        p.drawRect(18, 36, 94, 28)
        # Veios dourados/cinzas do mármore
        p.setPen(QPen(QColor("#94A3B8"), 1.0))
        p.drawLine(30, 42, 60, 52)
        p.drawLine(70, 40, 95, 56)
        # Saia
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#E2E8F0")))
        p.drawRect(18, 64, 94, 16)
        # Badge "ILHA GOURMET"
        p.setBrush(QBrush(QColor("#475569")))
        p.drawRoundedRect(30, 96, 70, 12, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
    elif module_id in ("peca_tampo_engrossado", "tampo_engrossado"):
        # ── Tampo Engrossado ── Chapa de topo + testeira perimetral de engrosso ──
        # Chapa superior
        p.setBrush(QBrush(QColor("#B45309")))  # Tom amadeirado quente ou laca
        p.setPen(QPen(QColor("#78350F"), 1.2))
        p.drawRect(20, 42, 88, 18)
        # Borda frontal de engrosso (dupla espessura)
        p.setBrush(QBrush(QColor("#92400E")))
        p.drawRect(20, 60, 88, 22)
        # Linha de divisão sutil entre chapa e engrosso
        p.setPen(QPen(QColor("#FDE68A"), 1.0))
        p.drawLine(20, 60, 108, 60)
        # Linhas de réguas inferiores laterais
        p.setPen(QPen(QColor("#78350F"), 1.0))
        p.drawLine(34, 60, 34, 82)
        p.drawLine(94, 60, 94, 82)
        # Badge "ENGROSSO"
        p.setPen(Qt.NoPen)
        p.setBrush(QBrush(QColor("#B45309")))
        p.drawRoundedRect(28, 96, 72, 12, 3, 3)
        font = p.font()
        font.setPointSize(6)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(28, 96, 72, 12, Qt.AlignCenter, "ENGROSSO")

    p.end()
    icon = QIcon(pix)
    _THUMBNAIL_CACHE[module_id] = icon
    return icon


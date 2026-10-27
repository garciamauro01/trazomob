# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Barra de Ferramentas com Abas de Módulos (Ribbon/Dock Toolbar) para TrazoMob.

Exibe os módulos de marcenaria e design de interiores agrupados por abas temáticas:
- Cozinha (Inferiores, Aéreos, Torres)
- Dormitório / Quarto (Roupeiros, Cabideiros, Sapateiras)
- Banheiro (Gabinetes suspensos, Nichos)
- Nichos & Estantes
- Marmoraria & Pias
- Peças Avulsas

Permite inserir o módulo diretamente na cena no ponto correto (ao lado do anterior ou na origem)
em um único clique, abrindo imediatamente seus parâmetros na barra lateral.
"""
from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import QSize, Qt, QTimer, Signal
from PySide6.QtGui import QIcon, QKeySequence, QVector3D
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTabWidget,
    QToolBar,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from core.group import Group, iter_placements
from core.history import SnapshotImport
from core.i18n import tr
from core.paths import app_root
from .builder import CabinetBuilder
from .catalog import MODULE_CATALOG
from .icons import get_module_thumbnail



def get_module_carcass_bounds(mod: Group) -> tuple[float, float, float, float, float, float] | None:
    """Calcula os limites em metros da caixaria (min_x, max_x, min_y, max_y, min_z, max_z)."""
    min_x, max_x = float("inf"), float("-inf")
    min_y, max_y = float("inf"), float("-inf")
    min_z, max_z = float("inf"), float("-inf")
    found = False
    tipo = ""
    if getattr(mod, "ext", None) and isinstance(mod.ext, dict) and "trazomob_module" in mod.ext:
        tipo = str(mod.ext["trazomob_module"].get("tipo", ""))
    ignore_terms = ("Puxador", "Perfil", "Base Projetada") if tipo == "peca_porta" else ("Porta", "Frente", "Puxador", "Perfil", "Base Projetada")
    for pg, m in iter_placements(mod):
        nome = getattr(pg, "name", "")
        if any(ign in nome for ign in ignore_terms):
            continue
        mesh = getattr(pg, "mesh", None)
        if mesh is not None and getattr(mesh, "vertices", None):
            for v in mesh.vertices:
                p = getattr(v, "position", v)
                if m is not None:
                    p = m.map(p)
                min_x, max_x = min(min_x, p.x()), max(max_x, p.x())
                min_y, max_y = min(min_y, p.y()), max(max_y, p.y())
                min_z, max_z = min(min_z, p.z()), max(max_z, p.z())
                found = True
    if not found:
        # Fallback de segurança: calcula com todos os vértices do módulo se os nomes divergirem
        for pg, m in iter_placements(mod):
            mesh = getattr(pg, "mesh", None)
            if mesh is not None and getattr(mesh, "vertices", None):
                for v in mesh.vertices:
                    p = getattr(v, "position", v)
                    if m is not None:
                        p = m.map(p)
                    min_x, max_x = min(min_x, p.x()), max(max_x, p.x())
                    min_y, max_y = min(min_y, p.y()), max(max_y, p.y())
                    min_z, max_z = min(min_z, p.z()), max(max_z, p.z())
                    found = True

    if not found:
        return None
    return (min_x, max_x, min_y, max_y, min_z, max_z)


def get_module_back_normal(rot_z_deg: float) -> QVector3D:
    """Retorna o vetor unitário apontando para a traseira/fundo do módulo no plano XY."""
    rad = math.radians(rot_z_deg % 360.0)
    # No construtor (rot_z=0), a traseira fica em +Y
    # Rotacionando em Z por 'rot_z':
    # x' = -sin(rot)
    # y' = cos(rot)
    return QVector3D(-math.sin(rad), math.cos(rad), 0.0).normalized()


def preserve_module_back_alignment(old_mod: Group, new_mod: Group, rot_z_deg: float) -> None:
    """Ajusta new_mod para que sua quina traseira-esquerda e sua base Z permaneçam rigorosamente no mesmo ponto de old_mod.

    Isso garante que ao alterar largura, profundidade, altura ou se o móvel tiver sido movido/rotacionado
    no 3D (com snap magnético ou com a ferramenta Move/Rotate nativa), a traseira continue colada na parede,
    a lateral esquerda continue ancorada nos módulos vizinhos e a base continue na mesma altura Z.
    """
    b_old = get_module_carcass_bounds(old_mod)
    b_new = get_module_carcass_bounds(new_mod)
    if b_old is None or b_new is None:
        return

    back_n = get_module_back_normal(rot_z_deg)
    # Vetor unitário apontando para a Esquerda local do móvel (-X local rotacionado por rot_z_deg)
    rad = math.radians(rot_z_deg % 360.0)
    left_n = QVector3D(-math.cos(rad), -math.sin(rad), 0.0).normalized()

    corners_old = [
        QVector3D(b_old[0], b_old[2], 0.0), QVector3D(b_old[1], b_old[2], 0.0),
        QVector3D(b_old[0], b_old[3], 0.0), QVector3D(b_old[1], b_old[3], 0.0)
    ]
    corners_new = [
        QVector3D(b_new[0], b_new[2], 0.0), QVector3D(b_new[1], b_new[2], 0.0),
        QVector3D(b_new[0], b_new[3], 0.0), QVector3D(b_new[1], b_new[3], 0.0)
    ]

    proj_back_old = max(QVector3D.dotProduct(p, back_n) for p in corners_old)
    proj_back_new = max(QVector3D.dotProduct(p, back_n) for p in corners_new)
    delta_back = proj_back_old - proj_back_new

    proj_left_old = max(QVector3D.dotProduct(p, left_n) for p in corners_old)
    proj_left_new = max(QVector3D.dotProduct(p, left_n) for p in corners_new)
    delta_left = proj_left_old - proj_left_new

    dz = b_old[4] - b_new[4]

    shift = back_n * delta_back + left_n * delta_left + QVector3D(0.0, 0.0, dz)
    if shift.length() > 1e-7:
        targets = getattr(new_mod, "children", []) or [new_mod]
        for t in targets:
            m_sub = getattr(t, "mesh", None)
            if m_sub and hasattr(m_sub, "vertices"):
                for v in m_sub.vertices:
                    v.position += shift
                m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
            if getattr(t, "ext", None) is not None:
                if "orig_vertices" in t.ext:
                    t.ext["orig_vertices"] = [orig + shift for orig in t.ext["orig_vertices"]]
                if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                    t.ext["hinge_pivot"] += shift



def get_reference_module(scene) -> Group | None:
    """Retorna o módulo selecionado ou o último inserido na cena para ancoragem."""
    if scene is None:
        return None
    sel = list(getattr(scene, "selection", []))
    for item in sel:
        if hasattr(item, "ext") and isinstance(item.ext, dict) and "trazomob_module" in item.ext:
            return item
    for g in getattr(scene, "groups", []):
        if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext:
            children = getattr(g, "children", []) or []
            if any(c in sel for c in children):
                return g
    # Se nenhum selecionado, pega o último da cena
    mods = [
        g for g in getattr(scene, "groups", [])
        if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_module" in g.ext
    ]
    return mods[-1] if mods else None


def get_module_category(tipo: str, default_z: float = 0.0) -> str:
    """Classifica o módulo em uma categoria funcional para herança de cotas e alinhamento contíguo.

    Categorias:
    - 'aereo': módulos aéreos suspensos (Z >= 0.8m, nichos de parede, aéreos)
    - 'alto': torres de eletro, roupeiros, armários verticais altos (H >= 1.6m)
    - 'bancada': tampos e bancadas de pedra / marmoraria
    - 'inferior': balcões de chão, gaveteiros, etc. (Z < 0.8m)
    """
    t = str(tipo).lower()
    if "bancada" in t or "ilha" in t:
        return "bancada"
    if "torre" in t or "geladeira" in t or "roupeiro" in t or "armario" in t:
        return "alto"
    if "aereo" in t or "nicho" in t:
        return "aereo"
    if "balcao" in t or "gaveteiro" in t or "porta_tempero" in t or "gabinete" in t:
        return "inferior"
    if default_z >= 0.80:
        return "aereo"
    return "inferior"


def is_compatible_category(cat1: str, cat2: str) -> bool:
    """Retorna True se duas categorias devem compartilhar e herdar altura, profundidade e alinhamento."""
    if cat1 == cat2:
        return True
    # Inferiores e Gabinetes de banheiro compartilham profundidade/alinhamento de chão
    if cat1 in ("inferior", "banheiro") and cat2 in ("inferior", "banheiro"):
        return True
    # Aéreos e Nichos suspensos compartilham elevação e profundidade
    if cat1 in ("aereo", "nicho") and cat2 in ("aereo", "nicho"):
        return True
    return False


def build_default_module_params(mod_data: dict[str, Any]) -> dict[str, Any]:
    """Prepara os parâmetros completos para construção do módulo a partir das preferências do usuário e defaults."""
    from .preferences import TrazoMobPreferencesManager
    prefs = TrazoMobPreferencesManager.get_instance()

    tipo = mod_data["id"]
    cat = get_module_category(tipo, default_z=float(mod_data.get("default_z", 0.0)))

    # 1. Dimensões: Catálogo base -> Sobrescrito por preferências do usuário para este tipo ou categoria
    L_mm = float(prefs.get_module_default(tipo, "largura", prefs.get_module_default(cat, "largura", mod_data.get("largura", 800))))
    A_mm = float(prefs.get_module_default(tipo, "altura", prefs.get_module_default(cat, "altura", mod_data.get("altura", 720))))
    P_mm = float(prefs.get_module_default(tipo, "profundidade", prefs.get_module_default(cat, "profundidade", mod_data.get("profundidade", 550))))
    rodape_mm = float(prefs.get_module_default(tipo, "rodape", prefs.get_module_default(cat, "rodape", mod_data.get("rodape", 0))))

    # 2. Padrões globais de marcenaria salvos pelo usuário
    esp_mm = float(prefs.get_global("espessura_caixa_mm", 15.0))
    esp_frentes_mm = float(prefs.get_global("espessura_frentes_mm", esp_mm))
    mat_caixa = str(prefs.get_global("material_caixa", "MDF Branco TX"))
    mat_frentes = str(prefs.get_global("material_frentes", "MDF Louro Freijó"))
    pux_tipo = str(prefs.get_global("puxador_tipo", "perfil"))
    pux_cor = str(prefs.get_global("puxador_cor", "anodizado_fosco"))
    pux_pos = str(prefs.get_global("puxador_pos", "superior"))
    perf_mod = str(prefs.get_global("perfil_modelo", "gola"))
    desc_perf = float(prefs.get_global("desconto_perfil_mm", 35.0))

    has_fundo_default = bool(mod_data.get("has_fundo", True))
    tipo_fundo_default = str(prefs.get_global("tipo_fundo", "rasgo")) if has_fundo_default else "sem_fundo"

    params: dict[str, Any] = {
        "tipo": tipo,
        "largura": L_mm,
        "altura": A_mm,
        "profundidade": P_mm,
        "espessura": esp_mm,
        "rodape": rodape_mm,
        "material": f"{mat_caixa} {int(esp_mm)}mm" if not mat_caixa.endswith("mm") else mat_caixa,
        "material_frentes": f"{mat_frentes} {int(esp_frentes_mm)}mm" if not mat_frentes.endswith("mm") else mat_frentes,
        "espessura_frentes": esp_frentes_mm,
        "tem_fundo": has_fundo_default and (tipo_fundo_default != "sem_fundo"),
        "tipo_fundo": tipo_fundo_default,
        "esp_fundo": float(prefs.get_global("esp_fundo_mm", 6.0)),
        "recuo_fundo": float(prefs.get_global("recuo_fundo_mm", 10.0)),
        "prof_rasgo": float(prefs.get_global("prof_rasgo_mm", 7.0)),
        "folga_fundo": float(prefs.get_global("folga_fundo_mm", 2.0)),
        "puxador_tipo": pux_tipo,
        "puxador_cor": pux_cor,
        "puxador_pos": pux_pos,
        "desconto_perfil": desc_perf,
        "perfil_modelo": perf_mod,
        "fita_caixa_modo": str(prefs.get_global("fita_caixa_modo", "frontal_1L")),
        "material_fita_caixa": prefs.get_global("material_fita_caixa", None),
        "gerar_furacao": bool(prefs.get_global("gerar_furacao", True)),
        "dispositivo_fixacao": str(prefs.get_global("dispositivo_fixacao", "minifix_cavilha")),
        "rot_z": 0.0,
    }

    # Se for bancada de pedra, aplica os defaults específicos
    if "bancada" in str(tipo):
        params["esp_pedra"] = float(prefs.get_module_default("bancada", "esp_pedra", 20.0))
        params["altura_saia"] = float(prefs.get_module_default("bancada", "altura_saia", 40.0))
        params["altura_frontao"] = float(prefs.get_module_default("bancada", "altura_frontao", 100.0))

    if tipo == "balcao_misto":
        params["num_gavetas"] = int(mod_data.get("num_gavetas", 4))
        params["num_portas"] = int(mod_data.get("num_portas", 2))
        params["largura_gaveteiro"] = float(mod_data.get("largura_gaveteiro", 450.0))
    elif mod_data.get("has_gavetas"):
        params["num_gavetas"] = int(mod_data.get("num_gavetas", 4))
    elif mod_data.get("has_portas"):
        params["num_portas"] = int(mod_data.get("num_portas", 2))

    if mod_data.get("has_prateleiras"):
        params["num_prateleiras"] = int(mod_data.get("num_prateleiras", 1))

    # Travessas cozinha inferiores (carrega preferências globais do usuário se configuradas)
    _IDS_COZ_INF = {
        "balcao", "gaveteiro", "balcao_misto", "balcao_pia",
        "balcao_canto", "balcao_canto_l", "porta_tempero", "balcao_forno"
    }
    if tipo in _IDS_COZ_INF:
        params["travessa_frontal_em_pe"] = bool(prefs.get_global("travessa_frontal_em_pe", mod_data.get("travessa_frontal_em_pe", False)))
        params["travessa_traseira_em_pe"] = bool(prefs.get_global("travessa_traseira_em_pe", False))
        params["larg_travessa_frontal_mm"] = float(prefs.get_global("larg_travessa_frontal_mm", mod_data.get("larg_travessa_frontal_mm", 70.0)))
        params["larg_travessa_traseira_mm"] = float(prefs.get_global("larg_travessa_traseira_mm", mod_data.get("larg_travessa_traseira_mm", 70.0)))
        params["recuo_porta_topo_mm"] = float(prefs.get_global("recuo_porta_topo_mm", mod_data.get("recuo_porta_topo_mm", 50.0)))
        params["fita_travessas_modo"] = str(prefs.get_global("fita_travessas_modo", "frontal_1L"))
        if prefs.get_global("material_travessas") is not None:
            params["material_travessas"] = prefs.get_global("material_travessas")
        if prefs.get_global("esp_travessas_mm") is not None:
            params["esp_travessas_mm"] = prefs.get_global("esp_travessas_mm")
            params["espessura_travessas"] = params["esp_travessas_mm"]
        if prefs.get_global("material_fita_travessas") is not None:
            params["material_fita_travessas"] = prefs.get_global("material_fita_travessas")

    if tipo == "balcao_forno":
        params["tem_gaveta"] = bool(mod_data.get("tem_gaveta", True))
        params["alt_gaveta_mm"] = float(mod_data.get("alt_gaveta_mm", 150.0))

    if tipo == "caixa_geladeira":
        params["alt_nicho_geladeira_mm"] = float(mod_data.get("alt_nicho_geladeira_mm", 1800.0))
        params["tipo_porta_superior"] = "duas_portas"
        params["num_portas"] = 2

    if tipo == "aereo_microondas":
        params["tipo_porta_superior"] = "basculante"
        params["num_portas"] = 1

    # Gavetas
    if mod_data.get("has_gavetas") or tipo in ("gaveteiro", "balcao_misto", "torre_quente", "gabinete_banheiro"):
        params["tipo_fundo_gaveta"] = "rasgo"
        params["folga_corredica_mm"] = 26.0
        params["esp_gaveta_mm"] = 15.0
        params["esp_fundo_gaveta_mm"] = 6.0

    # Bancadas de pedra
    if "bancada" in str(tipo):
        params["esp_pedra"] = float(mod_data.get("esp_pedra", 20.0))
        params["altura_saia"] = float(mod_data.get("altura_saia", 40.0))
        params["altura_frontao"] = float(mod_data.get("altura_frontao", 100.0))
        params["tem_saia_esq"] = True
        params["tem_saia_dir"] = True
        params["tipo_cuba"] = mod_data.get("tipo_cuba", "inox_simples")
        params["has_cuba"] = (params["tipo_cuba"] != "sem_cuba")
        params["posicao_cuba"] = "centro"
        params["tem_torneira"] = True
        params["canto_recorte"] = "arredondado"
        params["raio_canto_mm"] = 20.0
        params["tem_area_molhada"] = True
        if tipo in ("bancada_canto_l", "bancada_canto"):
            params["larg_asa"] = float(mod_data.get("larg_asa", 600.0))

    # Tampo engrossado de marcenaria
    if tipo in ("peca_tampo_engrossado", "tampo_engrossado"):
        params["esp_chapa"] = float(mod_data.get("esp_chapa", 18.0))
        params["qtd_engrosso"] = int(mod_data.get("qtd_engrosso", 1))
        params["larg_engrosso"] = float(mod_data.get("larg_engrosso", 70.0))
        params["tipo_engrosso"] = str(mod_data.get("tipo_engrosso", "3_lados"))
        params["fechar_embaixo"] = bool(mod_data.get("fechar_embaixo", False))

    return params


class ModuleButton(QToolButton):
    """Botão visual moderno de módulo com miniatura vetorial, título e tooltip rica."""

    def __init__(self, mod_data: dict[str, Any], on_clicked, parent=None):
        super().__init__(parent)
        self.mod_data = mod_data
        self.on_clicked = on_clicked

        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIcon(get_module_thumbnail(mod_data["id"]))
        self.setIconSize(QSize(52, 52))
        self.setFixedSize(100, 84)

        nome = mod_data.get("nome", "")
        # Trunca nome longo para 2 linhas legíveis no botão
        if len(nome) > 18:
            parts = nome.split(" (")[0]
            display_name = parts if len(parts) <= 18 else (parts[:16] + "…")
        else:
            display_name = nome

        self.setText(display_name)
        dim_info = f"{mod_data.get('largura', 0)} x {mod_data.get('altura', 0)} x {mod_data.get('profundidade', 0)} mm"
        desc = mod_data.get("desc", "")
        self.setToolTip(f"<b>{nome}</b><br>📏 {dim_info}<br>💡 {desc}<br><i>Duplo clique para inserir na cena 3D</i>")
        self.setStatusTip(f"Duplo clique para inserir {nome} ({dim_info})")

        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "QToolButton {"
            "  border: 1px solid palette(midlight);"
            "  border-radius: 6px;"
            "  background-color: palette(base);"
            "  color: palette(text);"
            "  font-size: 11px;"
            "  font-weight: 500;"
            "  padding: 4px;"
            "}"
            "QToolButton:hover {"
            "  border: 1.5px solid palette(highlight);"
            "  background-color: palette(alternate-base);"
            "}"
            "QToolButton:focus {"
            "  border: 2px solid palette(highlight);"
            "  background-color: palette(alternate-base);"
            "}"
            "QToolButton:pressed {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
        )

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            # 1. Clique simples: se houver frame armado, atualiza seu tamanho imediatamente no 3D!
            from .wall_selection import WallSelectionManager
            wall_mgr = WallSelectionManager.get_instance()
            if wall_mgr.active_placement_slot is not None:
                mod_w = float(self.mod_data.get("largura", 800.0)) / 1000.0
                mod_p = float(self.mod_data.get("profundidade", 550.0)) / 1000.0
                wall_mgr.update_frame_dimensions(mod_w, mod_p)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.on_clicked(self.mod_data)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)



class DecorationButton(QToolButton):

    """Botão visual moderno para itens de decoração e componentes da biblioteca do IngeTrazo."""

    def __init__(self, item_data: dict[str, Any], on_clicked, parent=None):
        super().__init__(parent)
        self.item_data = item_data
        self.on_clicked = on_clicked

        self.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        self.setIconSize(QSize(52, 52))
        self.setFixedSize(100, 84)

        nome = item_data.get("name") or item_data.get("nombre", "")
        if len(nome) > 18:
            parts = nome.split(" (")[0]
            display_name = parts if len(parts) <= 18 else (parts[:16] + "…")
        else:
            display_name = nome

        self.setText(display_name)
        tip = item_data.get("tip") or nome
        self.setToolTip(f"<b>{nome}</b><br>{tip}<br><i>Duplo clique para inserir na cena</i>")
        self.setStatusTip(f"Duplo clique para inserir {nome}")
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet(
            "QToolButton {"
            "  border: 1px solid palette(midlight);"
            "  border-radius: 6px;"
            "  background-color: palette(base);"
            "  color: palette(text);"
            "  font-size: 11px;"
            "  font-weight: 500;"
            "  padding: 4px;"
            "}"
            "QToolButton:hover {"
            "  border: 1.5px solid palette(highlight);"
            "  background-color: palette(alternate-base);"
            "}"
            "QToolButton:focus {"
            "  border: 2px solid palette(highlight);"
            "  background-color: palette(alternate-base);"
            "}"
            "QToolButton:pressed {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
        )

        icon_path = item_data.get("icon_path")
        if icon_path and os.path.exists(str(icon_path)):
            self.setIcon(QIcon(str(icon_path)))
        elif "library_id" in item_data:
            from core import library
            ident = item_data["library_id"]
            p = library.cached_thumbnail(ident)
            if p and os.path.exists(str(p)):
                self.setIcon(QIcon(str(p)))
            else:
                # Carregamento sob demanda
                library.prefetch_thumbnails([ident])
                QTimer.singleShot(600, self._check_thumb)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self.on_clicked(self.item_data)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def _check_thumb(self):
        ident = self.item_data.get("library_id")
        if not ident:
            return
        from core import library
        p = library.cached_thumbnail(ident)
        if p and os.path.exists(str(p)):
            self.setIcon(QIcon(str(p)))


class TrazoMobModuleRibbonBar(QToolBar):

    """Barra de ferramentas superior em abas que organiza os móveis por categoria/ambiente.

    Abre logo abaixo da barra principal ao clicar em 'Módulos', permitindo navegar e
    inserir balcões, aéreos, torres, quartos, banheiros e marmorarias diretamente na cena.
    """

    def __init__(self, main_window, viewport, sidebar_panel, parent=None):
        parent_widget = parent if isinstance(parent, QWidget) else (main_window if isinstance(main_window, QWidget) else None)
        super().__init__("Catálogo de Módulos (TrazoMob)", parent_widget)
        self.setObjectName("TrazoMobModuleRibbonBar")
        self.main_window = main_window
        self.viewport = viewport
        self.sidebar_panel = sidebar_panel

        self.setMovable(True)
        self.setFloatable(False)

        # Widget central com abas
        self.container = QWidget()
        layout = QHBoxLayout(self.container)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        # QTabWidget principal compacto para os ambientes
        self.tabs = QTabWidget()
        self.tabs.setTabPosition(QTabWidget.North)
        self.tabs.setDocumentMode(True)
        self.tabs.setStyleSheet(
            "QTabWidget::pane { border: 1px solid palette(midlight); border-radius: 6px; background-color: palette(base); }"
            "QTabBar::tab {"
            "  padding: 5px 12px;"
            "  font-weight: bold;"
            "  font-size: 11px;"
            "  border-top-left-radius: 4px;"
            "  border-top-right-radius: 4px;"
            "  margin-right: 2px;"
            "  background-color: palette(button);"
            "  color: palette(button-text);"
            "}"
            "QTabBar::tab:selected {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
            "QTabBar::tab:hover:!selected {"
            "  background-color: palette(midlight);"
            "}"
        )

        self._populate_tabs()
        layout.addWidget(self.tabs, stretch=1)

        # Botão Rápido de Bancada sobre Balcões no Ribbon Superior
        self.btn_ribbon_bancada = QPushButton("🪨 Encaixar Bancada")
        self.btn_ribbon_bancada.setToolTip("Cria e encaixa uma bancada contínua de pedra sobre os balcões da parede selecionada")
        self.btn_ribbon_bancada.setFixedHeight(32)
        self.btn_ribbon_bancada.setStyleSheet(
            "QPushButton { background-color: #0284C7; color: white; font-weight: bold; border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background-color: #0369A1; }"
        )
        def _on_click_ribbon_bancada():
            if self.sidebar_panel is not None and hasattr(self.sidebar_panel, "_on_encaixar_bancada_sobre_balcoes"):
                self.sidebar_panel._on_encaixar_bancada_sobre_balcoes()
        self.btn_ribbon_bancada.clicked.connect(_on_click_ribbon_bancada)
        layout.addWidget(self.btn_ribbon_bancada)

        # Bot?o Eleva??o 2D com Cotas no Ribbon Superior
        self.btn_ribbon_elevacao = QPushButton("?? Eleva??o 2D")
        self.btn_ribbon_elevacao.setToolTip("Abre a eleva??o t?cnica ortogonal 2D com cotas milim?tricas da parede e m?dulos")
        self.btn_ribbon_elevacao.setFixedHeight(32)
        self.btn_ribbon_elevacao.setStyleSheet(
            "QPushButton { background-color: #4338CA; color: white; font-weight: bold; border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background-color: #3730A3; }"
        )
        def _on_click_ribbon_elevacao():
            if self.sidebar_panel is not None and hasattr(self.sidebar_panel, "_on_abrir_elevacao_parede"):
                self.sidebar_panel._on_abrir_elevacao_parede()
            else:
                from .wall_elevation_dialog import WallElevationDialog
                dlg = WallElevationDialog(viewport=self.viewport, parent=self.window())
                dlg.exec()
        self.btn_ribbon_elevacao.clicked.connect(_on_click_ribbon_elevacao)
        layout.addWidget(self.btn_ribbon_elevacao)

        # Bot?o Fechamento / Arremate de Canto no Ribbon Superior
        self.btn_ribbon_arremate = QPushButton("?? Arremate de Canto")
        self.btn_ribbon_arremate.setToolTip("Preenche a folga residual entre o ?ltimo m?dulo e o final da parede com uma r?gua de testeira e sarrafo")
        self.btn_ribbon_arremate.setFixedHeight(32)
        self.btn_ribbon_arremate.setStyleSheet(
            "QPushButton { background-color: #0D9488; color: white; font-weight: bold; border-radius: 4px; padding: 4px 10px; font-size: 11px; }"
            "QPushButton:hover { background-color: #0F766E; }"
        )
        def _on_click_ribbon_arremate():
            if self.sidebar_panel is not None and hasattr(self.sidebar_panel, "_on_fechar_vao_canto"):
                self.sidebar_panel._on_fechar_vao_canto()
        self.btn_ribbon_arremate.clicked.connect(_on_click_ribbon_arremate)
        layout.addWidget(self.btn_ribbon_arremate)



        # Botão Fechar barra
        btn_close = QPushButton("✕")
        btn_close.setToolTip("Fechar barra de módulos")
        btn_close.setFixedSize(24, 24)
        btn_close.setStyleSheet(
            "QPushButton { border: none; font-weight: bold; border-radius: 12px; color: palette(text); }"
            "QPushButton:hover { background-color: palette(dark); color: #EF4444; }"
        )
        btn_close.clicked.connect(self.hide)
        layout.addWidget(btn_close)

        self.addWidget(self.container)

    def _create_module_scroll_area(self, items: list[dict[str, Any]]) -> QScrollArea:
        """Cria uma área horizontal com scroll de botões de módulos."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(94)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        h_layout = QHBoxLayout(content)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(6)
        h_layout.setAlignment(Qt.AlignLeft)

        for mod_data in items:
            btn = ModuleButton(mod_data, on_clicked=self.insert_module_into_scene, parent=content)
            h_layout.addWidget(btn)

        scroll.setWidget(content)
        return scroll

    def _create_decoration_scroll_area(self, items: list[dict[str, Any]]) -> QScrollArea:
        """Cria uma área horizontal com scroll de botões de decoração/componentes."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFixedHeight(94)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.NoFrame)

        content = QWidget()
        h_layout = QHBoxLayout(content)
        h_layout.setContentsMargins(4, 2, 4, 2)
        h_layout.setSpacing(6)
        h_layout.setAlignment(Qt.AlignLeft)

        for item_data in items:
            btn = DecorationButton(item_data, on_clicked=self.insert_decoration_into_scene, parent=content)
            h_layout.addWidget(btn)

        # Botão para abrir o diálogo completo da biblioteca
        btn_more = QToolButton(content)
        btn_more.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        btn_more.setIcon(self.style().standardIcon(self.style().StandardPixmap.SP_FileDialogContentsView))
        btn_more.setIconSize(QSize(40, 40))
        btn_more.setFixedSize(100, 84)
        btn_more.setText("Biblioteca…")
        btn_more.setToolTip("Abrir diálogo completo da Biblioteca de Componentes com busca")
        btn_more.setCursor(Qt.PointingHandCursor)
        btn_more.setStyleSheet(
            "QToolButton {"
            "  border: 1px dashed palette(highlight);"
            "  border-radius: 6px;"
            "  background-color: palette(base);"
            "  color: palette(highlight);"
            "  font-size: 11px;"
            "  font-weight: bold;"
            "  padding: 4px;"
            "}"
            "QToolButton:hover {"
            "  background-color: palette(alternate-base);"
            "}"
        )
        if hasattr(self.main_window, "_on_open_library"):
            btn_more.clicked.connect(self.main_window._on_open_library)
        h_layout.addWidget(btn_more)

        scroll.setWidget(content)
        return scroll

    def _populate_tabs(self):
        """Preenche as abas principais e sub-abas categorizadas (ex: Cozinha -> Inferiores, Aéreos, Torres)."""
        # Estrutura: Ambiente -> { Subcategoria: [itens] }
        env_map: dict[str, dict[str, list[dict[str, Any]]]] = {
            "🍳 Cozinha": {
                "Balcões Inferiores": [],
                "Aéreos & Suspensos": [],
                "Torres de Eletros": [],
            },
            "🛏️ Dormitório": {
                "Roupeiros & Armários": [],
            },
            "🚿 Banheiro": {
                "Gabinetes & Pias": [],
            },
            "📦 Nichos & Prateleiras": {
                "Nichos & Estantes": [],
            },
            "🪨 Marmoraria": {
                "Bancadas & Tampos": [],
            },
            "🚪 Portas & Janelas": {
                "Portas": [],
                "Janelas": [],
            },
            "📐 Peças Avulsas": {
                "Peças": [],
            },
        }

        for cat_name, items in MODULE_CATALOG.items():
            if "Cozinha — Inferiores" in cat_name:
                env_map["🍳 Cozinha"]["Balcões Inferiores"].extend(items)
            elif "Cozinha — Aéreos" in cat_name:
                env_map["🍳 Cozinha"]["Aéreos & Suspensos"].extend(items)
            elif "Cozinha — Torres" in cat_name:
                env_map["🍳 Cozinha"]["Torres de Eletros"].extend(items)
            elif "Armário" in cat_name or "Dormitório" in cat_name:
                env_map["🛏️ Dormitório"]["Roupeiros & Armários"].extend(items)
            elif "Banheiro" in cat_name:
                env_map["🚿 Banheiro"]["Gabinetes & Pias"].extend(items)
            elif "Nicho" in cat_name:
                env_map["📦 Nichos & Prateleiras"]["Nichos & Estantes"].extend(items)
            elif "Marmoraria" in cat_name:
                env_map["🪨 Marmoraria"]["Bancadas & Tampos"].extend(items)
            elif "Portas" in cat_name or "Janelas" in cat_name:
                for it in items:
                    if "porta" in it.get("id", ""):
                        env_map["🚪 Portas & Janelas"]["Portas"].append(it)
                    else:
                        env_map["🚪 Portas & Janelas"]["Janelas"].append(it)
            else:
                env_map["📐 Peças Avulsas"]["Peças"].extend(items)

        subtab_style = (
            "QTabWidget::pane { border: none; background-color: transparent; }"
            "QTabBar::tab {"
            "  padding: 3px 10px;"
            "  font-size: 10px;"
            "  font-weight: 600;"
            "  border-radius: 4px;"
            "  margin-right: 4px;"
            "  background-color: palette(button);"
            "  color: palette(button-text);"
            "}"
            "QTabBar::tab:selected {"
            "  background-color: palette(highlight);"
            "  color: palette(highlighted-text);"
            "}"
            "QTabBar::tab:hover:!selected {"
            "  background-color: palette(midlight);"
            "}"
        )

        for env_label, subcategories in env_map.items():
            valid_subcats = {k: v for k, v in subcategories.items() if v}
            if not valid_subcats:
                continue

            # Se houver mais de uma subcategoria (como na Cozinha: Inferiores, Aéreos, Torres),
            # renderiza um QTabWidget de sub-abas interno na parte inferior!
            if len(valid_subcats) > 1:
                sub_tabs = QTabWidget()
                sub_tabs.setTabPosition(QTabWidget.South)
                sub_tabs.setDocumentMode(True)
                sub_tabs.setStyleSheet(subtab_style)
                for sub_label, sub_items in valid_subcats.items():
                    sub_tabs.addTab(self._create_module_scroll_area(sub_items), sub_label)
                self.tabs.addTab(sub_tabs, env_label)
            else:
                # Subcategoria única direta
                sub_items = next(iter(valid_subcats.values()))
                self.tabs.addTab(self._create_module_scroll_area(sub_items), env_label)


        # ── ABA DECORAÇÃO (CARREGADA SOB DEMANDA AO CLICAR NA ABA) ──────
        self._decor_populated = False
        self._decor_subtab_style = subtab_style
        self._decor_placeholder = QWidget()
        self._decor_tab_idx = self.tabs.addTab(self._decor_placeholder, "🎨 Decoração")
        self.tabs.currentChanged.connect(self._on_main_tab_changed)

    def _on_main_tab_changed(self, idx: int) -> None:
        if idx == getattr(self, "_decor_tab_idx", -1) and not getattr(self, "_decor_populated", False):
            self._decor_populated = True
            self._populate_decoration_tab()

    def _populate_decoration_tab(self) -> None:
        """Popula a aba de Decoração sob demanda quando o usuário clica nela pela primeira vez."""
        decor_categories: dict[str, list[dict[str, Any]]] = {
            "Geral & Starters": [],
            "Pessoas (Escala)": [],
            "Sala & Estar": [],
            "Cozinha & Eletros": [],
            "Banheiro": [],
            "Quarto": [],
            "Iluminação": [],
            "Plantas & Exterior": [],
            "Decoração & Vários": [],
        }

        # 1. Carrega os componentes nativos locais do IngeTrazo
        res_comp = app_root() / "resources" / "components"
        manifest_path = res_comp / "components.json"
        if manifest_path.exists():
            try:
                for entry in json.loads(manifest_path.read_text(encoding="utf-8")):
                    key = entry.get("key", "")
                    icon_file = res_comp / "thumbs" / f"{key}.png"
                    decor_categories["Geral & Starters"].append({
                        "tipo": "native_3d",
                        "key": key,
                        "name": tr(entry.get("name", key.capitalize())),
                        "tip": tr(entry.get("tip", "")),
                        "icon_path": str(icon_file) if icon_file.exists() else None,
                    })
            except Exception:
                pass

        people_path = res_comp / "people.json"
        if people_path.exists():
            try:
                for entry in json.loads(people_path.read_text(encoding="utf-8")):
                    key = entry.get("key", "")
                    icon_file = res_comp / f"{key}.png"
                    decor_categories["Pessoas (Escala)"].append({
                        "tipo": "native_person",
                        "key": key,
                        "height": float(entry.get("height", 1.75)),
                        "name": tr(entry.get("name", key.capitalize())),
                        "tip": tr(entry.get("tip", "")),
                        "icon_path": str(icon_file) if icon_file.exists() else None,
                    })
            except Exception:
                pass

        # 2. Carrega destaques de cada categoria do catálogo (máx 24 por aba rápida; o botão Biblioteca abre todos os 1500+)
        MAX_RIBBON_ITEMS_PER_SUBTAB = 24
        try:
            from core import library
            lib_entries = library.index()
            cat_target_map = {
                "Salón": "Sala & Estar",
                "Cocina": "Cozinha & Eletros",
                "Cuarto de Baño": "Banheiro",
                "Dormitorio": "Quarto",
                "Iluminación": "Iluminação",
                "Exterior": "Plantas & Exterior",
                "Personajes": "Pessoas (Escala)",
                "Varios": "Decoração & Vários",
                "Oficina": "Decoração & Vários",
            }
            for e in lib_entries:
                c_orig = e.get("categoria", "")
                sub_target = cat_target_map.get(c_orig)
                if not sub_target or len(decor_categories[sub_target]) >= MAX_RIBBON_ITEMS_PER_SUBTAB:
                    continue
                name = e.get("nombre_en") or e.get("nombre") or e.get("id", "")
                decor_categories[sub_target].append({
                    "tipo": "library_model",
                    "library_id": e.get("id"),
                    "name": name,
                    "tip": f"{name} ({c_orig})",
                    "entry": e,
                })
        except Exception:
            pass

        decor_tabs = QTabWidget()
        decor_tabs.setTabPosition(QTabWidget.South)
        decor_tabs.setDocumentMode(True)
        decor_tabs.setStyleSheet(self._decor_subtab_style)

        for sub_label, items in decor_categories.items():
            if items:
                decor_tabs.addTab(self._create_decoration_scroll_area(items), sub_label)

        lay = QVBoxLayout(self._decor_placeholder)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(decor_tabs)


    def insert_decoration_into_scene(self, item_data: dict[str, Any]):
        """Insere o item de decoração selecionado na cena 3D."""
        tipo = item_data.get("tipo")
        if tipo == "native_3d":
            key = item_data.get("key", "")
            name = item_data.get("name")
            if hasattr(self.main_window, "_on_insert_component"):
                self.main_window._on_insert_component(key, name)
        elif tipo == "native_person":
            key = item_data.get("key", "")
            height = float(item_data.get("height", 1.75))
            name = item_data.get("name")
            if hasattr(self.main_window, "_on_insert_person_2d"):
                self.main_window._on_insert_person_2d(f"{key}.png", height, name)
        elif tipo == "library_model":
            entry = item_data.get("entry")
            if entry and hasattr(self.main_window, "insert_library_component"):
                self.main_window.insert_library_component(entry)

    def insert_module_into_scene(self, mod_data: dict[str, Any]):

        """Insere o módulo diretamente no 3D com posicionamento inteligente e abre no editor lateral."""
        scene = getattr(self.viewport, "scene", None)
        if scene is None or self.viewport is None:
            return

        params = build_default_module_params(mod_data)
        ref_mod = get_reference_module(scene)
        default_z = float(mod_data.get("default_z", 0.0))
        novo_L_m = float(params["largura"]) / 1000.0

        # ── VERIFICAÇÃO DE MESMA CATEGORIA E HERANÇA DE MEDIDAS ────────
        cat_novo = get_module_category(mod_data.get("id", ""), default_z)
        is_same_cat = False
        ref_b = None
        ref_cc = {}
        if ref_mod is not None:
            ref_b = get_module_carcass_bounds(ref_mod)
            if hasattr(ref_mod, "ext") and "trazomob_module" in ref_mod.ext:
                ref_cc = ref_mod.ext["trazomob_module"]
            
            # Determina Z real da base do módulo de referência
            ref_z = ref_b[4] if ref_b is not None else float(ref_cc.get("offset", (0, 0, 0))[2])
            ref_tipo = ref_cc.get("tipo", getattr(ref_mod, "name", ""))
            cat_ref = get_module_category(ref_tipo, ref_z)

            if is_compatible_category(cat_novo, cat_ref):
                is_same_cat = True
                # Herda profundidade da caixa anterior (do dict ou das dimensões físicas da caixa)
                if "profundidade" in ref_cc and float(ref_cc["profundidade"]) > 0:
                    params["profundidade"] = float(ref_cc["profundidade"])
                elif ref_b is not None:
                    ref_rot = float(ref_cc.get("rot_z", 0.0)) % 360.0
                    if abs(ref_rot) < 45.0 or abs(ref_rot - 180.0) < 45.0:
                        params["profundidade"] = round((ref_b[3] - ref_b[2]) * 1000.0)
                    else:
                        params["profundidade"] = round((ref_b[1] - ref_b[0]) * 1000.0)

                # Herda altura da caixa anterior (do dict ou das dimensões físicas da caixa)
                if "altura" in ref_cc and float(ref_cc["altura"]) > 0:
                    params["altura"] = float(ref_cc["altura"])
                elif ref_b is not None:
                    params["altura"] = round((ref_b[5] - ref_b[4]) * 1000.0)

                # Herda rodapé se ambos forem inferiores/altos com rodapé
                if "rodape" in ref_cc and cat_novo in ("inferior", "alto"):
                    params["rodape"] = float(ref_cc["rodape"])

                # Adota o nível vertical Z exato da base do móvel de referência
                if ref_b is not None:
                    default_z = ref_b[4]

        novo_L_m = float(params["largura"]) / 1000.0

        # ── VERIFICAÇÃO DE PAREDE SELECIONADA E FRAME ARMADO ─────────
        from .wall_selection import WallSelectionManager
        wall_mgr = WallSelectionManager.get_instance(self.viewport)
        sel_wf = wall_mgr.selected_wall_face
        active_slot = getattr(wall_mgr, "active_placement_slot", None)

        # Regra de negócio estrita: esquadrias (portas e janelas) NÃO devem sofrer alinhamento
        # automático ou redimensionamento pelas réguas-guia de marcenaria.
        is_esquadria = (
            mod_data.get("tipo") == "esquadria"
            or "porta" in str(mod_data.get("id", "")).lower()
            or "janela" in str(mod_data.get("id", "")).lower()
        )

        # Se houver um frame armado entre linhas-guia estilo Promob, ele tem prioridade para marcenaria:
        if active_slot is not None and sel_wf is not None and not is_esquadria:
            norm = sel_wf.normal
            n_dir = QVector3D(norm.x(), norm.y(), 0.0).normalized()
            u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()

            # Rotação Z para encostar traseira na parede e frente apontada para o cômodo (+n_dir)
            angle_deg = math.degrees(math.atan2(n_dir.y(), n_dir.x())) + 90.0
            params["rot_z"] = (round(angle_deg / 90.0) * 90.0) % 360.0

            # 1. Ajusta o módulo para a altura exata do vão entre réguas
            z_base = float(active_slot["z_base"])
            z_top = float(active_slot["z_top"])
            slot_height_mm = float(active_slot.get("height_mm", round((z_top - z_base) * 1000.0)))

            # Ajusta altura se o vão for delimitado entre duas réguas elevadas (ex: aéreos, torres, nichos)
            if slot_height_mm > 100:
                params["altura"] = slot_height_mm

            # Se a profundidade padrão do slot for recomendada (ex: 350mm para aéreos, 550mm para balcões)
            if "default_depth_mm" in active_slot:
                params["profundidade"] = float(active_slot["default_depth_mm"])

            # Atualiza o frame para ter a largura real do móvel selecionado
            # e reconfinar dentro dos limites físicos da parede
            mod_larg_m = float(params.get("largura", 800.0)) / 1000.0
            mod_prof_m = float(params.get("profundidade", 550.0)) / 1000.0
            if hasattr(wall_mgr, "update_frame_dimensions"):
                wall_mgr.update_frame_dimensions(mod_larg_m, mod_prof_m)

            # Constrói temporariamente em (0, 0, 0) para calcular bounds reais pós-rotação
            new_module_group = CabinetBuilder.build_module_group(params, offset=(0.0, 0.0, 0.0))

            from .magnetic_drag import get_module_bounds, get_bounds_min_projection
            b = get_module_carcass_bounds(new_module_group) or get_module_bounds(new_module_group)
            if b is not None:
                p_wall = active_slot["center_pt"]

                # 2. Encosta a traseira rigorosamente na face da parede ao longo de n_dir
                cur_min_n = get_bounds_min_projection(b, n_dir)
                wall_n = QVector3D.dotProduct(p_wall, n_dir)
                shift_n = (wall_n - cur_min_n) + 0.001

                # 3. Alinha com o centro horizontal do frame já confinado aos limites da parede
                cur_center_u = QVector3D.dotProduct(QVector3D((b[0] + b[1]) * 0.5, (b[2] + b[3]) * 0.5, 0.0), u_dir)
                wall_u = QVector3D.dotProduct(p_wall, u_dir)
                shift_u = wall_u - cur_center_u

                # 4. Encaixa a base Z exatamente na cota z_base do slot
                shift_z = z_base - b[4]

                shift = n_dir * shift_n + u_dir * shift_u + QVector3D(0.0, 0.0, shift_z)

                targets = getattr(new_module_group, "children", []) or [new_module_group]
                for t in targets:
                    m_sub = getattr(t, "mesh", None)
                    if m_sub and hasattr(m_sub, "vertices"):
                        for v in m_sub.vertices:
                            v.position += shift
                        m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
                    if getattr(t, "ext", None) is not None:
                        if "orig_vertices" in t.ext:
                            t.ext["orig_vertices"] = [orig + shift for orig in t.ext["orig_vertices"]]
                        if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                            t.ext["hinge_pivot"] += shift
                if "trazomob_module" in new_module_group.ext:
                    mod_ext = new_module_group.ext["trazomob_module"]
                    mod_ext["offset"] = (float(shift.x()), float(shift.y()), float(shift.z()))
        elif sel_wf is not None and sel_wf.face is not None:
            norm = sel_wf.normal
            n_dir = QVector3D(norm.x(), norm.y(), 0.0)
            if n_dir.length() > 1e-4:
                n_dir.normalize()
                angle_deg = math.degrees(math.atan2(n_dir.y(), n_dir.x())) + 90.0
                params["rot_z"] = (round(angle_deg / 90.0) * 90.0) % 360.0

                u_dir = QVector3D(-n_dir.y(), n_dir.x(), 0.0).normalized()
                c_pt = sel_wf.center

                positioned_next_to_ref = False
                if ref_mod is not None and ref_b is not None:
                    ref_rot = float(ref_cc.get("rot_z", 0.0)) % 360.0
                    if abs(ref_rot - params["rot_z"]) < 1e-2 or abs(abs(ref_rot - params["rot_z"]) - 360.0) < 1e-2:
                        novo_P_m = float(params.get("profundidade", 550.0)) / 1000.0
                        half_diff = (novo_L_m - novo_P_m) * 0.5
                        if abs(ref_rot) < 1e-4:
                            offset = (ref_b[1], ref_b[2], default_z)
                        elif abs(ref_rot - 180.0) < 1e-4:
                            cand_x = ref_b[0] - novo_L_m
                            if cand_x < 0.14:
                                cand_x = ref_b[1]
                            offset = (cand_x, ref_b[2], default_z)
                        elif abs(ref_rot - 90.0) < 1e-4:
                            cand_min_y = ref_b[3]
                            offset = (ref_b[0] - half_diff, cand_min_y + half_diff, default_z)
                        elif abs(ref_rot - 270.0) < 1e-4:
                            cand_min_y = ref_b[2] - novo_L_m
                            if cand_min_y < 0.14:
                                cand_min_y = ref_b[3]
                            offset = (ref_b[0] - half_diff, cand_min_y + half_diff, default_z)
                        else:
                            offset = (ref_b[1], ref_b[2], default_z)
                        positioned_next_to_ref = True

                if not positioned_next_to_ref:
                    larg_m = float(params.get("largura", 800.0)) / 1000.0
                    pos_base = c_pt + n_dir * 0.001 - u_dir * (larg_m * 0.5)
                    offset = (pos_base.x(), pos_base.y(), default_z)
            else:
                offset = (sel_wf.center.x(), sel_wf.center.y(), default_z)

            new_module_group = CabinetBuilder.build_module_group(params, offset=offset)

            if n_dir.length() > 1e-4:
                from .magnetic_drag import get_module_bounds, get_bounds_min_projection
                b = get_module_carcass_bounds(new_module_group) or get_module_bounds(new_module_group)
                if b is not None:
                    cur_min_n = get_bounds_min_projection(b, n_dir)
                    wall_face_n = QVector3D.dotProduct(sel_wf.center, n_dir)
                    delta_n = (wall_face_n - cur_min_n) + 0.001
                    if abs(delta_n) > 1e-4:
                        shift = n_dir * delta_n
                        targets = getattr(new_module_group, "children", []) or [new_module_group]
                        for t in targets:
                            m_sub = getattr(t, "mesh", None)
                            if m_sub and hasattr(m_sub, "vertices"):
                                for v in m_sub.vertices:
                                    v.position += shift
                                m_sub._mut_serial = getattr(m_sub, "_mut_serial", 0) + 1
                            if getattr(t, "ext", None) is not None:
                                if "orig_vertices" in t.ext:
                                    t.ext["orig_vertices"] = [orig + shift for orig in t.ext["orig_vertices"]]
                                if "hinge_pivot" in t.ext and isinstance(t.ext["hinge_pivot"], QVector3D):
                                    t.ext["hinge_pivot"] += shift
                        if "trazomob_module" in new_module_group.ext:
                            mod_ext = new_module_group.ext["trazomob_module"]
                            old_off = mod_ext.get("offset", (0.0, 0.0, 0.0))
                            mod_ext["offset"] = (
                                float(old_off[0]) + float(shift.x()),
                                float(old_off[1]) + float(shift.y()),
                                float(old_off[2]) + float(shift.z()),
                            )
        elif ref_mod is not None:
            ref_rot_z = 0.0
            if hasattr(ref_mod, "ext") and "trazomob_module" in ref_mod.ext:
                ref_rot_z = float(ref_mod.ext["trazomob_module"].get("rot_z", 0.0)) % 360.0
            params["rot_z"] = ref_rot_z

            if ref_b is not None:
                novo_P_m = float(params.get("profundidade", 550.0)) / 1000.0
                half_diff = (novo_L_m - novo_P_m) * 0.5
                if abs(ref_rot_z) < 1e-4:
                    offset = (ref_b[1], ref_b[2], ref_b[4])
                elif abs(ref_rot_z - 180.0) < 1e-4:
                    offset = (ref_b[0] - novo_L_m, ref_b[2], ref_b[4])
                elif abs(ref_rot_z - 90.0) < 1e-4:
                    offset = (ref_b[0] - half_diff, ref_b[3] + half_diff, ref_b[4])
                elif abs(ref_rot_z - 270.0) < 1e-4:
                    offset = (ref_b[0] - half_diff, (ref_b[2] - novo_L_m) + half_diff, ref_b[4])
                else:
                    offset = (ref_b[1], ref_b[2], ref_b[4])
            else:
                offset = (0.0, 0.0, default_z)
            new_module_group = CabinetBuilder.build_module_group(params, offset=offset)
        else:
            camera = getattr(self.viewport, "camera", None)
            if camera is not None and hasattr(camera, "target"):
                offset = (camera.target.x(), camera.target.y(), default_z)
            else:
                offset = (0.0, 0.0, default_z)
            new_module_group = CabinetBuilder.build_module_group(params, offset=offset)

        def apply_insert(sc):
            target_layer = getattr(new_module_group, "layer", None)
            if target_layer and hasattr(sc, "layer") and hasattr(sc, "layers"):
                if sc.layer(target_layer) is None:
                    from core.layers import Layer
                    sc.layers.append(Layer(target_layer))
            sc.groups.append(new_module_group)
            sc.selection = {new_module_group}

        self.viewport.history.execute(SnapshotImport(apply_insert))
        self.viewport.notify_scene_changed()

        # Desloca o frame 3D armado para a posição imediatamente contígua para o próximo móvel (estilo Promob)
        if active_slot is not None and hasattr(wall_mgr, "advance_slot_after_placement"):
            placed_larg_m = float(params.get("largura", 800.0)) / 1000.0
            wall_mgr.advance_slot_after_placement(placed_larg_m)

        self.viewport.update()

        # Abre o módulo recém-inserido diretamente no painel lateral
        if self.sidebar_panel is not None:
            self.sidebar_panel.focus_panel()
            self.sidebar_panel.load_module(new_module_group)

        if hasattr(self.viewport, "flash_status"):
            self.viewport.flash_status(f"✨ Módulo '{new_module_group.name}' inserido na cena!")

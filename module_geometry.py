# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Utilitários geométricos, alinhamento espacial e classificação funcional de módulos do TrazoMob.

Concentra:
1. Cálculo de limites de caixaria (desconsiderando portas, puxadores e frentes projetadas).
2. Vetores normais de alinhamento traseiro/lateral conforme rotação espacial.
3. Preservação de alinhamento traseiro e canto de parede durante redimensionamento.
4. Classificação funcional de categorias para herança de medidas (inferior, aéreo, torre, esquadrias).
"""
from __future__ import annotations

import math
from typing import Any, Tuple, Optional

from PySide6.QtGui import QVector3D

from core.group import Group, iter_placements
from .schema import kind_of, module_params


def get_module_carcass_bounds(mod: Group) -> Optional[Tuple[float, float, float, float, float, float]]:
    """Calcula os limites em metros da caixaria (min_x, max_x, min_y, max_y, min_z, max_z).
    
    Ignora frentes móveis, portas abertas, puxadores e perfis de acabamento para obter o volume
    bruto real da estrutura de madeira ou alvenaria.
    """
    if mod is None:
        return None

    min_x, max_x = float("inf"), float("-inf")
    min_y, max_y = float("inf"), float("-inf")
    min_z, max_z = float("inf"), float("-inf")
    found = False
    tipo = ""
    is_esquadria = getattr(mod, "layer", "") == "ESQUADRIAS"
    if getattr(mod, "ext", None) and isinstance(mod.ext, dict):
        if kind_of(mod) == "esquadria":
            is_esquadria = True
        tipo = str(module_params(mod).get("tipo", ""))
        if tipo.startswith(("porta_", "janela_")):
            is_esquadria = True

    if is_esquadria:
        ignore_terms: tuple[str, ...] = ("Folha", "Fechadura", "Ferragem", "Maçaneta", "Alavanca", "Espelho", "Puxador")
    elif tipo == "peca_porta":
        ignore_terms = ("Puxador", "Perfil", "Base Projetada")
    else:
        ignore_terms = ("Porta", "Frente", "Puxador", "Perfil", "Base Projetada")

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
        QVector3D(b_old[0], b_old[3], 0.0), QVector3D(b_old[1], b_old[3], 0.0),
    ]
    corners_new = [
        QVector3D(b_new[0], b_new[2], 0.0), QVector3D(b_new[1], b_new[2], 0.0),
        QVector3D(b_new[0], b_new[3], 0.0), QVector3D(b_new[1], b_new[3], 0.0),
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
                    t.ext["orig_vertices"] = [p + shift for p in t.ext["orig_vertices"]]
                if "trazomob" in t.ext and "rot_origin" in t.ext["trazomob"]:
                    orig_ro = t.ext["trazomob"]["rot_origin"]
                    if isinstance(orig_ro, QVector3D):
                        t.ext["trazomob"]["rot_origin"] = orig_ro + shift


def get_reference_module(scene) -> Optional[Group]:
    """Retorna o módulo de referência selecionado ou o último adicionado na cena."""
    if scene is None:
        return None
    sel = getattr(scene, "selection", None)
    if sel:
        from .assembly import is_module
        for s in sel:
            if is_module(s):
                return s
    grps = getattr(scene, "groups", [])
    if grps:
        from .assembly import is_module
        for g in reversed(grps):
            if is_module(g):
                return g
    return None


def get_module_category(tipo: str, default_z: float = 0.0) -> str:
    """Classifica o módulo em uma categoria funcional para herança de cotas e alinhamento contíguo.

    Categorias:
    - 'porta': esquadrias do tipo porta (nível do solo Z=0)
    - 'janela': esquadrias do tipo janela (peitoril elevado Z>0)
    - 'aereo': módulos aéreos suspensos (Z >= 0.8m, nichos de parede, aéreos)
    - 'alto': torres de eletro, roupeiros, armários verticais altos (H >= 1.6m)
    - 'bancada': tampos e bancadas de pedra / marmoraria
    - 'inferior': balcões de chão, gaveteiros, etc. (Z < 0.8m)
    """
    t = str(tipo).lower()
    if "porta" in t and "porta_tempero" not in t:
        return "porta"
    if "janela" in t:
        return "janela"
    if "bancada" in t or "ilha" in t:
        return "bancada"
    if any(k in t for k in ("aereo", "nicho")):
        return "aereo"
    if any(k in t for k in ("torre", "geladeira", "roupeiro", "armario")):
        return "alto"
    if "banheiro" in t or "gabinete" in t:
        return "banheiro"
    if float(default_z) >= 0.8:
        return "aereo"
    return "inferior"


def is_compatible_category(cat1: str, cat2: str) -> bool:
    """Retorna True se duas categorias devem compartilhar e herdar altura, profundidade e alinhamento."""
    # Portas e Janelas NUNCA são compatíveis entre si para herdar elevações ou medidas
    if cat1 in ("porta", "janela") or cat2 in ("porta", "janela"):
        return False
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
    """Preenche um dicionário de parâmetros completo a partir do schema do catálogo."""
    params = dict(mod_data)
    params["largura"] = float(mod_data.get("largura", 800.0))
    params["altura"] = float(mod_data.get("altura", 720.0))
    params["profundidade"] = float(mod_data.get("profundidade", 550.0))
    params["espessura"] = float(mod_data.get("espessura", 15.0))
    params["rodape"] = float(mod_data.get("rodape", 100.0 if params.get("has_rodape", True) else 0.0))
    return params


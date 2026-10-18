# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Extração e agrupamento de peças 3D da cena para plano de corte."""
from __future__ import annotations

from typing import Any

from core.group import iter_placements


def _get_entity_bbox(entity, xform=None):
    positions = []
    mesh = getattr(entity, "mesh", None)
    if mesh is not None:
        for v in mesh.vertices:
            p = v.position
            if xform is not None:
                p = xform.map(p)
            positions.append(p)

    if not positions:
        return None

    xs = [p.x() for p in positions]
    ys = [p.y() for p in positions]
    zs = [p.z() for p in positions]

    return (max(xs) - min(xs), max(ys) - min(ys), max(zs) - min(zs))


def detect_grain_orientation(
    material_name: str,
    piece_name: str = "",
    dims_sorted: tuple[float, float, float] | None = None,
) -> bool:
    """Detecta automaticamente se uma peça pode ignorar o sentido do veio.

    Retorna True se a peça pode girar livremente (unicolor, sem veio perceptível).
    Retorna False se o material possui veio orientado (madeirado, ripado, etc.).
    """
    if isinstance(material_name, dict):
        material_name = material_name.get("nome") or material_name.get("material") or ""
    mat_lower = str(material_name or "").lower()

    # 1. Padrões característicos amadeirados / com sentido obrigatório
    veio_keywords = [
        "amadeirado", "freijo", "freijó", "carvalho", "nogal", "nogueira", "louro",
        "teka", "teca", "cedro", "ipê", "ipe", "imbuia", "pinus", "marfim",
        "castanho", "noce", "rovere", "canyon", "rustic", "wood", "ripado",
        "compensado", "palha", "linho", "savana", "itapuã", "itapua",
    ]
    if any(k in mat_lower for k in veio_keywords):
        return False

    # 2. Padrões comprovadamente unicolores ou neutros (podem girar para otimizar corte)
    unicolor_keywords = [
        "branco", "white", "preto", "black", "grafite", "cinza", "grey", "gray",
        "tx", "silk", "liso", "matt", "fosco", "brilho", "argila", "verde",
        "azul", "rosa", "amarelo", "vermelho", "bege", "areia", "cru", "mdf cru"
    ]
    if any(k in mat_lower for k in unicolor_keywords):
        return True

    # Por padrão em marcenaria tradicional, se o nome não for expressamente unicolor, preserva o veio
    return False


def extract_parts(scene, selected_only: bool = False) -> list[dict[str, Any]]:
    parts = []
    groups = getattr(scene, "groups", [])
    selected_set = set(getattr(scene, "selected_groups", []))

    from core.group import iter_placements

    idx = 1
    # Se o grupo for um container de módulo, inspeciona seus filhos
    for g in groups:
        if selected_only and g not in selected_set:
            continue
        if not getattr(scene, "entity_visible", lambda _: True)(g):
            continue
        if getattr(g, "layer", None) in ("Paredes", "Piso", "Bancadas", "Walls", "Floor"):
            continue

        # Se for um container mestre de módulo com peças filhas
        if getattr(g, "children", None) and hasattr(g, "ext") and g.ext and ("trazomob_module" in g.ext or "corte_cloud_module" in g.ext or "hellomob_module" in g.ext):
            for pg, m in iter_placements(g):
                if pg is g:
                    continue
                dims = _get_entity_bbox(pg, m)
                if not dims:
                    continue

                dx_mm = round(dims[0] * 1000.0, 1)
                dy_mm = round(dims[1] * 1000.0, 1)
                dz_mm = round(dims[2] * 1000.0, 1)

                sorted_dims = sorted([dx_mm, dy_mm, dz_mm])
                espessura = sorted_dims[0]
                largura = sorted_dims[1]
                comprimento = sorted_dims[2]

                if espessura < 1.0 or comprimento < 5.0 or largura < 5.0:
                    continue

                saved_meta = {}
                if hasattr(pg, "ext") and isinstance(pg.ext, dict):
                    saved_meta = pg.ext.get("trazomob") or pg.ext.get("corte_cloud") or pg.ext.get("hellomob") or {}

                if saved_meta.get("espessura") is not None:
                    espessura = float(saved_meta["espessura"])
                if saved_meta.get("largura") is not None:
                    largura = float(saved_meta["largura"])
                if saved_meta.get("comprimento") is not None:
                    comprimento = float(saved_meta["comprimento"])

                name = saved_meta.get("nome") or getattr(pg, "name", None) or f"Peca_{idx}"
                mat_name = saved_meta.get("material") or getattr(pg, "material", None) or f"MDF {round(espessura)}mm"

                # Detecção inteligente de veio se não definido explicitamente
                ign_veio = saved_meta.get("ignorar_veio")
                if ign_veio is None:
                    ign_veio = detect_grain_orientation(mat_name, name, (espessura, largura, comprimento))
                else:
                    ign_veio = bool(ign_veio)

                operacoes = saved_meta.get("operacoes", [])

                parts.append({
                    "id": idx,
                    "group": pg,
                    "nome": name,
                    "comprimento": round(comprimento, 1),
                    "largura": round(largura, 1),
                    "espessura": round(espessura, 1),
                    "material": mat_name,
                    "fita_c1": saved_meta.get("fita_c1", False),
                    "fita_c2": saved_meta.get("fita_c2", False),
                    "fita_l1": saved_meta.get("fita_l1", False),
                    "fita_l2": saved_meta.get("fita_l2", False),
                    "ignorar_veio": ign_veio,
                    "operacoes": operacoes,
                    "quantidade": 1,
                })
                idx += 1
            continue

        targets = [g]

        for tgt in targets:
            for pg, m in iter_placements(tgt):
                dims = _get_entity_bbox(pg, m)
                if not dims:
                    continue

                dx_mm = round(dims[0] * 1000.0, 1)
                dy_mm = round(dims[1] * 1000.0, 1)
                dz_mm = round(dims[2] * 1000.0, 1)

                sorted_dims = sorted([dx_mm, dy_mm, dz_mm])
                espessura = sorted_dims[0]
                largura = sorted_dims[1]
                comprimento = sorted_dims[2]

                if espessura < 1.0 or comprimento < 5.0 or largura < 5.0:
                    continue

                saved_meta = {}
                if hasattr(tgt, "ext") and isinstance(tgt.ext, dict):
                    saved_meta = tgt.ext.get("trazomob") or tgt.ext.get("corte_cloud") or tgt.ext.get("hellomob") or {}
                if not saved_meta and hasattr(pg, "ext") and isinstance(pg.ext, dict):
                    saved_meta = pg.ext.get("trazomob") or pg.ext.get("corte_cloud") or pg.ext.get("hellomob") or {}

                if saved_meta.get("espessura") is not None:
                    espessura = float(saved_meta["espessura"])
                if saved_meta.get("largura") is not None:
                    largura = float(saved_meta["largura"])
                if saved_meta.get("comprimento") is not None:
                    comprimento = float(saved_meta["comprimento"])

                name = saved_meta.get("nome") or getattr(tgt, "name", None) or getattr(pg, "name", None) or f"Peca_{idx}"
                mat_name = saved_meta.get("material") or getattr(tgt, "material", None) or getattr(pg, "material", None) or f"MDF {round(espessura)}mm"
                if isinstance(mat_name, dict):
                    mat_name = mat_name.get("nome") or mat_name.get("material") or f"MDF {round(espessura)}mm"
                mat_name = str(mat_name or f"MDF {round(espessura)}mm")

                ign_veio = saved_meta.get("ignorar_veio")
                if ign_veio is None:
                    ign_veio = detect_grain_orientation(mat_name, name, (espessura, largura, comprimento))
                else:
                    ign_veio = bool(ign_veio)

                operacoes = saved_meta.get("operacoes", [])

                parts.append({
                    "id": idx,
                    "group": tgt,
                    "nome": name,
                    "comprimento": round(comprimento, 1),
                    "largura": round(largura, 1),
                    "espessura": round(espessura, 1),
                    "material": mat_name,
                    "fita_c1": saved_meta.get("fita_c1", False),
                    "fita_c2": saved_meta.get("fita_c2", False),
                    "fita_l1": saved_meta.get("fita_l1", False),
                    "fita_l2": saved_meta.get("fita_l2", False),
                    "ignorar_veio": ign_veio,
                    "operacoes": operacoes,
                    "quantidade": 1,
                })
                idx += 1

    return parts


def group_similar_parts(parts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = {}
    for p in parts:
        # Serializa operações para agrupamento estrito
        ops_key = tuple(
            (o.get("tipo"), o.get("face"), o.get("x"), o.get("y"), o.get("diametro"))
            for o in p.get("operacoes", [])
        )
        key = (
            p["nome"],
            p["comprimento"],
            p["largura"],
            p["espessura"],
            p["material"],
            p["fita_c1"],
            p["fita_c2"],
            p["fita_l1"],
            p["fita_l2"],
            p["ignorar_veio"],
            ops_key,
        )
        if key in grouped:
            grouped[key]["quantidade"] += 1
        else:
            grouped[key] = dict(p)
    return list(grouped.values())



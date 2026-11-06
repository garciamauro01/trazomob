# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Geometria 3D simplificada de ferragens.

Cada ferragem é criada como um grupo filho do módulo (``Group``) e marcada em
``ext["trazomob"]["kind"] = "hardware"``. Isso permite:

* localizá-la facilmente (``is_hardware_group``);
* excluí-la do cutlist / caixaria / cálculos de área;
* ocultá-la no viewport se desejado (``hidden=True``).

São geometrias *esquemáticas*: suficientes para visualizar onde vão as
dobradiças, corrediças, trilhos e pés, sem depender de um CAD paramétrico por
fornecedor.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from PySide6.QtGui import QVector3D

from core.group import Group, iter_placements
from core.mesh import Mesh
from ..domain.hardware import HARDWARE_CATALOG

Coord = Tuple[float, float, float]

_COLOR_METAL_CLARO = (0.78, 0.80, 0.84)
_COLOR_METAL_ESCURO = (0.35, 0.37, 0.42)
_COLOR_IMEX = (0.55, 0.58, 0.64)


def is_hardware_group(group: Any) -> bool:
    """Indica se ``group`` é uma representação 3D de ferragem."""
    if group is None:
        return False
    ext = getattr(group, "ext", None)
    if isinstance(ext, dict):
        tm = ext.get("trazomob")
        if isinstance(tm, dict) and tm.get("kind") == "hardware":
            return True
        if ext.get("trazomob_hardware") is True:
            return True
    name = str(getattr(group, "name", ""))
    return name.startswith("Ferragem -")


def hardware_row(name: str, key: str, mesh: Mesh, module_tag: str = "",
                 linked_piece: str | None = None) -> Group:
    """Cria um grupo filho que representa uma ferragem."""
    tm: Dict[str, Any] = {
        "kind": "hardware",
        "hardware_code": key,
        "nome": name,
        "modulo": module_tag,
    }
    if linked_piece:
        tm["linked_piece"] = linked_piece
    g = Group(mesh, name=f"Ferragem - {name}")
    g.ext = {
        "trazomob": tm,
        "trazomob_hardware": True,
    }
    return g


# ------------------------------------------------------------- primitivas

def _bounds(mesh: Mesh | None):
    if mesh is None or not getattr(mesh, "vertices", None):
        return None
    xs = [v.position.x() for v in mesh.vertices]
    ys = [v.position.y() for v in mesh.vertices]
    zs = [v.position.z() for v in mesh.vertices]
    return min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)


def _add_box(
    mesh: Mesh,
    x0: float, y0: float, z0: float,
    sx: float, sy: float, sz: float,
    color: tuple[float, float, float] = _COLOR_METAL_ESCURO,
) -> None:
    x1, y1, z1 = x0 + sx, y0 + sy, z0 + sz
    v = [
        QVector3D(x0, y0, z0), QVector3D(x1, y0, z0),
        QVector3D(x1, y1, z0), QVector3D(x0, y1, z0),
        QVector3D(x0, y0, z1), QVector3D(x1, y0, z1),
        QVector3D(x1, y1, z1), QVector3D(x0, y1, z1),
    ]
    faces = [  # (verts, color)
        ([2, 3, 0, 1], color),
        ([4, 5, 6, 7], color),
        ([0, 4, 7, 3], color),
        ([1, 2, 6, 5], color),
        ([3, 7, 6, 2], color),
        ([0, 1, 5, 4], color),
    ]
    for idxs, c in faces:
        f = mesh.add_face([v[i] for i in idxs])
        f.attrs["color"] = c


def _add_cylinder_y(
    mesh: Mesh,
    cx: float, cz: float,
    y0: float, y1: float,
    r: float,
    color: tuple[float, float, float] = _COLOR_METAL_CLARO,
    segs: int = 16,
) -> None:
    circ0 = [
        QVector3D(cx + r * math.cos(2 * math.pi * i / segs), y0,
                   cz + r * math.sin(2 * math.pi * i / segs))
        for i in range(segs)
    ]
    circ1 = [
        QVector3D(cx + r * math.cos(2 * math.pi * i / segs), y1,
                   cz + r * math.sin(2 * math.pi * i / segs))
        for i in range(segs)
    ]
    f0 = mesh.add_face(list(reversed(circ0)))
    f0.attrs["color"] = color
    f1 = mesh.add_face(circ1)
    f1.attrs["color"] = color
    for i in range(segs):
        nxt = (i + 1) % segs
        f = mesh.add_face([circ0[i], circ0[nxt], circ1[nxt], circ1[i]])
        f.attrs["color"] = color


def _add_cylinder_z(
    mesh: Mesh,
    cx: float, cy: float,
    z0: float, z1: float,
    r: float,
    color: tuple[float, float, float] = _COLOR_METAL_CLARO,
    segs: int = 16,
) -> None:
    circ0 = [
        QVector3D(cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs), z0)
        for i in range(segs)
    ]
    circ1 = [
        QVector3D(cx + r * math.cos(2 * math.pi * i / segs), cy + r * math.sin(2 * math.pi * i / segs), z1)
        for i in range(segs)
    ]
    f0 = mesh.add_face(list(reversed(circ0)))
    f0.attrs["color"] = color
    f1 = mesh.add_face(circ1)
    f1.attrs["color"] = color
    for i in range(segs):
        nxt = (i + 1) % segs
        f = mesh.add_face([circ0[i], circ0[nxt], circ1[nxt], circ1[i]])
        f.attrs["color"] = color


def _hinge_positions(altura_m: float, n: int) -> List[float]:
    """Posições Z (m) das dobradiças, com afastamento de 100 mm dos cantos."""
    h = float(altura_m or 0.0)
    if h <= 0:
        return []
    base, topo = 0.1, h - 0.1
    if n <= 1:
        return [base]
    passo = (topo - base) / (n - 1)
    return [base + i * passo for i in range(n)]


def _make_hinge(name: str, key: str, p_min: QVector3D, p_max: QVector3D,
                door_side: str | None, count: int, module_tag: str = "",
                linked_piece: str | None = None) -> Group | None:
    """Grupo com ``count`` canecos na lateral que recebe a dobradiça."""
    n = max(int(count or 0), 0)
    if n == 0:
        return None
    target = linked_piece or name
    face_h = p_max.z() - p_min.z()
    zs = _hinge_positions(face_h, n)
    if door_side == "left":
        x_edge = p_min.x()
    elif door_side == "right":
        x_edge = p_max.x()
    else:
        # basculantes? sem lado definido -> proximidade da quina esquerda
        x_edge = p_min.x()

    dx = 0.0215 if door_side != "right" else -0.0215
    y_back = p_max.y()
    mesh = Mesh()
    for zoff in zs:
        cz = p_min.z() + float(zoff)
        _add_cylinder_y(mesh, x_edge + dx, cz, y_back, y_back + 0.016, 0.0175,
                         _COLOR_METAL_CLARO, segs=16)
    return hardware_row(f"Dobradiças ({n}x) {target}", key, mesh, module_tag,
                        linked_piece=target)


def _drawer_index_from_name(name: str | None) -> int | None:
    """Extrai o índice 1-based da gaveta a partir do nome da peça."""
    import re
    m = re.search(r"(?:gaveta|frente)\s*(\d+)", (name or "").lower())
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _make_drawer_runners(
    name: str, key: str, bounds: tuple[float, ...], num_gavetas: int,
    module_tag: str = "",
    pieces: List[Group] | None = None,
) -> List[Group]:
    """Grupos com corrediças telescópicas em escada vertical (esquemático).

    Cria um grupo por gaveta e o vincula a uma peça da gaveta para que o
    trilho interno acompanhe a abertura/fechamento da gaveta.
    """
    n = max(int(num_gavetas or 0), 0)
    if n == 0:
        return []
    min_x, max_x, min_y, max_y, min_z, max_z = bounds
    h = max_z - min_z
    cell = h / n
    length = max(0.1, (max_y - min_y) - 0.075)
    groups: List[Group] = []

    targets: Dict[int, str] = {}
    for p in pieces or []:
        idx = _drawer_index_from_name(getattr(p, "name", None))
        if idx is not None and idx not in targets:
            targets[idx] = str(getattr(p, "name", ""))

    for i in range(n):
        cz = min_z + cell * (i + 0.55)
        target = targets.get(i + 1)
        mesh = Mesh()
        # par esquerda/direita, apoiadas nas laterais da gaveta
        _add_box(mesh, min_x + 0.008, min_y + 0.0375, cz - 0.025,
                  0.014, length, 0.050, _COLOR_IMEX)
        _add_box(mesh, max_x - 0.022, min_y + 0.0375, cz - 0.025,
                  0.014, length, 0.050, _COLOR_IMEX)
        g = hardware_row(
            f"Corrediças Gaveta {i + 1} (2x) {module_tag or name}".strip(),
            key, mesh, module_tag, linked_piece=target,
        )
        groups.append(g)
    return groups


def _make_sliding_tracks(
    name: str, key: str, bounds: tuple[float, ...], num_rails: int,
    module_tag: str = "",
) -> Group | None:
    """Trilhos superior e inferior para portas de correr."""
    n = max(int(num_rails or 0), 0)
    if n == 0:
        return None
    min_x, max_x, min_y, max_y, min_z, max_z = bounds
    w = max_x - min_x
    # duas vias por trilho (trilho duplo)
    num_channels = 2
    mesh = Mesh()
    for z in (min_z + 0.02, max_z - 0.022):
        for c in range(num_channels):
            y_off = 0.012 + c * 0.030
            _add_box(mesh, min_x + 0.005, min_y + y_off, z,
                      w - 0.010, 0.016, 0.006, _COLOR_IMEX)
    return hardware_row(f"Trilhos ({n}x) {module_tag or name}".strip(), key, mesh, module_tag)


def _make_feet(name: str, key: str, bounds: tuple[float, ...], n: int,
               module_tag: str = "") -> Group | None:
    count = max(int(n or 0), 0)
    if count == 0:
        return None
    min_x, max_x, min_y, max_y, min_z, max_z = bounds
    from itertools import repeat
    if count <= 4:
        positions = [(min_x + 0.06, min_y + 0.06), (max_x - 0.06, min_y + 0.06),
                     (min_x + 0.06, max_y - 0.06), (max_x - 0.06, max_y - 0.06)]
    else:
        positions = [(min_x + 0.06, min_y + 0.06), (max_x - 0.06, min_y + 0.06)]
    mesh = Mesh()
    for x, y in positions[:count]:
        _add_cylinder_z(mesh, x, y, min_z - 0.08, min_z, 0.030,
                        (0.35, 0.36, 0.40), segs=12)
    return hardware_row(f"Pés Niveladores ({count}x) {module_tag or name}".strip(), key, mesh, module_tag)


def build_module_hardware_3d(
    master: Group | None,
    hardware_items: Any,
    pieces: List[Group] | None = None,
    params: Dict[str, Any] | None = None,
) -> List[Group]:
    """Cria grupos 3D esquemáticos de ferragem e os anexa ao módulo.

    Retorna a lista de grupos criados. Nunca lança exceção.
    """
    if master is None:
        return []
    params = params or {}
    try:
        from ..domain.hardware import deserialize_hardware
        if isinstance(hardware_items, str):
            import json
            hardware_items = json.loads(hardware_items)
        items = (
            deserialize_hardware(hardware_items)
            if not isinstance(hardware_items, list)
            or (hardware_items and not hasattr(hardware_items[0], "key"))
            else hardware_items
        )
    except Exception:
        items = []

    if not items:
        return []

    # Aceita tanto lista de dicts quanto HardwareItem
    try:
        from ..domain.hardware import HardwareItem  # noqa: F401  (type check only)
    except Exception:
        pass

    bb_by_piece: List[Tuple[Group, Tuple[float, ...]]] = []
    for p in pieces or []:
        b = _bounds(getattr(p, "mesh", None))
        if b:
            bb_by_piece.append((p, b))

    module_tag = str(params.get("tipo", "Módulo"))
    by_key = {getattr(it, "key", None): it for it in items}

    # limites do módulo (caixaria, aproximadamente, incluindo frentes)
    xs: List[float] = []
    ys: List[float] = []
    zs: List[float] = []
    for _p, b in bb_by_piece:
        xs.extend([b[0], b[1]])
        ys.extend([b[2], b[3]])
        zs.extend([b[4], b[5]])
    full = (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs)) if xs else None

    criadas: List[Group] = []

    # ── Dobradiças ──────────────────────────────────────────────────
    dobra = by_key.get("dobradica_35mm")
    if dobra is not None and bb_by_piece:
        per_door = int((getattr(dobra, "posicao", {}) or {}).get("por_porta", 2))
        for p, b in bb_by_piece:
            ext = getattr(p, "ext", None)
            tm = ext.get("trazomob", {}) if isinstance(ext, dict) else {}
            door_side = tm.get("door_side") if isinstance(tm, dict) else None
            nome_p = str(getattr(p, "name", "")).lower()
            if door_side or "porta" in nome_p or "frente de gaveta" in nome_p or "frente -" in nome_p:
                # só portas de abrir: frente de gaveta recebe corrediça, não dobradiça
                if "gaveta" in nome_p and not door_side:
                    continue
                p_min = QVector3D(b[0], b[2], b[4])
                p_max = QVector3D(b[1], b[3], b[5])
                g = _make_hinge(
                    getattr(p, "name", "Porta"),
                    "dobradica_35mm", p_min, p_max, door_side, per_door, module_tag,
                    linked_piece=getattr(p, "name", None),
                )
                if g is not None:
                    criadas.append(g)

    # ── Corrediças ──────────────────────────────────────────────────
    corredica = None
    if "corredica_40" in by_key:
        corredica = by_key["corredica_40"]
    elif "corredica_50" in by_key:
        corredica = by_key["corredica_50"]
    num_gavetas = int(params.get("num_gavetas", 0) or 0)
    if corredica is not None and full is not None and num_gavetas:
        for g in _make_drawer_runners(
            module_tag, getattr(corredica, "key", "corredica_40"), full, num_gavetas, module_tag,
            pieces=[p for p, _b in bb_by_piece],
        ):
            criadas.append(g)

    # ── Trilhos ─────────────────────────────────────────────────────
    trilho = by_key.get("trilho_correr")
    num_portas = int(params.get("num_portas", 0) or 0)
    if trilho is not None and full is not None and "correr" in str(params.get("tipo", "")).lower():
        g = _make_sliding_tracks(module_tag, "trilho_correr", full, num_portas, module_tag)
        if g is not None:
            criadas.append(g)

    # ── Pés niveladores ─────────────────────────────────────────────
    pes = by_key.get("pes_nivelador")
    if pes is not None and full is not None:
        g = _make_feet(module_tag, "pes_nivelador", full, int(pes.quantidade or 4), module_tag)
        if g is not None:
            criadas.append(g)

    for g in criadas:
        master.children = list(getattr(master, "children", []) or []) + [g]

    return criadas

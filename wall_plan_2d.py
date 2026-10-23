# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Estrutura de dados para Planta Baixa 2D de paredes e extrusão para malhas 3D sólidas."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional, Dict, Set

from PySide6.QtGui import QVector3D
from core.mesh import Mesh
from core.group import Group
from core.layers import Layer
from core.triangulate import triangulate


Point2D = Tuple[float, float]


def dist_2d(p1: Point2D, p2: Point2D) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


@dataclass
class WallNode2D:
    """Vértice / nó da planta baixa 2D."""
    id: int
    x: float
    y: float

    @property
    def pt(self) -> Point2D:
        return (self.x, self.y)

    def to_qvector3d(self, z: float = 0.0) -> QVector3D:
        return QVector3D(self.x, self.y, z)


@dataclass
class WallSegment2D:
    """Segmento de parede conectando dois nós."""
    id: int
    node_a_id: int
    node_b_id: int
    thickness: float = 0.15  # em metros

    def length(self, graph: WallGraph2D) -> float:
        na = graph.get_node(self.node_a_id)
        nb = graph.get_node(self.node_b_id)
        if na is None or nb is None:
            return 0.0
        return dist_2d(na.pt, nb.pt)


class WallGraph2D:
    """Grafo topológico 2D de paredes.
    
    Gerencia nós, arestas/segmentos, junções (L, T, X) e gera os contornos
    2D unificados e polígonos para extrusão direta em sólidos 3D.
    """

    def __init__(self, default_thickness: float = 0.15, default_height: float = 2.60):
        self.default_thickness = default_thickness
        self.default_height = default_height
        self.nodes: Dict[int, WallNode2D] = {}
        self.segments: Dict[int, WallSegment2D] = {}
        self._next_node_id: int = 1
        self._next_seg_id: int = 1

    def clear(self) -> None:
        self.nodes.clear()
        self.segments.clear()
        self._next_node_id = 1
        self._next_seg_id = 1

    def is_empty(self) -> bool:
        return len(self.segments) == 0

    def add_node(self, x: float, y: float, merge_threshold: float = 0.05) -> int:
        """Adiciona um nó ou reutiliza um nó existente próximo dentro da tolerância."""
        for n_id, node in self.nodes.items():
            if dist_2d((x, y), (node.x, node.y)) <= merge_threshold:
                return n_id
        n_id = self._next_node_id
        self._next_node_id += 1
        self.nodes[n_id] = WallNode2D(id=n_id, x=x, y=y)
        return n_id

    def get_node(self, node_id: int) -> Optional[WallNode2D]:
        return self.nodes.get(node_id)

    def add_segment(self, x1: float, y1: float, x2: float, y2: float, thickness: Optional[float] = None) -> Optional[int]:
        """Cria uma parede conectando (x1, y1) a (x2, y2).
        
        Se o ponto inicial ou final cair em cima de uma parede existente,
        a parede existente é subdividida no ponto de contato criando uma junção em T perfeita.
        """
        if dist_2d((x1, y1), (x2, y2)) < 0.02:
            return None

        # 1. Verifica se (x1, y1) cai sobre algum segmento existente e faz split se necessário
        na_id = self._get_or_split_at_point(x1, y1)
        # 2. Verifica se (x2, y2) cai sobre algum segmento existente e faz split se necessário
        nb_id = self._get_or_split_at_point(x2, y2)

        if na_id == nb_id:
            return None

        # Evita segmento duplicado
        for seg in self.segments.values():
            if (seg.node_a_id == na_id and seg.node_b_id == nb_id) or (seg.node_a_id == nb_id and seg.node_b_id == na_id):
                return seg.id

        th = thickness if thickness is not None else self.default_thickness
        seg_id = self._next_seg_id
        self._next_seg_id += 1
        self.segments[seg_id] = WallSegment2D(id=seg_id, node_a_id=na_id, node_b_id=nb_id, thickness=th)
        return seg_id

    def _get_or_split_at_point(self, x: float, y: float, threshold: float = 0.05) -> int:
        """Encontra ou cria nó em (x, y), subdividindo segmento existente se estiver no meio."""
        # Primeiro checa nós existentes
        for n_id, node in self.nodes.items():
            if dist_2d((x, y), (node.x, node.y)) <= threshold:
                return n_id

        # Checa se o ponto cai em algum segmento existente
        pt = (x, y)
        for seg_id, seg in list(self.segments.items()):
            na = self.nodes[seg.node_a_id]
            nb = self.nodes[seg.node_b_id]
            proj_pt, t = self._project_point_on_segment(pt, na.pt, nb.pt)
            if 0.03 < t < 0.97 and dist_2d(pt, proj_pt) <= threshold:
                # Subdivide o segmento existente neste ponto
                split_node_id = self.add_node(proj_pt[0], proj_pt[1], merge_threshold=0.01)
                orig_b = seg.node_b_id
                th = seg.thickness
                # Segmento existente passa a ir de na até split_node
                seg.node_b_id = split_node_id
                # Novo segmento vai de split_node até orig_b
                new_s_id = self._next_seg_id
                self._next_seg_id += 1
                self.segments[new_s_id] = WallSegment2D(id=new_s_id, node_a_id=split_node_id, node_b_id=orig_b, thickness=th)
                return split_node_id

        # Se não caiu em nenhum segmento, cria um nó livre
        return self.add_node(x, y, merge_threshold=threshold)

    @staticmethod
    def _project_point_on_segment(p: Point2D, a: Point2D, b: Point2D) -> Tuple[Point2D, float]:
        dx = b[0] - a[0]
        dy = b[1] - a[1]
        l2 = dx * dx + dy * dy
        if l2 < 1e-9:
            return a, 0.0
        t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / l2))
        return (a[0] + t * dx, a[1] + t * dy), t

    def snap_point(self, x: float, y: float, threshold: float = 0.20) -> Tuple[float, float, Optional[str]]:
        """Atracão magnética para auxílio ao desenho do usuário."""
        # 1. Cantos / nós
        for node in self.nodes.values():
            if dist_2d((x, y), (node.x, node.y)) <= threshold:
                return node.x, node.y, "canto"

        # 2. Ao longo de paredes (Junção em T)
        for seg in self.segments.values():
            na = self.nodes[seg.node_a_id]
            nb = self.nodes[seg.node_b_id]
            proj, t = self._project_point_on_segment((x, y), na.pt, nb.pt)
            if 0.0 <= t <= 1.0 and dist_2d((x, y), proj) <= threshold:
                return proj[0], proj[1], "parede"

        return x, y, None

    def to_dict(self) -> dict:
        """Serializa o grafo 2D para salvar nos metadados do grupo 3D."""
        return {
            "default_thickness": self.default_thickness,
            "default_height": self.default_height,
            "nodes": [{"id": n.id, "x": n.x, "y": n.y} for n in self.nodes.values()],
            "segments": [
                {
                    "id": s.id,
                    "node_a_id": s.node_a_id,
                    "node_b_id": s.node_b_id,
                    "thickness": s.thickness,
                }
                for s in self.segments.values()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> WallGraph2D:
        """Restaura o grafo 2D a partir dos metadados salvos."""
        graph = cls(
            default_thickness=data.get("default_thickness", 0.15),
            default_height=data.get("default_height", 2.60),
        )
        for nd in data.get("nodes", []):
            graph.nodes[nd["id"]] = WallNode2D(id=nd["id"], x=nd["x"], y=nd["y"])
        for sd in data.get("segments", []):
            graph.segments[sd["id"]] = WallSegment2D(
                id=sd["id"],
                node_a_id=sd["node_a_id"],
                node_b_id=sd["node_b_id"],
                thickness=sd.get("thickness", graph.default_thickness),
            )
        if graph.nodes:
            graph._next_node_id = max(graph.nodes.keys()) + 1
        if graph.segments:
            graph._next_seg_id = max(graph.segments.keys()) + 1
        return graph

    @classmethod
    def from_group(cls, group: Group) -> Optional[WallGraph2D]:
        """Tenta carregar o grafo 2D de um grupo de parede existente na cena."""
        ext = getattr(group, "ext", {})
        if not isinstance(ext, dict):
            return None
        w_data = ext.get("trazomob_wall")
        if not isinstance(w_data, dict):
            return None

        # 1. Se já possui o grafo 2D salvo diretamente
        if "graph_2d" in w_data:
            return cls.from_dict(w_data["graph_2d"])

        # 2. Se for uma parede legada com lista de pontos sequenciais
        pts = w_data.get("pontos", [])
        if len(pts) >= 2:
            th = w_data.get("espessura", 0.15)
            h = w_data.get("altura", 2.60)
            graph = cls(default_thickness=th, default_height=h)
            is_closed = w_data.get("is_closed", False)
            n = len(pts)
            n_segs = n if is_closed else (n - 1)
            for i in range(n_segs):
                p1 = pts[i]
                p2 = pts[(i + 1) % n]
                graph.add_segment(p1[0], p1[1], p2[0], p2[1], thickness=th)
            return graph

        return None

    def build_3d_group(self, scene, altura_m: float = 2.6, name: str = "Ambiente Paredes") -> Optional[Group]:
        """Gera o grupo de malha 3D contínua a partir de todos os segmentos do grafo 2D.
        
        Salva o próprio grafo 2D serializado em ext['trazomob_wall']['graph_2d'],
        permitindo reabrir e continuar editando a qualquer momento.
        """
        if not self.segments:
            return None

        zv = QVector3D(0, 0, altura_m)
        mesh = Mesh()

        # Cada segmento de parede gera 4 cantos na base (offset em torno da linha central)
        for seg in self.segments.values():
            na = self.nodes[seg.node_a_id]
            nb = self.nodes[seg.node_b_id]
            dx = nb.x - na.x
            dy = nb.y - na.y
            seg_len = math.hypot(dx, dy)
            if seg_len < 1e-5:
                continue

            ux = dx / seg_len
            uy = dy / seg_len
            nx = -uy
            ny = ux

            half_th = seg.thickness / 2.0
            ox = nx * half_th
            oy = ny * half_th

            c0 = QVector3D(na.x - ox, na.y - oy, 0.0)
            c1 = QVector3D(nb.x - ox, nb.y - oy, 0.0)
            c2 = QVector3D(nb.x + ox, nb.y + oy, 0.0)
            c3 = QVector3D(na.x + ox, na.y + oy, 0.0)

            # Base (Z=0)
            mesh.add_face([c0, c1, c2, c3])
            # Topo (Z=altura_m)
            mesh.add_face([c3 + zv, c2 + zv, c1 + zv, c0 + zv])
            # Lateral 1
            mesh.add_face([c0, c0 + zv, c1 + zv, c1])
            # Lateral 2
            mesh.add_face([c1, c1 + zv, c2 + zv, c2])
            # Lateral 3
            mesh.add_face([c2, c2 + zv, c3 + zv, c3])
            # Lateral 4
            mesh.add_face([c3, c3 + zv, c0 + zv, c0])

        # Suaviza arestas coplanares
        for e in mesh.edges:
            if len(e.faces) == 2:
                n0 = e.faces[0].normal()
                n1 = e.faces[1].normal()
                if abs(QVector3D.dotProduct(n0, n1) - 1.0) < 1e-4:
                    e.soft = True

        layer_name = "Parede"
        if scene is not None and scene.layer(layer_name) is None:
            scene.layers.append(Layer(layer_name))

        grp = Group(mesh, name=name)
        grp.layer = layer_name
        grp.ext = {
            "trazomob_wall": {
                "altura": altura_m,
                "espessura": self.default_thickness,
                "is_graph_2d": True,
                "num_segments": len(self.segments),
                "graph_2d": self.to_dict(),
            }
        }
        return grp


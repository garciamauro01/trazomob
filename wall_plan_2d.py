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


def line_intersection_2d(p1: Point2D, d1: Point2D, p2: Point2D, d2: Point2D) -> Optional[Point2D]:
    """Calcula a interseção entre duas retas parametrizadas: p1 + s*d1 e p2 + t*d2."""
    det = d1[0] * d2[1] - d1[1] * d2[0]
    if abs(det) < 1e-6:
        return None
    dp = (p2[0] - p1[0], p2[1] - p1[1])
    s = (dp[0] * d2[1] - dp[1] * d2[0]) / det
    return (p1[0] + s * d1[0], p1[1] + s * d1[1])


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

    def compute_wall_polygons(self) -> Dict[int, Tuple[Point2D, Point2D, Point2D, Point2D]]:
        """Calcula os 4 vértices 2D (c0, c1, c2, c3) para cada segmento de parede.
        
        c0 e c1 são os vértices na borda 'esquerda' (de node_a a node_b).
        c2 e c3 são os vértices na borda 'direita' (de node_b a node_a).
        
        Em nós de canto (onde 2 paredes se encontram), calcula a bissetriz (miter a 45°
        para ângulos retos), fechando perfeitamente os cantos internos e externos.
        """
        # Mapeia quais segmentos incidem em cada nó
        node_segments: Dict[int, List[int]] = {nid: [] for nid in self.nodes}
        for seg_id, seg in self.segments.items():
            node_segments[seg.node_a_id].append(seg_id)
            node_segments[seg.node_b_id].append(seg_id)

        polys: Dict[int, Tuple[Point2D, Point2D, Point2D, Point2D]] = {}
        for seg_id, seg in self.segments.items():
            na = self.nodes[seg.node_a_id]
            nb = self.nodes[seg.node_b_id]

            dx = nb.x - na.x
            dy = nb.y - na.y
            seg_len = math.hypot(dx, dy)
            if seg_len < 1e-6:
                half_th = seg.thickness / 2.0
                c0 = (na.x - half_th, na.y - half_th)
                c1 = (nb.x - half_th, nb.y - half_th)
                c2 = (nb.x + half_th, nb.y + half_th)
                c3 = (na.x + half_th, na.y + half_th)
                polys[seg_id] = (c0, c1, c2, c3)
                continue

            ux = dx / seg_len
            uy = dy / seg_len
            # Normal à esquerda
            nx = -uy
            ny = ux
            half_th = seg.thickness / 2.0

            # Padrão plano nas extremidades (se livres)
            c0 = (na.x + nx * half_th, na.y + ny * half_th)
            c3 = (na.x - nx * half_th, na.y - ny * half_th)
            c1 = (nb.x + nx * half_th, nb.y + ny * half_th)
            c2 = (nb.x - nx * half_th, nb.y - ny * half_th)
            polys[seg_id] = (c0, c1, c2, c3)

        # Para cada nó com grau 2 (canto), calculamos a bissetriz / corte em 45°
        for nid, seg_ids in node_segments.items():
            if len(seg_ids) != 2:
                continue

            s_id1, s_id2 = seg_ids
            seg1 = self.segments[s_id1]
            seg2 = self.segments[s_id2]
            node = self.nodes[nid]

            # Vetor unitário saindo do nó nid ao longo de seg1
            other_n1 = self.nodes[seg1.node_b_id if seg1.node_a_id == nid else seg1.node_a_id]
            d1x = other_n1.x - node.x
            d1y = other_n1.y - node.y
            l1 = math.hypot(d1x, d1y)
            if l1 < 1e-6:
                continue
            u1x, u1y = d1x / l1, d1y / l1

            # Vetor unitário saindo do nó nid ao longo de seg2
            other_n2 = self.nodes[seg2.node_b_id if seg2.node_a_id == nid else seg2.node_a_id]
            d2x = other_n2.x - node.x
            d2y = other_n2.y - node.y
            l2 = math.hypot(d2x, d2y)
            if l2 < 1e-6:
                continue
            u2x, u2y = d2x / l2, d2y / l2

            # Normais à esquerda em relação ao vetor saindo do nó
            n1x, n1y = -u1y, u1x
            n2x, n2y = -u2y, u2x

            h1 = seg1.thickness / 2.0
            h2 = seg2.thickness / 2.0

            # Retas de contorno saindo do nó:
            # seg1: reta_l1 passa por node + n1*h1, dir u1
            #       reta_r1 passa por node - n1*h1, dir u1
            # seg2: reta_l2 passa por node + n2*h2, dir u2
            #       reta_r2 passa por node - n2*h2, dir u2
            # Produto vetorial 2D (u1 x u2) determina para qual lado a parede vira
            cross = u1x * u2y - u1y * u2x
            if abs(cross) < 1e-4:
                # Paredes colineares
                continue

            if cross > 0:
                # Vira para a esquerda (ângulo interno entre as esquerdas)
                # O lado esquerdo (interno) cruza com o lado direito de seg2 (que entra pelo mesmo lado)
                # Ou seja: reta_l1 cruza reta_r2, e reta_r1 cruza reta_l2
                p_in = line_intersection_2d(
                    (node.x + n1x * h1, node.y + n1y * h1), (u1x, u1y),
                    (node.x - n2x * h2, node.y - n2y * h2), (u2x, u2y)
                )
                p_out = line_intersection_2d(
                    (node.x - n1x * h1, node.y - n1y * h1), (u1x, u1y),
                    (node.x + n2x * h2, node.y + n2y * h2), (u2x, u2y)
                )
            else:
                # Vira para a direita (ângulo interno entre as direitas)
                p_in = line_intersection_2d(
                    (node.x - n1x * h1, node.y - n1y * h1), (u1x, u1y),
                    (node.x + n2x * h2, node.y + n2y * h2), (u2x, u2y)
                )
                p_out = line_intersection_2d(
                    (node.x + n1x * h1, node.y + n1y * h1), (u1x, u1y),
                    (node.x - n2x * h2, node.y - n2y * h2), (u2x, u2y)
                )

            max_d = max(h1, h2) * 3.5
            if p_in and dist_2d(node.pt, p_in) <= max_d and p_out and dist_2d(node.pt, p_out) <= max_d:
                # Atribui os pontos p_in e p_out aos vértices corretos do quad de cada segmento
                for sid in (s_id1, s_id2):
                    s_obj = self.segments[sid]
                    c0, c1, c2, c3 = polys[sid]
                    if s_obj.node_a_id == nid:
                        # Vértices no node_a são c0 e c3
                        # c0 é borda esquerda no sentido a->b
                        # Descobre se c0 está mais perto de p_in ou p_out
                        d_c0_in = dist_2d(c0, p_in)
                        d_c0_out = dist_2d(c0, p_out)
                        if d_c0_in < d_c0_out:
                            c0, c3 = p_in, p_out
                        else:
                            c0, c3 = p_out, p_in
                    else:
                        # Vértices no node_b são c1 e c2
                        d_c1_in = dist_2d(c1, p_in)
                        d_c1_out = dist_2d(c1, p_out)
                        if d_c1_in < d_c1_out:
                            c1, c2 = p_in, p_out
                        else:
                            c1, c2 = p_out, p_in
                    polys[sid] = (c0, c1, c2, c3)

        # Ajuste para nós com coluna (T-junctions ou X):
        # As paredes que chegam ao nó com coluna devem terminar exatamente na face da coluna,
        # sem invadir o espaço interno da coluna nem o espaço das outras paredes.
        columns = self.compute_columns()
        for nid, col_quad in columns.items():
            for sid in node_segments.get(nid, []):
                s_obj = self.segments[sid]
                c0, c1, c2, c3 = polys[sid]

                na = self.nodes[s_obj.node_a_id]
                nb = self.nodes[s_obj.node_b_id]
                dx = nb.x - na.x
                dy = nb.y - na.y
                slen = math.hypot(dx, dy)
                if slen < 1e-6:
                    continue
                ux = dx / slen
                uy = dy / slen

                if s_obj.node_a_id == nid:
                    # Parede começa no nó nid e vai em direção a nb (direção +u)
                    # c0 (borda esquerda) e c3 (borda direita) devem ser aparadas na coluna
                    p0 = self._intersect_quad_with_line(col_quad, c1, (-ux, -uy))
                    p3 = self._intersect_quad_with_line(col_quad, c2, (-ux, -uy))
                    if p0:
                        c0 = p0
                    if p3:
                        c3 = p3
                else:
                    # Parede termina no nó nid (vem de na em direção a nb, direção +u)
                    # c1 (borda esquerda) e c2 (borda direita) devem ser aparadas na coluna
                    p1 = self._intersect_quad_with_line(col_quad, c0, (ux, uy))
                    p2 = self._intersect_quad_with_line(col_quad, c3, (ux, uy))
                    if p1:
                        c1 = p1
                    if p2:
                        c2 = p2

                polys[sid] = (c0, c1, c2, c3)

        return polys

    @staticmethod
    def _intersect_quad_with_line(quad: Tuple[Point2D, Point2D, Point2D, Point2D], p: Point2D, d: Point2D) -> Optional[Point2D]:
        """Calcula a interseção entre o raio p + t*d (t >= 0) e as 4 arestas do polígono quad."""
        edges = [(quad[0], quad[1]), (quad[1], quad[2]), (quad[2], quad[3]), (quad[3], quad[0])]
        pts = []
        for a, b in edges:
            adx = b[0] - a[0]
            ady = b[1] - a[1]
            det = d[0] * ady - d[1] * adx
            if abs(det) < 1e-6:
                continue
            dp = (a[0] - p[0], a[1] - p[1])
            t = (dp[0] * ady - dp[1] * adx) / det
            s = (dp[0] * d[1] - dp[1] * d[0]) / det
            if t >= -1e-4 and -1e-4 <= s <= 1.0001:
                pts.append((p[0] + t * d[0], p[1] + t * d[1]))
        if not pts:
            return None
        # Pega a interseção mais próxima do ponto de partida p
        return min(pts, key=lambda pt: (pt[0] - p[0]) ** 2 + (pt[1] - p[1]) ** 2)

    def compute_columns(self) -> Dict[int, Tuple[Point2D, Point2D, Point2D, Point2D]]:
        """Calcula as colunas estruturais nos nós que formam junção em T (ou X).
        
        Quando 3 ou mais paredes se encontram em um nó (ou junção em T),
        gera uma coluna quadrada separando as paredes que chegam ao nó.
        Retorna um dicionário {node_id: (c0, c1, c2, c3)}.
        """
        node_segments: Dict[int, List[int]] = {nid: [] for nid in self.nodes}
        for seg_id, seg in self.segments.items():
            node_segments[seg.node_a_id].append(seg_id)
            node_segments[seg.node_b_id].append(seg_id)

        columns: Dict[int, Tuple[Point2D, Point2D, Point2D, Point2D]] = {}
        for nid, seg_ids in node_segments.items():
            if len(seg_ids) >= 3:
                node = self.nodes[nid]
                # A largura da coluna baseia-se na maior espessura das paredes que chegam
                max_th = max(self.segments[sid].thickness for sid in seg_ids)
                half = max_th / 2.0
                # Coluna quadrada alinhada ao nó
                c0 = (node.x - half, node.y - half)
                c1 = (node.x + half, node.y - half)
                c2 = (node.x + half, node.y + half)
                c3 = (node.x - half, node.y + half)
                columns[nid] = (c0, c1, c2, c3)

        return columns

    def build_3d_group(self, scene, altura_m: float = 2.6, name: str = "Ambiente Paredes") -> Optional[Group]:
        """Gera o grupo de malha 3D contínua a partir de todos os segmentos do grafo 2D.
        
        Salva o próprio grafo 2D serializado em ext['trazomob_wall']['graph_2d'],
        permitindo reabrir e continuar editando a qualquer momento.
        """
        if not self.segments:
            return None

        zv = QVector3D(0, 0, altura_m)
        mesh = Mesh()

        wall_polys = self.compute_wall_polygons()
        columns = self.compute_columns()

        # 1. Cada segmento de parede gera 4 cantos na base (com chanfro/miter a 45° nos cantos)
        for seg_id, quad in wall_polys.items():
            p0, p1, p2, p3 = quad
            c0 = QVector3D(p0[0], p0[1], 0.0)
            c1 = QVector3D(p1[0], p1[1], 0.0)
            c2 = QVector3D(p2[0], p2[1], 0.0)
            c3 = QVector3D(p3[0], p3[1], 0.0)

            # Base (Z=0)
            mesh.add_face([c0, c1, c2, c3])
            # Topo (Z=altura_m)
            mesh.add_face([c3 + zv, c2 + zv, c1 + zv, c0 + zv])
            # Lateral 1 (esquerda)
            mesh.add_face([c0, c0 + zv, c1 + zv, c1])
            # Lateral 2 (topo/extremo B)
            mesh.add_face([c1, c1 + zv, c2 + zv, c2])
            # Lateral 3 (direita)
            mesh.add_face([c2, c2 + zv, c3 + zv, c3])
            # Lateral 4 (fundo/extremo A)
            mesh.add_face([c3, c3 + zv, c0 + zv, c0])

        # 2. Gera as colunas estruturais 3D nos nós de junção em T (ou X)
        for nid, col_quad in columns.items():
            p0, p1, p2, p3 = col_quad
            c0 = QVector3D(p0[0], p0[1], 0.0)
            c1 = QVector3D(p1[0], p1[1], 0.0)
            c2 = QVector3D(p2[0], p2[1], 0.0)
            c3 = QVector3D(p3[0], p3[1], 0.0)

            # Base (Z=0)
            mesh.add_face([c0, c1, c2, c3])
            # Topo (Z=altura_m)
            mesh.add_face([c3 + zv, c2 + zv, c1 + zv, c0 + zv])
            # 4 laterais da coluna
            mesh.add_face([c0, c0 + zv, c1 + zv, c1])
            mesh.add_face([c1, c1 + zv, c2 + zv, c2])
            mesh.add_face([c2, c2 + zv, c3 + zv, c3])
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


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
    flip_side: bool = False  # mantido para compatibilidade de arquivos legados
    height: Optional[float] = None  # altura individual em metros

    def length(self, graph: WallGraph2D) -> float:
        na = graph.get_node(self.node_a_id)
        nb = graph.get_node(self.node_b_id)
        if na is None or nb is None:
            return 0.0
        return dist_2d(na.pt, nb.pt)


@dataclass
class CustomDimension2D:
    """Cota livre definida pelo usuário entre dois pontos quaisquer (ex: faces, cantos ou centros)."""
    id: int
    p1: Point2D
    p2: Point2D
    seg_id: Optional[int] = None  # segmento de parede associado, se houver
    offset: float = 0.25          # distância visual da linha de cota em relação aos pontos cotados
    node_a_id: Optional[int] = None  # nó do grafo vinculado a p1
    node_b_id: Optional[int] = None  # nó do grafo vinculado a p2


class WallGraph2D:
    """Grafo topológico 2D de paredes.
    
    Gerencia nós, arestas/segmentos, junções (L, T, X) e gera os contornos
    2D unificados e polígonos para extrusão direta em sólidos 3D.
    """

    def __init__(self, default_thickness: float = 0.15, default_height: float = 2.60, alignment: str = "centro"):
        self.default_thickness = default_thickness
        self.default_height = default_height
        self.alignment = "centro"  # Todas as paredes são desenhadas e calculadas pelo eixo central
        self.nodes: Dict[int, WallNode2D] = {}
        self.segments: Dict[int, WallSegment2D] = {}
        self.dimensions: Dict[int, CustomDimension2D] = {}
        self._next_node_id: int = 1
        self._next_seg_id: int = 1
        self._next_dim_id: int = 1

    def clear(self) -> None:
        self.nodes.clear()
        self.segments.clear()
        self.dimensions.clear()
        self._next_node_id = 1
        self._next_seg_id = 1
        self._next_dim_id = 1

    def add_dimension(self, p1: Point2D, p2: Point2D, seg_id: Optional[int] = None, offset: float = 0.25) -> Optional[int]:
        """Adiciona uma nova cota personalizada entre dois pontos."""
        if dist_2d(p1, p2) < 0.01:
            return None
        did = self._next_dim_id
        self._next_dim_id += 1

        node_a_id = None
        node_b_id = None
        if seg_id is not None and seg_id in self.segments:
            seg = self.segments[seg_id]
            na = self.nodes.get(seg.node_a_id)
            nb = self.nodes.get(seg.node_b_id)
            if na and nb:
                d_a1 = dist_2d(p1, na.pt)
                d_b1 = dist_2d(p1, nb.pt)
                if d_a1 <= d_b1:
                    node_a_id, node_b_id = seg.node_a_id, seg.node_b_id
                else:
                    node_a_id, node_b_id = seg.node_b_id, seg.node_a_id
        else:
            # Associa aos nós mais próximos de p1 e p2
            best_a, best_d_a = None, 0.40
            best_b, best_d_b = None, 0.40
            for nid, node in self.nodes.items():
                da = dist_2d(p1, node.pt)
                db = dist_2d(p2, node.pt)
                if da < best_d_a:
                    best_d_a = da
                    best_a = nid
                if db < best_d_b:
                    best_d_b = db
                    best_b = nid
            node_a_id, node_b_id = best_a, best_b

        self.dimensions[did] = CustomDimension2D(
            id=did, p1=p1, p2=p2, seg_id=seg_id, offset=offset,
            node_a_id=node_a_id, node_b_id=node_b_id
        )
        return did

    def sync_all_dimensions(self, old_node_positions: Dict[int, Point2D]) -> None:
        """Sincroniza rigorosamente todas as cotas com os deslocamentos sofridos pelos nós do grafo.
        
        Isso garante que cotas em cadeias de paredes, ciclos fechados ou divisórias
        sejam tratadas como restrições paramétricas reais de CAD: quando paredes se deslocam,
        as cotas acompanham exatamente seus nós vinculados, mantendo comprimentos e orientações
        com precisão milimétrica sem deformação.
        """
        for d in self.dimensions.values():
            # Se a cota ainda não tiver nós associados ou precisar revalidar
            if d.node_a_id is None or d.node_b_id is None:
                if d.seg_id is not None and d.seg_id in self.segments:
                    seg = self.segments[d.seg_id]
                    na_pt = old_node_positions.get(seg.node_a_id)
                    nb_pt = old_node_positions.get(seg.node_b_id)
                    if na_pt and nb_pt:
                        if dist_2d(d.p1, na_pt) <= dist_2d(d.p1, nb_pt):
                            d.node_a_id, d.node_b_id = seg.node_a_id, seg.node_b_id
                        else:
                            d.node_a_id, d.node_b_id = seg.node_b_id, seg.node_a_id
                else:
                    best_a, best_d_a = None, 0.40
                    best_b, best_d_b = None, 0.40
                    for nid, old_pt in old_node_positions.items():
                        da = dist_2d(d.p1, old_pt)
                        db = dist_2d(d.p2, old_pt)
                        if da < best_d_a:
                            best_d_a = da
                            best_a = nid
                        if db < best_d_b:
                            best_d_b = db
                            best_b = nid
                    if best_a is not None:
                        d.node_a_id = best_a
                    if best_b is not None:
                        d.node_b_id = best_b

            # Translada p1 pelo deslocamento sofrido por node_a_id
            if d.node_a_id is not None and d.node_a_id in self.nodes and d.node_a_id in old_node_positions:
                curr_a = self.nodes[d.node_a_id]
                old_a = old_node_positions[d.node_a_id]
                dx_a = curr_a.x - old_a[0]
                dy_a = curr_a.y - old_a[1]
                if abs(dx_a) > 1e-7 or abs(dy_a) > 1e-7:
                    d.p1 = (d.p1[0] + dx_a, d.p1[1] + dy_a)

            # Translada p2 pelo deslocamento sofrido por node_b_id
            if d.node_b_id is not None and d.node_b_id in self.nodes and d.node_b_id in old_node_positions:
                curr_b = self.nodes[d.node_b_id]
                old_b = old_node_positions[d.node_b_id]
                dx_b = curr_b.x - old_b[0]
                dy_b = curr_b.y - old_b[1]
                if abs(dx_b) > 1e-7 or abs(dy_b) > 1e-7:
                    d.p2 = (d.p2[0] + dx_b, d.p2[1] + dy_b)

    def remove_dimension(self, dim_id: int) -> bool:
        if dim_id in self.dimensions:
            del self.dimensions[dim_id]
            return True
        return False

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
        flip = self._determine_auto_flip(na_id, nb_id)
        seg_id = self._next_seg_id
        self._next_seg_id += 1
        self.segments[seg_id] = WallSegment2D(id=seg_id, node_a_id=na_id, node_b_id=nb_id, thickness=th, flip_side=flip)
        return seg_id

    def _get_or_split_at_point(self, x: float, y: float, threshold: float = 0.20) -> int:
        """Encontra ou cria nó em (x, y), subdividindo segmento existente se estiver no meio."""
        # Primeiro checa nós existentes (tolerância de atração para fechar cômodos ou conectar)
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
                orig_flip = seg.flip_side
                # Segmento existente passa a ir de na até split_node
                seg.node_b_id = split_node_id
                # Novo segmento vai de split_node até orig_b
                new_s_id = self._next_seg_id
                self._next_seg_id += 1
                self.segments[new_s_id] = WallSegment2D(id=new_s_id, node_a_id=split_node_id, node_b_id=orig_b, thickness=th, flip_side=orig_flip)
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

    def find_node_at(self, x: float, y: float, threshold: float = 0.20) -> Optional[int]:
        """Retorna o id do nó mais próximo de (x, y) dentro do raio threshold."""
        closest_id = None
        min_d = threshold
        for nid, node in self.nodes.items():
            d = dist_2d((x, y), (node.x, node.y))
            if d <= min_d:
                min_d = d
                closest_id = nid
        return closest_id

    def find_segment_at(self, x: float, y: float, threshold: float = 0.25) -> Optional[int]:
        """Retorna o id do segmento mais próximo de (x, y) dentro da distância threshold."""
        closest_id = None
        min_d = threshold
        for sid, seg in self.segments.items():
            na = self.nodes[seg.node_a_id]
            nb = self.nodes[seg.node_b_id]
            proj, t = self._project_point_on_segment((x, y), na.pt, nb.pt)
            d = dist_2d((x, y), proj)
            if d <= min_d:
                min_d = d
                closest_id = sid
        return closest_id

    def get_rigid_component(self, start_nid: int) -> Set[int]:
        """Calcula o componente rígido paramétrico a partir de um nó inicial.
        
        Em softwares CAD paramétricos, uma cota é imutável: ela define uma restrição
        geométrica rígida. Todos os nós interligados por paredes cotadas formam um corpo
        rígido indeformável. Divisórias perpendiculares conectadas a esses nós também se
        deslocam em bloco com o corpo rígido. Apenas paredes e nós NÃO cotados absorvem
        o deslocamento/deformação.
        """
        dim_segs = {d.seg_id for d in self.dimensions.values() if d.seg_id is not None}

        # 1. Se start_nid for extremidade livre de uma divisória conectada a uma base cotada:
        base_nid = start_nid
        for sid, s in self.segments.items():
            if s.node_a_id == start_nid or s.node_b_id == start_nid:
                other = s.node_b_id if s.node_a_id == start_nid else s.node_a_id
                deg_curr = sum(1 for s2 in self.segments.values() if s2.node_a_id == start_nid or s2.node_b_id == start_nid)
                deg_other = sum(1 for s2 in self.segments.values() if s2.node_a_id == other or s2.node_b_id == other)
                if deg_curr == 1 and deg_other >= 3:
                    dx = self.nodes[start_nid].x - self.nodes[other].x
                    dy = self.nodes[start_nid].y - self.nodes[other].y
                    L = math.hypot(dx, dy)
                    if L > 1e-4:
                        ux, uy = dx / L, dy / L
                        other_segs = [s2 for s2 in self.segments.values() if s2.id != sid and (s2.node_a_id == other or s2.node_b_id == other)]
                        for s2 in other_segs:
                            s2_other = s2.node_b_id if s2.node_a_id == other else s2.node_a_id
                            s2_dx = self.nodes[s2_other].x - self.nodes[other].x
                            s2_dy = self.nodes[s2_other].y - self.nodes[other].y
                            s2_L = math.hypot(s2_dx, s2_dy)
                            if s2_L > 1e-4 and abs((ux * s2_dx + uy * s2_dy) / s2_L) < 0.20:
                                base_nid = other
                                break

        # 2. Localiza todos os nós cotados interligados a base_nid via segmentos com cota
        dim_nodes: Set[int] = set()
        if any(s.node_a_id == base_nid or s.node_b_id == base_nid for sid, s in self.segments.items() if sid in dim_segs):
            q = [base_nid]
            dim_nodes.add(base_nid)
            while q:
                curr = q.pop(0)
                for sid in dim_segs:
                    s = self.segments.get(sid)
                    if s:
                        if s.node_a_id == curr and s.node_b_id not in dim_nodes:
                            dim_nodes.add(s.node_b_id)
                            q.append(s.node_b_id)
                        elif s.node_b_id == curr and s.node_a_id not in dim_nodes:
                            dim_nodes.add(s.node_a_id)
                            q.append(s.node_a_id)

        # Se não há cotas no grafo ou este nó não participa de nenhuma cota,
        # move apenas o nó ou a divisória simples sem afetar outros
        if not dim_nodes:
            # Se não há cota nenhuma no grafo inteiro, move o conjunto conectado para manter cantos
            if not dim_segs:
                connected_nodes = {start_nid}
                queue = [start_nid]
                while queue:
                    curr = queue.pop(0)
                    for s in self.segments.values():
                        if s.node_a_id == curr or s.node_b_id == curr:
                            nxt = s.node_b_id if s.node_a_id == curr else s.node_a_id
                            if nxt not in connected_nodes:
                                connected_nodes.add(nxt)
                                queue.append(nxt)
                return connected_nodes
            return {start_nid, base_nid} if base_nid != start_nid else {start_nid}

        # 3. Inclui divisórias perpendiculares que brotam dos nós cotados (ex: as paredes verticais)
        rigid: Set[int] = set(dim_nodes)
        for bn in dim_nodes:
            for sid, s in self.segments.items():
                if sid not in dim_segs:
                    other = s.node_b_id if s.node_a_id == bn else (s.node_a_id if s.node_b_id == bn else None)
                    if other is not None and other not in rigid:
                        deg_other = sum(1 for s2 in self.segments.values() if s2.node_a_id == other or s2.node_b_id == other)
                        if deg_other == 1:
                            dx = self.nodes[other].x - self.nodes[bn].x
                            dy = self.nodes[other].y - self.nodes[bn].y
                            L = math.hypot(dx, dy)
                            if L > 1e-4:
                                ux, uy = dx / L, dy / L
                                dim_connected_segs = [s2 for s2 in self.segments.values() if s2.id in dim_segs and (s2.node_a_id == bn or s2.node_b_id == bn)]
                                if dim_connected_segs:
                                    s2 = dim_connected_segs[0]
                                    s2_other = s2.node_b_id if s2.node_a_id == bn else s2.node_a_id
                                    s2_dx = self.nodes[s2_other].x - self.nodes[bn].x
                                    s2_dy = self.nodes[s2_other].y - self.nodes[bn].y
                                    s2_L = math.hypot(s2_dx, s2_dy)
                                    if s2_L > 1e-4 and abs((ux * s2_dx + uy * s2_dy) / s2_L) < 0.20:
                                        rigid.add(other)

        return rigid

    def move_node(self, node_id: int, new_x: float, new_y: float) -> bool:
        """Move as coordenadas de um nó existente respeitando rigorosamente as cotas paramétricas imutáveis.
        
        As cotas são tratadas como restrições rígidas: se uma ou mais paredes possuem cotas,
        elas e suas divisórias a 90° formam um corpo rígido inalterável. Ao arrastar qualquer
        um dos nós cotados, o bloco inteiro é transladado junto, e os segmentos/paredes NÃO
        cotados absorvem a diferença de posição.
        """
        node = self.nodes.get(node_id)
        if node is None:
            return False

        dx = new_x - node.x
        dy = new_y - node.y

        if abs(dx) < 1e-6 and abs(dy) < 1e-6:
            return True

        old_positions = {nid: (n.x, n.y) for nid, n in self.nodes.items()}

        # Obtém o componente rígido imutável vinculado por cotas
        rigid_nodes = self.get_rigid_component(node_id)

        # Atualiza as posições de todos os nós do componente rígido
        for nid in rigid_nodes:
            n = self.nodes.get(nid)
            if n:
                n.x += dx
                n.y += dy

        # Sincroniza deterministicamente todas as cotas com os nós movidos
        self.sync_all_dimensions(old_positions)
        return True

    def merge_close_nodes(self, threshold: float = 0.20) -> int:
        """Mescla nós que ficaram muito próximos um do outro (detectando fechamento de paredes).
        
        Quando o usuário edita a medida ou arrasta a ponta de uma parede para encostar
        em outro nó, os dois nós se fundem em um único nó, fechando o cômodo e ativando
        automaticamente o canto chanfrado a 45° ou a junção em T/coluna.
        """
        merged_count = 0
        changed = True
        while changed:
            changed = False
            for nid1 in list(self.nodes.keys()):
                if nid1 not in self.nodes:
                    continue
                node1 = self.nodes[nid1]
                for nid2 in list(self.nodes.keys()):
                    if nid2 <= nid1 or nid2 not in self.nodes:
                        continue
                    node2 = self.nodes[nid2]
                    if dist_2d((node1.x, node1.y), (node2.x, node2.y)) <= threshold:
                        # Mescla nid2 em nid1: redireciona todos os segmentos que usam nid2
                        for seg in self.segments.values():
                            if seg.node_a_id == nid2:
                                seg.node_a_id = nid1
                            if seg.node_b_id == nid2:
                                seg.node_b_id = nid1

                        # Remove segmentos degenerados (de nid1 para nid1) se houver
                        degen = [sid for sid, s in self.segments.items() if s.node_a_id == s.node_b_id]
                        for sid in degen:
                            del self.segments[sid]

                        # Remove nó duplicado
                        del self.nodes[nid2]
                        merged_count += 1
                        changed = True
                        break
                if changed:
                    break
        return merged_count

    def set_segment_length(self, seg_id: int, new_length_m: float, anchor_node_id: Optional[int] = None) -> bool:
        """Altera o comprimento de uma parede ajustando a posição do nó livre/móvel."""
        seg = self.segments.get(seg_id)
        if seg is None or new_length_m <= 0.01:
            return False

        na = self.nodes[seg.node_a_id]
        nb = self.nodes[seg.node_b_id]
        dx = nb.x - na.x
        dy = nb.y - na.y
        cur_len = math.hypot(dx, dy)
        if cur_len < 1e-6:
            return False

        ux = dx / cur_len
        uy = dy / cur_len

        old_positions = {nid: (n.x, n.y) for nid, n in self.nodes.items()}

        # Decide qual nó mover: o nó oposto ao anchor_node_id
        # Se ancorado em um canto existente com alinhamento interno/externo, compensa a extensão
        # para que o comprimento da face terminada seja exatamente new_length_m.
        deg_a = sum(1 for s in self.segments.values() if s.node_a_id == seg.node_a_id or s.node_b_id == seg.node_a_id)
        deg_b = sum(1 for s in self.segments.values() if s.node_a_id == seg.node_b_id or s.node_b_id == seg.node_b_id)

        actual_anchor = anchor_node_id
        if actual_anchor is None:
            # 1. Regra Paramétrica de CAD: Um lado que já possui cota definida é rígido/protegido
            # e DEVE atuar como âncora fixa para que a alteração de medida empurre o lado livre/não cotado.
            dim_segs = {d.seg_id for d in self.dimensions.values() if d.seg_id is not None and d.seg_id != seg_id}
            
            # Checa se o subgrafo a partir de node_a tem paredes cotadas (sem passar por seg_id)
            def has_dim_connected(start_nid: int) -> bool:
                vis = {start_nid}
                q = [start_nid]
                while q:
                    cur = q.pop(0)
                    for sid, s in self.segments.items():
                        if sid == seg_id:
                            continue
                        if s.node_a_id == cur or s.node_b_id == cur:
                            if sid in dim_segs:
                                return True
                            nxt = s.node_b_id if s.node_a_id == cur else s.node_a_id
                            if nxt not in vis:
                                vis.add(nxt)
                                q.append(nxt)
                return False

            has_dim_a = has_dim_connected(seg.node_a_id)
            has_dim_b = has_dim_connected(seg.node_b_id)

            if has_dim_a and not has_dim_b:
                actual_anchor = seg.node_a_id
            elif has_dim_b and not has_dim_a:
                actual_anchor = seg.node_b_id
            else:
                # Se ambos têm cotas ou nenhum tem cota, ancora na extremidade conectada anterior
                segs_a = [s.id for s in self.segments.values() if s.id != seg_id and (s.node_a_id == seg.node_a_id or s.node_b_id == seg.node_a_id)]
                segs_b = [s.id for s in self.segments.values() if s.id != seg_id and (s.node_a_id == seg.node_b_id or s.node_b_id == seg.node_b_id)]
                min_a = min(segs_a) if segs_a else 999999
                min_b = min(segs_b) if segs_b else 999999

                if min_a < seg_id and min_a < min_b:
                    actual_anchor = seg.node_a_id
                elif min_b < seg_id and min_b < min_a:
                    actual_anchor = seg.node_b_id
                else:
                    actual_anchor = seg.node_a_id

        if actual_anchor == seg.node_a_id:
            ext = self.get_start_extension((na.x, na.y), (ux, uy))
            eff_len = new_length_m + ext
            delta_L = eff_len - cur_len
            # Move nb e propaga para paredes perpendiculares conectadas em nb mantendo os cantos ortogonais
            self._move_node_with_orthogonal_propagation(seg.node_b_id, seg_id, (ux * delta_L, uy * delta_L))
        elif actual_anchor == seg.node_b_id:
            ext = self.get_start_extension((nb.x, nb.y), (-ux, -uy))
            eff_len = new_length_m + ext
            delta_L = eff_len - cur_len
            self._move_node_with_orthogonal_propagation(seg.node_a_id, seg_id, (-ux * delta_L, -uy * delta_L))
        else:
            delta_L = new_length_m - cur_len
            self._move_node_with_orthogonal_propagation(seg.node_b_id, seg_id, (ux * delta_L, uy * delta_L))

        # Sincroniza todas as cotas do grafo com as novas posições dos nós
        self.sync_all_dimensions(old_positions)

        # Após alterar o comprimento, verifica se o nó movido fechou com outro nó próximo
        self.merge_close_nodes(threshold=0.20)
        return True

    def _move_node_with_orthogonal_propagation(self, move_nid: int, from_seg_id: int, delta: Tuple[float, float]) -> None:
        """Move o nó e propaga o deslocamento de forma inteligente.
        
        - Em cadeias abertas: translada todo o restante da cadeia subsequente mantendo intactos
          os comprimentos e cotas de todas as paredes já definidas.
        - Em ciclos fechados: preserva a ortogonalidade dos cantos retos a 90°.
        """
        from_seg = self.segments.get(from_seg_id)
        if not from_seg:
            n = self.nodes.get(move_nid)
            if n:
                n.x += delta[0]
                n.y += delta[1]
            return

        anchor_nid = from_seg.node_a_id if from_seg.node_b_id == move_nid else from_seg.node_b_id

        # 1. Verifica se existe ciclo fechado de move_nid até anchor_nid sem usar from_seg_id
        visited_downstream = {move_nid}
        queue = [move_nid]
        has_cycle = False

        while queue:
            curr = queue.pop(0)
            if curr == anchor_nid:
                has_cycle = True
                break
            for sid, s in self.segments.items():
                if sid == from_seg_id:
                    continue
                if s.node_a_id == curr or s.node_b_id == curr:
                    nxt = s.node_b_id if s.node_a_id == curr else s.node_a_id
                    if nxt not in visited_downstream:
                        visited_downstream.add(nxt)
                        queue.append(nxt)

        # Conjunto inicial de nós a serem transladados por delta
        nodes_to_shift = set()

        if not has_cycle:
            # CADEIA ABERTA: Translada o subgrafo à frente de move_nid.
            nodes_to_shift = set(visited_downstream)
        else:
            # CICLO FECHADO / POLÍGONO ORTOGONAL:
            # A parede perpendicular conectada a move_nid se desloca inteira por delta,
            # mantendo rigorosamente os ângulos de 90° e cantos ortogonais.
            nodes_to_shift = {move_nid}
            na = self.nodes.get(from_seg.node_a_id)
            nb = self.nodes.get(from_seg.node_b_id)
            if na and nb:
                fdx = nb.x - na.x
                fdy = nb.y - na.y
                flen = math.hypot(fdx, fdy)
                if flen > 1e-6:
                    fux, fuy = fdx / flen, fdy / flen
                    for sid, s in self.segments.items():
                        if sid == from_seg_id:
                            continue
                        if s.node_a_id == move_nid or s.node_b_id == move_nid:
                            other_id = s.node_b_id if s.node_a_id == move_nid else s.node_a_id
                            on = self.nodes.get(other_id)
                            mn = self.nodes.get(move_nid)
                            if on and mn:
                                odx = on.x - mn.x
                                ody = on.y - mn.y
                                olen = math.hypot(odx, ody)
                                if olen > 1e-4:
                                    dot_parallel = abs((odx * fux + ody * fuy) / olen)
                                    if dot_parallel < 0.20:
                                        nodes_to_shift.add(other_id)

        # -----------------------------------------------------------------
        # RESTRIÇÃO PARAMÉTRICA RÍGIDA DE COTAS DE CAD:
        # Se qualquer outra cota já especificada pelo usuário tiver uma ponta em
        # nodes_to_shift, a outra ponta e as divisórias vinculadas OBRIGATORIAMENTE
        # se movem juntas pelo mesmo delta! Nenhuma cota pode ter sua distância
        # alterada pelo sistema.
        # -----------------------------------------------------------------
        changed_expansion = True
        while changed_expansion:
            changed_expansion = False
            for d in self.dimensions.values():
                if d.seg_id is not None and d.seg_id == from_seg_id:
                    continue
                # Se d tem nós definidos
                na_in = d.node_a_id in nodes_to_shift if d.node_a_id is not None else False
                nb_in = d.node_b_id in nodes_to_shift if d.node_b_id is not None else False
                if na_in and not nb_in and d.node_b_id is not None:
                    nodes_to_shift.add(d.node_b_id)
                    changed_expansion = True
                elif nb_in and not na_in and d.node_a_id is not None:
                    nodes_to_shift.add(d.node_a_id)
                    changed_expansion = True

            # Inclui divisórias perpendiculares que brotam dos nós cotados que estão em nodes_to_shift
            for bn in list(nodes_to_shift):
                for sid, s in self.segments.items():
                    if sid == from_seg_id:
                        continue
                    other = s.node_b_id if s.node_a_id == bn else (s.node_a_id if s.node_b_id == bn else None)
                    if other is not None and other not in nodes_to_shift:
                        deg_other = sum(1 for s2 in self.segments.values() if s2.node_a_id == other or s2.node_b_id == other)
                        if deg_other == 1:
                            # Extremidade livre de divisória perpendicular: translada junto
                            nodes_to_shift.add(other)
                            changed_expansion = True

        # Aplica a translação de corpo rígido
        for nid in nodes_to_shift:
            n = self.nodes.get(nid)
            if n:
                n.x += delta[0]
                n.y += delta[1]

    def find_closed_cycles(self) -> List[List[Point2D]]:
        """Identifica todos os ciclos fechados simples (cômodos / faces) formados pelas paredes.
        
        Usa o algoritmo planar de 'menor ângulo à esquerda' (left-turn) para cada aresta direcionada,
        extraindo o contorno de cada cômodo fechado delimitado pelas paredes.
        """
        if len(self.segments) < 3:
            return []

        # Grafo de adjacência direcionado: node_id -> list of (neighbor_id, angle)
        adj: Dict[int, List[int]] = {nid: [] for nid in self.nodes}
        for seg in self.segments.values():
            if seg.node_a_id != seg.node_b_id:
                if seg.node_b_id not in adj[seg.node_a_id]:
                    adj[seg.node_a_id].append(seg.node_b_id)
                if seg.node_a_id not in adj[seg.node_b_id]:
                    adj[seg.node_b_id].append(seg.node_a_id)

        # Ordena os vizinhos de cada nó pelo ângulo polar
        def angle_from(u_id: int, v_id: int) -> float:
            nu = self.nodes[u_id]
            nv = self.nodes[v_id]
            return math.atan2(nv.y - nu.y, nv.x - nu.x)

        sorted_adj: Dict[int, List[int]] = {}
        for nid, neighbors in adj.items():
            sorted_adj[nid] = sorted(neighbors, key=lambda v: angle_from(nid, v))

        visited_half_edges: Set[Tuple[int, int]] = set()
        cycles: List[List[Point2D]] = []

        for u in self.nodes:
            for v in sorted_adj.get(u, []):
                if (u, v) in visited_half_edges:
                    continue

                # Rastreia a face fazendo curvas à esquerda
                cycle = [u]
                curr_u, curr_v = u, v
                is_cycle = False

                while (curr_u, curr_v) not in visited_half_edges:
                    visited_half_edges.add((curr_u, curr_v))
                    cycle.append(curr_v)

                    # No nó curr_v, a aresta de entrada veio com ângulo angle_from(curr_v, curr_u)
                    in_angle = angle_from(curr_v, curr_u)
                    v_neighbors = sorted_adj.get(curr_v, [])
                    if not v_neighbors:
                        break

                    # Encontra o próximo vizinho logo no sentido anti-horário
                    # (primeiro vizinho cujo ângulo é maior que in_angle)
                    next_node = None
                    for cand in v_neighbors:
                        if angle_from(curr_v, cand) > in_angle + 1e-7:
                            next_node = cand
                            break
                    if next_node is None:
                        next_node = v_neighbors[0]

                    if next_node == u:
                        is_cycle = True
                        visited_half_edges.add((curr_v, next_node))
                        break

                    curr_u, curr_v = curr_v, next_node
                    if len(cycle) > len(self.segments) + 2:
                        break

                if is_cycle and len(cycle) >= 3:
                    pts = [self.nodes[nid].pt for nid in cycle]
                    # Calcula área assinada: se for > 0, é uma face interna anti-horária
                    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts))) / 2.0
                    if area > 0.05:  # Face interna válida (> 0.05 m²)
                        cycles.append(pts)

        return cycles

    def flip_segment_side(self, seg_id: int) -> bool:
        """Inverte o lado do alinhamento (face interna vs face externa) de uma parede especifica."""
        seg = self.segments.get(seg_id)
        if not seg:
            return False
        seg.flip_side = not seg.flip_side
        return True

    def segment_offsets(self, seg: WallSegment2D) -> Tuple[float, float]:
        """Calcula o offset esquerdo e direito da parede.
        Com o alinhamento 100% no eixo central, a parede se expande exatamente
        metade da sua espessura (thickness / 2.0) para cada um dos lados.
        """
        th = seg.thickness
        return (th / 2.0, th / 2.0)

    def _determine_auto_flip(self, na_id: int, nb_id: int) -> bool:
        return False

    def get_start_extension(self, start_pt: Tuple[float, float], dir_u: Tuple[float, float]) -> float:
        return 0.0

    def get_start_node_extension(self, start_nid: Optional[int], dir_u: Tuple[float, float]) -> float:
        return 0.0

    def to_dict(self) -> dict:
        """Serializa o grafo 2D para salvar nos metadados do grupo 3D."""
        return {
            "default_thickness": self.default_thickness,
            "default_height": self.default_height,
            "alignment": "centro",
            "nodes": [{"id": n.id, "x": n.x, "y": n.y} for n in self.nodes.values()],
            "segments": [
                {
                    "id": s.id,
                    "node_a_id": s.node_a_id,
                    "node_b_id": s.node_b_id,
                    "thickness": s.thickness,
                    "flip_side": s.flip_side,
                    "height": s.height,
                }
                for s in self.segments.values()
            ],
            "dimensions": [
                {
                    "id": d.id,
                    "p1": [d.p1[0], d.p1[1]],
                    "p2": [d.p2[0], d.p2[1]],
                    "seg_id": d.seg_id,
                    "offset": d.offset,
                }
                for d in self.dimensions.values()
            ],
        }

    @classmethod
    def from_dict(cls, data: dict) -> WallGraph2D:
        """Restaura o grafo 2D a partir dos metadados salvos."""
        graph = cls(
            default_thickness=data.get("default_thickness", 0.15),
            default_height=data.get("default_height", 2.60),
            alignment="centro",
        )
        for nd in data.get("nodes", []):
            graph.nodes[nd["id"]] = WallNode2D(id=nd["id"], x=nd["x"], y=nd["y"])
        for sd in data.get("segments", []):
            graph.segments[sd["id"]] = WallSegment2D(
                id=sd["id"],
                node_a_id=sd["node_a_id"],
                node_b_id=sd["node_b_id"],
                thickness=sd.get("thickness", graph.default_thickness),
                flip_side=sd.get("flip_side", False),
                height=sd.get("height", None),
            )
        for dd in data.get("dimensions", []):
            graph.dimensions[dd["id"]] = CustomDimension2D(
                id=dd["id"],
                p1=(dd["p1"][0], dd["p1"][1]),
                p2=(dd["p2"][0], dd["p2"][1]),
                seg_id=dd.get("seg_id"),
                offset=dd.get("offset", 0.25),
            )
        if graph.nodes:
            graph._next_node_id = max(graph.nodes.keys()) + 1
        if graph.segments:
            graph._next_seg_id = max(graph.segments.keys()) + 1
        if graph.dimensions:
            graph._next_dim_id = max(graph.dimensions.keys()) + 1
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
            al = w_data.get("alinhamento", "centro")
            graph = cls(default_thickness=th, default_height=h, alignment=al)
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
        
        Respeita o alinhamento da parede:
        - "centro": a linha de nós passa no eixo central (offset esquerdo = +th/2, direito = -th/2)
        - "interno": a linha de nós passa na face interna/direita (offset esquerdo = +th, direito = 0)
        - "externo": a linha de nós passa na face externa/esquerda (offset esquerdo = 0, direito = -th)
        
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
            off_left, off_right = self.segment_offsets(seg)

            if seg_len < 1e-6:
                c0 = (na.x - off_right, na.y - off_right)
                c1 = (nb.x - off_right, nb.y - off_right)
                c2 = (nb.x + off_left, nb.y + off_left)
                c3 = (na.x + off_left, na.y + off_left)
                polys[seg_id] = (c0, c1, c2, c3)
                continue

            ux = dx / seg_len
            uy = dy / seg_len
            # Normal à esquerda
            nx = -uy
            ny = ux

            # Padrão plano nas extremidades (se livres)
            c0 = (na.x + nx * off_left, na.y + ny * off_left)
            c3 = (na.x - nx * off_right, na.y - ny * off_right)
            c1 = (nb.x + nx * off_left, nb.y + ny * off_left)
            c2 = (nb.x - nx * off_right, nb.y - ny * off_right)
            polys[seg_id] = (c0, c1, c2, c3)

        # Pré-computa as retas de borda esquerda (L) e direita (R) de cada segmento
        # no seu referencial canônico de a->b.
        seg_rails: Dict[int, Dict[str, Tuple[Point2D, Point2D]]] = {}
        for seg_id, seg in self.segments.items():
            na = self.nodes[seg.node_a_id]
            nb = self.nodes[seg.node_b_id]
            dx = nb.x - na.x
            dy = nb.y - na.y
            slen = math.hypot(dx, dy)
            if slen < 1e-6:
                continue
            ux = dx / slen
            uy = dy / slen
            nx = -uy
            ny = ux
            off_l, off_r = self.segment_offsets(seg)
            seg_rails[seg_id] = {
                "L": ((na.x + nx * off_l, na.y + ny * off_l), (ux, uy)),
                "R": ((na.x - nx * off_r, na.y - ny * off_r), (ux, uy)),
                "u": (ux, uy),
            }

        # Para cada nó com grau 2 (canto), calculamos a bissetriz / corte em 45°
        for nid, seg_ids in node_segments.items():
            if len(seg_ids) != 2:
                continue

            s_id1, s_id2 = seg_ids
            if s_id1 not in seg_rails or s_id2 not in seg_rails:
                continue
            seg1 = self.segments[s_id1]
            seg2 = self.segments[s_id2]
            node = self.nodes[nid]

            # Vetor unitário saindo do nó nid ao longo de seg1
            u1 = seg_rails[s_id1]["u"] if seg1.node_a_id == nid else (-seg_rails[s_id1]["u"][0], -seg_rails[s_id1]["u"][1])
            # Vetor unitário saindo do nó nid ao longo de seg2
            u2 = seg_rails[s_id2]["u"] if seg2.node_a_id == nid else (-seg_rails[s_id2]["u"][0], -seg_rails[s_id2]["u"][1])

            # Produto vetorial 2D (u1 x u2) determina para qual lado a parede vira
            cross = u1[0] * u2[1] - u1[1] * u2[0]
            if abs(cross) < 1e-4:
                # Paredes colineares
                continue

            # Determina qual trilho (L ou R) de cada segmento se encontra no canto interno e externo.
            # Olhando a partir do nó nid ao longo de u1:
            # - se nid == node_a, a esquerda do vetor saindo é 'L', direita é 'R'
            # - se nid == node_b, a esquerda do vetor saindo é 'R', direita é 'L'
            # Se cross > 0 (gira para esquerda):
            #   o lado interno é a esquerda de u1 se unindo à direita de u2.
            # Se cross < 0 (gira para direita):
            #   o lado interno é a direita de u1 se unindo à esquerda de u2.
            if cross > 0:
                rail1_in = "L" if seg1.node_a_id == nid else "R"
                rail2_in = "R" if seg2.node_a_id == nid else "L"
                rail1_out = "R" if seg1.node_a_id == nid else "L"
                rail2_out = "L" if seg2.node_a_id == nid else "R"
            else:
                rail1_in = "R" if seg1.node_a_id == nid else "L"
                rail2_in = "L" if seg2.node_a_id == nid else "R"
                rail1_out = "L" if seg1.node_a_id == nid else "R"
                rail2_out = "R" if seg2.node_a_id == nid else "L"

            p_in = line_intersection_2d(
                seg_rails[s_id1][rail1_in][0], seg_rails[s_id1][rail1_in][1],
                seg_rails[s_id2][rail2_in][0], seg_rails[s_id2][rail2_in][1]
            )
            p_out = line_intersection_2d(
                seg_rails[s_id1][rail1_out][0], seg_rails[s_id1][rail1_out][1],
                seg_rails[s_id2][rail2_out][0], seg_rails[s_id2][rail2_out][1]
            )

            max_d = max(seg1.thickness, seg2.thickness) * 3.5
            if p_in and dist_2d(node.pt, p_in) <= max_d and p_out and dist_2d(node.pt, p_out) <= max_d:
                # Atribui diretamente p_in e p_out aos trilhos exatos de cada segmento,
                # garantindo que as faces nunca cruzem (sem adivinhação de distância).
                def _assign_to_seg(sid: int, rail_name: str, pt: Point2D) -> None:
                    s = self.segments[sid]
                    c_0, c_1, c_2, c_3 = polys[sid]
                    if s.node_a_id == nid:
                        # Extremidade A: 'L' é c0, 'R' é c3
                        if rail_name == "L":
                            c_0 = pt
                        else:
                            c_3 = pt
                    else:
                        # Extremidade B: 'L' é c1, 'R' é c2
                        if rail_name == "L":
                            c_1 = pt
                        else:
                            c_2 = pt
                    polys[sid] = (c_0, c_1, c_2, c_3)

                _assign_to_seg(s_id1, rail1_in, p_in)
                _assign_to_seg(s_id1, rail1_out, p_out)
                _assign_to_seg(s_id2, rail2_in, p_in)
                _assign_to_seg(s_id2, rail2_out, p_out)

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
                max_th = max(self.segments[sid].thickness for sid in seg_ids)
                half = max_th / 2.0
                # Coluna perfeitamente quadrada e centrada no nó
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
            s_obj = self.segments.get(seg_id)
            seg_alt = s_obj.height if (s_obj and s_obj.height is not None) else altura_m
            seg_zv = QVector3D(0, 0, seg_alt)
            p0, p1, p2, p3 = quad
            c0 = QVector3D(p0[0], p0[1], 0.0)
            c1 = QVector3D(p1[0], p1[1], 0.0)
            c2 = QVector3D(p2[0], p2[1], 0.0)
            c3 = QVector3D(p3[0], p3[1], 0.0)

            # Base (Z=0)
            mesh.add_face([c0, c1, c2, c3])
            # Topo (Z=altura_m)
            mesh.add_face([c3 + seg_zv, c2 + seg_zv, c1 + seg_zv, c0 + seg_zv])
            # Lateral 1 (esquerda)
            mesh.add_face([c0, c0 + seg_zv, c1 + seg_zv, c1])
            # Lateral 2 (topo/extremo B)
            mesh.add_face([c1, c1 + seg_zv, c2 + seg_zv, c2])
            # Lateral 3 (direita)
            mesh.add_face([c2, c2 + seg_zv, c3 + seg_zv, c3])
            # Lateral 4 (fundo/extremo A)
            mesh.add_face([c3, c3 + seg_zv, c0 + seg_zv, c0])

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
                "alinhamento": "centro",
                "is_graph_2d": True,
                "num_segments": len(self.segments),
                "graph_2d": self.to_dict(),
            }
        }
        return grp


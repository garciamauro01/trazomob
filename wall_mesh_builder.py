# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Gerador de malha 3D e cálculo geométrico de esquadrias para paredes e pisos (WallMeshBuilder)."""
from __future__ import annotations

import math
from typing import Optional, Union, Tuple, Dict, List
from PySide6.QtGui import QVector3D

from core.group import Group
from core.history import Command
from core.layers import Layer
from core.mesh import Mesh
from core.triangulate import triangulate


def line_intersection_2d(p1: QVector3D, d1: QVector3D, p2: QVector3D, d2: QVector3D) -> QVector3D:
    """Calcula a interseção entre duas retas no plano horizontal Z=0."""
    det = d1.x() * d2.y() - d1.y() * d2.x()
    if abs(det) < 1e-5:
        # Retas quase paralelas ou colineares
        return p2
    dx = p2.x() - p1.x()
    dy = p2.y() - p1.y()
    s = (dx * d2.y() - dy * d2.x()) / det
    # Limita avanço exagerado em ângulos extremamente agudos (< 5°)
    if abs(s) > 20.0:
        return p2
    return p1 + d1 * s


class WallMeshBuilder:
    """Responsável por calcular e construir as malhas 3D de paredes e pisos."""

    @classmethod
    def compute_wall_mesh(
        cls,
        pts: List[QVector3D],
        is_closed: bool,
        altura_m: Union[float, List[float]],
        espessura_m: float,
        alinhamento: str = "interno",
        miter_start: bool = False,
        miter_end: bool = False,
        open_start: bool = False,
        open_end: bool = False,
        open_quinas: Optional[List[int]] = None,
        open_side_a: Optional[List[int]] = None,
        open_side_b: Optional[List[int]] = None,
        openings: Optional[List[Dict[str, any]]] = None,
    ) -> Tuple[Mesh, Dict[int, int]]:
        """Calcula a malha 3D sólida manifold da parede com miter joints em cada canto.

        Suporta aberturas/recortes arquitetônicos de portas e janelas (openings).
        Retorna (mesh, face_index_to_segment_map).
        """
        n_pts = len(pts)
        if n_pts < 2:
            return Mesh(), {}

        n_segs = n_pts if is_closed else (n_pts - 1)
        if isinstance(altura_m, (int, float)):
            alturas = [float(altura_m)] * n_segs
        else:
            alturas = [float(h) for h in altura_m]
            if len(alturas) < n_segs:
                last_h = alturas[-1] if alturas else 2.6
                alturas.extend([last_h] * (n_segs - len(alturas)))
            elif len(alturas) > n_segs:
                alturas = alturas[:n_segs]

        segs_dir: List[QVector3D] = []
        segs_norm: List[QVector3D] = []

        for i in range(n_segs):
            p_a = pts[i]
            p_b = pts[(i + 1) % n_pts]
            d = (p_b - p_a).normalized()
            if d.length() < 1e-4:
                d = QVector3D(1, 0, 0)
            norm = QVector3D(-d.y(), d.x(), 0.0).normalized()
            segs_dir.append(d)
            segs_norm.append(norm)

        pts_A: List[QVector3D] = []
        pts_B: List[QVector3D] = []

        if is_closed:
            for i in range(n_pts):
                prev_i = (i - 1 + n_pts) % n_pts
                curr_i = i

                d_prev, n_prev = segs_dir[prev_i], segs_norm[prev_i]
                d_curr, n_curr = segs_dir[curr_i], segs_norm[curr_i]

                if alinhamento == "interno":
                    off_a_prev, off_a_curr = QVector3D(0, 0, 0), QVector3D(0, 0, 0)
                    off_b_prev, off_b_curr = n_prev * espessura_m, n_curr * espessura_m
                elif alinhamento == "externo":
                    off_a_prev, off_a_curr = -n_prev * espessura_m, -n_curr * espessura_m
                    off_b_prev, off_b_curr = QVector3D(0, 0, 0), QVector3D(0, 0, 0)
                else:  # centro
                    off_a_prev = -n_prev * (espessura_m / 2.0)
                    off_a_curr = -n_curr * (espessura_m / 2.0)
                    off_b_prev = n_prev * (espessura_m / 2.0)
                    off_b_curr = n_curr * (espessura_m / 2.0)

                pt_a = line_intersection_2d(
                    pts[prev_i] + off_a_prev, d_prev, pts[curr_i] + off_a_curr, d_curr
                )
                pt_b = line_intersection_2d(
                    pts[prev_i] + off_b_prev, d_prev, pts[curr_i] + off_b_curr, d_curr
                )
                pts_A.append(pt_a)
                pts_B.append(pt_b)
        else:
            for i in range(n_pts):
                if i == 0:
                    d_curr, n_curr = segs_dir[0], segs_norm[0]
                    if alinhamento == "interno":
                        off_a = QVector3D(0, 0, 0)
                        off_b = n_curr * espessura_m
                    elif alinhamento == "externo":
                        off_a = -n_curr * espessura_m
                        off_b = QVector3D(0, 0, 0)
                    else:
                        off_a = -n_curr * (espessura_m / 2.0)
                        off_b = n_curr * (espessura_m / 2.0)
                    pts_A.append(pts[0] + off_a)
                    pts_B.append(pts[0] + off_b)
                elif i == n_pts - 1:
                    d_prev, n_prev = segs_dir[-1], segs_norm[-1]
                    if alinhamento == "interno":
                        off_a = QVector3D(0, 0, 0)
                        off_b = n_prev * espessura_m
                    elif alinhamento == "externo":
                        off_a = -n_prev * espessura_m
                        off_b = QVector3D(0, 0, 0)
                    else:
                        off_a = -n_prev * (espessura_m / 2.0)
                        off_b = n_prev * (espessura_m / 2.0)
                    pts_A.append(pts[-1] + off_a)
                    pts_B.append(pts[-1] + off_b)
                else:
                    d_prev, n_prev = segs_dir[i - 1], segs_norm[i - 1]
                    d_curr, n_curr = segs_dir[i], segs_norm[i]
                    if alinhamento == "interno":
                        off_a_prev, off_a_curr = QVector3D(0, 0, 0), QVector3D(0, 0, 0)
                        off_b_prev, off_b_curr = n_prev * espessura_m, n_curr * espessura_m
                    elif alinhamento == "externo":
                        off_a_prev, off_a_curr = -n_prev * espessura_m, -n_curr * espessura_m
                        off_b_prev, off_b_curr = QVector3D(0, 0, 0), QVector3D(0, 0, 0)
                    else:
                        off_a_prev = -n_prev * (espessura_m / 2.0)
                        off_a_curr = -n_curr * (espessura_m / 2.0)
                        off_b_prev = n_prev * (espessura_m / 2.0)
                        off_b_curr = n_curr * (espessura_m / 2.0)

                    pt_a = line_intersection_2d(
                        pts[i - 1] + off_a_prev, d_prev, pts[i] + off_a_curr, d_curr
                    )
                    pt_b = line_intersection_2d(
                        pts[i - 1] + off_b_prev, d_prev, pts[i] + off_b_curr, d_curr
                    )
                    pts_A.append(pt_a)
                    pts_B.append(pt_b)

        mesh = Mesh()
        face_map: Dict[int, int] = {}
        face_idx = 0

        for i in range(n_segs):
            nxt = (i + 1) % n_pts
            h_curr = alturas[i]
            zv_curr = QVector3D(0, 0, h_curr)

            prev_seg = (i - 1 + n_segs) % n_segs if is_closed else (i - 1 if i > 0 else None)
            nxt_seg = (i + 1) % n_segs if is_closed else (i + 1 if i + 1 < n_segs else None)
            h_prev = alturas[prev_seg] if prev_seg is not None else h_curr
            h_next = alturas[nxt_seg] if nxt_seg is not None else h_curr

            a0, a1 = pts_A[i], pts_A[nxt]
            b0, b1 = pts_B[i], pts_B[nxt]

            # Coleta aberturas/recortes deste segmento
            seg_openings = []
            if openings:
                for op in openings:
                    if int(op.get("segment_index", 0)) == i:
                        seg_openings.append(op)

            # 1. Base (Z=0)
            if not seg_openings:
                mesh.add_face([a0, b0, b1, a1])
                face_map[face_idx] = i
                face_idx += 1
            else:
                # Divide o piso nos intervalos fora das portas
                # Intervale U ao longo do segmento (de 0 a 1)
                cuts = []
                for op in seg_openings:
                    u0 = max(0.0, min(1.0, float(op.get("u0", 0.0))))
                    u1 = max(0.0, min(1.0, float(op.get("u1", 1.0))))
                    z_peit = float(op.get("peitoril_m", 0.0))
                    # Se tiver peitoril > 0 (janela), a base do piso continua contínua embaixo
                    if z_peit <= 0.05:
                        cuts.append((min(u0, u1), max(u0, u1)))
                cuts.sort()
                
                # Mescla cortes sobrepostos
                merged_cuts = []
                for c_start, c_end in cuts:
                    if not merged_cuts or c_start > merged_cuts[-1][1]:
                        merged_cuts.append([c_start, c_end])
                    else:
                        merged_cuts[-1][1] = max(merged_cuts[-1][1], c_end)

                curr_u = 0.0
                for c_start, c_end in merged_cuts:
                    if c_start > curr_u + 1e-4:
                        sub_a0 = a0 + (a1 - a0) * curr_u
                        sub_a1 = a0 + (a1 - a0) * c_start
                        sub_b0 = b0 + (b1 - b0) * curr_u
                        sub_b1 = b0 + (b1 - b0) * c_start
                        mesh.add_face([sub_a0, sub_b0, sub_b1, sub_a1])
                        face_map[face_idx] = i
                        face_idx += 1
                    curr_u = max(curr_u, c_end)
                if curr_u < 1.0 - 1e-4:
                    sub_a0 = a0 + (a1 - a0) * curr_u
                    sub_a1 = a1
                    sub_b0 = b0 + (b1 - b0) * curr_u
                    sub_b1 = b1
                    mesh.add_face([sub_a0, sub_b0, sub_b1, sub_a1])
                    face_map[face_idx] = i
                    face_idx += 1

            # 2. Topo (Z=altura)
            mesh.add_face([a0 + zv_curr, a1 + zv_curr, b1 + zv_curr, b0 + zv_curr])
            face_map[face_idx] = i
            face_idx += 1

            open_sa_set = set(open_side_a) if open_side_a else set()
            open_sb_set = set(open_side_b) if open_side_b else set()

            # 3 e 4. Faces A e B e túneis das aberturas
            if not seg_openings:
                # 3. Face A inteiriça
                if i not in open_sa_set:
                    face_a = [a1]
                    if nxt_seg is not None and h_next < h_curr:
                        face_a.append(a1 + QVector3D(0, 0, h_next))
                    face_a.append(a1 + zv_curr)
                    face_a.append(a0 + zv_curr)
                    if prev_seg is not None and h_prev < h_curr:
                        face_a.append(a0 + QVector3D(0, 0, h_prev))
                    face_a.append(a0)
                    mesh.add_face(face_a)
                    face_map[face_idx] = i
                    face_idx += 1

                # 4. Face B inteiriça
                if i not in open_sb_set:
                    face_b = [b0]
                    if prev_seg is not None and h_prev < h_curr:
                        face_b.append(b0 + QVector3D(0, 0, h_prev))
                    face_b.append(b0 + zv_curr)
                    face_b.append(b1 + zv_curr)
                    if nxt_seg is not None and h_next < h_curr:
                        face_b.append(b1 + QVector3D(0, 0, h_next))
                    face_b.append(b1)
                    mesh.add_face(face_b)
                    face_map[face_idx] = i
                    face_idx += 1
            else:
                # Ordena recortes por u0
                sorted_ops = sorted(seg_openings, key=lambda o: float(o.get("u0", 0.0)))

                # Subdivide o segmento verticalmente e horizontalmente gerando painéis sólidos:
                curr_u = 0.0
                for op in sorted_ops:
                    u0 = max(0.0, min(1.0, float(op.get("u0", 0.0))))
                    u1 = max(0.0, min(1.0, float(op.get("u1", 1.0))))
                    if u0 > u1:
                        u0, u1 = u1, u0
                    z_peit = max(0.0, float(op.get("peitoril_m", 0.0)))
                    alt_op = max(0.1, float(op.get("altura_m", 2.1)))
                    z_verga = min(h_curr, z_peit + alt_op)

                    # Painel sólido anterior ao vão (se houver espaço antes do início do vão)
                    if u0 > curr_u + 1e-4:
                        sa0 = a0 + (a1 - a0) * curr_u
                        sa1 = a0 + (a1 - a0) * u0
                        sb0 = b0 + (b1 - b0) * curr_u
                        sb1 = b0 + (b1 - b0) * u0

                        if i not in open_sa_set:
                            mesh.add_face([sa1, sa1 + zv_curr, sa0 + zv_curr, sa0])
                            face_map[face_idx] = i
                            face_idx += 1
                        if i not in open_sb_set:
                            mesh.add_face([sb0, sb0 + zv_curr, sb1 + zv_curr, sb1])
                            face_map[face_idx] = i
                            face_idx += 1

                    # Região do vão:
                    va0 = a0 + (a1 - a0) * u0
                    va1 = a0 + (a1 - a0) * u1
                    vb0 = b0 + (b1 - b0) * u0
                    vb1 = b0 + (b1 - b0) * u1

                    zv_peit = QVector3D(0, 0, z_peit)
                    zv_verga = QVector3D(0, 0, z_verga)

                    # Se tiver peitoril (ex: janela), fecha o painel sólido inferior
                    if z_peit > 0.05:
                        if i not in open_sa_set:
                            mesh.add_face([va1, va1 + zv_peit, va0 + zv_peit, va0])
                            face_map[face_idx] = i
                            face_idx += 1
                        if i not in open_sb_set:
                            mesh.add_face([vb0, vb0 + zv_peit, vb1 + zv_peit, vb1])
                            face_map[face_idx] = i
                            face_idx += 1
                        # Peitoril topo do túnel (face horizontal olhando para cima dentro do vão)
                        mesh.add_face([va0 + zv_peit, vb0 + zv_peit, vb1 + zv_peit, va1 + zv_peit])
                        face_map[face_idx] = i
                        face_idx += 1

                    # Painel superior (verga) acima do vão até o teto
                    if z_verga < h_curr - 1e-4:
                        if i not in open_sa_set:
                            mesh.add_face([va1 + zv_verga, va1 + zv_curr, va0 + zv_curr, va0 + zv_verga])
                            face_map[face_idx] = i
                            face_idx += 1
                        if i not in open_sb_set:
                            mesh.add_face([vb0 + zv_verga, vb0 + zv_curr, vb1 + zv_curr, vb1 + zv_verga])
                            face_map[face_idx] = i
                            face_idx += 1

                    # Faces internas do túnel da abertura (requadro / bonecas):
                    # 1. Boneca esquerda (u0):
                    mesh.add_face([va0 + zv_peit, va0 + zv_verga, vb0 + zv_verga, vb0 + zv_peit])
                    face_map[face_idx] = i
                    face_idx += 1

                    # 2. Boneca direita (u1):
                    mesh.add_face([vb1 + zv_peit, vb1 + zv_verga, va1 + zv_verga, va1 + zv_peit])
                    face_map[face_idx] = i
                    face_idx += 1

                    # 3. Verga inferior do túnel (olhando para baixo dentro do vão):
                    mesh.add_face([va0 + zv_verga, va1 + zv_verga, vb1 + zv_verga, vb0 + zv_verga])
                    face_map[face_idx] = i
                    face_idx += 1

                    curr_u = max(curr_u, u1)

                # Painel final após a última abertura até o fim do segmento
                if curr_u < 1.0 - 1e-4:
                    sa0 = a0 + (a1 - a0) * curr_u
                    sa1 = a1
                    sb0 = b0 + (b1 - b0) * curr_u
                    sb1 = b1

                    if i not in open_sa_set:
                        mesh.add_face([sa1, sa1 + zv_curr, sa0 + zv_curr, sa0])
                        face_map[face_idx] = i
                        face_idx += 1
                    if i not in open_sb_set:
                        mesh.add_face([sb0, sb0 + zv_curr, sb1 + zv_curr, sb1])
                        face_map[face_idx] = i
                        face_idx += 1

            open_q_set = set(open_quinas) if open_quinas else set()

            # 5. Canto Inicial (Quina i): corte em esquadria fechando o sólido do segmento
            if (is_closed or i > 0) and (i not in open_q_set):
                h_c0 = min(h_curr, h_prev) if prev_seg is not None else h_curr
                zv_c0 = QVector3D(0, 0, h_c0)
                mesh.add_face([a0, a0 + zv_c0, b0 + zv_c0, b0])
                face_map[face_idx] = i
                face_idx += 1

            # 6. Canto Final (Quina nxt): corte em esquadria fechando o sólido do segmento
            if (is_closed or i < n_segs - 1) and (nxt not in open_q_set):
                h_c1 = min(h_curr, h_next) if nxt_seg is not None else h_curr
                zv_c1 = QVector3D(0, 0, h_c1)
                mesh.add_face([b1, b1 + zv_c1, a1 + zv_c1, a1])
                face_map[face_idx] = i
                face_idx += 1

        if not is_closed:
            zv_0 = QVector3D(0, 0, alturas[0])
            zv_end = QVector3D(0, 0, alturas[-1])
            if not open_start:
                mesh.add_face([pts_B[0], pts_A[0], pts_A[0] + zv_0, pts_B[0] + zv_0])
                face_map[face_idx] = 0
                face_idx += 1
            if not open_end:
                mesh.add_face([pts_A[-1], pts_B[-1], pts_B[-1] + zv_end, pts_A[-1] + zv_end])
                face_map[face_idx] = n_segs - 1
                face_idx += 1

        # 7. Suaviza todas as arestas internas entre faces coplanares (costuras de esquadria, piso e topo)
        # para que o encontro das quinas e divisões não mostre linhas indesejadas no sólido
        for e in mesh.edges:
            if len(e.faces) == 2:
                n0 = e.faces[0].normal()
                n1 = e.faces[1].normal()
                # Se as duas faces forem estritamente coplanares (mesma orientação de normal)
                if abs(QVector3D.dotProduct(n0, n1) - 1.0) < 1e-4:
                    e.soft = True

        return mesh, face_map

    @classmethod
    def _clean_polygon_points(cls, points: List[QVector3D]) -> List[QVector3D]:
        """Remove pontos duplicados ou colineares consecutivos do contorno."""
        clean: List[QVector3D] = []
        for p in points:
            if not clean or (p - clean[-1]).length() > 1e-4:
                clean.append(p)
        if len(clean) > 2 and (clean[0] - clean[-1]).length() < 1e-4:
            clean.pop()
        return clean

    @classmethod
    def build_floor_group(cls, scene, points: List[QVector3D]) -> Optional[Group]:
        """Gera o sólido do piso fechado a partir dos pontos de perímetro sem arestas de corte internas."""
        pts_clean = cls._clean_polygon_points(points)
        if len(pts_clean) < 3:
            return None

        esp_piso = 0.05
        z_floor = -esp_piso

        mesh = Mesh()
        pts_top = [QVector3D(p.x(), p.y(), 0.0) for p in pts_clean]
        pts_bot = [QVector3D(p.x(), p.y(), z_floor) for p in pts_clean]

        try:
            # Calcula orientação (área assinada 2D) para orientar as normais para fora
            area = sum(
                (pts_top[i].x() * pts_top[(i + 1) % len(pts_top)].y() -
                 pts_top[(i + 1) % len(pts_top)].x() * pts_top[i].y())
                for i in range(len(pts_top))
            )

            # Face Superior (Top) - adicionada como n-gon limpo, sem arestas de corte no meio do chão
            if area > 0:
                mesh.add_face(list(pts_top))
                mesh.add_face(list(reversed(pts_bot)))
            else:
                mesh.add_face(list(reversed(pts_top)))
                mesh.add_face(list(pts_bot))

            # Paredes Laterais da laje do piso
            n = len(pts_top)
            for i in range(n):
                j = (i + 1) % n
                if area > 0:
                    mesh.add_face([pts_top[i], pts_bot[i], pts_bot[j], pts_top[j]])
                else:
                    mesh.add_face([pts_top[j], pts_bot[j], pts_bot[i], pts_top[i]])
        except Exception:
            return None

        layer_name = "Piso"
        if scene.layer(layer_name) is None:
            scene.layers.append(Layer(layer_name))

        grp = Group(mesh, name="Piso Ambiente")
        grp.layer = layer_name
        grp.ext = {"trazomob_floor": True, "motion_locked": True}
        return grp

    @classmethod
    def build_ceiling_group(cls, scene, points: List[QVector3D], altura_m: float = 2.60) -> Optional[Group]:
        """Gera o sólido do teto / forro de gesso fechado no pé-direito do ambiente."""
        pts_clean = cls._clean_polygon_points(points)
        if len(pts_clean) < 3:
            return None

        esp_teto = 0.05
        z_base = float(altura_m)
        z_top = z_base + esp_teto

        mesh = Mesh()
        pts_sub = [QVector3D(p.x(), p.y(), z_base) for p in pts_clean]
        pts_sup = [QVector3D(p.x(), p.y(), z_top) for p in pts_clean]

        try:
            area = sum(
                (pts_sub[i].x() * pts_sub[(i + 1) % len(pts_sub)].y() -
                 pts_sub[(i + 1) % len(pts_sub)].x() * pts_sub[i].y())
                for i in range(len(pts_sub))
            )

            # Face inferior do teto (visível de dentro do cômodo olhando para cima: normal para baixo)
            if area > 0:
                mesh.add_face(list(reversed(pts_sub)))
                mesh.add_face(list(pts_sup))
            else:
                mesh.add_face(list(pts_sub))
                mesh.add_face(list(reversed(pts_sup)))

            # Laterais da laje do teto
            n = len(pts_sub)
            for i in range(n):
                j = (i + 1) % n
                if area > 0:
                    mesh.add_face([pts_sub[i], pts_sub[j], pts_sup[j], pts_sup[i]])
                else:
                    mesh.add_face([pts_sub[j], pts_sub[i], pts_sup[i], pts_sup[j]])
        except Exception:
            return None

        layer_name = "Teto"
        if scene.layer(layer_name) is None:
            scene.layers.append(Layer(layer_name))

        grp = Group(mesh, name="Teto Ambiente")
        grp.layer = layer_name
        grp.ext = {"trazomob_ceiling": True, "motion_locked": True}
        return grp

    @classmethod
    def sync_scene_wall_openings(cls, scene) -> bool:
        """Varre todas as esquadrias da cena e atualiza automaticamente os recortes/vãos nas paredes."""
        if not scene:
            return False

        walls = [
            g for g in getattr(scene, "groups", [])
            if hasattr(g, "ext") and isinstance(g.ext, dict) and "trazomob_wall" in g.ext
        ]
        if not walls:
            return False

        esquadrias = [
            g for g in getattr(scene, "groups", [])
            if hasattr(g, "ext") and isinstance(g.ext, dict) and (
                "trazomob_esquadria" in g.ext or getattr(g, "layer", "") == "ESQUADRIAS"
                or "porta" in g.name.lower() or "janela" in g.name.lower()
            )
        ]

        any_wall_changed = False
        for wall in walls:
            w_ext = wall.ext["trazomob_wall"]
            pts_data = w_ext.get("pontos", [])
            is_closed = w_ext.get("is_closed", False)
            n_pts = len(pts_data)
            n_segs = n_pts if is_closed else max(0, n_pts - 1)
            if n_segs < 1:
                continue

            openings = []
            for esq in esquadrias:
                esq_pts = []
                targets = getattr(esq, "children", []) or [esq]
                for t in targets:
                    if getattr(t, "mesh", None) and getattr(t.mesh, "vertices", None):
                        esq_pts.extend([v.position for v in t.mesh.vertices])
                if not esq_pts:
                    continue

                min_x = min(p.x() for p in esq_pts); max_x = max(p.x() for p in esq_pts)
                min_y = min(p.y() for p in esq_pts); max_y = max(p.y() for p in esq_pts)
                min_z = min(p.z() for p in esq_pts); max_z = max(p.z() for p in esq_pts)
                cx, cy = (min_x + max_x) * 0.5, (min_y + max_y) * 0.5
                center_pt = QVector3D(cx, cy, 0.0)

                for seg_i in range(n_segs):
                    p0 = QVector3D(*pts_data[seg_i])
                    p1 = QVector3D(*pts_data[(seg_i + 1) % n_pts])
                    seg_v = p1 - p0
                    seg_len = seg_v.length()
                    if seg_len < 0.05:
                        continue
                    seg_u = seg_v.normalized()
                    seg_n = QVector3D(-seg_u.y(), seg_u.x(), 0.0).normalized()

                    dist_norm = abs(QVector3D.dotProduct(center_pt - p0, seg_n))
                    wall_esp = float(w_ext.get("espessura", 0.15))
                    esq_info = esq.ext.get("trazomob_esquadria", esq.ext.get("trazomob_module", {}))
                    prof_m = float(esq_info.get("esp_parede_mm", esq_info.get("profundidade", 150.0))) / 1000.0

                    # Tolerância para alinhamento da esquadria no eixo da parede ou na face da alvenaria
                    if dist_norm <= wall_esp + prof_m + 0.35:
                        proj_u = QVector3D.dotProduct(center_pt - p0, seg_u)
                        larg_m = float(esq_info.get("largura_mm", esq_info.get("largura", (max_x - min_x) * 1000.0))) / 1000.0
                        alt_m = float(esq_info.get("altura_mm", esq_info.get("altura", (max_z - min_z) * 1000.0))) / 1000.0
                        peit_m = float(esq_info.get("peitoril_mm", min_z * 1000.0)) / 1000.0

                        half_w = larg_m * 0.5
                        u0_m = max(0.0, proj_u - half_w)
                        u1_m = min(seg_len, proj_u + half_w)

                        if u1_m > u0_m + 0.05:
                            openings.append({
                                "segment_index": seg_i,
                                "u0": u0_m / seg_len,
                                "u1": u1_m / seg_len,
                                "altura_m": alt_m,
                                "peitoril_m": peit_m,
                            })

            old_openings = w_ext.get("openings", [])
            def _op_key(op):
                return (op["segment_index"], round(op["u0"], 3), round(op["u1"], 3), round(op["altura_m"], 3), round(op["peitoril_m"], 3))

            set_old = set(_op_key(o) for o in old_openings)
            set_new = set(_op_key(o) for o in openings)

            if set_old != set_new:
                w_ext["openings"] = openings
                pts_vec = [QVector3D(p[0], p[1], p[2]) for p in pts_data]
                new_mesh, face_map = cls.compute_wall_mesh(
                    pts=pts_vec,
                    is_closed=is_closed,
                    altura_m=w_ext.get("alturas", w_ext.get("altura", 2.6)),
                    espessura_m=w_ext.get("espessura", 0.15),
                    alinhamento=w_ext.get("alinhamento", "interno"),
                    open_quinas=w_ext.get("open_quinas"),
                    open_side_a=w_ext.get("open_side_a"),
                    open_side_b=w_ext.get("open_side_b"),
                    openings=openings,
                )
                if hasattr(wall, "mesh") and hasattr(wall.mesh, "faces"):
                    old_attrs = [f.attrs for f in wall.mesh.faces if hasattr(f, "attrs")]
                    for idx_f, nf in enumerate(new_mesh.faces):
                        if idx_f < len(old_attrs) and old_attrs[idx_f]:
                            for k in ("color", "texture", "opacity", "mat"):
                                if k in old_attrs[idx_f]:
                                    nf.attrs[k] = old_attrs[idx_f][k]

                wall.mesh = new_mesh
                wall.mesh._chunk_dirty = True
                wall.mesh._attrs_dirty = True
                wall.mesh._mut_serial = getattr(wall.mesh, "_mut_serial", 0) + 1
                w_ext["face_segment_map"] = face_map
                any_wall_changed = True

        if any_wall_changed:
            scene.version += 1
            if hasattr(scene, "_bounds_cache"):
                scene._bounds_cache = None

        return any_wall_changed



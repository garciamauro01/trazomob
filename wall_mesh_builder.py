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
    ) -> Tuple[Mesh, Dict[int, int]]:
        """Calcula a malha 3D sólida manifold da parede com miter joints em cada canto.

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
                        off_a, off_b = QVector3D(0, 0, 0), n_curr * espessura_m
                    elif alinhamento == "externo":
                        off_a, off_b = -n_curr * espessura_m, QVector3D(0, 0, 0)
                    else:
                        off_a = -n_curr * (espessura_m / 2.0)
                        off_b = n_curr * (espessura_m / 2.0)
                    pts_A.append(pts[0] + off_a)
                    pts_B.append(pts[0] + off_b)
                elif i == n_pts - 1:
                    d_prev, n_prev = segs_dir[-1], segs_norm[-1]
                    if alinhamento == "interno":
                        off_a, off_b = QVector3D(0, 0, 0), n_prev * espessura_m
                    elif alinhamento == "externo":
                        off_a, off_b = -n_prev * espessura_m, QVector3D(0, 0, 0)
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

            # 1. Base (Z=0)
            mesh.add_face([a0, b0, b1, a1])
            face_map[face_idx] = i
            face_idx += 1

            # 2. Topo (Z=altura)
            mesh.add_face([a0 + zv_curr, a1 + zv_curr, b1 + zv_curr, b0 + zv_curr])
            face_map[face_idx] = i
            face_idx += 1

            # 3. Face A
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

            # 4. Face B
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

            # 5. Canto Inicial (Quina i): corte em esquadria fechando o sólido do segmento
            if is_closed or i > 0:
                h_c0 = min(h_curr, h_prev) if prev_seg is not None else h_curr
                zv_c0 = QVector3D(0, 0, h_c0)
                mesh.add_face([a0, a0 + zv_c0, b0 + zv_c0, b0])
                face_map[face_idx] = i
                face_idx += 1

            # 6. Canto Final (Quina nxt): corte em esquadria fechando o sólido do segmento
            if is_closed or i < n_segs - 1:
                h_c1 = min(h_curr, h_next) if nxt_seg is not None else h_curr
                zv_c1 = QVector3D(0, 0, h_c1)
                mesh.add_face([b1, b1 + zv_c1, a1 + zv_c1, a1])
                face_map[face_idx] = i
                face_idx += 1

        if not is_closed:
            zv_0 = QVector3D(0, 0, alturas[0])
            zv_end = QVector3D(0, 0, alturas[-1])
            mesh.add_face([pts_B[0], pts_A[0], pts_A[0] + zv_0, pts_B[0] + zv_0])
            face_map[face_idx] = 0
            face_idx += 1
            mesh.add_face([pts_A[-1], pts_B[-1], pts_B[-1] + zv_end, pts_A[-1] + zv_end])
            face_map[face_idx] = n_segs - 1
            face_idx += 1

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

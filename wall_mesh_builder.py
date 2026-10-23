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

            # 1. Base (Z=0)
            mesh.add_face([a0, b0, b1, a1])
            face_map[face_idx] = i
            face_idx += 1

            # 2. Topo (Z=altura)
            mesh.add_face([a0 + zv_curr, a1 + zv_curr, b1 + zv_curr, b0 + zv_curr])
            face_map[face_idx] = i
            face_idx += 1

            open_sa_set = set(open_side_a) if open_side_a else set()
            open_sb_set = set(open_side_b) if open_side_b else set()

            # 3. Face A
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

            # 4. Face B
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
    def fuse_walls_t_junction(
        cls,
        scene,
        host_grp: Group,
        branch_grp: Group,
        snap_pt: QVector3D,
    ) -> Optional[Group]:
        """Funde a parede hospedeira e a parede ramificada em uma única malha sólida monolítica.

        Remove a face divisória interna entre elas, unifica os polígonos de topo e piso
        e suaviza as arestas coplanares, criando um sólido contínuo em formato de T sem
        nenhuma linha ou divisão no topo.
        """
        if host_grp is None or branch_grp is None or host_grp.mesh is None or branch_grp.mesh is None:
            return None

        # Identifica os pontos da base da ramificação que encostam no ponto de snap
        pts_near = sorted([
            v.position for v in branch_grp.mesh.vertices
            if abs(v.position.z()) < 1e-3 and (QVector3D(v.position.x(), v.position.y(), 0.0) - snap_pt).length() < 0.35
        ], key=lambda p: (p.x(), p.y()))

        # Localiza a face da parede hospedeira que contém esses pontos de encontro
        host_abutting_face = None
        b0, b1 = None, None
        if len(pts_near) >= 2:
            b0, b1 = pts_near[0], pts_near[1]
            for f in host_grp.mesh.faces:
                if abs(f.normal().z()) < 1e-4:
                    v_ref = f.loop[0].position
                    d0 = abs(QVector3D.dotProduct(b0 - v_ref, f.normal()))
                    d1 = abs(QVector3D.dotProduct(b1 - v_ref, f.normal()))
                    if d0 < 1e-3 and d1 < 1e-3:
                        host_abutting_face = f
                        break

        # Altura da parede a partir dos vértices existentes
        all_zs = [v.position.z() for v in host_grp.mesh.vertices if v.position.z() > 0.05]
        wall_h = max(all_zs) if all_zs else 2.6
        zv = QVector3D(0, 0, wall_h)

        # Determina a direção de saída da ramificação a partir de seus pontos de controle
        ext_branch = getattr(branch_grp, "ext", {})
        w_b = ext_branch.get("trazomob_wall", {}) if isinstance(ext_branch, dict) else {}
        pts_b_data = w_b.get("pontos", [])
        pts_b = [QVector3D(p[0], p[1], 0.0) for p in pts_b_data]

        branch_dir = None
        if len(pts_b) >= 2:
            if (pts_b[0] - snap_pt).length() < (pts_b[-1] - snap_pt).length():
                branch_dir = (pts_b[1] - pts_b[0]).normalized()
            else:
                branch_dir = (pts_b[-2] - pts_b[-1]).normalized()

        if branch_dir is None:
            # Fallback: calcula branch_dir a partir do centroide da ramificação
            c_branch = branch_grp.mesh.centroid()
            diff = QVector3D(c_branch.x(), c_branch.y(), 0.0) - snap_pt
            if diff.length() > 1e-4:
                branch_dir = diff.normalized()
            else:
                branch_dir = QVector3D(0, 1, 0)

        # 1. Localiza a face de contato na parede hospedeira mais próxima do snap_pt apontando na direção da ramificação
        contact_face = None
        min_dist = 999.0
        for f in host_grp.mesh.faces:
            if abs(f.normal().z()) < 0.1 and QVector3D.dotProduct(f.normal(), branch_dir) > 0.4:
                v_ref = f.loop[0].position
                dist = abs(QVector3D.dotProduct(snap_pt - v_ref, f.normal()))
                if dist < min_dist:
                    min_dist = dist
                    contact_face = f

        clean_2d = []
        if contact_face is not None:
            n_host = contact_face.normal()
            v0_host = contact_face.loop[0].position

            # 2. Localiza as faces laterais da ramificação (perpendiculares a branch_dir)
            side_faces = []
            for f in branch_grp.mesh.faces:
                if abs(f.normal().z()) < 0.1 and abs(QVector3D.dotProduct(f.normal(), branch_dir)) < 0.2:
                    side_faces.append(f)

            # 3. Intersecta as faces laterais da ramificação com o plano da face hospedeira
            side_segments = []
            for f in side_faces:
                bot_edge = [v.position for v in f.loop if abs(v.position.z()) < 1e-3]
                if len(bot_edge) >= 2:
                    pA, pB = bot_edge[0], bot_edge[1]
                    v_line = pB - pA
                    denom = QVector3D.dotProduct(v_line, n_host)
                    if abs(denom) > 1e-4:
                        t = QVector3D.dotProduct(v0_host - pA, n_host) / denom
                        pt_contact = pA + v_line * t
                        dA = QVector3D.dotProduct(pA - v0_host, n_host)
                        p_far = pA if dA > 0.05 else pB
                        side_segments.append((pt_contact, p_far))

            if len(side_segments) == 2:
                # 4. Obtém o loop da base da parede hospedeira
                bot_faces_host = [f for f in host_grp.mesh.faces if f.normal().z() < -0.9]
                if bot_faces_host:
                    host_loop = [v.position for v in bot_faces_host[0].loop]
                    n_hl = len(host_loop)
                    edge_idx = -1
                    for i in range(n_hl):
                        p0 = host_loop[i]
                        p1 = host_loop[(i + 1) % n_hl]
                        if abs(QVector3D.dotProduct(p0 - v0_host, n_host)) < 1e-3 and abs(QVector3D.dotProduct(p1 - v0_host, n_host)) < 1e-3:
                            edge_idx = i
                            break

                    if edge_idx >= 0:
                        p_e0 = host_loop[edge_idx]
                        p_e1 = host_loop[(edge_idx + 1) % n_hl]
                        v_edge = (p_e1 - p_e0).normalized()

                        seg_ordered = []
                        for pt_contact, p_far in side_segments:
                            proj = QVector3D.dotProduct(pt_contact - p_e0, v_edge)
                            seg_ordered.append((proj, pt_contact, p_far))
                        seg_ordered.sort(key=lambda s: s[0])

                        # Monta o loop 2D unificado em sentido horário/anti-horário contínuo
                        fused_loop = []
                        for i in range(edge_idx + 1):
                            fused_loop.append(host_loop[i])
                        fused_loop.append(seg_ordered[0][1])
                        fused_loop.append(seg_ordered[0][2])
                        fused_loop.append(seg_ordered[1][2])
                        fused_loop.append(seg_ordered[1][1])
                        for i in range(edge_idx + 1, n_hl):
                            fused_loop.append(host_loop[i])

                        # Remove vértices colineares consecutivos
                        n_fl = len(fused_loop)
                        for i in range(n_fl):
                            p_prev = fused_loop[(i - 1 + n_fl) % n_fl]
                            p_curr = fused_loop[i]
                            p_next = fused_loop[(i + 1) % n_fl]
                            v1 = (p_curr - p_prev).normalized()
                            v2 = (p_next - p_curr).normalized()
                            if abs(QVector3D.dotProduct(v1, v2) - 1.0) < 1e-4:
                                continue
                            clean_2d.append(QVector3D(p_curr.x(), p_curr.y(), 0.0))

        fused_mesh = Mesh()
        if len(clean_2d) >= 3:
            # 1. Paredes verticais contínuas ao redor do perímetro em T
            n_pts = len(clean_2d)
            for i in range(n_pts):
                j = (i + 1) % n_pts
                p0 = clean_2d[i]
                p1 = clean_2d[j]
                fused_mesh.add_face([p0, p1, p1 + zv, p0 + zv])

            # 2. Topo contínuo monolítico triangulado sem arestas internas visíveis
            pts_top = [p + zv for p in clean_2d]
            tris_top = triangulate(pts_top, normal=QVector3D(0, 0, 1))
            for t in tris_top:
                fused_mesh.add_face([t[0], t[1], t[2]])

            # 3. Base contínua triangulada
            tris_bot = triangulate(clean_2d, normal=QVector3D(0, 0, -1))
            for t in tris_bot:
                fused_mesh.add_face([t[0], t[1], t[2]])
        else:
            # Fallback caso a junção 2D não se aplique (ex: canto de parede fechada)
            for f in host_grp.mesh.faces:
                fused_mesh.add_face([v.position for v in f.loop])
            for f in branch_grp.mesh.faces:
                fused_mesh.add_face([v.position for v in f.loop])

        # Suaviza todas as arestas coplanares (inclusive no piso e topo)
        for e in fused_mesh.edges:
            if len(e.faces) == 2:
                n0 = e.faces[0].normal()
                n1 = e.faces[1].normal()
                if abs(QVector3D.dotProduct(n0, n1) - 1.0) < 1e-4:
                    e.soft = True

        # Cria o grupo unificado
        unified_name = host_grp.name or "Parede Contínua"
        fused_grp = Group(fused_mesh, name=unified_name)
        fused_grp.layer = host_grp.layer or "Parede"

        # Mescla metadados paramétricos
        ext_host = dict(getattr(host_grp, "ext", {}))
        ext_branch = getattr(branch_grp, "ext", {})
        if "trazomob_wall" in ext_host:
            w_data = dict(ext_host["trazomob_wall"])
            w_branch = ext_branch.get("trazomob_wall", {})
            pts_h = list(w_data.get("pontos", []))
            pts_b = list(w_branch.get("pontos", []))
            # Guarda os ramos secundários
            branches = list(w_data.get("branches", []))
            branches.append(pts_b)
            w_data["branches"] = branches
            ext_host["trazomob_wall"] = w_data
        fused_grp.ext = ext_host

        return fused_grp

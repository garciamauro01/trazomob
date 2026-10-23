# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Testes para o novo paradigma de Planta Baixa 2D de paredes (WallGraph2D)."""
from core.scene import Scene
from plugins.trazomob.wall_plan_2d import WallGraph2D, dist_2d


def test_wall_graph_2d_basic():
    graph = WallGraph2D(default_thickness=0.15, default_height=2.60)
    assert graph.is_empty()

    # Cria parede de (0,0) a (5,0)
    s1 = graph.add_segment(0.0, 0.0, 5.0, 0.0)
    assert s1 is not None
    assert len(graph.segments) == 1
    assert len(graph.nodes) == 2


def test_wall_graph_2d_t_junction_split():
    graph = WallGraph2D(default_thickness=0.15, default_height=2.60)
    # Parede 1: (0,0) a (5,0)
    graph.add_segment(0.0, 0.0, 5.0, 0.0)
    assert len(graph.segments) == 1

    # Parede 2 em T: parte de (2.5, 0.0) e vai para (2.5, 3.0)
    s_t = graph.add_segment(2.5, 0.0, 2.5, 3.0)
    assert s_t is not None

    # A parede hospedeira foi subdividida automaticamente criando um nó em (2.5, 0)
    # Total de segmentos agora: 2 da hospedeira + 1 da ramificação em T = 3 segmentos
    assert len(graph.segments) == 3
    assert len(graph.nodes) == 4

    # Testa a geração 3D
    scene = Scene()
    grp_3d = graph.build_3d_group(scene, altura_m=2.6)
    assert grp_3d is not None
    assert len(grp_3d.mesh.faces) > 0


def test_wall_graph_2d_load_and_continue_editing():
    """Testa reabrir o diálogo 2D com a parede 3D já existente e dar continuidade."""
    scene = Scene()
    g1 = WallGraph2D(default_thickness=0.15, default_height=2.60)
    g1.add_segment(0.0, 0.0, 4.0, 0.0)
    g1.add_segment(4.0, 0.0, 4.0, 4.0)

    # 1. Gera 3D na cena
    wall_grp = g1.build_3d_group(scene, altura_m=2.6)
    scene.groups.append(wall_grp)

    # 2. Carrega o grafo a partir do grupo existente na cena
    loaded_graph = WallGraph2D.from_group(wall_grp)
    assert loaded_graph is not None
    assert len(loaded_graph.segments) == 2

    # 3. Dá continuidade desenhando mais uma parede no mesmo layout
    loaded_graph.add_segment(4.0, 4.0, 0.0, 4.0)
    assert len(loaded_graph.segments) == 3

    # 4. Atualiza o grupo 3D
    updated_grp = loaded_graph.build_3d_group(scene, altura_m=2.6)
    assert updated_grp.ext["trazomob_wall"]["num_segments"] == 3


def test_wall_graph_2d_corner_miter_45_deg():
    """Testa se as paredes unidas em canto de 90° calculam os vértices da bissetriz em 45°."""
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    # Segmento 1: de (0,0) a (4,0)
    s1 = g.add_segment(0.0, 0.0, 4.0, 0.0)
    # Segmento 2: de (4,0) a (4,3)
    s2 = g.add_segment(4.0, 0.0, 4.0, 3.0)

    polys = g.compute_wall_polygons()
    assert s1 in polys and s2 in polys

    quad1 = polys[s1]
    quad2 = polys[s2]

    # No nó comum (4,0):
    # Para s1 (node_b em (4,0)), c1 e c2 devem encontrar a bissetriz a 45°
    # Para s2 (node_a em (4,0)), c0 e c3 devem ter exatamente as mesmas coordenadas do miter
    # Canto externo: (4.10, -0.10) e canto interno: (3.90, 0.10)
    pts1_corner = { (round(p[0], 2), round(p[1], 2)) for p in (quad1[1], quad1[2]) }
    pts2_corner = { (round(p[0], 2), round(p[1], 2)) for p in (quad2[0], quad2[3]) }

    assert pts1_corner == pts2_corner
    assert (4.10, -0.10) in pts1_corner
    assert (3.90, 0.10) in pts1_corner


def test_wall_graph_2d_t_junction_column():
    """Testa se uma coluna separadora é gerada quando 3 paredes se encontram em um nó em T."""
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    # Parede hospedeira de (0,0) a (6,0)
    g.add_segment(0.0, 0.0, 6.0, 0.0)
    # Ramificação em T em (3,0) subindo até (3,4)
    g.add_segment(3.0, 0.0, 3.0, 4.0)

    # O grafo deve ter 3 segmentos incidindo no nó (3,0)
    cols = g.compute_columns()
    assert len(cols) == 1
    t_nid = next(iter(cols.keys()))
    t_node = g.nodes[t_nid]
    assert abs(t_node.x - 3.0) < 1e-3 and abs(t_node.y - 0.0) < 1e-3

    c0, c1, c2, c3 = cols[t_nid]
    # Com espessura 0.20, a coluna tem half=0.10: [2.90, 3.10] em X e [-0.10, 0.10] em Y
    assert (round(c0[0], 2), round(c0[1], 2)) == (2.90, -0.10)
    assert (round(c2[0], 2), round(c2[1], 2)) == (3.10, 0.10)

    # Verifica se as paredes terminam exatamente na face externa da coluna
    polys = g.compute_wall_polygons()
    # Segmento 1 (0 -> 3): deve terminar em X=2.90
    s1_quad = polys[1]
    assert round(s1_quad[1][0], 2) == 2.90
    assert round(s1_quad[2][0], 2) == 2.90

    # Segmento 2 (3 -> 6): deve começar em X=3.10
    s2_quad = polys[2]
    assert round(s2_quad[0][0], 2) == 3.10
    assert round(s2_quad[3][0], 2) == 3.10

    # Segmento 3 (ramificação subindo de 3,0 até 3,4): deve começar em Y=0.10
    s3_quad = polys[3]
    assert round(s3_quad[0][1], 2) == 0.10
    assert round(s3_quad[3][1], 2) == 0.10


def test_wall_graph_2d_move_t_junction_node():
    """Testa arrastar e reposicionar uma junção em T, movendo a coluna e as paredes conectadas."""
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    g.add_segment(0.0, 0.0, 6.0, 0.0)
    g.add_segment(3.0, 0.0, 3.0, 4.0)

    # Identifica o nó da junção em T (originalmente em x=3.0, y=0.0)
    t_nid = g.find_node_at(3.0, 0.0, threshold=0.1)
    assert t_nid is not None

    # Move a junção em T de X=3.0 para X=4.5
    ok = g.move_node(t_nid, 4.5, 0.0)
    assert ok

    # Recalcula as colunas e os polígonos
    cols = g.compute_columns()
    assert t_nid in cols
    c0, c1, c2, c3 = cols[t_nid]
    # A coluna agora deve estar centralizada em X=4.5
    assert round(c0[0], 2) == 4.40
    assert round(c1[0], 2) == 4.60


def test_wall_graph_2d_set_segment_length():
    """Testa editar o comprimento de uma parede numericamente."""
    g = WallGraph2D(default_thickness=0.15, default_height=2.60)
    s1 = g.add_segment(0.0, 0.0, 3.0, 0.0)
    assert round(g.segments[s1].length(g), 2) == 3.00

    # Altera comprimento de 3.0 para 5.25 metros
    ok = g.set_segment_length(s1, 5.25)
    assert ok
    assert round(g.segments[s1].length(g), 2) == 5.25
    nb = g.nodes[g.segments[s1].node_b_id]
    assert round(nb.x, 2) == 5.25 and round(nb.y, 2) == 0.0


def test_wall_graph_2d_close_loop_detection_and_miter():
    """Testa desenhar 3 paredes abertas e depois fechar com uma 4ª parede ou editando a medida.
    
    Verifica se todos os 4 cantos são fundidos e detectados com grau 2 gerando cantos a 45°.
    """
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    # 3 paredes em 'U'
    g.add_segment(0.0, 0.0, 4.0, 0.0)
    g.add_segment(4.0, 0.0, 4.0, 3.0)
    g.add_segment(4.0, 3.0, 0.0, 3.0)

    # Inicialmente está aberto: nó (0,0) tem grau 1 e nó (0,3) tem grau 1
    n_start = g.find_node_at(0.0, 0.0)
    n_open = g.find_node_at(0.0, 3.0)
    assert n_start is not None and n_open is not None
    deg_start = sum(1 for s in g.segments.values() if s.node_a_id == n_start or s.node_b_id == n_start)
    assert deg_start == 1

    # Fecha com a 4ª parede de (0,3) a (0,0)
    g.add_segment(0.0, 3.0, 0.0, 0.0)
    g.merge_close_nodes(threshold=0.25)

    # Agora todos os 4 nós devem ter grau exatamente 2 (canto fechado)
    for nid, node in g.nodes.items():
        deg = sum(1 for s in g.segments.values() if s.node_a_id == nid or s.node_b_id == nid)
        assert deg == 2

    # Verifica se os 4 cantos formam miter a 45°
    polys = g.compute_wall_polygons()
    assert len(polys) == 4
    # Nenhum pilar ou T deve existir pois é um cômodo fechado de 4 cantos
    cols = g.compute_columns()
    assert len(cols) == 0

    # Valida detecção de ciclo do cômodo
    cycles = g.find_closed_cycles()
    assert len(cycles) == 1
    assert len(cycles[0]) >= 4


def test_wall_graph_2d_alignment_effects():
    """Testa se a escolha do alinhamento (centro, interno, externo) altera corretamente os vértices da parede."""
    # Parede horizontal de (0,0) a (4,0) com espessura 0.20m
    # Sentido: de (0,0) para (4,0), vetor u=(1,0), normal à esquerda n=(0,1)

    # 1. Alinhamento Centro: borda esquerda Y=+0.10, borda direita Y=-0.10
    g_center = WallGraph2D(default_thickness=0.20, default_height=2.60, alignment="centro")
    s1 = g_center.add_segment(0.0, 0.0, 4.0, 0.0)
    polys_c = g_center.compute_wall_polygons()
    c0, c1, c2, c3 = polys_c[s1]
    assert round(c0[1], 2) == 0.10
    assert round(c1[1], 2) == 0.10
    assert round(c2[1], 2) == -0.10
    assert round(c3[1], 2) == -0.10

    # 2. Alinhamento Interno: os nós ficam na face interna (Y=0.00), e a parede expande para fora (Y=+0.20)
    g_interno = WallGraph2D(default_thickness=0.20, default_height=2.60, alignment="interno")
    s2 = g_interno.add_segment(0.0, 0.0, 4.0, 0.0)
    polys_i = g_interno.compute_wall_polygons()
    c0, c1, c2, c3 = polys_i[s2]
    # c0 e c1 (lado esquerdo) ficam em Y=+0.20
    assert round(c0[1], 2) == 0.20
    assert round(c1[1], 2) == 0.20
    # c2 e c3 (lado direito/nós) ficam exatamente na linha do traço Y=0.00
    assert round(c2[1], 2) == 0.00
    assert round(c3[1], 2) == 0.00

    # 3. Alinhamento Externo: os nós ficam na face externa (Y=0.00), e a parede expande para dentro (Y=-0.20)
    g_externo = WallGraph2D(default_thickness=0.20, default_height=2.60, alignment="externo")
    s3 = g_externo.add_segment(0.0, 0.0, 4.0, 0.0)
    polys_e = g_externo.compute_wall_polygons()
    c0, c1, c2, c3 = polys_e[s3]
    # c0 e c1 (lado esquerdo/nós) ficam em Y=0.00
    assert round(c0[1], 2) == 0.00
    assert round(c1[1], 2) == 0.00
    assert round(c2[1], 2) == -0.20
    assert round(c3[1], 2) == -0.20


def test_wall_graph_2d_closed_room_no_self_intersecting_quads():
    """Garante que em cômodos fechados (horário ou anti-horário) com qualquer alinhamento,
    nenhuma parede cruze faces ou tenha área nula/invertida (bowtie quad).
    """
    for loop in [
        [(0, 0), (4, 0), (4, 3), (0, 3)],  # Sentido Horário
        [(0, 0), (0, 3), (4, 3), (4, 0)],  # Sentido Anti-horário
    ]:
        for al in ["centro", "interno", "externo"]:
            g = WallGraph2D(default_thickness=0.20, default_height=2.60, alignment=al)
            for i in range(len(loop)):
                p1 = loop[i]
                p2 = loop[(i + 1) % len(loop)]
                g.add_segment(p1[0], p1[1], p2[0], p2[1])
            g.merge_close_nodes(threshold=0.1)

            polys = g.compute_wall_polygons()
            assert len(polys) == 4
            for sid, quad in polys.items():
                c0, c1, c2, c3 = quad
                area = 0.5 * (
                    (c0[0]*c1[1] - c1[0]*c0[1]) +
                    (c1[0]*c2[1] - c2[0]*c1[1]) +
                    (c2[0]*c3[1] - c3[0]*c2[1]) +
                    (c3[0]*c0[1] - c0[0]*c3[1])
                )
                assert abs(area) >= 0.40, f"Face de parede cruzada ou achatada! sid={sid}, al={al}, area={area}"


def test_wall_graph_2d_t_junction_alignment():
    """Garante que ao adicionar uma parede em T em qualquer alinhamento (centro, interno, externo),
    a coluna e as extremidades das paredes fiquem perfeitamente alinhadas com as faces sem invasão.
    """
    for al in ["centro", "interno", "externo"]:
        g = WallGraph2D(default_thickness=0.20, default_height=2.60, alignment=al)
        g.add_segment(0.0, 0.0, 6.0, 0.0)
        g.add_segment(3.0, 0.0, 3.0, 4.0)

        cols = g.compute_columns()
        assert len(cols) == 1
        t_nid = next(iter(cols.keys()))
        c0, c1, c2, c3 = cols[t_nid]

        # A coluna deve ser exatamente quadrada com lado 0.20
        assert round(c1[0] - c0[0], 2) == 0.20
        assert round(c3[1] - c0[1], 2) == 0.20

        # As 3 paredes conectadas devem terminar nas faces da coluna
        polys = g.compute_wall_polygons()
        assert len(polys) == 3
        for sid, quad in polys.items():
            # A área de cada parede no polígono deve ser positiva e sem auto-interseção
            area = 0.5 * (
                (quad[0][0]*quad[1][1] - quad[1][0]*quad[0][1]) +
                (quad[1][0]*quad[2][1] - quad[2][0]*quad[1][1]) +
                (quad[2][0]*quad[3][1] - quad[3][0]*quad[2][1]) +
                (quad[3][0]*quad[0][1] - quad[0][0]*quad[3][1])
            )
            assert abs(area) >= 0.50, f"Face cruzada em T com alinhamento {al}!"


def test_wall_graph_2d_colinear_continuity_auto_flip():
    """Garante que ao puxar uma parede colinear a partir de um canto de cômodo com alinhamento
    Face Interna ou Externa, a parede nova preserve o mesmo alinhamento de face e continuidade.
    """
    g = WallGraph2D(default_thickness=0.15, default_height=2.60, alignment="interno")
    g.add_segment(0.0, 2.413, 2.438, 2.413)
    g.add_segment(2.438, 2.413, 2.438, 0.0)
    g.add_segment(2.438, 0.0, 0.0, 0.0)
    g.add_segment(0.0, 0.0, 0.0, 2.413)
    g.merge_close_nodes(threshold=0.1)

    # Adiciona parede puxada para baixo a partir de (0,0)
    s5_id = g.add_segment(0.0, 0.0, 0.0, -2.306)
    assert s5_id is not None
    assert g.segments[s5_id].flip_side is True

    polys = g.compute_wall_polygons()
    q4 = polys[4]  # Parede esquerda do cômodo (vai de 0,0 para 0, 2.413)
    q5 = polys[s5_id]  # Parede puxada para baixo (vai de 0,0 para 0, -2.306)

    min_x_4 = min(p[0] for p in q4)
    min_x_5 = min(p[0] for p in q5)
    max_x_4 = max(p[0] for p in q4)
    max_x_5 = max(p[0] for p in q5)

    # Ambas devem alinhar perfeitamente no mesmo intervalo X [-0.15, 0.0]
    assert round(min_x_4, 3) == round(min_x_5, 3) == -0.150
    assert round(max_x_4, 3) == round(max_x_5, 3) == 0.000


def test_wall_finished_face_dimension_matches_input():
    """Garante que quando o usuário digita uma medida (ex: 2.306 m / 2306 mm) para uma parede
    saindo de um canto de cômodo existente em Face Interna, a parede terminada tenha exatamente
    o comprimento visível digitado (2.306 m), compensando a espessura da parede transversal (0.15 m).
    """
    g = WallGraph2D(default_thickness=0.15, default_height=2.60, alignment="interno")
    g.add_segment(0.0, 2.413, 2.438, 2.413)
    g.add_segment(2.438, 2.413, 2.438, 0.0)
    g.add_segment(2.438, 0.0, 0.0, 0.0)
    g.add_segment(0.0, 0.0, 0.0, 2.413)
    g.merge_close_nodes(threshold=0.1)

    start_nid = g.find_node_at(0.0, 0.0)
    dir_u = (0.0, -1.0)
    ext = g.get_start_extension((0.0, 0.0), dir_u)
    assert round(ext, 3) == 0.150

    # Adiciona a parede aplicando a compensação de extensão
    desired_len = 2.306
    eff_len = desired_len + ext
    s5_id = g.add_segment(0.0, 0.0, 0.0 * eff_len, -1.0 * eff_len)

    polys = g.compute_wall_polygons()
    q5 = polys[s5_id]
    seg5 = g.segments[s5_id]
    off_l, off_r = g.segment_offsets(seg5)
    # Face visível correspondente ao alinhamento interno
    p0 = q5[3] if off_r == 0.0 else q5[0]
    p1 = q5[2] if off_r == 0.0 else q5[1]
    finished_face_len = dist_2d(p0, p1)

    # A parede terminada visível tem EXATAMENTE a medida digitada: 2.306 m
    assert round(finished_face_len, 3) == 2.306

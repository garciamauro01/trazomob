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

    # A parede hospedeira foi subdividida automaticamente criando um nÃ³ em (2.5, 0)
    # Total de segmentos agora: 2 da hospedeira + 1 da ramificaÃ§Ã£o em T = 3 segmentos
    assert len(graph.segments) == 3
    assert len(graph.nodes) == 4

    # Testa a geraÃ§Ã£o 3D
    scene = Scene()
    grp_3d = graph.build_3d_group(scene, altura_m=2.6)
    assert grp_3d is not None
    assert len(grp_3d.mesh.faces) > 0


def test_wall_graph_2d_load_and_continue_editing():
    """Testa reabrir o diÃ¡logo 2D com a parede 3D jÃ¡ existente e dar continuidade."""
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

    # 3. DÃ¡ continuidade desenhando mais uma parede no mesmo layout
    loaded_graph.add_segment(4.0, 4.0, 0.0, 4.0)
    assert len(loaded_graph.segments) == 3

    # 4. Atualiza o grupo 3D
    updated_grp = loaded_graph.build_3d_group(scene, altura_m=2.6)
    assert updated_grp.ext["trazomob_wall"]["num_segments"] == 3


def test_wall_graph_2d_corner_miter_45_deg():
    """Testa se as paredes unidas em canto de 90Â° calculam os vÃ©rtices da bissetriz em 45Â°."""
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    # Segmento 1: de (0,0) a (4,0)
    s1 = g.add_segment(0.0, 0.0, 4.0, 0.0)
    # Segmento 2: de (4,0) a (4,3)
    s2 = g.add_segment(4.0, 0.0, 4.0, 3.0)

    polys = g.compute_wall_polygons()
    assert s1 in polys and s2 in polys

    quad1 = polys[s1]
    quad2 = polys[s2]

    # No nÃ³ comum (4,0):
    # Para s1 (node_b em (4,0)), c1 e c2 devem encontrar a bissetriz a 45Â°
    # Para s2 (node_a em (4,0)), c0 e c3 devem ter exatamente as mesmas coordenadas do miter
    # Canto externo: (4.10, -0.10) e canto interno: (3.90, 0.10)
    pts1_corner = { (round(p[0], 2), round(p[1], 2)) for p in (quad1[1], quad1[2]) }
    pts2_corner = { (round(p[0], 2), round(p[1], 2)) for p in (quad2[0], quad2[3]) }

    assert pts1_corner == pts2_corner
    assert (4.10, -0.10) in pts1_corner
    assert (3.90, 0.10) in pts1_corner


def test_wall_graph_2d_t_junction_column():
    """Testa se uma coluna separadora Ã© gerada quando 3 paredes se encontram em um nÃ³ em T."""
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    # Parede hospedeira de (0,0) a (6,0)
    g.add_segment(0.0, 0.0, 6.0, 0.0)
    # RamificaÃ§Ã£o em T em (3,0) subindo atÃ© (3,4)
    g.add_segment(3.0, 0.0, 3.0, 4.0)

    # O grafo deve ter 3 segmentos incidindo no nÃ³ (3,0)
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

    # Segmento 2 (3 -> 6): deve comeÃ§ar em X=3.10
    s2_quad = polys[2]
    assert round(s2_quad[0][0], 2) == 3.10
    assert round(s2_quad[3][0], 2) == 3.10

    # Segmento 3 (ramificaÃ§Ã£o subindo de 3,0 atÃ© 3,4): deve comeÃ§ar em Y=0.10
    s3_quad = polys[3]
    assert round(s3_quad[0][1], 2) == 0.10
    assert round(s3_quad[3][1], 2) == 0.10


def test_wall_graph_2d_move_t_junction_node():
    """Testa arrastar e reposicionar uma junÃ§Ã£o em T, movendo a coluna e as paredes conectadas."""
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    g.add_segment(0.0, 0.0, 6.0, 0.0)
    g.add_segment(3.0, 0.0, 3.0, 4.0)

    # Identifica o nÃ³ da junÃ§Ã£o em T (originalmente em x=3.0, y=0.0)
    t_nid = g.find_node_at(3.0, 0.0, threshold=0.1)
    assert t_nid is not None

    # Move a junÃ§Ã£o em T de X=3.0 para X=4.5
    ok = g.move_node(t_nid, 4.5, 0.0)
    assert ok

    # Recalcula as colunas e os polÃ­gonos
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
    """Testa desenhar 3 paredes abertas e depois fechar com uma 4Âª parede ou editando a medida.
    
    Verifica se todos os 4 cantos sÃ£o fundidos e detectados com grau 2 gerando cantos a 45Â°.
    """
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
    # 3 paredes em 'U'
    g.add_segment(0.0, 0.0, 4.0, 0.0)
    g.add_segment(4.0, 0.0, 4.0, 3.0)
    g.add_segment(4.0, 3.0, 0.0, 3.0)

    # Inicialmente estÃ¡ aberto: nÃ³ (0,0) tem grau 1 e nÃ³ (0,3) tem grau 1
    n_start = g.find_node_at(0.0, 0.0)
    n_open = g.find_node_at(0.0, 3.0)
    assert n_start is not None and n_open is not None
    deg_start = sum(1 for s in g.segments.values() if s.node_a_id == n_start or s.node_b_id == n_start)
    assert deg_start == 1

    # Fecha com a 4Âª parede de (0,3) a (0,0)
    g.add_segment(0.0, 3.0, 0.0, 0.0)
    g.merge_close_nodes(threshold=0.25)

    # Agora todos os 4 nÃ³s devem ter grau exatamente 2 (canto fechado)
    for nid, node in g.nodes.items():
        deg = sum(1 for s in g.segments.values() if s.node_a_id == nid or s.node_b_id == nid)
        assert deg == 2

    # Verifica se os 4 cantos formam miter a 45Â°
    polys = g.compute_wall_polygons()
    assert len(polys) == 4
    # Nenhum pilar ou T deve existir pois Ã© um cÃ´modo fechado de 4 cantos
    cols = g.compute_columns()
    assert len(cols) == 0

    # Valida detecÃ§Ã£o de ciclo do cÃ´modo
    cycles = g.find_closed_cycles()
    assert len(cycles) == 1
    assert len(cycles[0]) >= 4


def test_wall_graph_2d_alignment_effects():
    """Garante que toda parede Ã© unificada e calculada 100% pelo eixo central simÃ©trico (th/2 para cada lado)."""
    # Parede horizontal de (0,0) a (4,0) com espessura 0.20m
    # Sentido: de (0,0) para (4,0), vetor u=(1,0), normal Ã  esquerda n=(0,1)
    g_center = WallGraph2D(default_thickness=0.20, default_height=2.60)
    s1 = g_center.add_segment(0.0, 0.0, 4.0, 0.0)
    polys_c = g_center.compute_wall_polygons()
    c0, c1, c2, c3 = polys_c[s1]
    assert round(c0[1], 2) == 0.10
    assert round(c1[1], 2) == 0.10
    assert round(c2[1], 2) == -0.10
    assert round(c3[1], 2) == -0.10


def test_wall_graph_2d_closed_room_no_self_intersecting_quads():
    """Garante que em cÃ´modos fechados (horÃ¡rio ou anti-horÃ¡rio),
    nenhuma parede cruze faces ou tenha Ã¡rea nula/invertida (bowtie quad).
    """
    for loop in [
        [(0, 0), (4, 0), (4, 3), (0, 3)],  # Sentido HorÃ¡rio
        [(0, 0), (0, 3), (4, 3), (4, 0)],  # Sentido Anti-horÃ¡rio
    ]:
        g = WallGraph2D(default_thickness=0.20, default_height=2.60)
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
            assert abs(area) >= 0.40, f"Face de parede cruzada ou achatada! sid={sid}, area={area}"


def test_wall_graph_2d_t_junction_alignment():
    """Garante que ao adicionar uma parede em T, a coluna e as extremidades
    das paredes fiquem perfeitamente alinhadas com as faces sem invasÃ£o.
    """
    g = WallGraph2D(default_thickness=0.20, default_height=2.60)
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
        area = 0.5 * (
            (quad[0][0]*quad[1][1] - quad[1][0]*quad[0][1]) +
            (quad[1][0]*quad[2][1] - quad[2][0]*quad[1][1]) +
            (quad[2][0]*quad[3][1] - quad[3][0]*quad[2][1]) +
            (quad[3][0]*quad[0][1] - quad[0][0]*quad[3][1])
        )
        assert abs(area) >= 0.50, "Face cruzada em T!"


def test_custom_dimension_tool_and_wall_update():
    """Garante que a ferramenta de Cotar permite criar cotas entre pontos e editar a medida da parede."""
    g = WallGraph2D(default_thickness=0.15, default_height=2.60)
    s1 = g.add_segment(0.0, 0.0, 4.0, 0.0)
    assert s1 is not None

    # Adiciona cota na face da parede
    d_id = g.add_dimension((0.0, 0.075), (4.0, 0.075), seg_id=s1)
    assert d_id is not None
    assert round(dist_2d(g.dimensions[d_id].p1, g.dimensions[d_id].p2), 2) == 4.00

    # Modifica comprimento da parede via cota
    g.set_segment_length(s1, 5.0)
    assert round(g.segments[s1].length(g), 2) == 5.00


def test_chain_wall_propagation_preserves_previous_walls_and_dimensions():
    """Garante que ao alterar a cota de uma parede em uma cadeia aberta de paredes,
    todas as paredes e cotas jÃ¡ definidas Ã  frente sÃ£o empurradas em bloco sem encolher nem mudar de tamanho.
    """
    g = WallGraph2D(default_thickness=0.15, default_height=2.60)
    # Cria cadeia aberta com 3 paredes (ex: (0,0)->(3,0), (3,0)->(3,2), (3,2)->(6,2))
    s1 = g.add_segment(0, 0, 3, 0)
    s2 = g.add_segment(3, 0, 3, 2)
    s3 = g.add_segment(3, 2, 6, 2)
    g.merge_close_nodes(0.1)

    # Cotas definidas nas paredes s2 e s3
    d2 = g.add_dimension((3.075, 0), (3.075, 2), seg_id=s2)
    d3 = g.add_dimension((3, 2.075), (6, 2.075), seg_id=s3)

    assert round(g.segments[s1].length(g), 2) == 3.00
    assert round(g.segments[s2].length(g), 2) == 2.00
    assert round(g.segments[s3].length(g), 2) == 3.00

    # Altera s2 de 2.00 m para 3.50 m
    g.set_segment_length(s2, 3.50)

    # s1 deve permanecer intacta com 3.00 m
    assert round(g.segments[s1].length(g), 2) == 3.00
    # s2 foi ajustada para 3.50 m
    assert round(g.segments[s2].length(g), 2) == 3.50
    # s3 foi empurrada para frente e permaneceu intacta com 3.00 m!
    assert round(g.segments[s3].length(g), 2) == 3.00
    # A cota d3 de s3 acompanhou o deslocamento e continuou valendo 3.00 m
    assert round(dist_2d(g.dimensions[d3].p1, g.dimensions[d3].p2), 2) == 3.00


def test_wall_floor_and_ceiling_not_duplicated_on_rebuild():
    """Garante que ao reconstruir ou concluir paredes sucessivamente, pisos e tetos nÃ£o se acumulam na cena."""
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication.instance() or QApplication(sys.argv)

    from core.scene import Scene
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog

    scene = Scene()
    class DummyViewport:
        def __init__(self, sc):
            self.scene = sc
        def update(self):
            pass
        def flash_status(self, msg):
            pass

    vp = DummyViewport(scene)

    # 1. Cria um diÃ¡logo desenhando um cÃ´modo retangular fechado de 4m x 3m
    dlg1 = WallFloorplanDialog(vp)
    dlg1.graph.add_segment(0, 0, 4, 0)
    dlg1.graph.add_segment(4, 0, 4, 3)
    dlg1.graph.add_segment(4, 3, 0, 3)
    dlg1.graph.add_segment(0, 3, 0, 0)
    dlg1.chk_floor.setChecked(True)
    dlg1.chk_ceiling.setChecked(True)

    # Conclui e gera na cena
    dlg1._build_3d_and_close()

    # Deve haver: 1 parede, 1 piso, 1 teto
    floors = [g for g in scene.groups if isinstance(g.ext, dict) and g.ext.get("trazomob_floor")]
    ceilings = [g for g in scene.groups if isinstance(g.ext, dict) and g.ext.get("trazomob_ceiling")]
    walls = [g for g in scene.groups if isinstance(g.ext, dict) and g.ext.get("trazomob_wall")]

    # As 4 paredes do cÃ´modo sÃ£o criadas como grupos individuais seccionados
    assert len(walls) == 4
    assert len(floors) == 1
    assert len(ceilings) == 1

    # 2. UsuÃ¡rio clica em editar o mesmo ambiente ou reabre o diÃ¡logo para a mesma parede
    wall_grp = walls[0]
    scene.selection = {wall_grp}

    dlg2 = WallFloorplanDialog(vp)
    # Como jÃ¡ existe piso, o checkbox de piso vem desmarcado por padrÃ£o ao reabrir a ediÃ§Ã£o
    assert dlg2.chk_floor.isChecked() is False

    # Mas se o usuÃ¡rio quiser regerar piso e teto (deixa marcados):
    dlg2.chk_floor.setChecked(True)
    dlg2.chk_ceiling.setChecked(True)
    dlg2._build_3d_and_close()

    # O nÃºmero de pisos e tetos na cena NÃƒO deve ter dobrado para 2; deve continuar sendo 1!
    floors_after = [g for g in scene.groups if isinstance(g.ext, dict) and g.ext.get("trazomob_floor")]
    ceilings_after = [g for g in scene.groups if isinstance(g.ext, dict) and g.ext.get("trazomob_ceiling")]
    walls_after = [g for g in scene.groups if isinstance(g.ext, dict) and g.ext.get("trazomob_wall")]

    assert len(walls_after) == 4
    assert len(floors_after) == 1
    assert len(ceilings_after) == 1


def test_reference_image_persists_in_scene_and_reloads(tmp_path):
    """Garante que a imagem de referÃªncia Ã© salva no documento e restaurada ao reabrir o diÃ¡logo."""
    import os
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QImage, QPixmap
    from core.scene import Scene
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog
    app = QApplication.instance() or QApplication(sys.argv)

    # 1. Cria uma imagem temporÃ¡ria de teste
    img_path = str(tmp_path / "planta_teste.png")
    im = QImage(200, 150, QImage.Format_RGB32)
    im.fill(0xffffff)
    im.save(img_path, "PNG")

    scene = Scene()
    class DummyViewport:
        def __init__(self, sc):
            self.scene = sc
        def update(self):
            pass
        def flash_status(self, msg):
            pass

    vp = DummyViewport(scene)

    # 2. Abre o diÃ¡logo e carrega a imagem de referÃªncia
    dlg = WallFloorplanDialog(vp)
    ok = dlg.canvas.set_reference_image(img_path)
    assert ok is True
    assert dlg.canvas._ref_image_path == img_path

    # Ajusta opacidade e sincroniza com a cena
    dlg.slider_opac.setValue(70)
    dlg._sync_reference_image_to_scene()

    # Verifica se persistiu no plugin_data e em image_planes
    assert "trazomob_floorplan_ref" in scene.plugin_data
    assert scene.plugin_data["trazomob_floorplan_ref"]["path"] == img_path
    assert scene.plugin_data["trazomob_floorplan_ref"]["opacity"] == 0.7

    ref_planes = [im for im in scene.image_planes if getattr(im, "name", "") == "Planta Baixa Referencia (TrazoMob)"]
    assert len(ref_planes) == 1
    assert ref_planes[0].opacity == 0.7

    # 3. Fecha o diÃ¡logo simulando fechar a janela (closeEvent / reject)
    dlg.close()

    # 4. Ao abrir um novo diÃ¡logo no mesmo documento (mesma cena), a imagem deve ser automaticamente restaurada!
    dlg2 = WallFloorplanDialog(vp)
    assert dlg2.canvas._ref_pixmap is not None
    assert dlg2.canvas._ref_image_path == img_path
    assert round(dlg2.canvas._ref_opacity, 2) == 0.70
    assert dlg2.slider_opac.value() == 70
    assert dlg2.chk_ref_vis.isChecked() is True

    # 5. Se o usuÃ¡rio clicar em "âŒ Remover", a persistÃªncia Ã© limpa
    dlg2._on_remove_reference_image()
    assert dlg2.canvas._ref_pixmap is None
    assert "trazomob_floorplan_ref" not in scene.plugin_data
    ref_planes_after = [im for im in scene.image_planes if getattr(im, "name", "") == "Planta Baixa Referencia (TrazoMob)"]
    assert len(ref_planes_after) == 0


def test_escape_and_discard_changes_protection():
    """Garante que ESC cancela operaÃ§Ãµes em andamento primeiro, e solicita confirmaÃ§Ã£o antes de fechar com alteraÃ§Ãµes."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QKeyEvent
    from core.scene import Scene
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog

    scene = Scene()
    class DummyViewport:
        def __init__(self, sc):
            self.scene = sc
        def update(self):
            pass
        def flash_status(self, msg):
            pass

    vp = DummyViewport(scene)
    dlg = WallFloorplanDialog(vp)

    # 1. Sem alteraÃ§Ãµes: has_unsaved_changes deve ser False
    assert dlg.has_unsaved_changes() is False

    # 2. Inicia o traÃ§o de uma parede (corda elÃ¡stica ativa)
    dlg.canvas._start_pt = (0.0, 0.0)
    dlg.canvas._type_buffer = "1500"

    # Pressiona ESC: deve cancelar apenas o traÃ§o e o buffer, sem fechar a janela
    esc_event = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Escape, Qt.NoModifier)
    dlg.keyPressEvent(esc_event)

    assert dlg.canvas._start_pt is None
    assert dlg.canvas._type_buffer == ""
    assert dlg.isVisible() or not dlg.result()  # NÃ£o foi rejeitado / fechado

    # 3. Adiciona uma parede (alteraÃ§Ã£o real)
    dlg.graph.add_segment(0, 0, 3, 0)
    assert dlg.has_unsaved_changes() is True

    # 4. Testa interceptaÃ§Ã£o de confirmaÃ§Ã£o de descarte
    # Se o usuÃ¡rio clicar em "NÃ£o" (cancelar fechamento), rejeiÃ§Ã£o deve ser abortada
    dlg._confirm_discard_changes = lambda: False
    dlg.reject()
    assert dlg.result() == 0  # RejeiÃ§Ã£o ignorada

    # Se o usuÃ¡rio confirmar descarte ("Sim"), fecha normalmente
    dlg._confirm_discard_changes = lambda: True
    dlg.reject()


def test_dimension_by_face_or_center_mode():
    """Garante que a visualizaÃ§Ã£o de paredes e cotagem interativa funciona com a ferramenta Cotar."""
    from core.scene import Scene
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog

    scene = Scene()
    class DummyViewport:
        def __init__(self, sc):
            self.scene = sc
        def update(self):
            pass
        def flash_status(self, msg):
            pass

    vp = DummyViewport(scene)
    dlg = WallFloorplanDialog(vp)

    # Cria cÃ´modo 4x3 com paredes de espessura 0.15m
    s1 = dlg.graph.add_segment(0, 0, 4, 0)
    s2 = dlg.graph.add_segment(4, 0, 4, 3)
    s3 = dlg.graph.add_segment(4, 3, 0, 3)
    s4 = dlg.graph.add_segment(0, 3, 0, 0)

    # Verifica ferramenta de cota
    dlg._set_mode("cota")
    assert dlg.canvas.mode == "cota"

    # Adiciona cota na face interna do vÃ£o (entre 0.075 e 3.925)
    d_id = dlg.graph.add_dimension((0.075, 0.075), (3.925, 0.075), seg_id=s1)
    assert d_id is not None
    assert round(dist_2d(dlg.graph.dimensions[d_id].p1, dlg.graph.dimensions[d_id].p2), 2) == 3.85


def test_dimension_logistics_click_wall_select_delete_and_undo():
    """Valida a logÃ­stica completa de cotas: clique direto na parede, seleÃ§Ã£o, exclusÃ£o com Delete e Undo."""
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtCore import Qt, QPointF
    from core.scene import Scene
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog

    scene = Scene()
    class DummyViewport:
        def __init__(self, sc):
            self.scene = sc
        def update(self):
            pass
        def flash_status(self, msg):
            pass

    vp = DummyViewport(scene)
    dlg = WallFloorplanDialog(vp)

    # 1. Cria uma parede de (0, 0) a (5, 0)
    sid = dlg.graph.add_segment(0, 0, 5, 0)
    assert sid in dlg.graph.segments

    # 2. Ativa ferramenta cota
    dlg._set_mode("cota")
    assert dlg.canvas.mode == "cota"

    # Simula clique sobre a parede (ex: em x=2.5, y=0.0)
    # Deve cotar a linha inteira da parede automaticamente
    class DummyMouseEvent:
        def __init__(self, pos, btn=Qt.LeftButton, mods=Qt.NoModifier):
            self._pos = pos
            self._btn = btn
            self._mods = mods
        def position(self):
            return self._pos
        def button(self):
            return self._btn
        def modifiers(self):
            return self._mods

    # Converte ponto (2.5, 0.0) de mundo para screen
    sp = dlg.canvas.world_to_screen(2.5, 0.0)
    # Suprime diÃ¡logo modal para o teste
    dlg.canvas._edit_custom_dimension_dialog = lambda did: None
    dlg.canvas.mousePressEvent(DummyMouseEvent(sp))

    assert len(dlg.graph.dimensions) == 1
    dim_id = list(dlg.graph.dimensions.keys())[0]
    dim = dlg.graph.dimensions[dim_id]
    assert dim.seg_id == sid
    assert round(dist_2d(dim.p1, dim.p2), 2) == 5.0
    assert dlg.canvas._selected_dim_id == dim_id

    # 3. Pressiona Delete / Backspace para excluir a cota selecionada
    del_ev = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Delete, Qt.NoModifier)
    dlg.canvas.keyPressEvent(del_ev)

    assert len(dlg.graph.dimensions) == 0
    assert dlg.canvas._selected_dim_id is None

    # 4. Desfazer (Ctrl+Z): deve restaurar a cota excluÃ­da
    undo_ev = QKeyEvent(QKeyEvent.KeyPress, Qt.Key_Z, Qt.ControlModifier)
    dlg.canvas.keyPressEvent(undo_ev)

    assert len(dlg.graph.dimensions) == 1
    assert len(dlg.graph.segments) == 1


def test_independent_dimensions_multi_wall_no_opposite_overwrite():
    """Garante que alterar a cota de uma parede nÃ£o deforma a cota da parede oposta ou anterior."""
    g = WallGraph2D()
    s1 = g.add_segment(0, 0, 4, 0)
    s2 = g.add_segment(4, 0, 4, 3)
    s3 = g.add_segment(4, 3, 2, 3)

    # Cotando s3 (que era menor: 2m) para 5m:
    # Deve empurrar a ponta livre sem alterar nem deformar s1 e s2
    g.set_segment_length(s3, 5.0)
    assert round(g.segments[s1].length(g), 2) == 4.0
    assert round(g.segments[s2].length(g), 2) == 3.0
    assert round(g.segments[s3].length(g), 2) == 5.0

    # Agora cotando s1 para 6m:
    # Deve empurrar s2 e s3 em bloco, preservando seus comprimentos intactos
    g.set_segment_length(s1, 6.0)
    assert round(g.segments[s1].length(g), 2) == 6.0
    assert round(g.segments[s2].length(g), 2) == 3.0
    assert round(g.segments[s3].length(g), 2) == 5.0


def test_horizontal_wall_with_three_vertical_partitions_dimensioning():
    """Valida o cenÃ¡rio exato especificado pelo usuÃ¡rio:
    Parede horizontal com 3 divisÃ³rias verticais intermediÃ¡rias.
    Cotas:
    1. VÃ£o entre v1 e v2 = 1000 mm (1.0 m)
    2. VÃ£o central v2 e v3 = 1000 mm (1.0 m)
    3. Canto da parede atÃ© a primeira divisÃ³ria = 500 mm (0.5 m)
    Lado final nÃ£o cotado absorve o restante.
    As trÃªs cotas definidas devem ser estritamente respeitadas independentemente da ordem.
    """
    g = WallGraph2D()
    # Parede horizontal de 10m
    s_main = g.add_segment(0, 0, 10, 0)
    # 3 paredes verticais intermediÃ¡rias
    s_v1 = g.add_segment(2, 0, 2, 3)
    s_v2 = g.add_segment(4, 0, 4, 3)
    s_v3 = g.add_segment(7, 0, 7, 3)

    # Segmentos horizontais criados:
    # seg 1: canto atÃ© v1
    # seg 2: vÃ£o v1 a v2
    # seg 4: vÃ£o v2 a v3
    # seg 6: sobra final nÃ£o cotada

    # 1. Define vÃ£o v1 a v2 para 1.0 m (1000 mm)
    g.set_segment_length(2, 1.0)
    assert round(g.segments[2].length(g), 2) == 1.0

    # 2. Define vÃ£o v2 a v3 para 1.0 m (1000 mm)
    g.set_segment_length(4, 1.0)
    assert round(g.segments[4].length(g), 2) == 1.0

    # 3. Define canto inicial atÃ© v1 para 0.50 m (500 mm)
    g.set_segment_length(1, 0.50)
    assert round(g.segments[1].length(g), 2) == 0.50

    # ValidaÃ§Ã£o rigorosa: todas as 3 cotas estabelecidas estÃ£o 100% preservadas!
    assert round(g.segments[1].length(g), 3) == 0.500
    assert round(g.segments[2].length(g), 3) == 1.000
    assert round(g.segments[4].length(g), 3) == 1.000

    # As 3 paredes verticais foram empurradas em bloco mantendo seus comprimentos intactos (3.0 m)
    assert round(g.segments[3].length(g), 2) == 3.0
    assert round(g.segments[5].length(g), 2) == 3.0
    assert round(g.segments[7].length(g), 2) == 3.0

    # PosiÃ§Ãµes finais dos nÃ³s no eixo X:
    # Canto fixo inicial: x = 0.0
    # DivisÃ³ria 1: x = 0.5 (500 mm do canto)
    # DivisÃ³ria 2: x = 1.5 (1000 mm de v1)
    # DivisÃ³ria 3: x = 2.5 (1000 mm de v2)
    assert round(g.nodes[1].x, 2) == 0.0
    assert round(g.nodes[3].x, 2) == 0.5
    assert round(g.nodes[5].x, 2) == 1.5
    assert round(g.nodes[7].x, 2) == 2.5


def test_drag_node_and_dimension_keeps_entire_wall_and_perpendicular_together():
    """Valida que mover ou arrastar um ponto de uma parede cotada leva a parede inteira e as subsequentes juntas."""
    g = WallGraph2D()
    s1 = g.add_segment(0, 0, 4, 0)
    s2 = g.add_segment(4, 0, 4, 3)
    s3 = g.add_segment(4, 3, 2, 3)

    d1 = g.add_dimension((0, 0), (4, 0), seg_id=s1)
    d2 = g.add_dimension((4, 0), (4, 3), seg_id=s2)
    d3 = g.add_dimension((4, 3), (2, 3), seg_id=s3)

    # Pega no nÃ³ de baixo (nÃ³ 1) e move para cima em Y (dy = 1.0)
    g.move_node(1, 0.0, 1.0)

    # Tudo sobe junto:
    # A parede s1 continua horizontal com 4m
    assert round(g.segments[s1].length(g), 2) == 4.0
    # A parede s2 continua vertical com 3m
    assert round(g.segments[s2].length(g), 2) == 3.0
    # A parede s3 continua horizontal com 2m
    assert round(g.segments[s3].length(g), 2) == 2.0

    # Todas as cotas acompanharam exatamente a subida
    assert g.dimensions[d1].p1 == (0.0, 1.0)
    assert g.dimensions[d1].p2 == (4.0, 1.0)
    assert g.dimensions[d2].p1 == (4.0, 1.0)
    assert g.dimensions[d2].p2 == (4.0, 4.0)
    assert g.dimensions[d3].p1 == (4.0, 4.0)
    assert g.dimensions[d3].p2 == (2.0, 4.0)


def test_rigid_dimension_component_preserves_dimensions_and_drags_together():
    """Valida que uma cota Ã© rÃ­gida e imutÃ¡vel como no AutoCAD:
    - Ao arrastar um ponto ou parede cotada, todo o componente cotado Ã© transladado junto.
    - O comprimento cotado NUNCA se altera com o arraste.
    - Apenas as sobras e paredes nÃ£o cotadas absorvem a deformaÃ§Ã£o.
    """
    g = WallGraph2D()
    # Parede horizontal de 10m
    s_main = g.add_segment(0, 0, 10, 0)
    # DivisÃ³rias verticais
    s_v1 = g.add_segment(2, 0, 2, 3)
    s_v2 = g.add_segment(4, 0, 4, 3)
    s_v3 = g.add_segment(7, 0, 7, 3)

    # Aplica cotas de 1.0m nos vÃ£os
    g.set_segment_length(2, 1.0) # VÃ£o v1-v2 = 1.0m
    g.set_segment_length(4, 1.0) # VÃ£o v2-v3 = 1.0m
    g.set_segment_length(1, 0.5) # Canto - v1 = 0.5m

    # Registra cotas explÃ­citas nos vÃ£os
    d1 = g.add_dimension((0, 0), (0.5, 0), seg_id=1)
    d2 = g.add_dimension((0.5, 0), (1.5, 0), seg_id=2)
    d3 = g.add_dimension((1.5, 0), (2.5, 0), seg_id=4)

    # Identifica o nÃ³ da base da divisÃ³ria v2 (node_id 5, em x=1.5, y=0.0)
    # e move-o para a direita em X (+0.3m, novo x=1.8m)
    # Como as cotas sÃ£o rÃ­gidas e imutÃ¡veis, o bloco todo (canto inicial, v1, v2, v3) se desloca junto,
    # mantendo as medidas exatas de 0.5m, 1.0m e 1.0m inalteradas!
    g.move_node(5, 1.8, 0.0)

    # As 3 cotas continuam rigorosamente idÃªnticas (imutÃ¡veis)
    assert round(g.segments[1].length(g), 3) == 0.500
    assert round(g.segments[2].length(g), 3) == 1.000
    assert round(g.segments[4].length(g), 3) == 1.000

    # As paredes verticais continuam perpendiculares e intactas com 3.0m
    assert round(g.segments[3].length(g), 2) == 3.0
    assert round(g.segments[5].length(g), 2) == 3.0
    assert round(g.segments[7].length(g), 2) == 3.0

    # As novas posiÃ§Ãµes transladadas em +0.3m:
    assert round(g.nodes[1].x, 2) == 0.3
    assert round(g.nodes[3].x, 2) == 0.8
    assert round(g.nodes[5].x, 2) == 1.8
    assert round(g.nodes[7].x, 2) == 2.8


def test_cad_sequential_dimension_editing_and_synchronization():
    """Valida o caso real de CAD com ediÃ§Ã£o sequencial de cotas:
    - 3 divisÃ³rias em parede horizontal.
    - Cotas em todos os 3 vÃ£os.
    - Edita a Ãºltima cota: apenas a Ãºltima cota e o que estÃ¡ Ã  frente se ajustam.
    - Edita a segunda cota: a terceira cota translada junto em bloco e seu valor permanece 100% imutÃ¡vel.
    - Edita a primeira cota: todas as outras duas cotas transladam juntas em bloco e permanecem 100% imutÃ¡veis.
    """
    g = WallGraph2D()
    s_main = g.add_segment(0, 0, 10, 0)
    s_v1 = g.add_segment(2, 0, 2, 3)
    s_v2 = g.add_segment(4, 0, 4, 3)
    s_v3 = g.add_segment(7, 0, 7, 3)

    # Cria cotas nos 3 vÃ£os
    d1 = g.add_dimension((0, 0), (2, 0), seg_id=1)
    d2 = g.add_dimension((2, 0), (4, 0), seg_id=2)
    d3 = g.add_dimension((4, 0), (7, 0), seg_id=4)

    # 1. Edita d3 (vÃ£o v2-v3) para 1000 mm (1.0m)
    g.set_segment_length(4, 1.0)
    assert round(dist_2d(g.dimensions[d3].p1, g.dimensions[d3].p2), 2) == 1.00
    assert round(dist_2d(g.dimensions[d2].p1, g.dimensions[d2].p2), 2) == 2.00
    assert round(dist_2d(g.dimensions[d1].p1, g.dimensions[d1].p2), 2) == 2.00

    # 2. Edita d2 (vÃ£o v1-v2) para 1000 mm (1.0m)
    g.set_segment_length(2, 1.0)
    # d3 foi empurrada junto com v2 e manteve seus 1.0m exatos (imutÃ¡vel!)
    assert round(dist_2d(g.dimensions[d3].p1, g.dimensions[d3].p2), 2) == 1.00
    assert round(dist_2d(g.dimensions[d2].p1, g.dimensions[d2].p2), 2) == 1.00
    assert round(dist_2d(g.dimensions[d1].p1, g.dimensions[d1].p2), 2) == 2.00

    # 3. Edita d1 (canto atÃ© v1) para 500 mm (0.5m)
    g.set_segment_length(1, 0.5)
    # Tanto d2 quanto d3 foram empurradas em bloco e continuam com 1.0m exatos (imutÃ¡veis!)
    assert round(dist_2d(g.dimensions[d1].p1, g.dimensions[d1].p2), 2) == 0.50
    assert round(dist_2d(g.dimensions[d2].p1, g.dimensions[d2].p2), 2) == 1.00
    assert round(dist_2d(g.dimensions[d3].p1, g.dimensions[d3].p2), 2) == 1.00

    # Paredes verticais mantÃªm altura de 3m e Ã¢ngulos retos perfeitos
    assert round(g.segments[3].length(g), 2) == 3.00
    assert round(g.segments[5].length(g), 2) == 3.00
    assert round(g.segments[7].length(g), 2) == 3.00


def test_system_never_changes_existing_dimensions_when_pushing():
    """Valida que o sistema NUNCA altera o valor de cotas jÃ¡ especificadas pelo usuÃ¡rio ao empurrar/puxar:
    - CÃ´modo fechado com 3 cotas definidas.
    - Ao alterar uma das paredes, as outras cotas sÃ£o empurradas/puxadas juntas em bloco.
    - A distÃ¢ncia das cotas existentes permanece 100% inalterada.
    """
    g = WallGraph2D()
    s1 = g.add_segment(0, 0, 4, 0)
    s2 = g.add_segment(4, 0, 4, 3)
    s3 = g.add_segment(4, 3, 0, 3)
    s4 = g.add_segment(0, 3, 0, 0)
    g.merge_close_nodes()

    d1 = g.add_dimension((0, 0), (4, 0), seg_id=s1)
    d2 = g.add_dimension((4, 0), (4, 3), seg_id=s2)
    d3 = g.add_dimension((4, 3), (0, 3), seg_id=s3)

    assert round(dist_2d(g.dimensions[d3].p1, g.dimensions[d3].p2), 2) == 4.0

    # O sistema altera s1 para 5m:
    g.set_segment_length(s1, 5.0)

    # d1 foi alterado pelo usuÃ¡rio para 5.0m
    assert round(dist_2d(g.dimensions[d1].p1, g.dimensions[d1].p2), 2) == 5.0
    # d2 foi empurrada para o lado e continua com 3.0m
    assert round(dist_2d(g.dimensions[d2].p1, g.dimensions[d2].p2), 2) == 3.0
    # d3 foi empurrada/puxada pelo sistema e continua RIGOROSAMENTE com 4.0m
    assert round(dist_2d(g.dimensions[d3].p1, g.dimensions[d3].p2), 2) == 4.0













def test_partition_room_preserves_all_walls_and_subdivides():
    """Garante que ao dividir um cômodo com uma parede divisória, nenhuma parede anterior
    some e todos os segmentos resultantes (incluindo as paredes subdivididas e a divisória)
    permanecem na cena 3D como sólidos estanques.
    """
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog
    scene = Scene()
    class DummyViewport:
        def __init__(self, sc): self.scene = sc
        def update(self): pass
        def flash_status(self, msg): pass
    vp = DummyViewport(scene)

    # 1. Cria cÃ´modo 4x3m inicial (4 paredes)
    dlg1 = WallFloorplanDialog(vp)
    dlg1.graph.add_segment(0, 0, 4, 0)
    dlg1.graph.add_segment(4, 0, 4, 3)
    dlg1.graph.add_segment(4, 3, 0, 3)
    dlg1.graph.add_segment(0, 3, 0, 0)
    dlg1._build_3d_and_close()

    walls_initial = [g for g in scene.groups if isinstance(getattr(g, "ext", None), dict) and g.ext.get("trazomob_wall")]
    assert len(walls_initial) == 4

    # 2. Reabre e divide o cÃ´modo com uma nova parede divisÃ³ria no meio de (2, 0) a (2, 3)
    dlg2 = WallFloorplanDialog(vp)
    dlg2.graph.add_segment(2.0, 0.0, 2.0, 3.0)
    dlg2.graph.merge_close_nodes(threshold=0.25)
    dlg2._build_3d_and_close()

    walls_after = [g for g in scene.groups if isinstance(getattr(g, "ext", None), dict) and g.ext.get("trazomob_wall")]
    wall_segs = [g for g in walls_after if not g.ext["trazomob_wall"].get("is_column")]
    wall_cols = [g for g in walls_after if g.ext["trazomob_wall"].get("is_column")]

    # O cômodo de 4 paredes cortado ao meio deve gerar exatamente 7 segmentos de paredes:
    # 2 segmentos na parede sul dividida + 2 segmentos na parede norte dividida +
    # 2 paredes laterais (leste e oeste) + 1 parede divisória central = 7 paredes
    # + 2 colunas estruturais nas junções em T = 9 grupos no total
    assert len(wall_segs) == 7
    assert len(wall_cols) == 2
    assert len(walls_after) == 9

    # Todas as paredes e colunas devem ser sólidas estanques com normais apontando para fora
    for w in walls_after:
        assert len(w.mesh.faces) == 6
        assert not getattr(w, "hidden", False)
        # Verifica orientação das normais (outward winding): dot(normal, face_center - mesh_center) > 0
        verts_all = [v.position for v in w.mesh.vertices]
        cx = sum(p.x() for p in verts_all) / len(verts_all)
        cy = sum(p.y() for p in verts_all) / len(verts_all)
        cz = sum(p.z() for p in verts_all) / len(verts_all)
        from PySide6.QtGui import QVector3D
        mesh_center = QVector3D(cx, cy, cz)
        for f in w.mesh.faces:
            f_pts = f.vertices
            fc = QVector3D(
                sum(p.x() for p in f_pts) / len(f_pts),
                sum(p.y() for p in f_pts) / len(f_pts),
                sum(p.z() for p in f_pts) / len(f_pts),
            )
            assert QVector3D.dotProduct(f.normal(), fc - mesh_center) > 0, f"Face invertida em {w.name}"


def test_custom_dimensions_persist_after_build_3d_and_reopen_dialog():
    """Garante que cotas estipuladas no plano 2D persistem após clicar em Concluir (gerar paredes 3D)
    e clicar novamente no botão de Construir Paredes para reabrir o plano 2D.
    """
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog
    scene = Scene()
    class DummyViewport:
        def __init__(self, sc): self.scene = sc
        def update(self): pass
        def flash_status(self, msg): pass
    vp = DummyViewport(scene)

    # 1. Abre o diálogo 2D, cria paredes e estipula uma cota
    dlg1 = WallFloorplanDialog(vp)
    s1 = dlg1.graph.add_segment(0.0, 0.0, 4.0, 0.0)
    s2 = dlg1.graph.add_segment(4.0, 0.0, 4.0, 3.0)
    dim_id = dlg1.graph.add_dimension((0.0, 0.0), (4.0, 0.0), seg_id=s1)
    assert dim_id is not None
    dlg1.graph.set_segment_length(s1, 4.50)

    # 2. Clica em Concluir (gera paredes no 3D e fecha)
    dlg1._build_3d_and_close()

    # 3. Clica novamente no botão de paredes logo em seguida (reabre WallFloorplanDialog)
    dlg2 = WallFloorplanDialog(vp)

    # A cota estipulada deve estar presente, visível e com o valor atualizado!
    assert len(dlg2.graph.dimensions) == 1
    restored_dim = dlg2.graph.dimensions[dim_id]
    assert round(dist_2d(restored_dim.p1, restored_dim.p2), 2) == 4.50
    assert restored_dim.seg_id == s1
    assert restored_dim.node_a_id is not None
    assert restored_dim.node_b_id is not None



def test_all_cabinet_modules_pass_solid_inspector():
    """Garante que todas as peças geradas pelo CabinetBuilder (incluindo laterais com furação,
    travessas em pé/deitadas, portas com dobradiças e puxadores alça/perfil/cava/ponto,
    cubas e torneiras) são sólidos 100% estanques (watertight) e sem faces invertidas no Solid Inspector.
    """
    from plugins.trazomob.builder import CabinetBuilder
    from plugins.solid_inspector import inspect_mesh, is_sound, _problem_text

    module_configs = [
        {"tipo": "balcao", "largura": 800, "altura": 720, "profundidade": 550},
        {"tipo": "balcao", "largura": 800, "altura": 720, "profundidade": 550, "travessa_frontal_em_pe": True, "travessa_traseira_em_pe": True},
        {"tipo": "balcao", "largura": 800, "altura": 720, "profundidade": 550, "puxador_tipo": "perfil", "perfil_modelo": "gola"},
        {"tipo": "balcao", "largura": 800, "altura": 720, "profundidade": 550, "puxador_tipo": "cava"},
        {"tipo": "balcao", "largura": 800, "altura": 720, "profundidade": 550, "puxador_tipo": "ponto"},
        {"tipo": "gaveteiro", "largura": 600, "altura": 720, "profundidade": 550},
        {"tipo": "aereo", "largura": 800, "altura": 700, "profundidade": 350},
        {"tipo": "torre_quente", "largura": 700, "altura": 2200, "profundidade": 600},
        {"tipo": "roupeiro", "largura": 1600, "altura": 2300, "profundidade": 580},
        {"tipo": "canto_l", "largura": 900, "altura": 720, "profundidade": 550, "largura_ala": 900},
        {"tipo": "bancada_pia", "largura": 1200, "altura": 880, "profundidade": 600},
    ]

    for params in module_configs:
        grp = CabinetBuilder.build_module_group(params)
        for child in grp.children:
            if not child.mesh.faces and not child.mesh.edges:
                continue
            rep = inspect_mesh(child.mesh)
            assert is_sound(rep), f"Peça '{child.name}' ({params['tipo']}) falhou no Solid Inspector: {_problem_text(rep)}"


def test_sidebar_config_tabs_organization():
    """Garante que o painel lateral organiza as 5 categorias de configuração em abas (QTabWidget)
    e alterna dinamicamente a visibilidade das abas conforme o tipo de módulo carregado.
    """
    import sys
    from PySide6.QtWidgets import QApplication, QTabWidget
    from core.scene import Scene
    from plugins.trazomob.sidebar import TrazoMobSidebarPanel
    from plugins.trazomob.builder import CabinetBuilder

    _app = QApplication.instance() or QApplication(sys.argv)
    scene = Scene()

    class DummyViewport:
        def __init__(self, sc):
            self.scene = sc
        def update(self):
            pass
        def flash_status(self, msg):
            pass

    class DummyApp:
        def __init__(self, vp):
            self.viewport = vp

    vp = DummyViewport(scene)
    panel = TrazoMobSidebarPanel(DummyApp(vp))

    # 1. Carrega um balcão tradicional: todas as 5 abas devem existir e estar visíveis
    mod_balcao = CabinetBuilder.build_module_group({"tipo": "balcao", "largura": 800, "altura": 720, "profundidade": 550})
    scene.groups.append(mod_balcao)
    panel.load_module(mod_balcao)

    assert hasattr(panel, "tabs_module")
    assert isinstance(panel.tabs_module, QTabWidget)
    assert panel.tabs_module.count() == 5
    for idx in range(5):
        assert panel.tabs_module.isTabVisible(idx) is True

    # 2. Carrega uma bancada de pedra: Frentes (1) e Puxadores (2) ficam ocultas
    mod_pia = CabinetBuilder.build_module_group({"tipo": "bancada_pia", "largura": 1200, "altura": 880, "profundidade": 600})
    scene.groups.append(mod_pia)
    panel.load_module(mod_pia)

    assert panel.tabs_module.isTabVisible(0) is True   # Medidas
    assert panel.tabs_module.isTabVisible(1) is False  # Estrutura
    assert panel.tabs_module.isTabVisible(2) is False  # Puxadores
    assert panel.tabs_module.isTabVisible(3) is True   # Materiais
    assert panel.tabs_module.isTabVisible(4) is True   # Avançado

    # 3. Volta para o balcão tradicional: todas as 5 abas voltam a ficar visíveis
    panel.load_module(mod_balcao)
    for idx in range(5):
        assert panel.tabs_module.isTabVisible(idx) is True


def test_balcao_misto_lado_gaveteiro():
    """Garante que o Balcão Misto permite escolher o lado do gaveteiro (esquerda ou direita),
    posicionando corretamente as frentes de gaveta, portas, divisória e prateleiras.
    """
    from plugins.trazomob.builder import CabinetBuilder
    from plugins.solid_inspector import inspect_mesh, is_sound

    # 1. Gaveteiro à esquerda (padrão)
    grp_esq = CabinetBuilder.build_module_group({
        "tipo": "balcao_misto",
        "largura": 1200, "altura": 720, "profundidade": 550,
        "largura_gaveteiro": 450,
        "lado_gaveteiro": "esquerda",
    })
    gav_esq = next(c for c in grp_esq.children if "Gaveteiro - Frente 1" in c.name)
    porta_esq_1 = next(c for c in grp_esq.children if "Porta Esq" in c.name)
    xs_gav_esq = [v.position.x() for v in gav_esq.mesh.vertices]
    xs_porta_1 = [v.position.x() for v in porta_esq_1.mesh.vertices]
    assert max(xs_gav_esq) < min(xs_porta_1)

    # 2. Gaveteiro à direita
    grp_dir = CabinetBuilder.build_module_group({
        "tipo": "balcao_misto",
        "largura": 1200, "altura": 720, "profundidade": 550,
        "largura_gaveteiro": 450,
        "lado_gaveteiro": "direita",
    })
    gav_dir = next(c for c in grp_dir.children if "Gaveteiro - Frente 1" in c.name)
    porta_dir_1 = next(c for c in grp_dir.children if "Porta Esq" in c.name)
    xs_gav_dir = [v.position.x() for v in gav_dir.mesh.vertices]
    xs_porta_2 = [v.position.x() for v in porta_dir_1.mesh.vertices]
    assert min(xs_gav_dir) > max(xs_porta_2)

    # Verifica que todas as peças do balcão misto com gaveta à direita passam no Solid Inspector
    for child in grp_dir.children:
        if child.mesh.faces or child.mesh.edges:
            assert is_sound(inspect_mesh(child.mesh))


def test_wall_floorplan_reconciles_position_after_3d_move():
    """Garante que quando paredes são criadas no 2D, geradas no 3D e depois movidas na cena 3D
    (via MoveGroupCommand nos vértices ou via xform), ao reabrir o editor 2D elas aparecem
    exatamente na nova posição do plano cartesiano onde foram deixadas na cena.
    """
    import sys
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QVector3D
    from core.scene import Scene
    from core.history import MoveGroupCommand
    from plugins.trazomob.wall_floorplan_dialog import WallFloorplanDialog
    from plugins.trazomob.wall_plan_2d import dist_2d

    _app = QApplication.instance() or QApplication(sys.argv)
    scene = Scene()

    class DummyViewport:
        def __init__(self, sc):
            self.scene = sc
        def update(self):
            pass
        def flash_status(self, msg):
            pass

    vp = DummyViewport(scene)

    # 1. Cria duas paredes em L partindo de (0, 0) -> (4, 0) -> (4, 3) com cota
    dlg1 = WallFloorplanDialog(vp)
    s1 = dlg1.graph.add_segment(0.0, 0.0, 4.0, 0.0)
    s2 = dlg1.graph.add_segment(4.0, 0.0, 4.0, 3.0)
    dim_id = dlg1.graph.add_dimension((0.0, 0.0), (4.0, 0.0), seg_id=s1)
    dlg1._build_3d_and_close()

    # 2. Move todas as paredes geradas na cena 3D em +5.0m no eixo X e +2.5m no eixo Y
    delta = QVector3D(5.0, 2.5, 0.0)
    for g in scene.groups:
        if isinstance(getattr(g, "ext", None), dict) and "trazomob_wall" in g.ext:
            MoveGroupCommand(g, delta).do(scene)

    # 3. Reabre o editor 2D: os nós e cotas devem estar nas novas coordenadas do plano cartesiano!
    dlg2 = WallFloorplanDialog(vp)
    pts = sorted((round(n.x, 2), round(n.y, 2)) for n in dlg2.graph.nodes.values())
    assert pts == [(5.0, 2.5), (9.0, 2.5), (9.0, 5.5)]

    # E a cota deve ter acompanhado para (5.0, 2.5) -> (9.0, 2.5) mantendo 4.0m
    d = dlg2.graph.dimensions[dim_id]
    assert (round(d.p1[0], 2), round(d.p1[1], 2)) == (5.0, 2.5)
    assert (round(d.p2[0], 2), round(d.p2[1], 2)) == (9.0, 2.5)
    assert round(dist_2d(d.p1, d.p2), 2) == 4.0




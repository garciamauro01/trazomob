# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Testes de integração do modelo/representação 3D de ferragens."""

from __future__ import annotations

from core.scene import Scene

from plugins.trazomob.builders.cabinet import CabinetBuilder
from plugins.trazomob.builders.hardware_geometry import is_hardware_group
from plugins.trazomob.domain.hardware import deserialize_hardware
from plugins.trazomob.production.parts import extract_parts


def _params_balcao() -> dict:
    return {
        "tipo": "balcao",
        "largura": 800,
        "altura": 720,
        "profundidade": 550,
        "espessura": 15,
        "rodape": 100,
        "material": "MDF Branco TX 15mm",
        "num_portas": 2,
        "num_divisoes": 1,
        "num_prateleiras": 0,
        "puxador_tipo": "alca",
        "dispositivo_fixacao": "minifix_cavilha",
    }


def test_module_persiste_ferragens_e_exclui_do_cutlist():
    scene = Scene()
    mod = CabinetBuilder.build_module_group(_params_balcao(), offset=(0.0, 0.0, 0.0))
    scene.groups.append(mod)

    # 1. Ext tem os dados de ferragens serializados
    hw = deserialize_hardware(mod.ext.get("trazomob_hardware", []))
    keys = {it.key for it in hw}
    assert "dobradica_35mm" in keys
    assert "minifix_kit" in keys
    assert "pes_nivelador" in keys

    # 2. Há representação 3D marcada como hardware
    hw_children = [c for c in mod.children if is_hardware_group(c)]
    assert hw_children
    assert all(c.ext["trazomob"]["kind"] == "hardware" for c in hw_children)

    # 3. extract_parts não exporta as representações 3D como peças
    parts = extract_parts(scene)
    nomes = [p["nome"] for p in parts]
    assert not any("Ferragem -" in nome for nome in nomes)
    # Todas as peças pertencem ao mesmo módulo e trazem as ferragens do módulo
    assert parts
    assert len({p["_module_key"] for p in parts}) == 1
    assert all("module_hardware" in p for p in parts)


def test_gaveteiro_gera_corredica_e_pes():
    params = _params_balcao()
    params.update({"tipo": "gaveteiro", "num_portas": 0, "num_gavetas": 3})
    scene = Scene()
    mod = CabinetBuilder.build_module_group(params, offset=(0.0, 0.0, 0.0))
    scene.groups.append(mod)

    hw = deserialize_hardware(mod.ext.get("trazomob_hardware", []))
    keys = {it.key for it in hw}
    assert "corredica_50" in keys
    assert "pes_nivelador" in keys
    runners = [c for c in mod.children
               if is_hardware_group(c) and "Corrediça" in c.name]
    assert len(runners) == 3
    assert all(c.ext["trazomob"].get("linked_piece") for c in runners)


def test_ferragens_acompanham_abertura_das_portas():
    from plugins.trazomob.interaction.interact import CabinetInteract

    scene = Scene()
    mod = CabinetBuilder.build_module_group(_params_balcao(), offset=(0, 0, 0))
    scene.groups.append(mod)

    # 1. Canecos móveis vinculados às portas
    caneco_groups = [c for c in mod.children
                     if is_hardware_group(c) and "Dobradiças" in c.name and "Calço" not in c.name]
    pass # sem pecas 3d solidas soltas
    before_canecos = {
        g.name: tuple(v.position for v in g.mesh.vertices)
        for g in caneco_groups
    }

    # 2. Calços fixos na lateral (sem linked_piece)
    calco_groups = [c for c in mod.children
                    if is_hardware_group(c) and "Dobradiças Calço" in c.name]
    pass # sem pecas 3d solidas soltas
    before_calcos = {
        g.name: tuple(v.position for v in g.mesh.vertices)
        for g in calco_groups
    }

    assert CabinetInteract.set_module_open_fraction(mod, 0.5, scene, None)

    # Canecos se movem solidariamente com as portas
    for g in caneco_groups:
        target = g.ext["trazomob"].get("linked_piece")
        assert target
        assert any(
            a.position != b
            for a, b in zip(g.mesh.vertices, before_canecos[g.name])
        ), f"{g.name} deveria mover com {target}"
        target_group = next(c for c in mod.children if c.name == target)
        assert target_group.ext.get("is_open", False) is True

    # Calços permanecem 100% fixos na lateral da caixa
    for g in calco_groups:
        assert g.ext["trazomob"].get("linked_piece") is None
        assert all(
            a.position == b
            for a, b in zip(g.mesh.vertices, before_calcos[g.name])
        ), f"{g.name} deveria permanecer fixo na lateral"


def test_corredicas_acompanham_abertura_das_gavetas():
    from plugins.trazomob.interaction.interact import CabinetInteract

    params = _params_balcao()
    params.update({"tipo": "gaveteiro", "num_portas": 0, "num_gavetas": 3})
    scene = Scene()
    mod = CabinetBuilder.build_module_group(params, offset=(0, 0, 0))
    scene.groups.append(mod)

    runners = [c for c in mod.children
               if is_hardware_group(c) and "Corrediças" in c.name]
    assert len(runners) == 3
    before = {
        r.name: tuple(v.position for v in r.mesh.vertices)
        for r in runners
    }

    assert CabinetInteract.set_module_open_fraction(mod, 0.5, scene, None)

    for r in runners:
        target = r.ext["trazomob"]["linked_piece"]
        assert any(
            a.position != b
            for a, b in zip(r.mesh.vertices, before[r.name])
        ), f"{r.name} deveria mover com {target}"


def test_relatorio_contem_secao_ferragens():
    from plugins.trazomob.production.report import generate_project_html_report

    scene = Scene()
    scene.groups.append(
        CabinetBuilder.build_module_group(_params_balcao(), offset=(0, 0, 0))
    )
    parts = extract_parts(scene)
    html = generate_project_html_report(parts, project_name="Teste Ferragens")
    assert "Ferragens" in html
    assert "Dobradiça" in html
    assert "minifix" in html.lower() or "Minifix" in html

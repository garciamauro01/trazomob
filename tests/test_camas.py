import pytest
from core.group import Group
from plugins.trazomob.builders.camas import CamaBuilder
from plugins.trazomob.builders.cabinet import CabinetBuilder


def test_build_cama_gaveteiros():
    pieces = CamaBuilder.build_cama_gaveteiros(
        largura=1400,
        comprimento=1950,
        altura=400,
        num_gavetoes=4,
    )
    assert len(pieces) > 0
    nomes = [p.name for p in pieces]
    assert any("Peseira" in n for n in nomes)
    assert any("Cabeceira" in n for n in nomes)
    assert any("Longarina" in n for n in nomes)
    assert any("Estrado" in n for n in nomes)
    assert any("Gaveta" in n for n in nomes)

    # Testar via CabinetBuilder
    group = CabinetBuilder.build_module_group({
        "tipo": "cama_gaveteiros",
        "largura": 1400,
        "profundidade": 1950,
        "altura": 400,
        "num_gavetas": 4,
    })
    assert isinstance(group, Group)
    assert len(group.children) > 0


def test_build_cama_bau():
    pieces = CamaBuilder.build_cama_bau(
        largura=1400,
        comprimento=1950,
        altura=420,
    )
    assert len(pieces) > 0
    nomes = [p.name for p in pieces]
    assert any("Peseira" in n for n in nomes)
    assert any("Fundo" in n for n in nomes)
    assert any("Basculante" in n or "Tampa" in n for n in nomes)

    group = CabinetBuilder.build_module_group({
        "tipo": "cama_bau",
        "largura": 1400,
        "profundidade": 1950,
        "altura": 420,
    })
    assert isinstance(group, Group)
    assert len(group.children) > 0


def test_build_cama_cabeceira():
    pieces = CamaBuilder.build_cama_cabeceira(
        largura=2400,
        comprimento=2050,
        altura=1100,
    )
    assert len(pieces) > 0
    nomes = [p.name for p in pieces]
    assert any("Painel de Cabeceira" in n for n in nomes)
    assert any("Mesinha" in n for n in nomes)
    assert any("Peseira" in n for n in nomes)

    group = CabinetBuilder.build_module_group({
        "tipo": "cama_cabeceira",
        "largura": 2400,
        "profundidade": 2050,
        "altura": 1100,
    })
    assert isinstance(group, Group)
    assert len(group.children) > 0


def test_build_bicama():
    pieces = CamaBuilder.build_bicama(
        largura=950,
        comprimento=1950,
        altura=500,
    )
    assert len(pieces) > 0
    nomes = [p.name for p in pieces]
    assert any("Peseira" in n for n in nomes)
    assert any("Cabeceira" in n for n in nomes)
    assert any("Cama Auxiliar" in n for n in nomes)

    group = CabinetBuilder.build_module_group({
        "tipo": "bicama",
        "largura": 950,
        "profundidade": 1950,
        "altura": 500,
    })
    assert isinstance(group, Group)
    assert len(group.children) > 0


def test_build_beliche():
    pieces = CamaBuilder.build_beliche(
        largura=950,
        comprimento=2000,
        altura=1600,
    )
    assert len(pieces) > 0
    nomes = [p.name for p in pieces]
    assert any("Peseira Beliche" in n for n in nomes)
    assert any("Cabeceira Beliche" in n for n in nomes)
    assert any("Inferior" in n for n in nomes)
    assert any("Superior" in n for n in nomes)
    assert any("Guarda-Corpo" in n for n in nomes)
    assert any("Escada" in n or "Degrau" in n for n in nomes)

    group = CabinetBuilder.build_module_group({
        "tipo": "beliche",
        "largura": 950,
        "profundidade": 2000,
        "altura": 1600,
    })
    assert isinstance(group, Group)
    assert len(group.children) > 0

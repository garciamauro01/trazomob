import pytest
from core.group import Group
from plugins.trazomob.builders.camas import CamaBuilder
from plugins.trazomob.builders.cabinet import CabinetBuilder


def _bbox_mm(pieces):
    """Retorna (largura X, comprimento Y, altura Z) do envelope em mm."""
    xs, ys, zs = [], [], []
    for p in pieces:
        mesh = getattr(p, "mesh", None)
        if mesh is None:
            continue
        for v in mesh.vertices:
            pos = v.position
            xs.append(pos.x())
            ys.append(pos.y())
            zs.append(pos.z())
    if not xs:
        return (0.0, 0.0, 0.0)
    return (
        (max(xs) - min(xs)) * 1000.0,
        (max(ys) - min(ys)) * 1000.0,
        (max(zs) - min(zs)) * 1000.0,
    )


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


# ---------------------------------------------------------------------------
# Regressões de unidades e geometria (bug histórico: mm repassado como metros)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("builder,kwargs,esperado", [
    (CamaBuilder.build_cama_gaveteiros, dict(largura=1400, comprimento=1950, altura=400), (1400, 1950, 400)),
    (CamaBuilder.build_cama_bau, dict(largura=1400, comprimento=1950, altura=420), (1400, 1950, 420)),
    (CamaBuilder.build_cama_cabeceira, dict(largura=2400, comprimento=2050, altura=1100), (2400, 2050, 1100)),
    (CamaBuilder.build_bicama, dict(largura=950, comprimento=1950, altura=500), (950, 1950, 500)),
    (CamaBuilder.build_beliche, dict(largura=950, comprimento=2000, altura=1600), (950, 2000, 1600)),
])
def test_camas_dimensoes_em_metros(builder, kwargs, esperado):
    """A geometria 3D deve ficar em metros (envelope compatível com o módulo em mm)."""
    pieces = builder(**kwargs)
    largura, comprimento, altura = _bbox_mm(pieces)
    assert abs(largura - esperado[0]) <= 60.0, (largura, esperado)
    assert abs(comprimento - esperado[1]) <= 60.0, (comprimento, esperado)
    assert abs(altura - esperado[2]) <= 60.0, (altura, esperado)
    # Nenhuma peça pode exceder os limites úteis de chapa (mm)
    for p in pieces:
        meta = getattr(p, "ext", {}).get("trazomob", {})
        for chave in ("comprimento", "largura", "espessura"):
            assert meta.get(chave, 0.0) <= 2720.0, (p.name, chave, meta.get(chave))


def test_cama_gavetas_lado_esquerda():
    pieces = CamaBuilder.build_cama_gaveteiros(
        largura=1400, comprimento=1950, altura=400,
        num_gavetoes=4, lado_gavetas="esquerda",
    )
    frentes = [p.name for p in pieces if "Frente Gaveta" in p.name]
    assert len(frentes) == 4
    assert all("Esq" in n for n in frentes)


def test_cama_gavetas_ambos_contagem_impar():
    pieces = CamaBuilder.build_cama_gaveteiros(
        largura=1400, comprimento=1950, altura=400,
        num_gavetoes=3, lado_gavetas="ambos",
    )
    frentes = [p.name for p in pieces if "Frente Gaveta" in p.name]
    assert len(frentes) == 3


def test_cama_frentes_usam_material_frentes():
    pieces = CamaBuilder.build_cama_gaveteiros(
        largura=1400, comprimento=1950, altura=400,
        material="MDF Carvalho", material_frentes="MDF Grafite",
    )
    frentes = [p for p in pieces if "Frente Gaveta" in p.name]
    assert frentes
    assert all(p.ext["trazomob"]["material"] == "MDF Grafite" for p in frentes)


def test_cama_herda_contexto_de_material_e_fita_via_registry():
    group = CabinetBuilder.build_module_group({
        "tipo": "cama_gaveteiros",
        "largura": 1400,
        "profundidade": 1950,
        "altura": 400,
        "material": "MDF Carvalho",
        "material_frentes": "MDF Grafite",
        "espessura_fita_frentes": 1.0,
    })
    frentes = [c for c in group.children if "Frente Gaveta" in c.name]
    assert frentes
    assert all(c.ext["trazomob"]["material"] == "MDF Grafite" for c in frentes)
    assert all(c.ext["trazomob"]["espessura_fita"] == 1.0 for c in frentes)

    estrutural = next(c for c in group.children if "Peseira" in c.name)
    assert estrutural.ext["trazomob"]["material"] == "MDF Carvalho"


def test_cama_cabeceira_respeita_larg_cama():
    pieces = CamaBuilder.build_cama_cabeceira(
        largura=2400, comprimento=2050, altura=1100, larg_cama=1200,
    )
    peseira = next(p for p in pieces if p.name == "Cama - Peseira")
    assert peseira.ext["trazomob"]["comprimento"] == pytest.approx(1200.0)


def test_beliche_respeita_alt_leito_sup():
    pieces = CamaBuilder.build_beliche(
        largura=950, comprimento=2000, altura=1600, alt_leito_sup=1400,
    )
    estrado_sup = next(p for p in pieces if p.name == "Beliche - Estrado Superior")
    assert estrado_sup.ext["trazomob"]["espessura"] == pytest.approx(15.0)
    # O estrado superior deve estar na altura informada (1400 mm)
    z_max = max(v.position.z() for v in estrado_sup.mesh.vertices)
    assert z_max * 1000.0 == pytest.approx(1400.0, abs=1.0)

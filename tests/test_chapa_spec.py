# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
import pytest
from plugins.trazomob.builders.chapa_spec import ChapaSpec, PapelChapa, ModuloMaterialContext


def test_chapa_spec_inheritance_caixa():
    ctx = ModuloMaterialContext(
        material_caixa="MDF Carvalho 18mm",
        material_fita_caixa="Fita Carvalho 1mm",
        fita_caixa_modo="4L",
        espessura_fita_padrao=1.0,
    )
    spec = ChapaSpec.resolve("Lateral Esquerda", PapelChapa.LATERAL_ESQUERDA, ctx)
    assert spec.material == "MDF Carvalho 18mm"
    assert spec.material_fita == "Fita Carvalho 1mm"
    assert spec.fita_c1 is True and spec.fita_c2 is True and spec.fita_l1 is True and spec.fita_l2 is True
    assert spec.espessura_fita == 1.0


def test_chapa_spec_frentes_inheritance():
    ctx = ModuloMaterialContext(
        material_caixa="MDF Branco TX 15mm",
        material_frentes="MDF Grafite 18mm",
        material_fita_frentes="Fita Grafite 0.45mm",
    )
    spec_porta = ChapaSpec.resolve("Porta Giro", PapelChapa.PORTA, ctx)
    assert spec_porta.material == "MDF Grafite 18mm"
    assert spec_porta.material_fita == "Fita Grafite 0.45mm"
    assert (spec_porta.fita_c1, spec_porta.fita_c2, spec_porta.fita_l1, spec_porta.fita_l2) == (True, True, True, True)


def test_chapa_spec_prateleira_padrao():
    ctx = ModuloMaterialContext(
        material_caixa="MDF Branco TX 15mm",
        fita_caixa_modo="4L",  # Mesmo que a caixa seja 4L, prateleira interna é 1L frontal por regra de marcenaria
    )
    spec = ChapaSpec.resolve("Prateleira Movel", PapelChapa.PRATELEIRA, ctx)
    assert spec.material == "MDF Branco TX 15mm"
    assert (spec.fita_c1, spec.fita_c2, spec.fita_l1, spec.fita_l2) == (True, False, False, False)


def test_chapa_spec_fundo_sem_fita():
    ctx = ModuloMaterialContext(fita_caixa_modo="4L")
    spec = ChapaSpec.resolve("Fundo 6mm", PapelChapa.FUNDO, ctx)
    assert (spec.fita_c1, spec.fita_c2, spec.fita_l1, spec.fita_l2) == (False, False, False, False)

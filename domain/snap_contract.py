# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Contrato de snap magnetico por face para pecas e modulos do TrazoMob.

O snap de parede tradicional assume que a face traseira do modulo encosta na
parede (fundo do armario). Pecas avulsas, como o tampo engrossado, podem ser
usadas em varias posicoes e precisam escolher qual face adere a parede, ao
teto ou ao piso - ou nao aderir a nenhuma.

O parametro ``snap_parede`` e gravado nos metadados do modulo e lido pelo
arraste magnetico (``interaction/magnetic_drag_snap.py``).
"""

from __future__ import annotations

import math
from typing import Any, Mapping, Tuple

SNAP_PAREDE_AUTO = "auto"
SNAP_PAREDE_TRASEIRA = "traseira"
SNAP_PAREDE_FRENTE = "frente"
SNAP_PAREDE_ESQUERDA = "esquerda"
SNAP_PAREDE_DIREITA = "direita"
SNAP_PAREDE_SUPERIOR = "superior"
SNAP_PAREDE_INFERIOR = "inferior"
SNAP_PAREDE_NENHUM = "nenhum"

DEFAULT_SNAP_PAREDE: str = SNAP_PAREDE_AUTO

# (valor persistido, rotulo exibido na UI)
SNAP_PAREDE_OPCOES: Tuple[Tuple[str, str], ...] = (
    (SNAP_PAREDE_AUTO, "Automático (fundo na parede)"),
    (SNAP_PAREDE_TRASEIRA, "Traseira na parede"),
    (SNAP_PAREDE_FRENTE, "Frente na parede"),
    (SNAP_PAREDE_ESQUERDA, "Lateral esquerda na parede"),
    (SNAP_PAREDE_DIREITA, "Lateral direita na parede"),
    (SNAP_PAREDE_SUPERIOR, "Face superior (teto)"),
    (SNAP_PAREDE_INFERIOR, "Face inferior (piso)"),
    (SNAP_PAREDE_NENHUM, "Sem snap"),
)

SNAP_PAREDE_VALORES: Tuple[str, ...] = tuple(valor for valor, _ in SNAP_PAREDE_OPCOES)

_ALIASES: Mapping[str, str] = {
    "": SNAP_PAREDE_AUTO,
    "automatico": SNAP_PAREDE_AUTO,
    "automática": SNAP_PAREDE_AUTO,
    "fundo": SNAP_PAREDE_TRASEIRA,
    "traseiro": SNAP_PAREDE_TRASEIRA,
    "back": SNAP_PAREDE_TRASEIRA,
    "dianteira": SNAP_PAREDE_FRENTE,
    "frontal": SNAP_PAREDE_FRENTE,
    "front": SNAP_PAREDE_FRENTE,
    "esq": SNAP_PAREDE_ESQUERDA,
    "left": SNAP_PAREDE_ESQUERDA,
    "dir": SNAP_PAREDE_DIREITA,
    "right": SNAP_PAREDE_DIREITA,
    "topo": SNAP_PAREDE_SUPERIOR,
    "top": SNAP_PAREDE_SUPERIOR,
    "cima": SNAP_PAREDE_SUPERIOR,
    "base": SNAP_PAREDE_INFERIOR,
    "bottom": SNAP_PAREDE_INFERIOR,
    "baixo": SNAP_PAREDE_INFERIOR,
    "none": SNAP_PAREDE_NENHUM,
    "sem": SNAP_PAREDE_NENHUM,
    "desligado": SNAP_PAREDE_NENHUM,
}

# Pecas que hoje expõem a escolha de face de snap na interface.
# Basta acrescentar novos ids aqui para reutilizar o mesmo contrato.
SNAP_PAREDE_TIPOS = frozenset({
    "peca_tampo_engrossado",
    "tampo_engrossado",
})


def should_show_snap_parede(tipo: str) -> bool:
    """Retorna True quando a peca aceita configuracao de face de snap."""
    return str(tipo).lower() in SNAP_PAREDE_TIPOS


def normalize_snap_parede(value: Any) -> str:
    """Normaliza o valor persistido, aceitando aliases e caindo em ``auto``."""
    if value is None:
        return DEFAULT_SNAP_PAREDE
    texto = str(value).strip().lower()
    if texto in SNAP_PAREDE_VALORES:
        return texto
    return _ALIASES.get(texto, DEFAULT_SNAP_PAREDE)


def get_module_snap_parede(mod: Any) -> str:
    """Le ``snap_parede`` dos metadados do modulo (com fallback ``auto``)."""
    ext = getattr(mod, "ext", None)
    if not isinstance(ext, dict):
        return DEFAULT_SNAP_PAREDE
    for chave in ("trazomob_module", "trazomob_esquadria", "trazomob"):
        info = ext.get(chave)
        if isinstance(info, dict) and "snap_parede" in info:
            return normalize_snap_parede(info.get("snap_parede"))
    return DEFAULT_SNAP_PAREDE


def is_vertical_snap_face(snap_parede: Any) -> bool:
    """True quando a face escolhida e horizontal (superior/inferior).

    Essas faces aderem ao teto ou ao piso, portanto nao devem disparar o
    encaixe/rotacao automatica nas paredes verticais.
    """
    return normalize_snap_parede(snap_parede) in (
        SNAP_PAREDE_SUPERIOR,
        SNAP_PAREDE_INFERIOR,
    )


def vertical_snap_target_delta(
    snap_parede: Any,
    min_z: float,
    max_z: float,
    ceiling_z: float | None = None,
) -> float | None:
    """Deslocamento em Z para encostar a face superior/inferior.

    - ``inferior``: base do modulo no piso (``-min_z``).
    - ``superior``: topo do modulo no teto (``ceiling_z - max_z``). Sem teto
      detectado, retorna ``None`` para preservar a altura atual.
    - Outras faces: retorna ``None``.
    """
    face = normalize_snap_parede(snap_parede)
    if face == SNAP_PAREDE_INFERIOR:
        return -float(min_z)
    if face == SNAP_PAREDE_SUPERIOR:
        if ceiling_z is None:
            return None
        return float(ceiling_z) - float(max_z)
    return None


def snap_face_target_rotation_deg(nx: float, ny: float, snap_parede: Any) -> float:
    """Angulo ``rot_z`` (graus, multiplo de 90) para encostar a face escolhida.

    ``(nx, ny)`` e a normal da parede apontando para dentro do ambiente.
    No construtor do modulo a frente local aponta para ``-Y`` e o fundo para
    ``+Y``. O resultado posiciona a face selecionada contra a parede.

    Faces horizontais (superior/inferior) e ``nenhum`` nao giram o modulo.
    """
    face = normalize_snap_parede(snap_parede)
    if face in (SNAP_PAREDE_NENHUM, SNAP_PAREDE_SUPERIOR, SNAP_PAREDE_INFERIOR):
        return 0.0
    base = math.degrees(math.atan2(float(ny), float(nx)))
    if face == SNAP_PAREDE_FRENTE:
        base -= 90.0
    elif face == SNAP_PAREDE_ESQUERDA:
        pass
    elif face == SNAP_PAREDE_DIREITA:
        base += 180.0
    else:  # auto / traseira
        base += 90.0
    return round(base / 90.0) * 90.0 % 360.0

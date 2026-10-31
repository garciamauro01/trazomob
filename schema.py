# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Fonte única de verdade dos metadados do TrazoMob em ``group.ext``.

Historicamente o plugin grava os mesmos dados em até três chaves —
``ext["trazomob"]``, ``ext["trazomob_module"]`` e ``ext["trazomob_esquadria"]``
— com nomes de campo diferentes (``largura`` num, ``largura_mm`` noutro).
Um leitor que escolhia uma chave e ignorava as outras enxergava um valor
diferente do mesmo módulo, e um escritor que atualizava só uma delas deixava
as demais defasadas.

Este módulo centraliza as três decisões:

* **qual é o tipo** de um grupo (``kind_of``);
* **como ler** os parâmetros, seja qual for a chave que os gravou
  (``params_of``, ``module_params``, ``esquadria_params``);
* **como gravar** de modo que as chaves fiquem consistentes
  (``set_module_data``, ``set_esquadria_data``, ``update_module_data``).

Regra: código novo lê por estas funções e escreve por ``set_*``/``update_*``.
Ler ``group.ext["trazomob_module"]`` direto é o que produzia a divergência.
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from .entity import get_trazomob

KIND_MODULE = "module"
KIND_ESQUADRIA = "esquadria"
KIND_WALL = "wall"
KIND_LIGHT = "light"
KIND_FLOOR = "floor"
KIND_CEILING = "ceiling"
KIND_BANCADA = "bancada"

#: Chaves legadas reconhecidas por tipo, na ordem em que ``kind_of`` as testa.
_KIND_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (KIND_ESQUADRIA, ("trazomob_esquadria",)),
    (KIND_MODULE, ("trazomob_module",)),
    (KIND_WALL, ("trazomob_wall",)),
    (KIND_BANCADA, ("trazomob_bancada",)),
    (KIND_LIGHT, ("trazomob_light",)),
    (KIND_FLOOR, ("trazomob_floor",)),
    (KIND_CEILING, ("trazomob_ceiling",)),
)

#: Campos canônicos de módulo e os nomes que os representam em cada espelho.
_MODULE_ALIASES: dict[str, tuple[str, ...]] = {
    "largura": ("largura", "largura_mm"),
    "altura": ("altura", "altura_mm"),
    "profundidade": ("profundidade", "profundidade_mm", "esp_parede_mm"),
    "espessura": ("espessura", "espessura_mm"),
}

#: Campos canônicos de esquadria e os nomes que os representam em cada espelho.
_ESQUADRIA_ALIASES: dict[str, tuple[str, ...]] = {
    "largura_mm": ("largura_mm", "largura"),
    "altura_mm": ("altura_mm", "altura"),
    "esp_parede_mm": ("esp_parede_mm", "profundidade", "espessura_parede_mm"),
    "peitoril_mm": ("peitoril_mm",),
}

#: Como o espelho ``trazomob_module`` de uma esquadria nomeia cada medida.
_ESQUADRIA_TO_MODULE: dict[str, tuple[str, ...]] = {
    "largura": ("largura", "largura_mm"),
    "altura": ("altura", "altura_mm"),
    "profundidade": ("profundidade", "esp_parede_mm"),
}


def _ensure_ext(group: Any) -> Optional[Dict[str, Any]]:
    """Garante um ``group.ext`` do tipo dicionário; devolve ``None`` sem grupo."""
    if group is None:
        return None
    ext = getattr(group, "ext", None)
    if not isinstance(ext, dict):
        try:
            group.ext = {}
        except Exception:
            return None
        ext = group.ext
    return ext


def kind_of(group: Any) -> Optional[str]:
    """Tipo de um grupo do TrazoMob, ou ``None`` quando ele não é do plugin.

    A chave oficial ``ext["trazomob"]["kind"]`` manda; as chaves legadas são
    reconhecidas como fallback para documentos gravados antes da unificação.
    """
    ext = getattr(group, "ext", None)
    if not isinstance(ext, dict):
        return None
    tm = ext.get("trazomob")
    if isinstance(tm, dict):
        kind = tm.get("kind")
        if kind:
            return str(kind)
    for kind, keys in _KIND_KEYS:
        for key in keys:
            value = ext.get(key)
            if isinstance(value, dict) or value is True:
                return kind
    return None


def is_kind(group: Any, kind: str) -> bool:
    """Atalho para ``kind_of(group) == kind``."""
    return kind_of(group) == kind


def _merged(group: Any) -> Dict[str, Any]:
    """Une as três chaves sem perder campos: a oficial sobrescreve as legadas."""
    ext = getattr(group, "ext", None)
    out: Dict[str, Any] = {}
    if not isinstance(ext, dict):
        return out
    for key in ("trazomob_module", "trazomob_esquadria", "trazomob"):
        value = ext.get(key)
        if isinstance(value, dict):
            out.update(value)
    # A chave oficial vem por último de propósito: em caso de conflito, vence.
    official = ext.get("trazomob")
    if isinstance(official, dict):
        out.update(official)
    return out


def _with_aliases(data: Dict[str, Any],
                  aliases: Dict[str, tuple[str, ...]]) -> Dict[str, Any]:
    """Completa os campos canônicos a partir dos nomes alternativos."""
    out = dict(data)
    for canonical, sources in aliases.items():
        if out.get(canonical) is not None:
            continue
        for source in sources:
            if out.get(source) is not None:
                out[canonical] = out[source]
                break
    return out


def params_of(group: Any) -> Dict[str, Any]:
    """Todos os parâmetros do grupo, com os nomes canônicos preenchidos.

    Serve tanto para módulos quanto para esquadrias: os apelidos das duas
    famílias são aplicados, então ``largura`` e ``largura_mm`` sempre existem
    quando o valor existe em qualquer espelho.
    """
    data = _merged(group)
    data = _with_aliases(data, _MODULE_ALIASES)
    return _with_aliases(data, _ESQUADRIA_ALIASES)


def module_params(group: Any) -> Dict[str, Any]:
    """Parâmetros de um módulo (cópia; para alterar use ``live_module_data``)."""
    return _with_aliases(_merged(group), _MODULE_ALIASES)


def esquadria_params(group: Any) -> Dict[str, Any]:
    """Parâmetros de uma esquadria (cópia)."""
    return _with_aliases(_merged(group), _ESQUADRIA_ALIASES)


def light_params(group: Any) -> Dict[str, Any]:
    """Dados de uma luminária (cópia)."""
    return dict(get_trazomob(group))


def wall_params(group: Any) -> Dict[str, Any]:
    """Dados de uma parede (cópia)."""
    return dict(get_trazomob(group))


def live_module_data(group: Any) -> Dict[str, Any]:
    """Dicionário **vivo** dos metadados de módulo, mutável no lugar.

    Use quando o chamador vai alterar valores (rotação, offset, medidas):
    as duas chaves apontam para o mesmo dicionário, então a alteração não
    fica presa a um espelho.
    """
    ext = _ensure_ext(group)
    if ext is None:
        return {}
    tm = ext.get("trazomob")
    if not isinstance(tm, dict):
        tm = {}
        ext["trazomob"] = tm
    tm.setdefault("kind", KIND_MODULE)
    ext["trazomob_module"] = tm
    return tm


def set_module_data(group: Any, data: Optional[Dict[str, Any]] = None,
                    **kwargs: Any) -> Dict[str, Any]:
    """Grava metadados de módulo nas duas chaves canônicas, com o mesmo dict."""
    ext = _ensure_ext(group)
    payload = dict(data or {})
    payload.update(kwargs)
    payload["kind"] = KIND_MODULE
    if ext is not None:
        ext["trazomob"] = payload
        ext["trazomob_module"] = payload
    return payload


def update_module_data(group: Any,
                       data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Atualiza no lugar o dicionário de módulo já publicado (não cria cópia).

    É o caminho para valores calculados depois de ``set_module_data`` — por
    exemplo o span não-rotacionado da caixaria. Com ``set_trazomob`` (que
    copiava) esses campos ficavam só na variável local e nunca chegavam ao
    documento.
    """
    ext = _ensure_ext(group)
    if ext is None:
        return {}
    tm = ext.get("trazomob")
    if not isinstance(tm, dict):
        return set_module_data(group, data)
    tm.update(dict(data or {}))
    ext["trazomob_module"] = tm
    return tm


def set_esquadria_data(group: Any, data: Optional[Dict[str, Any]] = None,
                       **kwargs: Any) -> Dict[str, Any]:
    """Grava metadados de esquadria nas três chaves, com os apelidos certos.

    ``trazomob`` fica com o ``kind`` e os nomes ``*_mm``; ``trazomob_esquadria``
    mantém o formato histórico; ``trazomob_module`` recebe os apelidos
    ``largura``/``altura``/``profundidade`` que os leitores antigos esperam.
    """
    ext = _ensure_ext(group)
    payload = dict(data or {})
    payload.update(kwargs)
    payload["kind"] = KIND_ESQUADRIA
    if ext is None:
        return payload
    oficial = dict(payload)
    espelho_esquadria = {k: v for k, v in payload.items() if k != "kind"}
    espelho_module = _with_aliases(payload, _ESQUADRIA_TO_MODULE)
    espelho_module.pop("kind", None)
    ext["trazomob"] = oficial
    ext["trazomob_esquadria"] = espelho_esquadria
    ext["trazomob_module"] = espelho_module
    return oficial


def update_esquadria_data(group: Any,
                          data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Atualiza metadados de esquadria mantendo as três chaves coerentes.

    Parte do que já está gravado e reescreve tudo por ``set_esquadria_data``:
    um campo alterado num só espelho nunca fica divergente dos outros.
    """
    dados = esquadria_params(group)
    dados.update(dict(data or {}))
    return set_esquadria_data(group, dados)

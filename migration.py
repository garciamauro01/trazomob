# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Módulo de Compatibilidade Retroativa e Auto-Migração para o TrazoMob.

Garante que qualquer arquivo ou modelo construído em versões anteriores do plugin:
1. Tenha todos os metadados dinâmicos necessários restaurados e atualizados;
2. Calcule automaticamente dimensões físicas (L, A, P) a partir da malha geométrica caso ausentes;
3. Atualize o esquema de versão interna (schema_version = 2);
4. Assegure que as portas, frentes e caixarias funcionem com snap magnético, cotas e alinhamento de paredes;
5. Detecte módulos antigos ao abrir documentos ou ao carregar a cena, sem alterar ou corromper geometrias do usuário.
"""
from __future__ import annotations

import math
from typing import Any, Optional

from PySide6.QtGui import QVector3D
from core.group import Group, iter_placements
from .catalog import MODULE_CATALOG


CURRENT_SCHEMA_VERSION = 2

# Valores padrão seguros para garantir integridade caso faltem no arquivo antigo
DEFAULT_MODULE_PARAMS: dict[str, Any] = {
    "espessura": 15.0,
    "material": "MDF Branco TX 15mm",
    "material_frentes": "MDF Louro Freijó 15mm",
    "espessura_frentes": 15.0,
    "tem_fundo": True,
    "tipo_fundo": "rasgo",
    "esp_fundo": 6.0,
    "recuo_fundo": 10.0,
    "prof_rasgo": 7.0,
    "folga_fundo": 2.0,
    "puxador_tipo": "perfil",
    "puxador_cor": "anodizado_fosco",
    "puxador_pos": "superior",
    "desconto_perfil": 35.0,
    "perfil_modelo": "gola",
    "fita_caixa_modo": "frontal_1L",
    "gerar_furacao": True,
    "dispositivo_fixacao": "minifix_cavilha",
    "rot_z": 0.0,
}


def compute_geometry_bounds(group: Group) -> tuple[float, float, float, float, float, float] | None:
    """Calcula os limites em metros (min_x, max_x, min_y, max_y, min_z, max_z) da geometria real."""
    min_x, max_x = float("inf"), float("-inf")
    min_y, max_y = float("inf"), float("-inf")
    min_z, max_z = float("inf"), float("-inf")
    found = False

    for pg, xf in iter_placements(group):
        mesh = getattr(pg, "mesh", None)
        if mesh is not None and getattr(mesh, "vertices", None):
            for v in mesh.vertices:
                p = getattr(v, "position", v)
                if xf is not None:
                    p = xf.map(p)
                min_x = min(min_x, p.x())
                max_x = max(max_x, p.x())
                min_y = min(min_y, p.y())
                max_y = max(max_y, p.y())
                min_z = min(min_z, p.z())
                max_z = max(max_z, p.z())
                found = True

    if not found:
        return None
    return (min_x, max_x, min_y, max_y, min_z, max_z)


def deduce_module_type_from_name(name: str) -> str:
    """Infere o tipo do módulo a partir do nome caso a chave 'tipo' esteja ausente."""
    n = (name or "").lower()
    if "gavet" in n:
        return "gaveteiro"
    if "torre" in n or "forno" in n:
        return "torre_quente"
    if "aereo" in n or "aéreo" in n or "basculante" in n:
        return "aereo"
    if "armario" in n or "armário" in n or "roupeiro" in n:
        return "armario_2p_prat"
    if "banheiro" in n or "gabinete" in n:
        return "gabinete_banheiro"
    if "nicho" in n:
        return "nicho"
    if "ilha" in n:
        return "bancada_ilha"
    if "bancada" in n or "pedra" in n or "tampo" in n:
        return "bancada_reta"
    return "balcao"


def migrate_legacy_group(group: Group) -> bool:
    """Verifica e migra um grupo (módulo mestre, peça de marcenaria ou parede) para o schema do TrazoMob.
    
    Converte:
    - ext["corte_cloud_module"] ➔ ext["trazomob_module"]
    - ext["corte_cloud_wall"] ➔ ext["trazomob_wall"]
    - ext["corte_cloud"] ➔ ext["trazomob"] (em peças filhas e avulsas)
    - ext["hellomob"] ➔ ext["trazomob"]
    - Normaliza campos ausentes ou incompletos.
    
    Retorna True se o grupo sofreu alguma atualização/migração.
    """
    if not isinstance(group, Group):
        return False

    ext = getattr(group, "ext", None)
    if ext is None or not isinstance(ext, dict):
        return False

    migrated = False

    # ── 1. MIGRAÇÃO DE CHAVES LEGADAS NO PRÓPRIO GRUPO ──
    if "corte_cloud_module" in ext:
        if "trazomob_module" not in ext:
            ext["trazomob_module"] = ext["corte_cloud_module"]
        # Mantém compatibilidade mas dá preferência a trazomob_module
        del ext["corte_cloud_module"]
        migrated = True

    if "hellomob_module" in ext:
        if "trazomob_module" not in ext:
            ext["trazomob_module"] = ext["hellomob_module"]
        del ext["hellomob_module"]
        migrated = True

    if "corte_cloud_wall" in ext:
        if "trazomob_wall" not in ext:
            ext["trazomob_wall"] = ext["corte_cloud_wall"]
        del ext["corte_cloud_wall"]
        migrated = True

    if "corte_cloud" in ext:
        if "trazomob" not in ext:
            ext["trazomob"] = ext["corte_cloud"]
        del ext["corte_cloud"]
        migrated = True

    if "hellomob" in ext:
        if "trazomob" not in ext:
            ext["trazomob"] = ext["hellomob"]
        del ext["hellomob"]
        migrated = True

    # ── 2. MIGRAÇÃO RECURSIVA NAS PEÇAS FILHAS ──
    for child in getattr(group, "children", []) or []:
        if isinstance(child, Group) and hasattr(child, "ext") and isinstance(child.ext, dict):
            c_ext = child.ext
            if "corte_cloud" in c_ext:
                if "trazomob" not in c_ext:
                    c_ext["trazomob"] = c_ext["corte_cloud"]
                del c_ext["corte_cloud"]
                migrated = True
            if "hellomob" in c_ext:
                if "trazomob" not in c_ext:
                    c_ext["trazomob"] = c_ext["hellomob"]
                del c_ext["hellomob"]
                migrated = True
            if "corte_cloud_module" in c_ext:
                if "trazomob_module" not in c_ext:
                    c_ext["trazomob_module"] = c_ext["corte_cloud_module"]
                del c_ext["corte_cloud_module"]
                migrated = True

    # ── 3. MIGRAÇÃO DETALHADA SE FOR UM MÓDULO MESTRE ──
    cc_data = ext.get("trazomob_module")
    if cc_data is not None and isinstance(cc_data, dict):
        schema_v = int(cc_data.get("schema_version", 1))

        # Recupera ou deduz tipo
        tipo = cc_data.get("tipo")
        if not tipo:
            tipo = deduce_module_type_from_name(getattr(group, "name", ""))
            cc_data["tipo"] = tipo
            migrated = True

        # Normaliza campo rot_z consistente
        if "rotacao" in cc_data and "rot_z" not in cc_data:
            cc_data["rot_z"] = float(cc_data["rotacao"]) % 360.0
            migrated = True

        # Garante dimensões (largura, altura, profundidade) a partir da malha física se ausentes ou zeradas
        b = compute_geometry_bounds(group)
        if b is not None:
            geom_w_mm = round((b[1] - b[0]) * 1000.0)
            geom_d_mm = round((b[3] - b[2]) * 1000.0)
            geom_h_mm = round((b[5] - b[4]) * 1000.0)

            rot_z = float(cc_data.get("rot_z", 0.0)) % 360.0
            if abs(rot_z - 90.0) < 1.0 or abs(rot_z - 270.0) < 1.0:
                real_l_mm = geom_d_mm
                real_p_mm = geom_w_mm
            else:
                real_l_mm = geom_w_mm
                real_p_mm = geom_d_mm

            if not cc_data.get("largura") or float(cc_data.get("largura", 0)) <= 0:
                cc_data["largura"] = real_l_mm
                migrated = True
            if not cc_data.get("profundidade") or float(cc_data.get("profundidade", 0)) <= 0:
                cc_data["profundidade"] = real_p_mm
                migrated = True
            if not cc_data.get("altura") or float(cc_data.get("altura", 0)) <= 0:
                cc_data["altura"] = geom_h_mm
                migrated = True

        # Preenche chaves padrão faltantes (compatibilidade com UI e Builder)
        for k, v in DEFAULT_MODULE_PARAMS.items():
            if k not in cc_data:
                cc_data[k] = v
                migrated = True

        # Salva versão do schema atualizada
        if schema_v < CURRENT_SCHEMA_VERSION:
            cc_data["schema_version"] = CURRENT_SCHEMA_VERSION
            migrated = True

    return migrated


# Alias de compatibilidade
migrate_legacy_module = migrate_legacy_group


def migrate_scene_trazomob_entities(scene, viewport=None) -> int:
    """Varre todos os grupos da cena e aplica a migração em módulos e paredes legados.
    
    Retorna o número de grupos atualizados.
    """
    if scene is None:
        return 0

    count = 0
    groups = list(getattr(scene, "groups", []))
    for g in groups:
        if migrate_legacy_group(g):
            count += 1

    if count > 0 and viewport is not None:
        if hasattr(viewport, "flash_status"):
            viewport.flash_status(f"✨ {count} entidade(s) legada(s) migrada(s) para o TrazoMob com sucesso.")
        if hasattr(viewport, "notify_scene_changed"):
            viewport.notify_scene_changed()

    return count

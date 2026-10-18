# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Gerenciador centralizado de preferências persistentes do usuário para TrazoMob.

Armazena em arquivo JSON em %LOCALAPPDATA%/IngeTrazo (Windows) ou ~/.config/ingetrazo (Linux/macOS):
1. Padrões globais de marcenaria (espessuras, materiais, fita, puxadores, fixação);
2. Dimensões padrão por tipo ou categoria de módulo (balcões, gaveteiros, aéreos, roupeiros, etc.);
3. Configurações de réguas e linhas-guia de parede (presets ativos, visibilidade, cotas).
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

from core.paths import user_log_dir


PREFERENCES_FILENAME = "trazomob_preferences.json"


def get_preferences_file_path() -> Path:
    """Retorna o caminho absoluto do arquivo de preferências do usuário."""
    # user_log_dir() retorna a pasta base de dados do usuário (ex: %LOCALAPPDATA%/IngeTrazo)
    base_dir = user_log_dir()
    return base_dir / PREFERENCES_FILENAME


DEFAULT_PREFERENCES: Dict[str, Any] = {
    # ── 1. Padrões Globais de Marcenaria ──
    "global": {
        "espessura_caixa_mm": 15.0,
        "espessura_frentes_mm": 15.0,
        "material_caixa": "MDF Branco TX",
        "material_frentes": "MDF Louro Freijó",
        "material_fita_caixa": None,
        "fita_caixa_modo": "frontal_1L",
        "puxador_tipo": "perfil",
        "puxador_cor": "anodizado_fosco",
        "puxador_pos": "superior",
        "perfil_modelo": "gola",
        "desconto_perfil_mm": 35.0,
        "tem_fundo": True,
        "tipo_fundo": "rasgo",
        "esp_fundo_mm": 6.0,
        "recuo_fundo_mm": 10.0,
        "prof_rasgo_mm": 7.0,
        "folga_fundo_mm": 2.0,
        "gerar_furacao": True,
        "dispositivo_fixacao": "minifix_cavilha",
    },
    # ── 2. Dimensões Padrão por Categoria ou Tipo ──
    # Se uma chave de tipo (ex: 'balcao', 'aereo') ou categoria (ex: 'inferior') estiver aqui,
    # novos módulos inseridos usam estas dimensões no lugar do catálogo cru.
    "module_defaults": {
        "inferior": {
            "altura": 720.0,
            "profundidade": 550.0,
            "rodape": 0.0,
        },
        "aereo": {
            "altura": 720.0,
            "profundidade": 350.0,
        },
        "alto": {
            "altura": 2200.0,
            "profundidade": 550.0,
        },
        "bancada": {
            "esp_pedra": 20.0,
            "altura_saia": 40.0,
            "altura_frontao": 100.0,
        },
    },
    # ── 3. Réguas e Linhas-guia de Parede ──
    "wall_guides": {
        "active_preset": "Cozinha",
        "visible": True,
        "show_labels": False,
        "snap_enabled": True,
        "custom_presets": {},
    },
}


class TrazoMobPreferencesManager:
    """Gerenciador singleton para leitura e escrita segura de preferências do usuário."""

    _instance: Optional[TrazoMobPreferencesManager] = None

    def __init__(self) -> None:
        self.filepath = get_preferences_file_path()
        self._data: Dict[str, Any] = {}
        self.load()

    @classmethod
    def get_instance(cls) -> TrazoMobPreferencesManager:
        if cls._instance is None:
            cls._instance = TrazoMobPreferencesManager()
        return cls._instance

    def load(self) -> None:
        """Carrega as preferências do disco com fallback para os valores padrão."""
        import copy
        self._data = copy.deepcopy(DEFAULT_PREFERENCES)

        # Se o novo arquivo ainda não existe, tenta carregar o arquivo antigo corte_cloud_preferences.json
        if not self.filepath.exists():
            legacy_path = self.filepath.parent / "corte_cloud_preferences.json"
            if legacy_path.exists():
                try:
                    with open(legacy_path, "r", encoding="utf-8") as lf:
                        legacy_data = json.load(lf)
                    if isinstance(legacy_data, dict):
                        for section, values in legacy_data.items():
                            if isinstance(values, dict) and isinstance(self._data.get(section), dict):
                                self._data[section].update(values)
                        # Salva imediatamente no novo nome
                        self.save()
                        print(f"[TrazoMobPreferences] Preferências migradas com sucesso de {legacy_path.name} para {self.filepath.name}")
                except Exception as e:
                    print(f"[TrazoMobPreferences] Aviso ao migrar preferências legadas: {e}")

        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        # Merge recursivo de dicionários
                        for section, values in saved.items():
                            if isinstance(values, dict) and isinstance(self._data.get(section), dict):
                                self._data[section].update(values)
                            else:
                                self._data[section] = values
            except Exception as e:
                # Se corrompido, mantém os defaults
                print(f"[TrazoMobPreferences] Aviso ao carregar preferências: {e}")

    def save(self) -> bool:
        """Grava as preferências atuais no disco."""
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"[TrazoMobPreferences] Erro ao salvar preferências: {e}")
            return False

    def get_section(self, section: str) -> Dict[str, Any]:
        return self._data.setdefault(section, {})

    def get_global(self, key: str, default: Any = None) -> Any:
        return self._data.get("global", {}).get(key, default)

    def set_global(self, key: str, value: Any) -> None:
        self._data.setdefault("global", {})[key] = value

    def get_module_default(self, mod_id_or_cat: str, param: str, default: Any = None) -> Any:
        m_defs = self._data.get("module_defaults", {})
        if mod_id_or_cat in m_defs and param in m_defs[mod_id_or_cat]:
            return m_defs[mod_id_or_cat][param]
        return default

    def set_module_defaults(self, mod_id_or_cat: str, params: Dict[str, Any]) -> None:
        m_defs = self._data.setdefault("module_defaults", {})
        target = m_defs.setdefault(mod_id_or_cat, {})
        target.update(params)

    def get_wall_guides_config(self) -> Dict[str, Any]:
        return self._data.setdefault("wall_guides", {})

    def save_wall_guides_config(self, active_preset: str, visible: bool, show_labels: bool, snap_enabled: bool, custom_presets: Optional[Dict] = None) -> None:
        wg = self.get_wall_guides_config()
        wg["active_preset"] = active_preset
        wg["visible"] = bool(visible)
        wg["show_labels"] = bool(show_labels)
        wg["snap_enabled"] = bool(snap_enabled)
        if custom_presets is not None:
            wg["custom_presets"] = custom_presets
        self.save()

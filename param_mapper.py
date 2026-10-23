# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez, IngeTrazo contributors and Pair Programmer.
"""Mapeador e coletor unificado de parâmetros para módulos TrazoMob.

Evita a duplicação de regras de extração e conversão de valores entre
o Dialog (inserção/edição modal) e o Sidebar (painel lateral de edição ao vivo).
"""
from __future__ import annotations

from typing import Any, Dict, Optional
from . import perfis as perfis_lib


def extract_ui_module_params(form_owner: Any, base_params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Coleta e converte os valores dos widgets de formulário em um dicionário de parâmetros do módulo.
    
    Compatível tanto com TrazoMobDialog quanto com TrazoMobSidebar.
    """
    params = dict(base_params or {})

    # Dimensões e Caixa
    if hasattr(form_owner, "sp_largura"):
        params["largura"] = float(form_owner.sp_largura.value())
    if hasattr(form_owner, "sp_altura"):
        params["altura"] = float(form_owner.sp_altura.value())
    if hasattr(form_owner, "sp_prof"):
        params["profundidade"] = float(form_owner.sp_prof.value())
    if hasattr(form_owner, "sp_rodape"):
        params["rodape"] = float(form_owner.sp_rodape.value())
    if hasattr(form_owner, "sp_prateleiras"):
        params["num_prateleiras"] = int(form_owner.sp_prateleiras.value())
    if hasattr(form_owner, "sp_divisoes"):
        params["num_divisoes"] = int(form_owner.sp_divisoes.value())

    esp_mm = 15.0
    if hasattr(form_owner, "cb_espessura"):
        try:
            esp_mm = float(form_owner.cb_espessura.currentText().split()[0])
            params["espessura"] = esp_mm
        except (ValueError, IndexError):
            pass

    if hasattr(form_owner, "cb_material"):
        mat_base = form_owner.cb_material.currentText()
        params["material"] = f"{mat_base} {int(esp_mm)}mm"

    # Frentes (Portas e Gavetas)
    if hasattr(form_owner, "cb_material_frentes") and hasattr(form_owner, "cb_espessura_frentes"):
        mat_frente_txt = form_owner.cb_material_frentes.currentText()
        esp_frente_txt = form_owner.cb_espessura_frentes.currentText()
        esp_frentes_mm = esp_mm if esp_frente_txt.startswith("(") else float(esp_frente_txt.split()[0])
        params["espessura_frentes"] = esp_frentes_mm

        if mat_frente_txt.startswith("("):
            mat_base = form_owner.cb_material.currentText() if hasattr(form_owner, "cb_material") else "Branco TX"
            params["material_frentes"] = f"{mat_base} {int(esp_frentes_mm)}mm"
        else:
            params["material_frentes"] = f"{mat_frente_txt} {int(esp_frentes_mm)}mm"

    # Fundo do móvel (TrazoMob)
    if hasattr(form_owner, "cb_tipo_fundo"):
        idx_tf = form_owner.cb_tipo_fundo.currentIndex()
        tipo_fundo = "rasgo" if idx_tf == 0 else ("sobreposto" if idx_tf == 1 else "sem_fundo")
        params["tipo_fundo"] = tipo_fundo
        params["tem_fundo"] = (tipo_fundo != "sem_fundo")

    if hasattr(form_owner, "cb_esp_fundo"):
        try:
            params["esp_fundo"] = float(form_owner.cb_esp_fundo.currentText().split()[0])
        except (ValueError, IndexError):
            pass

    if hasattr(form_owner, "sp_recuo_fundo"):
        params["recuo_fundo"] = float(form_owner.sp_recuo_fundo.value())
    if hasattr(form_owner, "sp_prof_rasgo"):
        params["prof_rasgo"] = float(form_owner.sp_prof_rasgo.value())
    if hasattr(form_owner, "sp_folga_fundo"):
        params["folga_fundo"] = float(form_owner.sp_folga_fundo.value())

    # Puxadores
    pux_tipos = ["alca", "perfil", "cava", "ponto", "sem_puxador"]
    if hasattr(form_owner, "cb_puxador_tipo"):
        idx = form_owner.cb_puxador_tipo.currentIndex()
        params["puxador_tipo"] = pux_tipos[idx] if idx < len(pux_tipos) else "alca"

    pux_cores = ["preto", "aluminio", "dourado", "cobre", "branco"]
    if hasattr(form_owner, "cb_puxador_cor"):
        idx = form_owner.cb_puxador_cor.currentIndex()
        params["puxador_cor"] = pux_cores[idx] if idx < len(pux_cores) else "preto"

    pux_posicoes = ["padrao", "topo", "extensao", "base", "centro"]
    if hasattr(form_owner, "cb_puxador_pos"):
        idx = form_owner.cb_puxador_pos.currentIndex()
        params["puxador_pos"] = pux_posicoes[idx] if idx < len(pux_posicoes) else "padrao"

    # Perfis
    perfil_modelo = "gola"
    if hasattr(form_owner, "cb_perfil_modelo"):
        perfil_modelo = form_owner.cb_perfil_modelo.currentData() or "gola"
    params["perfil_modelo"] = perfil_modelo

    val_desc = 35.0
    if hasattr(form_owner, "cb_altura_perfil"):
        txt_alt = form_owner.cb_altura_perfil.currentText()
        if "padrão" in txt_alt.lower():
            val_desc = float(perfis_lib.get_profile(perfil_modelo).get("desconto_mm", 35.0))
        else:
            try:
                val_desc = float(txt_alt.split()[0])
            except (ValueError, IndexError):
                if hasattr(form_owner, "sp_desconto_perfil"):
                    val_desc = float(form_owner.sp_desconto_perfil.value())
    elif hasattr(form_owner, "sp_desconto_perfil"):
        val_desc = float(form_owner.sp_desconto_perfil.value())
    params["desconto_perfil"] = val_desc

    # Fitas de Borda e Usinagens
    if hasattr(form_owner, "cb_fita_caixa"):
        fitas = ["frontal_1L", "2L", "4L", "sem_fita"]
        idx = form_owner.cb_fita_caixa.currentIndex()
        params["fita_caixa_modo"] = fitas[idx] if idx < len(fitas) else "frontal_1L"

    if hasattr(form_owner, "cb_material_fita_caixa"):
        txt_fita = form_owner.cb_material_fita_caixa.currentText()
        params["material_fita_caixa"] = None if txt_fita.startswith("(") else txt_fita

    if hasattr(form_owner, "chk_gerar_furacao"):
        params["gerar_furacao"] = bool(form_owner.chk_gerar_furacao.isChecked())

    if hasattr(form_owner, "cb_dispositivo_fixacao"):
        disps = ["minifix_cavilha", "cavilha_soberba", "soberba", "cavilha"]
        idx = form_owner.cb_dispositivo_fixacao.currentIndex()
        params["dispositivo_fixacao"] = disps[idx] if idx < len(disps) else "minifix_cavilha"

    return params


def populate_ui_from_module(form_owner: Any, params: Dict[str, Any]) -> None:
    """Preenche os widgets de formulário a partir de um dicionário de parâmetros do módulo.
    
    Unifica a sincronização bidirecional entre TrazoMobDialog e TrazoMobSidebarPanel.
    """
    tipo = params.get("tipo", "balcao")

    # Dimensões e Rodapé
    if hasattr(form_owner, "sp_largura") and "largura" in params:
        form_owner.sp_largura.setValue(int(round(float(params["largura"]))))
    if hasattr(form_owner, "sp_altura") and "altura" in params:
        form_owner.sp_altura.setValue(int(round(float(params["altura"]))))
    if hasattr(form_owner, "sp_prof") and "profundidade" in params:
        form_owner.sp_prof.setValue(int(round(float(params["profundidade"]))))
    if hasattr(form_owner, "sp_rodape") and "rodape" in params:
        form_owner.sp_rodape.setValue(int(round(float(params["rodape"]))))

    # Espessura da Caixa
    esp = int(round(float(params.get("espessura", 15))))
    if hasattr(form_owner, "cb_espessura"):
        idx_esp = form_owner.cb_espessura.findText(f"{esp} mm")
        if idx_esp < 0:
            idx_esp = 0 if esp == 15 else (1 if esp == 18 else 2)
        form_owner.cb_espessura.setCurrentIndex(idx_esp)

    # Material Caixa (Adapta lista: MDF para marcenaria, Pedras para bancadas)
    mat_caixa = params.get("material", "MDF Branco TX")
    tipo_mod = str(params.get("tipo", "balcao")).lower()
    is_bancada = ("bancada" in tipo_mod or "ilha" in tipo_mod)

    if hasattr(form_owner, "cb_material"):
        from .materials_catalog import MDF_MATERIALS, STONE_MATERIALS
        target_list = STONE_MATERIALS if is_bancada else MDF_MATERIALS

        # Atualiza a lista de opções do combo se for diferente
        curr_items = [form_owner.cb_material.itemText(k) for k in range(form_owner.cb_material.count())]
        if curr_items != target_list:
            form_owner.cb_material.blockSignals(True)
            form_owner.cb_material.clear()
            form_owner.cb_material.addItems(target_list)
            form_owner.cb_material.blockSignals(False)

        matched = False
        for i in range(form_owner.cb_material.count()):
            if form_owner.cb_material.itemText(i).lower() in mat_caixa.lower():
                form_owner.cb_material.setCurrentIndex(i)
                matched = True
                break
        if not matched and form_owner.cb_material.count() > 0:
            form_owner.cb_material.setCurrentIndex(0)

    # Fita de Borda da Caixa
    if hasattr(form_owner, "cb_fita_caixa"):
        modo_fcx = params.get("fita_caixa_modo", "frontal_1L")
        fita_map_cx = {"frontal_1l": 0, "2l": 1, "4l": 2, "sem_fita": 3}
        form_owner.cb_fita_caixa.setCurrentIndex(fita_map_cx.get(str(modo_fcx).lower(), 0))

    if hasattr(form_owner, "cb_material_fita_caixa"):
        mat_fcx = params.get("material_fita_caixa")
        if mat_fcx:
            idx_fcx = 0
            for i in range(form_owner.cb_material_fita_caixa.count()):
                txt_i = form_owner.cb_material_fita_caixa.itemText(i)
                if txt_i in mat_fcx and not txt_i.startswith("("):
                    idx_fcx = i
                    break
            form_owner.cb_material_fita_caixa.setCurrentIndex(idx_fcx)
        else:
            form_owner.cb_material_fita_caixa.setCurrentIndex(0)

    # Frentes: Material e Espessura
    mat_frente = params.get("material_frentes")
    if hasattr(form_owner, "cb_material_frentes"):
        if mat_frente and mat_frente != mat_caixa:
            for i in range(form_owner.cb_material_frentes.count()):
                txt = form_owner.cb_material_frentes.itemText(i)
                if txt in mat_frente and not txt.startswith("("):
                    form_owner.cb_material_frentes.setCurrentIndex(i)
                    break
        else:
            form_owner.cb_material_frentes.setCurrentIndex(0)

    esp_frente = params.get("espessura_frentes")
    if hasattr(form_owner, "cb_espessura_frentes"):
        if esp_frente and esp_frente != esp:
            esp_f_str = f"{int(round(float(esp_frente)))} mm"
            f_idx = form_owner.cb_espessura_frentes.findText(esp_f_str)
            if f_idx >= 0:
                form_owner.cb_espessura_frentes.setCurrentIndex(f_idx)
        else:
            form_owner.cb_espessura_frentes.setCurrentIndex(0)

    # Quantidade de Portas / Gavetas / Prateleiras / Divisórias
    if hasattr(form_owner, "sp_qtd_elem"):
        if "num_gavetas" in params:
            form_owner.sp_qtd_elem.setValue(int(params["num_gavetas"]))
        elif "num_portas" in params:
            form_owner.sp_qtd_elem.setValue(int(params["num_portas"]))
    if hasattr(form_owner, "sp_prateleiras") and "num_prateleiras" in params:
        form_owner.sp_prateleiras.setValue(int(params["num_prateleiras"]))
    if hasattr(form_owner, "sp_divisoes") and "num_divisoes" in params:
        form_owner.sp_divisoes.setValue(int(params["num_divisoes"]))

    # Fundo do Móvel (TrazoMob)
    if hasattr(form_owner, "cb_tipo_fundo"):
        tipo_f = params.get("tipo_fundo")
        if not tipo_f:
            tipo_f = "rasgo" if params.get("tem_fundo", True) else "sem_fundo"
        if tipo_f == "rasgo":
            form_owner.cb_tipo_fundo.setCurrentIndex(0)
        elif tipo_f == "sobreposto":
            form_owner.cb_tipo_fundo.setCurrentIndex(1)
        else:
            form_owner.cb_tipo_fundo.setCurrentIndex(2)

    if hasattr(form_owner, "cb_esp_fundo"):
        esp_f = int(round(float(params.get("esp_fundo", 6.0))))
        idx_esp_f = form_owner.cb_esp_fundo.findText(f"{esp_f} mm")
        form_owner.cb_esp_fundo.setCurrentIndex(idx_esp_f if idx_esp_f >= 0 else 0)

    if hasattr(form_owner, "sp_recuo_fundo"):
        form_owner.sp_recuo_fundo.setValue(int(round(float(params.get("recuo_fundo", 15.0)))))
    if hasattr(form_owner, "sp_prof_rasgo"):
        form_owner.sp_prof_rasgo.setValue(int(round(float(params.get("prof_rasgo", 7.0)))))
    if hasattr(form_owner, "sp_folga_fundo"):
        form_owner.sp_folga_fundo.setValue(int(round(float(params.get("folga_fundo", 2.0)))))

    if hasattr(form_owner, "chk_fundo") and "tem_fundo" in params:
        form_owner.chk_fundo.setChecked(bool(params["tem_fundo"]))

    if hasattr(form_owner, "chk_gerar_furacao") and "gerar_furacao" in params:
        form_owner.chk_gerar_furacao.setChecked(bool(params["gerar_furacao"]))

    if hasattr(form_owner, "cb_dispositivo_fixacao"):
        disp = str(params.get("dispositivo_fixacao", "minifix_cavilha")).lower()
        disp_map = {"minifix_cavilha": 0, "cavilha_soberba": 1, "soberba": 2, "cavilha": 3}
        form_owner.cb_dispositivo_fixacao.setCurrentIndex(disp_map.get(disp, 0))

    # Puxadores
    pux_tipo = params.get("puxador_tipo", "alca")
    pux_map = {"alca": 0, "perfil": 1, "cava": 2, "ponto": 3, "sem_puxador": 4, "toque": 4, "nenhum": 4}
    if hasattr(form_owner, "cb_puxador_tipo"):
        form_owner.cb_puxador_tipo.setCurrentIndex(pux_map.get(pux_tipo, 0))

    pux_cor = params.get("puxador_cor", "preto")
    cor_map = {"preto": 0, "aluminio": 1, "inox": 1, "dourado": 2, "champanhe": 2, "cobre": 3, "rose": 3, "branco": 4}
    if hasattr(form_owner, "cb_puxador_cor"):
        form_owner.cb_puxador_cor.setCurrentIndex(cor_map.get(pux_cor, 0))

    pux_pos = params.get("puxador_pos", "padrao")
    pos_map = {"padrao": 0, "auto": 0, "topo": 1, "extensao": 2, "lateral": 2, "base": 3, "centro": 4}
    if hasattr(form_owner, "cb_puxador_pos"):
        form_owner.cb_puxador_pos.setCurrentIndex(pos_map.get(pux_pos, 0))

    # Perfil e Desconto
    desc_perfil = float(params.get("desconto_perfil", 35.0))
    if hasattr(form_owner, "sp_desconto_perfil"):
        form_owner.sp_desconto_perfil.setValue(int(round(desc_perfil)))
    if hasattr(form_owner, "cb_altura_perfil"):
        txt_find = f"{int(round(desc_perfil))} MM"
        idx_f = form_owner.cb_altura_perfil.findText(txt_find)
        form_owner.cb_altura_perfil.setCurrentIndex(idx_f if idx_f >= 0 else 0)

    perfil_mod = params.get("perfil_modelo", "gola")
    if hasattr(form_owner, "cb_perfil_modelo"):
        idx_mod = form_owner.cb_perfil_modelo.findData(perfil_mod)
        if idx_mod >= 0:
            form_owner.cb_perfil_modelo.setCurrentIndex(idx_mod)
        elif hasattr(form_owner, "_refresh_perfil_modelos"):
            form_owner._refresh_perfil_modelos(select_id=perfil_mod)


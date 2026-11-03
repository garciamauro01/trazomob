# Análise Comparativa — TrazoMob × Promob e softwares de categoria (v4)

**Projeto:** IngeTrazo — plugin `trazomob`
**Data:** 02/11/2026 (v4 — atualiza v3 de 02/11/2026)
**Escopo:** auditoria do plugin `trazomob` apenas (não do app IngeTrazo).
**Método:** leitura do código (66 arquivos `.py`, 19 arquivos de teste, 131 testes), inventário do catálogo e dos builders, execução da suíte, verificação de CI, persistência e metadados; dados de mercado coletados em out/2026.

---

## 0. O que mudou da v3 para a v4 (implementado na Onda 3 — Ciclo Comercial)

| Item | v3 (02/11) | v4 (02/11) — **ENTREGUE** |
|---|---|---|
| **Preços de insumos** | ❌ não existia | ✅ seção `"pricing"` em `preferences.py`: chapas por m², fita por metro, ferragens unitárias, mão de obra por m², markup, impostos, desconto, frete e dados da empresa |
| **Motor de orçamento** | ❌ não existia | ✅ `pricing.py` — `calcular_orcamento_cutlist()`, `calcular_orcamento_por_ambiente()`, `ResumoOrcamento`, `ItemCusto`, `formatar_moeda`, `gerar_proposta_dados` |
| **Proposta comercial** | ❌ não existia | ✅ `production_report.generate_proposal_html()` (imprimível como PDF) + `generate_proposal_pdf()` opcional via `weasyprint` com fallback para HTML |
| **Relatório com orçamento** | 🟡 HTML sem preço | ✅ `generate_project_html_report(..., include_pricing=True)` — seção de itens, resumo financeiro e orçamento por ambiente |
| **UI do ciclo comercial** | ❌ nenhum botão | ✅ `dialog_cutlist_tab.py` — botão **"📋 Proposta Comercial (PDF/HTML)"**, diálogo de dados do cliente, opção de incluir orçamento no relatório |
| Testes novos | 118 | **131** (13 novos: `test_pricing.py`) |
| Suíte verde | 118 passed | **131 passed** |

**Estado da Onda 3 (frente comercial):** **CONCLUÍDA** — o plugin deixou de terminar na fábrica e passou a fechar venda com orçamento e proposta. A Onda 3 de *produção* (Code 128 real, DXF/CAM, prancha PDF) permanece no backlog.

---

## 0.1 O que a Onda 2 entregou (v3 — mantido)

| Item | v2 (01/11) | v3 (02/11) — **ENTREGUE** |
|---|---|---|
| **Espelhar módulo paramétrico** | ❌ não existe | ✅ `mirror.py` + `builder.py` + `sidebar.py` — parâmetro `mirror_x` no `ext`, reconstrói com fita/usinagens/lados corretos, persiste em undo/redo |
| **Agrupar / desagrupar módulos** | ❌ não existe | ✅ `assembly.py` + `sidebar.py` — `MakeNestedGroupCommand`/`ExplodeGroupCommand` do core, marca `kind="assembly"`, cutlist vê módulos agrupados |
| **Ambientes / Pavimentos** | ❌ um grupo "Ambiente Paredes" | ✅ `ambiente.py` + `schema.py` + `wall_plan_2d.py` — entidade `KIND_AMBIENTE`/`KIND_PAVIMENTO` com nome, piso, teto, área, pé-direito, lista de módulos; `extract_parts(ambiente=...)` filtra cutlist; `WallPlan2D.build_ambiente_group()` integra planta 2D |
| Testes novos | 92 | **118** (26 novos: `test_mirror_and_assembly.py` 17, `test_ambiente_integration.py` 9) |
| Suíte verde | 92 passed | **118 passed** |

**Estado da Onda 2:** **CONCLUÍDA** — as três frentes de maior alavancagem (espelhar + agrupar + ambientes) estão implementadas e testadas.

---

## 1. Resumo executivo

O TrazoMob atingiu **paridade percebida** nos pilares de organização de projeto (Onda 2) e passou a cobrir o **ciclo comercial** (Onda 3):
- ✅ Espelhar paramétrico (reconstrução, não malha espelhada)
- ✅ Agrupar/desagrupar com undo/redo nativo
- ✅ Ambientes/pavimentos com cutlist filtrado por ambiente
- ✅ Preços, markup, impostos, desconto, frete e orçamento por ambiente
- ✅ Proposta comercial HTML imprimível (PDF via navegador ou `weasyprint`)

O que ainda separa o plugin do Promob agora é **interoperabilidade de produção** e **apresentação PDF nativa**:
1. **Produção** — o código de barras das etiquetas continua decorativo (MD5) e não há DXF/CNC.
2. **PDF nativo** — a proposta é HTML imprimível; PDF direto depende de `weasyprint` opcional.
3. **Apresentação ao cliente** — render bonito, mas sem prancha PDF unindo planta, elevações, vistas e lista de peças.

---

## 2. O que a Onda 1 entregou (mantido)

| Entrega | Evidência |
|---|---|
| Persistência de `_unrot_carcass_span`, `rot_z`, `rot_matrix_3d` | gravação via `schema.update_module_data` (dict vivo) |
| Fonte única de metadados | `schema.py`: `kind_of`, `params_of`, `module_params`, `esquadria_params`, `set_*`, `update_*` |
| Testes de metadados | `tests/test_metadata_schema.py` |
| CI protegendo o plugin | `.github/workflows/ci.yml` roda `plugins/trazomob/tests` |
| Undo das luzes | comandos compostos com `SetPluginDataCommand` |
| Erros visíveis | 0 ocorrências de `except Exception:` + `pass`; `logging` em 16 arquivos |

---

## 3. O que a Onda 2 entregou (NOVO — 02/11/2026)

| Entrega | Arquivos | Evidência |
|---|---|---|
| **Espelhar paramétrico** | `mirror.py`, `builder.py:1114`, `sidebar.py:btn_mirror` | `MIRROR_PARAM`, `is_mirrored()`, `mirror_module_geometry()`; reflete geometria + fita L1↔L2 + usinagens `operacoes.x` + `door_side` + nomes "Esquerda/Direita"; botão checkable sincroniza estado |
| **Agrupar/desagrupar** | `assembly.py`, `sidebar.py:_group_selected_modules` | `MakeNestedGroupCommand`/`ExplodeGroupCommand` + `GroupInContextCommand`; marca `ext["trazomob"]["kind"]="assembly"`; `iter_module_groups()` varre árvore; cutlist não perde peças |
| **Ambientes/Pavimentos** | `ambiente.py`, `schema.py:+KIND_AMBIENTE/KIND_PAVIMENTO`, `wall_plan_2d.py:build_ambiente_group` | Entidades com `nome`, `pavimento`, `area_m2`, `pe_direito`, `visivel`; piso/teto/paredes como filhos; `extract_parts(ambiente=...)` filtra; `resumo_ambiente()` para relatório |
| **Cutlist recursivo + filtro** | `parts.py:extract_parts` | Varre árvore respeitando visibilidade; `selected_only` filtra pela folha; parâmetro `ambiente` opcional |
| **Schema unificado estendido** | `schema.py` | `set_ambiente_data`, `update_ambiente_data`, `set_pavimento_data`, `ambiente_params`, `pavimento_params`, `set_floor_data`, `set_ceiling_data`, `set_wall_data` |

**Testes da Onda 2:** 26 novos testes cobrindo geometria do espelho, metadados, undo/redo, agrupamento, ambientes, cutlist filtrado.

---

## 3.1 O que a Onda 3 entregou (NOVO — 02/11/2026)

| Entrega | Arquivos | Evidência |
|---|---|---|
| **Precificação persistente** | `preferences.py` | Seção `"pricing"` com `chapas_m2`, `fita_borda_m`, `ferragens`, `mao_de_obra_m2`, `markup`, `impostos_percent`, `desconto_percent`, `frete_tipo/valor` e `empresa`; getters + `save_pricing_config` |
| **Motor de orçamento** | `pricing.py` | `calcular_orcamento_cutlist()` consolida chapas por material, fitas por espessura, ferragens inferidas e mão de obra; aplica markup → impostos → desconto → frete; `calcular_orcamento_por_ambiente()` agrupa por ambiente/pavimento |
| **Lookup flexível de preços** | `pricing.py` | `_get_chapa_preco_flexivel` (exato → sem "TX" → prefixo) e `_get_fita_preco_flexivel` (vírgula → ponto → prefixo) para tolerar variações de nome do builder |
| **Proposta comercial** | `production_report.py` | `generate_proposal_html()` com emitente, cliente, estatísticas, itens, resumo financeiro, validade, observações e assinatura; botão de impressão; `generate_proposal_pdf()` opcional via `weasyprint` com fallback |
| **Relatório com orçamento** | `production_report.py` | `generate_project_html_report(..., include_pricing=True)` adiciona itens detalhados, resumo financeiro e painel por ambiente |
| **UI comercial** | `dialog_cutlist_tab.py` | Botão **"📋 Proposta Comercial (PDF/HTML)"**, diálogo de dados do cliente (nome, CPF/CNPJ, endereço, telefone, e-mail, observações) e opção de incluir orçamento no relatório |

**Testes da Onda 3:** 13 novos testes (`tests/test_pricing.py`) cobrindo matemática do orçamento, markup/impostos/desconto/frete, consolidação de itens, filtro por ambiente, lookups flexíveis, formatação monetária e geração de HTML (proposta e relatório com/sem preços).

---

## 4. Números reais do plugin (recontados v4)

- **46 módulos em 9 categorias** (igual v2)
- **18 materiais** (9 MDF + 9 pedra), **5 presets de luz**, **4 perfis de alumínio** com biblioteca JSON
- **Cutlist:** 15 colunas + **filtro por ambiente**
- **Plano de corte:** guilhotina + best-fit, kerf/refilo/sobras, respeito ao veio
- **Render:** Cycles/EEVEE via Blender, até 4K, IES real, 5 presets
- **Produção:** etiquetas PNG, relatório HTML executivo
- **Comercial:** orçamento com preços/markup/impostos/desconto/frete + proposta HTML/PDF
- **Preferências:** JSON persistente (ainda sem tela), agora com seção de preços
- **Novos arquivos v4:** `pricing.py`, `tests/test_pricing.py`
- **Novos arquivos v3:** `ambiente.py`, `assembly.py`, `mirror.py`, `sidebar_ambiente_controller.py`, `report_html.py`, `tests/test_mirror_and_assembly.py`, `tests/test_ambiente_integration.py`

---

## 5. Comparativo por pilar (ATUALIZADO v4)

Legenda: ✅ paridade · 🟡 parcial · ❌ ausente

| Pilar | TrazoMob (v4) | Promob / líderes | Leitura |
|---|---|---|---|
| Módulos paramétricos | ✅ 46 módulos, 9 cat., medidas ao mm | ✅ | **Paridade** |
| Snap + cotas ao arrastar | ✅ parede, piso, réguas, vizinhos; cotas em mm | ✅ | **Paridade (diferencial)** |
| Paredes / planta / elevação | ✅ sólidos manifold, planta 2D, elevação PNG | ✅ | **Paridade** |
| Cutlist | ✅ 15 colunas, fita por face, veio, **filtro por ambiente** | ✅ | **Paridade** |
| Plano de corte | ✅ guilhotina + best-fit, kerf/refilo/sobras | ✅ Cut Pro | **Paridade** |
| Usinagem | ✅ copo Ø35, minifix, cavilha, rasgo, corrediça | ✅ + CAM | 🟡 **Descritiva, não gera CAM** |
| Iluminação + render | ✅ IES real, 4K, lote | ✅ nuvem/VR, IA | 🟡 **Depende de Blender local** |
| **Espelhar módulo paramétrico** | ✅ `mirror_x` no `ext`, reconstrói com fita/usinagens/lados | ✅ nativo | **✅ PARIDADE ALCANÇADA** |
| **Agrupar / desagrupar** | ✅ comandos do core, `kind=assembly`, undo/redo | ✅ nativo | **✅ PARIDADE ALCANÇADA** |
| **Ambientes / pavimentos** | ✅ entidade com nome, piso, teto, área, pé-direito, módulos | ✅ gerenciador | **✅ PARIDADE ALCANÇADA (MVP)** |
| Etiquetas de produção | 🟡 PNG com fita/medidas; barras **decorativas** (hash MD5) | ✅ Code 128 + ERP | 🟡 **Parece pronto, não é escaneável** |
| Relatório de produção | ✅ HTML executivo com/sem orçamento | ✅ + custos | ✅ **Paridade (HTML)** |
| Biblioteca do usuário | 🟡 perfis alumínio + medidas padrão; módulos não | ✅ móveis/acabamentos/ferragens | **Lacuna** |
| Orçamento / proposta / cliente | ✅ preços, markup, impostos, desconto, frete, orçamento por ambiente e proposta HTML | ✅ core do Promob | ✅ **PARIDADE ALCANÇADA (MVP)** |
| PDF / prancha comercial | 🟡 proposta HTML imprimível; PDF direto via `weasyprint` opcional | ✅ PDF nativo | 🟡 **Falta PDF nativo e prancha** |
| DXF / IFC / SKP | ❌ nenhum | ✅ (Promob importa SKP) | **Lacuna de interop** |
| Ferragens com SKU | ❌ só geometria (preço manual por chave) | ✅ Blum/Hafele com preço | 🟡 **Preço existe, catálogo/SKU não** |
| Preferências | 🟡 JSON persistente, **sem tela** (preços inclusos) | ✅ tela completa | 🟡 **Falta UI** |
| Onboarding / ajuda | ❌ banners/tooltips; manual no repo | ✅ tours | **Lacuna de UX** |
| Atalhos | ❌ `TrazoMobTool.shortcut = None` | ✅ | **Lacuna** |
| i18n | ❌ só `module_ribbon.py` usa `core.i18n` | ✅ multi-idioma | **Lacuna** |

---

## 6. Onde o plugin já é forte (não mexer)

- **Paramétrica real** com herança de medidas, preview de vãos, badges por aba
- **Snap magnético** com travas de eixo, cotas dinâmicas, colisão de abertura
- **Produção acima da média:** fita por face, veio, sobras, usinagem descritiva
- **Iluminação IES real** e render 4K local
- **Paredes manifold/watertight** com recorte de esquadria integrado ao undo
- **Base de engenharia sólida:** metadados fonte única, CI, logging, 131 testes verdes
- **Organização de projeto (Onda 2):** espelhar paramétrico, agrupar/desagrupar, ambientes/pavimentos — **PARIDADE ALCANÇADA**
- **Ciclo comercial (Onda 3):** orçamento real com markup/impostos/desconto/frete e proposta HTML/PDF — **PARIDADE ALCANÇADA (MVP)**

---

## 7. Lacunas remanescentes (ordem de impacto comercial)

### A. Ciclo comercial — ✅ resolvido na Onda 3
- Preço de chapa, fita, ferragem e mão de obra, markup, imposto, desconto e frete: **implementados** em `pricing.py` + `preferences.py`
- Proposta com cliente, empresa, ambientes, totais, validade e assinatura: **implementada** em `production_report.py`
- Pendências menores: tela visual para editar preços (hoje via JSON), catálogo de ferragens com SKU e "modo vendedor" offline

### B. Produção e interoperabilidade
- **Código de barras não escaneável:** `production_labels.py` usa hash MD5 (`_draw_code128_barcode`)
- **Sem DXF/CNC/CAM:** usinagem descritiva não vira arquivo para centro de usinagem
- **Sem PDF:** `export.py` só CSV/JSON/texto; README promete PDF
- **Sem IFC/DWG/SKP** para arquitetura
- **Sem integração ERP** (Promob tem FoccoERP/FoccoLOJAS)

### C. Apresentação ao cliente
- Render bonito, mas **sem prancha PDF** unindo planta, elevações, vistas, lista de peças
- Sem 360/VR, sem apresentação guiada, sem "Real Scene"-like

### D. Biblioteca do usuário
- Só perfis de alumínio e medidas padrão. Não salva "meu balcão de canto com essas ferragens"

### E. UX e aprendizado
- Quatro superfícies concorrentes (toolbar, ribbon, sidebar, diálogo) sem hierarquia clara
- Sem tela de preferências (JSON existe, não exposto)
- Sem menu de ajuda/tour acessível no app
- Sem atalhos para inserir/girar/ocultar/abrir sidebar
- Rotação só 90°/180°, sem gizmo de redimensionar no 3D
- i18n quase inexistente; mojibake em strings

### F. Engenharia (dívida restante)
1. **Inferência por nome PT** ("Folha", "Marco", "Puxador") — precisa `role` tipado no `ext`
2. **Monkey-patching** em `hooks.py` (`core.group.copy_group`, `MoveTool`, `ScaleTool`, `render_blender`)
3. **Monólitos:** `sidebar.py` ~260 KB, `dialog.py` ~106 KB, `builder.py` ~83 KB, `magnetic_drag.py` ~84 KB
4. **Documentação divergente:** README promete PDF; docstring etiqueta promete Code 128

---

## 8. Roadmap revisado (v4)

| Onda | Foco | Entregas | Status |
|---|---|---|---|
| **1 — Confiança** | Não perder dados / não quebrar | Persistência span; `schema.py` fonte única; CI; undo luzes; logging | ✅ **Concluída** |
| **2 — Paridade percebida** | O que o cliente compara de imediato | Espelhar paramétrico; agrupar/desagrupar; ambientes/pavimentos | ✅ **Concluída (02/11)** |
| **3 — Ciclo comercial** | Fechar venda | Preços, markup, impostos, desconto, frete; orçamento por ambiente; proposta HTML/PDF; UI na cutlist | ✅ **Concluída (02/11)** |
| **3b — Produção** | Fábrica e interop | Code 128 real + DXF etiquetas; DXF de usinagem; CAM opcional; prancha PDF; catálogo de ferragens com SKU | 🎯 **Próxima** |
| **4 — Biblioteca & UX** | Retenção e percepção | Biblioteca usuário (módulos+acabamentos); tela preferências (inclui preços); atalhos; ajuda/tour; i18n; gizmo 3D | 📋 **Backlog** |

### Quick wins restantes (dias, alto retorno) — Onda 3b

| Ação | Onde | Ganho |
|---|---|---|
| Implementar Code 128 real (tabela símbolos) ou QR | `production_labels.py` | Etiqueta escaneável; ERP possível |
| Tela de edição de preços sobre a seção `"pricing"` | `preferences.py` + diálogo | Torna o orçamento editável sem mexer no JSON |
| PDF real da proposta/cutlist **ou** corrigir README | `production_report.py`, `README.md` | Consistência documentação |
| Tela de preferências sobre JSON existente | `preferences.py` + diálogo | Feature quase pronta exposta |
| Atalhos inserir/girar/ocultar/sidebar | `__init__.py`, `module_ribbon.py` | Percepção produto maduro |
| Menu "Ajuda" com manual embutido | `module_ribbon.py` | Onboarding mínimo sem tour |
| `role` tipado no `ext` da peça | `builder_mesh_utils.py`, `interact.py`, `magnetic_drag.py` | Robustez a importados/i18n |
| Corrigir mojibake strings | vários | Percepção acabamento |

---

## 9. O que **não** copiar do Promob

- **Ecossistema fechado** e bibliotecas de fabricante pagas — diferencial do TrazoMob é ser aberto
- **Render em nuvem obrigatório** — render local via Blender é vantagem
- **Assistentes que escondem a paramétrica** — público quer controle milimétrico
- **Créditos de IA como gargalo** — se entrar IA, opcional e local-first

---

## 10. Recomendação

**As Ondas 1, 2 e 3 (frente comercial) estão concluídas.** O plugin deixou de terminar na fábrica: agora calcula custo direto, aplica markup/impostos/desconto/frete e gera proposta comercial com dados de cliente e empresa (131 testes verdes).

**Próximo investimento (Onda 3b): Produção e interoperabilidade.** É o que falta para o ciclo fechar de ponta a ponta. Ordem sugerida:

1. **Code 128 real** nas etiquetas (tabela de símbolos) — habilita ERP/leitor óptico
2. **PDF nativo** da proposta e da cutlist (ou dependência declarada de `weasyprint`)
3. **Prancha PDF** (planta + elevações + vistas + lista de peças)
4. **DXF de usinagem** (exporta `operacoes` para CAM)
5. **Catálogo de ferragens com SKU** e tela de preços
6. **Biblioteca do usuário** (salvar módulo completo com ferragens/acabamentos)
7. **Tela de preferências + atalhos + ajuda** (quick wins UX)

Se for escolher **uma** frente agora: **Code 128 real + PDF nativo**. É o que transforma documentos "bonitos" em documentos operacionais.

---

## 11. Anexo — Arquivos-chave analisados (v4)

**Novos na v4:**
`pricing.py`, `tests/test_pricing.py`

**Modificados na v4:**
`preferences.py` (+seção `"pricing"` e getters), `production_report.py` (orçamento, proposta HTML/PDF), `dialog_cutlist_tab.py` (botão de proposta, diálogo de cliente, opção de orçamento no relatório)

**Novos na v3:**
`ambiente.py`, `assembly.py`, `mirror.py`, `sidebar_ambiente_controller.py`, `report_html.py`, `tests/test_mirror_and_assembly.py`, `tests/test_ambiente_integration.py`

**Modificados na v3:**
`schema.py` (+KIND_AMBIENTE/KIND_PAVIMENTO, setters ambientes/pisos/tetos/paredes), `parts.py` (extract_parts recursivo + filtro ambiente), `wall_plan_2d.py` (build_ambiente_group), `sidebar.py` (btn_mirror, card_align, card_assembly, _group/_ungroup), `builder.py` (mirror_module_geometry call)

**Base (inalterados ou já na v2):**
`catalog.py`, `entity.py`, `builder.py`, `builder_*.py`, `optimizer.py`, `machining.py`, `dialog_cutlist_tab.py`, `cut_plan_viewer.py`, `export.py`, `production_labels.py`, `production_report.py`, `preferences.py`, `perfis.py`, `perfis_editor.py`, `materials_catalog.py`, `render_engine.py`, `render_dialog.py`, `blender_scripts/photoreal_render.py`, `light_tools.py`, `magnetic_drag.py`, `collision.py`, `interact.py`, `module_ribbon.py`, `dialog.py`, `dialog_gallery.py`, `material_editor_dialog.py`, `wall_*.py`, `migration.py`, `hooks.py`, `tests/`, `.github/workflows/ci.yml`, `README.md`.

**Fora do escopo:** app IngeTrazo (core, viewport, ferramentas nativas), integrações de terceiros, roadmap comercial/precificação do produto.
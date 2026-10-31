# Análise Comparativa — TrazoMob × Promob e softwares de categoria

**Projeto:** IngeTrazo — plugin `trazomob`
**Data:** 30/10/2026
**Escopo:** auditoria de funcionalidades, UX, produção e engenharia do plugin, comparada com Promob, 2020 Design, SketchUp + plugins e Planner 5D.
**Método:** leitura do código do plugin (58 arquivos `.py`, ~74 testes), inventário do catálogo/builders, verificação de fluxos e checagem de pontos de engenharia (persistência, CI, metadados).

---

## 1. Resumo executivo

O TrazoMob já está **no nível de categoria** em modelagem paramétrica, snap magnético e cutlist/plano de corte. Ele **perde** nos pilares que o mercado vende como "produtividade percebida":

1. **Ciclo comercial incompleto** — não há orçamento, preço, proposta ou PDF comercial.
2. **Organização de projeto** — não há agrupar/espelhar módulo paramétrico, gerenciador de ambientes/pavimentos nem biblioteca do usuário.
3. **Acabamento de UX** — 4 superfícies concorrentes, sem onboarding, sem preferências, i18n inexistente e luz fora do Ctrl+Z.

Além disso, há **dívida técnica relevante**: um bug confirmado de persistência de metadados, metadados triplicados com campos divergentes e testes do plugin fora do CI.

---

## 2. Comparativo por pilar

| Pilar | TrazoMob | Promob / líderes | Leitura |
|---|---|---|---|
| Módulos paramétricos | ✅ 48 módulos, 9 categorias, medidas ao mm (`catalog.py`, `builder_*.py`) | ✅ | **Paridade** |
| Snap + cotas ao arrastar | ✅ parede/piso/réguas/vizinhos, cotas em mm (`magnetic_drag.py`) | ✅ | **Paridade** (diferencial) |
| Cutlist + plano de corte | ✅ 15 colunas, fita por face, veio, kerf/refilo (`dialog_cutlist_tab.py`, `optimizer.py`) | ✅ | **Paridade** |
| Usinagem | ✅ copo Ø35, minifix, cavilha, rasgo (`machining.py`) | ✅ | **Paridade descritiva** (não gera CAM) |
| Iluminação + render | ✅ IES real, Cycles/EEVEE, até 4K, lote (`light_tools.py`, `render_engine.py`) | ✅ render em nuvem/VR | 🟡 **Bom, mas depende de Blender externo** |
| Paredes/planta/elevação | ✅ sólidos manifold, planta 2D, elevação PNG (`wall_*.py`) | ✅ | **Paridade** |
| **Agrupar / espelhar módulo** | ❌ não existe (só perfil e folha de esquadria) | ✅ nativo | **Lacuna grave** |
| **Ambientes / pavimentos** | ❌ um grupo "Ambiente Paredes" por planta | ✅ gerenciador | **Lacuna grave** |
| **Biblioteca do usuário** | 🟡 só perfis (`perfis_editor.py`) e "medidas padrão" | ✅ móveis/acabamentos/ferragens salvos | **Lacuna** |
| **Orçamento / proposta / cliente** | ❌ zero | ✅ core do Promob | **Lacuna estratégica** |
| **PDF / prancha comercial** | ❌ README promete PDF; código só faz CSV/JSON/TSV/PNG (`export.py`) | ✅ | **Lacuna + inconsistência de doc** |
| **Etiquetas / ERP / código de barras** | ❌ | ✅ Promob Fábrica | **Lacuna** |
| **DXF / IFC / SKP** | ❌ nenhum | ✅ | **Lacuna de interop** |
| **Catálogo real de ferragens (SKU)** | ❌ só geometria (minifix/corrediça) | ✅ Blum/Hafele com preço | **Lacuna** |
| Onboarding / ajuda in-app | ❌ só banners e tooltips | ✅ tours, "aprenda" | **Lacuna de UX** |
| i18n | ❌ 100% PT-BR hardcoded | ✅ multi-idioma | **Lacuna** |

---

## 3. Onde o plugin já é forte (não mexer sem necessidade)

- **Paramétrica real** (48 módulos) com herança de medidas, preview de vãos e badges por aba (`sidebar.py:2754`).
- **Snap magnético** com travas de eixo, cotas dinâmicas e colisão de abertura (`magnetic_drag.py`, `collision.py`) — o fluxo mais maduro e o mais próximo de Promob.
- **Produção** acima da média de plugins de CAD: fita por face, veio, sobras reaproveitáveis, usinagem descritiva.
- **Iluminação IES de verdade** no render (`blender_scripts/photoreal_render.py:722`).
- **Paredes manifold/watertight** com recorte de esquadria integrado ao undo.

Números de referência:

- 48 módulos em 9 categorias (7 inferiores, 4 aéreos, 2 torres, 8 armários, 1 banheiro, 1 nicho, 4 marmoraria, 12 portas/janelas, 9 peças avulsas).
- 18 materiais (9 MDF + 9 pedra), 13 texturas, 4 perfis de alumínio.
- Chapa padrão 2750×1850 mm, kerf 4 mm, refilo 10 mm, sobras reaproveitáveis ≥ 200×200 mm.
- 5 presets de luz, Kelvin configurável, IES importável.

---

## 4. Lacunas que mais pesam (em ordem de impacto comercial)

### A. Fecha o ciclo comercial (o que mais vende)

Hoje o plugin vai até a produção, mas para no CSV. Promob vende porque entrega **orçamento, proposta e apresentação**.

- Sem cadastro de preço de chapa/fita/ferragem/mão de obra, markup, imposto, desconto.
- Sem proposta em PDF com logo, cliente, ambientes, render e totais.
- Sem "modo vendedor" (Promob Mover): catálogo com preço, configurar e orçar no cliente.

**Impacto:** o projetista ainda monta orçamento no Excel → perde o maior diferencial percebido.

### B. Organização do projeto

- **Agrupar/desagrupar** e **espelhar módulo paramétrico** não existem. O espelho nativo do IngeTrazo gera malha espelhada, **quebrando portas/puxadores/furações** (`hooks.py:120` só evita compartilhar malha).
- **Ambientes/pavimentos:** casa de 2 andares vira ginástica de grupos e visibilidade.
- **Biblioteca do usuário:** não dá para salvar "meu balcão de canto" como item reutilizável; só perfis e medidas padrão.

**Impacto:** projetos grandes ficam lentos e sujeitos a erro; é o que mais afasta de Promob/2020.

### C. Produção e interoperabilidade

- **Sem DXF/CNC/CAM** — a usinagem é descritiva, não vira arquivo para centro de usinagem.
- **Sem etiquetas de peça** (código, cliente, ambiente, fita) e sem integração ERP.
- **Sem PDF da cutlist** (só CSV/JSON) — o README afirma PDF (`README.md:41`), mas não existe código.
- **Sem IFC/DWG/SKP** para arquitetura.

**Impacto:** a fábrica recebe planilha, não pacote de produção.

### D. Apresentação ao cliente

- Render bonito, mas **sem prancha PDF** unindo planta + elevações + vistas + lista.
- **Sem 360/VR** e sem apresentação guiada.

**Impacto:** concorrentes fecham venda com material pronto; aqui exige montar no PowerPoint/Canva.

### E. UX e aprendizado

- **4 superfícies concorrentes** (toolbar com 13 botões só de ícone, ribbon, sidebar, diálogo) sem hierarquia "projetar → mobiliar → iluminar → produzir → renderizar".
- **Sem menu de ajuda/tour**; `MANUAL_ILUMINACAO.md` existe no repo mas não é acessível no app.
- **Sem tela de preferências** (unidades, snap, atalhos, tema) — configuração espalhada.
- **Atalhos faltando** para inserir/girar/ocultar/abrir sidebar.
- **Luz fora do Ctrl+Z** (`light_tools.py:252` usa `undoable=False`) — quebra a expectativa criada pelo resto.
- **Rotação só 90°/180°**, sem alça/gizmo de redimensionar no 3D.
- **Erros silenciosos** (`except Exception: pass` em ~30 pontos) → "módulo estranho" sem diagnóstico.

### F. Engenharia (dívida que vai cobrar juros)

1. **Bug confirmado de persistência:** `_unrot_carcass_span` é calculado **depois** de `set_trazomob` (`builder.py:1094` vs `:1103`), então nunca é gravado. Verificação: módulo com `rot_z=90` persiste `rot_z`, mas `_unrot_carcass_span` fica `None`. Leitores caem no fallback e módulos rotacionados podem **derivar ao escalar/reconstruir**.
2. **Metadados triplicados** (`trazomob`, `trazomob_module`, `trazomob_esquadria`) com campos divergentes (`largura_mm` vs `largura`) → telas mostram valores diferentes após edição.
3. **CI não roda os testes do plugin:** `.github/workflows/ci.yml:75` executa só `tests/` da raiz e o glob não é recursivo (`scripts/pytest_batches.py:37`) → os ~74 testes do TrazoMob **nunca protegem o merge**.
4. **Acoplamento a APIs privadas + monkey-patching** (`hooks.py` patcheia `core.group.copy_group`, `MoveTool`, `ScaleTool`, `render_blender`) → qualquer refactor do core quebra o plugin em silêncio.
5. **Inferência por nome de peça em PT** ("Folha", "Marco", "Puxador") → modelos importados/renomeados/i18n quebram snap, bounds e recorte (foi a raiz do bug da porta que corrigimos).
6. **Monólitos:** `sidebar.py` 4.126 linhas, `dialog.py` 1.828, `builder.py` 1.529, `magnetic_drag.py` 1.449 — custo alto de manutenção.

---

## 5. Roadmap sugerido (3 ondas)

| Onda | Foco | Entregas | Esforço |
|---|---|---|---|
| **1 — Confiança** | Não perder dados / não quebrar | Corrigir persistência do span; fonte única de metadados (`schema.py` + `get_trazomob` em todos os leitores); CI rodando `plugins/trazomob/tests`; undo de luzes; logging em vez de `pass` | ~1–2 sprints |
| **2 — Paridade percebida** | O que o cliente compara de imediato | Agrupar/desagrupar + espelhar paramétrico; gerenciador de ambientes/pavimentos; biblioteca do usuário (módulos/acabamentos); preferências + atalhos; onboarding (tour 5 passos) | ~3–4 sprints |
| **3 — Diferencial de mercado** | Fechar venda e fábrica | Orçamento (preços, markup, impostos) + proposta PDF; prancha PDF (planta+elevações+render); DXF/etiquetas; catálogo de ferragens com SKU; opcional CAM | ~4–6 sprints |

### Quick wins (dias, alto retorno)

| Ação | Onde | Ganho |
|---|---|---|
| Mover `set_trazomob` para depois do cálculo do span | `builder.py:1094` | Corrige deriva de módulo rotacionado |
| Trocar leituras diretas por `get_trazomob` | `sidebar.py:2141`, `dialog.py:1125`, `module_ribbon.py:62`, `interact.py:102` | Consistência imediata |
| Incluir testes do plugin no CI | `ci.yml:75` / `pytest_batches.py:37` | 74 testes passam a proteger |
| PDF real da cutlist (ou corrigir README) | `export.py`, `dialog_cutlist_tab.py` | Promessa cumprida |
| Atalhos + menu "Ajuda" com link do manual | `__init__.py`, `module_ribbon.py` | Percepção de produto |
| Undo nas luzes | `light_tools.py:252` | Consistência de Ctrl+Z |
| Papel tipado da peça (`role` no `ext`) em vez de nome PT | `builder_mesh_utils.py`, `interact.py`, `magnetic_drag.py` | Robustez a importados/i18n |

---

## 6. O que **não** copiar do Promob

- Ecossistema fechado e dependente de bibliotecas de fabricante pagas — o diferencial do TrazoMob é ser **aberto e integrável** (CSV/DXF/IFC abertos valem mais que catálogo travado).
- Render em nuvem obrigatório — o render local via Blender já é vantagem para quem não quer mensalidade.
- Complexidade de "assistentes" que escondem a paramétrica — o público aqui é projetista que quer controle milimétrico.

---

## 7. Recomendação

Se for para escolher **uma** frente para começar: **Onda 1 + "Agrupar/espelhar + ambientes"**. Isso resolve o que mais dói no uso diário e elimina a maior comparação negativa com Promob ("não consigo organizar o projeto"). Orçamento/PDF vem depois, quando o projeto já estiver organizado — e vira o argumento de venda.

Ordem sugerida de implementação:

1. Corrigir o bug de persistência (`_unrot_carcass_span`) + colocar os testes do plugin no CI.
2. Unificar metadados (`schema.py`, leitura sempre por `get_trazomob`).
3. Agrupar/desagrupar e espelhar paramétrico.
4. Gerenciador de ambientes/pavimentos.
5. Biblioteca do usuário (módulos e acabamentos).
6. Preferências, atalhos e onboarding.
7. Orçamento + proposta PDF + prancha.
8. DXF/etiquetas e catálogo de ferragens.

---

## 8. Anexo — Arquivos-chave analisados

`catalog.py`, `builder.py`, `builder_*.py`, `parts.py`, `optimizer.py`, `machining.py`, `dialog_cutlist_tab.py`, `cut_plan_viewer.py`, `export.py`, `render_engine.py`, `render_dialog.py`, `blender_scripts/photoreal_render.py`, `light_tools.py`, `magnetic_drag.py`, `collision.py`, `interact.py`, `module_ribbon.py`, `sidebar.py`, `dialog.py`, `material_editor_dialog.py`, `wall_*.py`, `migration.py`, `entity.py`, `preferences.py`, `perfis*.py`, `hooks.py`, `tests/`.

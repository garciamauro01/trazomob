# Arquitetura do TrazoMob

Este documento descreve como o plugin está organizado atualmente e o plano de reorganização em fases.
Ele é a referência para novas contribuições: arquivos na raiz, subpacotes e responsabilidades.

## Estado atual

O ponto de entrada público do plugin é `__init__.py`. Ele registra:

- a ferramenta `TrazoMobTool`;
- o painel lateral `TrazoMobSidebarPanel`;
- a barra de ferramentas e os menus de contexto;
- as ferramentas interativas de portas, gavetas e paredes.

O código está separado em subpacotes por responsabilidade. A raiz contém apenas a entrada pública,
documentação, assets e testes.

## Responsabilidades

| Área | Responsabilidade |
| --- | --- |
| `domain/` | Catálogo, geometria paramétrica, esquema de dados, preferências e auto-layout. |
| `builders/` | Construção das malhas e peças dos módulos e esquadrias. |
| `wall/` | Paredes 2D/3D, planta baixa, seleção de faces, guias e pintura. |
| `interaction/` | Ferramentas interativas, arraste magnético, colisão e alinhamento. |
| `production/` | Extração de peças, furação, nesting, precificação e relatórios. |
| `render/` | Iluminação, PBR e renderização. |
| `profiles/` | Biblioteca e editor de perfis de alumínio. |
| `ui/` | Sidebar, ribbons, ícones, diálogos e galerias. |
| `integrations/` | Integração com o host IngeTrazo (`platform.py` e hooks de runtime). |
| `assets/` | Perfis, miniaturas, texturas e amostras. |
| `docs/` | Manuais e documentos de arquitetura. |

## Estrutura atual

```text
trazomob/
├── __init__.py                  # setup/registro público; sem lógica de domínio
├── assets/
│   ├── samples/
│   └── profiles/
├── blender_scripts/
├── domain/
├── builders/
├── wall/
├── interaction/
├── production/
├── render/
├── profiles/
├── ui/
├── integrations/
├── docs/
└── tests/
```

`domain/` é usado no lugar de `core/` para não sombrear o pacote `core/` do IngeTrazo
quando o diretório do plugin está no caminho de importação do Python.

## Fases de reorganização

### Fase 1 — Limpeza de raiz (concluída)

- Move amostras `.igz` para `assets/samples/`.
- Move `perfis_biblioteca.json` para `assets/profiles/`.
- Move manuais para `docs/`.
- Corrige links e ignora `.pytest_cache/`.

### Fase 2 — Separação em subpacotes (concluída)

- Módulos Python agrupados em `domain/`, `builders/`, `wall/`, `interaction/`,
  `production/`, `render/`, `profiles/`, `ui/` e `integrations/`.
- Imports relativos atualizados dentro do plugin.
- Testes atualizados para os novos caminhos.
- Ressincronizados os caminhos absolutos de `assets/` e `blender_scripts/` após as mudanças.

### Fase 3 — Divisão dos monólitos (concluída)

Cada monólito foi dividido por responsabilidade em mixins de um nível, mantendo o
arquivo original como fachada composta e preservando a API pública:

- `ui/sidebar_panel.py` → `sidebar_*_controller.py` (abas e ações do painel);
- `ui/module_dialog.py` → `module_dialog_build.py`, `module_dialog_sections.py`,
  `module_dialog_options.py`, `module_dialog_form.py`, `module_dialog_actions.py` e
  `module_dialog_style.py` (montagem, seções básicas e avançadas do formulário,
  carga de dados, ações 3D e tema);
- `wall/floorplan_canvas.py` → `mixin_navigation.py`, `mixin_history.py`,
  `mixin_input.py`, `mixin_drawing.py`, `mixin_measurement.py`, `mixin_dialogs.py`
  e `mixin_calibrate.py` (navegação, histórico, entrada, desenho, medição, diálogos e calibração);
- `builders/cabinet.py` → `cabinet_transform.py`, `cabinet_caixa.py`,
  `cabinet_module_group.py` e `cabinet_delegates.py` (transformações, caixa, grupos e delegações);
- `interaction/magnetic_drag.py` → `magnetic_drag_input.py`, `magnetic_drag_context.py`
  e `magnetic_drag_snap.py` (entrada/arraste, contexto/vizinhos e snap/cotas).

## Regras para novas contribuições

1. Não criar novos módulos Python na raiz, exceto `__init__.py`.
2. Colocar o código na área de responsabilidade correspondente.
3. Preservar a API pública exportada por `__init__.py`.
4. Não criar módulos “facade” na raiz apenas para compatibilidade.
5. Rodar `python -m pytest plugins/trazomob/tests -q` antes de concluir.
6. Usar `git mv` para mover arquivos, preservando o histórico.

## Comandos de validação

```powershell
python -m pytest plugins/trazomob/tests -q
python -m py_compile <arquivos alterados>
```

## Decisões

- A organização usa subpacotes de um nível, e não subpacotes muito aninhados.
- `domain/` não se chama `core/` porque o IngeTrazo também usa o pacote `core/`.
- A Fase 3 divide os monólitos internamente, separada da mudança de caminhos.
- O `__init__.py` continua exportando a API do plugin e delega o restante aos subpacotes.

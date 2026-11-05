# Arquitetura do TrazoMob

Este documento descreve como o plugin está organizado atualmente e o plano de reorganização em fases.
Ele é a referência para novas contribuições: arquivos na raiz, subpacotes e responsabilidades.

## Estado atual

O ponto de entrada público do plugin é `__init__.py`. Ele registra:

- a ferramenta `TrazoMobTool`;
- o painel lateral `TrazoMobSidebarPanel`;
- a barra de ferramentas e os menus de contexto;
- as ferramentas interativas de portas, gavetas e paredes.

Os módulos que implementam essas funções estão distribuídos pela raiz do repositório.
A Fase 1 da reorganização apenas moveu recursos de dados para `assets/` e documentação para `docs/`.

## Responsabilidades pretendidas

| Área | Responsabilidade |
| --- | --- |
| `core/` | Catálogo, geometria paramétrica, esquema de dados, preferências e auto-layout. |
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

## Estrutura alvo

```text
trazomob/
├── __init__.py                  # setup/registro público; sem lógica de domínio
├── assets/
│   ├── samples/
│   └── profiles/
├── blender_scripts/
├── core/
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

## Fases de reorganização

### Fase 1 — Limpeza de raiz

- Mover amostras `.igz` para `assets/samples/`.
- Mover `perfis_biblioteca.json` para `assets/profiles/`.
- Mover manuais para `docs/`.
- Corrigir links no README.
- Adicionar `docs/ARQUITETURA.md`.

Nenhum módulo Python muda de local nesta fase.

### Fase 2 — Separação em subpacotes

Mover arquivos existentes com `git mv`, sem alterar comportamento:

1. `production/`
2. `core/`
3. `builders/`
4. `wall/`
5. `interaction/`
6. `ui/`
7. `render/` e `profiles/`
8. `integrations/`

Depois de cada lote:

- atualizar imports internos para caminhos relativos (`from ..core.catalog import ...`);
- atualizar os testes para caminhos absolutos;
- executar a suíte completa.

### Fase 3 — Divisão dos monólitos

Mover arquivos é apenas a primeira etapa. Os arquivos maiores continuam grandes após a Fase 2,
então cada um deve ser dividido por responsabilidade:

- `ui/sidebar_panel.py` — por aba e por ação do painel;
- `ui/dialogs/module_dialog.py` — por seção do formulário;
- `wall/floorplan_canvas.py` — ferramentas, pintura, snap e comandos;
- `builders/cabinet.py` — caixa, fundos, furação e orquestração;
- `interaction/magnetic_drag.py` — snap, arraste e validação.

## Regras para novas contribuições

1. Não criar novos módulos Python na raiz, exceto `__init__.py`.
2. Colocar o código na área de responsabilidade correspondente.
3. Preservar a API pública exportada por `__init__.py`.
4. Não criar módulos “facade” na raiz apenas para compatibilidade.
5. Rodar `python -m pytest tests -q` antes de concluir.
6. Usar `git mv` para mover arquivos, preservando o histórico.

## Comandos de validação

```powershell
python -m pytest tests -q
python -m py_compile <arquivos alterados>
```

## Decisões

- A organização usa subpacotes de um nível (`core/`, `ui/`, `wall/` etc.), e não subpacotes muito aninhados.
- A Fase 3 divide os monólitos internamente, separada da mudança de caminhos.
- O `__init__.py` continua exportando a API do plugin e delega o restante aos subpacotes.

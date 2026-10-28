# TrazoMob — Modulação, Marcenaria e Arquitetura 3D para IngeTrazo

O **TrazoMob** é uma extensão profissional para o [IngeTrazo CAD 3D](https://github.com/ingelibre/ingetrazo) focada em marcenaria sob medida, projeto de interiores, modelagem paramétrica de ambientes, esquadrias e plano de corte integrado.

---

## 🚀 Principais Funcionalidades

### 🪵 1. Módulos Paramétricos de Marcenaria
* **Catálogo Completo:** Balcões baixos, armários aéreos, torres de eletrodomésticos, gaveteiros, despenseiros, cantos retos e cantos em L.
* **Bancadas Paramétricas:** Tampos retos e em L com engrossamento configurável, rodabanca e saia frontal.
* **Ajustes Milimétricos em Tempo Real:** Edição direta de largura, altura, profundidade, recuo de rodapé e espessura de chapas (15mm, 18mm, 25mm).
* **Interatividade 3D:** Clique interativo para abrir e fechar portas de giro, basculantes e gavetas diretamente na viewport.

### 🧲 2. Snapping Magnético e Posicionamento Inteligente
* **Atração Magnética em Paredes:** Os módulos detectam e alinham automaticamente sua face traseira à alvenaria, girando e ajustando a rotação angular.
* **Encaixe Módulo a Módulo:** Encoste balcões e aéreos lado a lado com travamento automático e alinhamento de frentes.
* **Cotas Dinâmicas Projetadas:** Medição instantânea em tempo real (em mm) da distância até cantos de paredes ou módulos vizinhos durante o arraste com o mouse.
* **Réguas de Montagem:** Réguas de altura padronizadas (rodapé, balcão, bancada, torre e aéreo) com editor visual de réguas personalizadas.

### 🧱 3. Paredes Inteligentes e Planta Baixa 2D
* **Planta Baixa Interativa:** Desenhe ambientes fechados ou paredes soltas em 2D com espessura e pé-direito configuráveis.
* **Geração Automática de Ambientes:** Criação simultânea de sólidos 3D herméticos para alvenaria, lajes de piso e forros de teto.
* **Sólidos Manifold Perfeitos:** Paredes fechadas em esquadria (miter joint), estanques (*watertight*) e sem costuras internas indesejadas.
* **Visualização Seletiva:** Ferramentas para ocultar paredes individuais e visualizar o interior do cômodo sem perder a geometria.

### 🚪 4. Esquadrias Integradas (Portas e Janelas)
* **Recorte Automático de Vãos:** Inserir uma porta ou janela recorta automaticamente a alvenaria da parede hospedeira, mantendo a malha 100% sólida e estanque (*watertight*).
* **Cotas de Boneca e Peitoril:** Exibição de cotas projetadas de distância até os cantos da parede e cotas verticais para janelas (piso ao peitoril, vão e verga).
* **Acompanhamento Dinâmico:** Mover uma esquadria com o mouse ou via barra lateral reposiciona o recorte na parede em tempo real.
* **Desfazer / Refazer Completo (Ctrl+Z):** Totalmente integrado ao histórico do IngeTrazo — ao desfazer a colocação ou movimentação de uma esquadria, o recorte da parede é restaurado perfeitamente.

### 💡 5. Iluminação Decorativa
* **Fitas de LED e Pontos de Luz (Spots):** Inserção de iluminação linear e pontual sob aéreos, painéis e sancas.
* **Visualizador Gráfico:** Cones de luz e traçados visíveis diretamente na viewport para conferência de projeto.

### 📋 6. Plano de Corte e Produção (Cutlist)
* **Lista de Peças Detalhada:** Identificação automática de laterais, bases, prateleiras, tampos, réguas, frentes e fundos.
* **Fitamento de Borda:** Controle de fita de borda por face (superior, inferior, esquerda e direita) com indicação de espessuras (0.45mm, 1.0mm, 2.0mm).
* **Otimizador de Corte 2D:** Distribuição e aproveitamento das peças em chapas de MDF, com suporte a veio da madeira, largura de serra e refilo.
* **Exportação:** Geração de relatórios para PDF e planilhas CSV.

---

## 📦 Instalação

### Opção 1: Pelo Gerenciador de Extensões do IngeTrazo (Recomendado)
1. No IngeTrazo, abra o menu **Extensões ▸ Gerenciar extensões…**.
2. Procure por **TrazoMob** e clique em **Baixar / Instalar**.
3. Reinicie o aplicativo para ativar a barra lateral e as ferramentas.

### Opção 2: Instalação Manual
1. Baixe o código do repositório ou o arquivo `.zip` da [última release](https://github.com/garciamauro01/trazomob/releases).
2. Extraia a pasta `trazomob` dentro do diretório de extensões do usuário:
   - **Windows:** `%APPDATA%\ingetrazo\plugins\trazomob\`
   - **Linux:** `~/.local/share/ingetrazo/plugins/trazomob/`
3. Inicie o IngeTrazo. A aba lateral **TrazoMob** aparecerá no dock da direita.

---

## 🛠️ Requisitos e Compatibilidade

* **IngeTrazo CAD 3D:** Versão `0.1.0` ou superior.
* **Sistema Operacional:** Windows 10/11 ou Linux.
* **Dependências:** `PySide6`, `numpy`, `trimesh` (inclusas no ambiente do IngeTrazo).

---

## 📄 Licença

Distribuído sob a licença **GPL-3.0-or-later**. Consulte o arquivo de licença do projeto para mais detalhes.

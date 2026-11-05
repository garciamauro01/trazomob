# MANUAL DE OPERAÇÃO COMPLETO — TRAZOMOB
*Guia Operacional Técnico e Prático para Marcenaria, Modulação Paramétrica, Arquitetura de Interiores, Orçamentação e Produção 3D no IngeTrazo.*

---

## 📑 ÍNDICE GERAL
1. [Visão Geral do TrazoMob e Filosofia Operacional](#1-visão-geral-do-trazomob)
2. [Interface, Barras de Ferramentas e Painéis de Controle](#2-interface-e-barras-de-ferramentas)
3. [Estrutura do Projeto: Pavimentos, Ambientes e Hierarquia](#3-pavimentos-ambientes-e-hierarquia)
4. [Arquitetura de Alvenaria: Paredes 2D, Sólidos 3D, Pisos e Tetos](#4-arquitetura-de-alvenaria-paredes-pisos-e-tetos)
5. [Pintura e Revestimento de Paredes (Wall Paint)](#5-pintura-e-revestimento-de-paredes)
6. [Elevação Técnica 2D com Cotas Arquitetônicas](#6-elevação-técnica-2d-com-cotas)
7. [Esquadrias Paramétricas (Portas e Janelas com Recorte Automático)](#7-esquadrias-paramétricas)
8. [Réguas de Altura e Linhas-Guia Magnéticas](#8-réguas-de-altura-e-linhas-guia)
9. [Catálogo e Inserção de Módulos de Marcenaria](#9-catálogo-e-inserção-de-módulos)
10. [Edição Paramétrica Detalhada na Barra Lateral](#10-edição-paramétrica-na-barra-lateral)
11. [Biblioteca e Editor de Perfis de Alumínio / Puxadores](#11-perfis-e-puxadores-de-alumínio)
12. [Snapping Magnético, Cotas Projetadas e Posicionamento Inteligente](#12-snapping-magnético-e-posicionamento)
13. [Alinhamento, Centralização, Distribuição no Vão e Grupos (Assemblies)](#13-alinhamento-distribuição-e-grupos)
14. [Cinemática 3D: Abertura Dinâmica e Detecção de Colisões](#14-cinemática-3d-e-colisões)
15. [Luminotécnica Interativa e Spots Físicos (Fotometria IES)](#15-luminotécnica-e-spots-físicos)
16. [Editor de Materiais PBR e Render Foto-Realista (Blender Cycles / EEVEE)](#16-materiais-pbr-e-render-foto-realista)
17. [Lista de Peças (Cutlist), Fitamento de Borda e Furações](#17-cutlist-fitamento-e-furações)
18. [Otimizador de Corte de Chapas 2D (Nesting)](#18-otimizador-de-corte-2d-nesting)
19. [Etiquetas Técnicas de Produção com Código de Barras](#19-etiquetas-técnicas-de-produção)
20. [Motor de Precificação, Orçamentos e Propostas Comerciais](#20-precificação-e-propostas-comerciais)
21. [Exportação, Integrações Externas e Tabela de Atalhos](#21-exportação-e-tabela-de-atalhos)
22. [Biblioteca de Componentes do Usuário (Eletrodomésticos e Modelos Próprios)](#22-biblioteca-de-componentes-do-usuário)

---

## 1. Visão Geral do TrazoMob

O **TrazoMob** é o ecossistema integrado para marcenaria sob medida, interiores e plano de corte do **IngeTrazo CAD 3D**. Ele une a facilidade do desenho paramétrico intuitivo à precisão milimétrica da indústria moveleira e fabril (estilo Promob/CorteCloud/Hellomob).

### Princípios Chave de Operação:
- **Geometria Paramétrica Real:** As alterações de medidas recalculam e reconstroem as chapas com espessuras constantes (15mm, 18mm, 25mm, etc.), sem deformar topos ou criar distorções de escala.
- **Sólidos Manifold Estanques (*Watertight*):** Paredes, pisos e peças são gerados como sólidos fechados, prontos para furações booleanas e renderização sem vazamento de luz.
- **Snapping Magnético e Cotas Dinâmicas:** Ao movimentar módulos próximos a paredes ou outros armários, o sistema alinha a face traseira, ajusta a rotação para 90° e exibe as folgas residuais em milímetros em tempo real.
- **Produção e Orçamento Diretos:** Cada chapa mantém identificação de material, fita de borda nos 4 topos, veio da madeira, furações de dobradiças/minifix e custo financeiro.

---

## 2. Interface e Barras de Ferramentas

Ao iniciar o IngeTrazo com o plugin TrazoMob ativo, você dispõe dos seguintes canais operacionais:

### 2.1 Barra de Ferramentas Superior (Toolbar TrazoMob)
Localizada no topo da área de trabalho:
- **TrazoMob (Ícone Principal):** Abre a janela central unificada com o catálogo de módulos e a tabela da Cutlist.
- **Editor Lateral:** Dá foco imediato ao painel acoplável direito de edição dinâmica.
- **Construir Paredes (Atalho: W):** Inicia a ferramenta interativa de desenho de alvenaria em planta baixa 2D.
- **Réguas de Altura:** Abre o editor e gerenciador de réguas padrão de montagem.
- **Módulos (Ribbon):** Alterna a barra de abas superiores com botões visuais diretos organizados por ambiente (Cozinha Baixos, Aéreos, Torres, Quartos, Banheiros, etc.).
- **Girar 90° (↺ / ↻):** Gira instantaneamente o móvel selecionado em passos ortogonais de 90° no eixo Z.
- **Interagir (Atalho: I):** Ativa a mãozinha de clique interativo para abrir e fechar portas e gavetas na viewport 3D.
- **Lista de Peças:** Acesso direto à tabela de cutlist, fitamento e conferência de chapas.
- **Plano de Corte 2D:** Abre o visualizador gráfico do diagrama de corte de chapas otimizado (*nesting*).
- **Estilos de Visualização (Paleta):** Menu rápido para alternar estilos de visualização de faces (Realista, Sombreado, Branco, Linhas Ocultas), exibir/ocultar arestas de contorno e modo Raio-X (**Alt+X**).
- **Iluminação e Spots Físicos:** Abre o gerenciador de spots, fitas LED e pontos de luz.
- **Render Foto-Realista:** Abre o diálogo de exportação e renderização PBR integrada via Blender Cycles/EEVEE.

### 2.2 Painel de Encaixe Direito (Dock Lateral TrazoMob)
O painel lateral adapta-se de forma inteligente ao contexto do documento:
1. **Modo Sem Seleção / Projeto Geral:** Apresenta ações rápidas para desenhar paredes, criar novos pavimentos e gerenciar a hierarquia do projeto (Pavimento Térreo, Superior, Ambientes Cozinha, Suíte, etc.).
2. **Modo Múltiplos Módulos Selecionados:** Apresenta botões para centralização (XY, X, Y, Z), distribuição equidistante de módulos em vãos e agrupamento em conjunto (*Assembly*).
3. **Modo Parede Selecionada:** Exibe seleção de segmentos, espessura da alvenaria, comprimento milimétrico, pé-direito, botão de pintura/texturização, vista de elevação 2D e comandos para ocultar/reexibir paredes.
4. **Modo Módulo Selecionado:** Ativa o formulário com 5 abas verticais detalhadas:
   - **Medidas:** Largura, altura, profundidade, recuo de rodapé, elevação Z.
   - **Estrutura:** Portas, gavetas, prateleiras, travessas frontais/traseiras, vão cego.
   - **Puxadores:** Modelo (Gola, Cava, Concha, Perfil Alumínio), espessura e acabamento.
   - **Materiais:** Chapa da caixa, chapa da frente, espessura de fitas de borda e cor.
   - **Avançado:** Fundo encaixado/ranhurado, folgas e parametrização especial.
5. **Modo Luz / Spot Selecionado:** Exibe potência (W), temperatura Kelvin (slider de cor), facho de abertura, altura Z e o botão de mira 3D.

---

## 3. Pavimentos, Ambientes e Hierarquia

O TrazoMob possui um sistema hierárquico estruturado para gerenciar residências completas e edifícios de múltiplos pavimentos:

### 3.1 Níveis de Organização
- **Pavimento (Story / Level):** Define a cota vertical base (Z) e o pé-direito padrão (ex.: *Pavimento Térreo*, *1º Andar*).
- **Ambiente (Room):** Subdivisão arquitetônica do pavimento (ex.: *Cozinha*, *Suíte Master*, *Lavanderia*). Cada parede, módulo e bancada pertence a um ambiente específico.

### 3.2 Como Operar Pavimentos e Ambientes
1. No painel lateral, localize o cartão **Pavimentos & Ambientes**.
2. Clique em **➕ Pavimento** para adicionar um novo piso (ex.: "Piso Superior", Altura base = 2.80 m).
3. Clique em **➕ Ambiente** para criar um cômodo dentro do pavimento ativo.
4. Ao desenhar paredes ou inserir móveis, selecione o ambiente no menu dropdown: todas as peças inseridas herdam a classificação para orçamentos e relatórios seletivos por cômodo.
5. Use o botão **👁️ Visibilidade** ao lado do nome do ambiente para ocultar ou exibir todas as paredes e móveis daquele cômodo simultaneamente, facilitando o trabalho em projetos extensos.

---

## 4. Arquitetura de Alvenaria: Paredes, Pisos e Tetos

O TrazoMob inclui um motor dedicado para geração de alvenaria paramétrica 2D/3D com junções em esquadria (*miter joints*) automáticas.

### 4.1 Desenhando Paredes com a Planta Baixa 2D
1. Clique no botão **Construir Paredes** (ou pressione a tecla de atalho **W**).
2. A janela interativa da **Planta Baixa 2D** será exibida com grade milimétrica, controle de snap a ângulos ortogonais (0°, 90°, 180°, 270°) e guia de medidas.
3. Defina a **Espessura da Parede** (padrão: 15 cm) e a **Altura / Pé-Direito** (padrão: 2.60 m ou 2.80 m).
4. Clique no canvas com o botão esquerdo do mouse para marcar o ponto inicial e mova o cursor:
   - Digite o comprimento exato em milímetros ou centímetros no teclado numérico e pressione **Enter** para travar a distância.
   - Pressione **Shift** para forçar travamento estritamente ortogonal.
5. Continue clicando para formar as paredes consecutivas do ambiente.
6. Ao clicar sobre o primeiro vértice ou pressionar **C**, o contorno é fechado automaticamente.
7. Marque as opções:
   - **Gerar Laje de Piso:** Cria um piso 3D no contorno interno do cômodo.
   - **Gerar Teto / Forro:** Cria uma laje superior ou forro de gesso no teto.
8. Clique em **Concluir / Gerar 3D**: o modelo de alvenaria sólida hermética é inserido na viewport 3D instantaneamente.

### 4.2 Edição e Ocultação Seletiva de Paredes
- **Ocultar Paredes para Visão Interna:** Em perspectivas ou renders de cômodos fechados, clique com o botão direito sobre a parede que está na frente da câmera e selecione **👁️ Ocultar Parede**.
- **Seccionar em Paredes Individuais:** Se você desenhou o cômodo como um polígono contínuo e precisa alterar a cor ou remover apenas um segmento de parede, clique com o botão direito e escolha **✂️ Seccionar em Paredes Individuais**.
- **Reexibir Paredes:** No menu de contexto (botão direito no vazio da cena), selecione **👁️ Reexibir Todas as Paredes e Tetos**.
- **Trava de Segurança (Lock):** No painel lateral, ative a opção **🔒 Travar Posição das Paredes e Piso** para evitar arrastar a alvenaria por engano durante a movimentação dos móveis.

---

## 5. Pintura e Revestimento de Paredes

A ferramenta **Wall Paint** permite aplicar cores e revestimentos de forma independente nas faces internas ou externas de cada parede.

### Como Operar:
1. No painel lateral (com uma parede selecionada) ou no menu de contexto, clique em **🎨 Pintar Parede / Revestimento**.
2. A paleta de cores e acabamentos será exibida com coleções pré-configuradas:
   - Cores neutras de alvenaria (Branco Neve, Cinza Urbano, Off-White, Grafite).
   - Revestimentos cerâmicos, porcelanatos e azulejos de cozinha/banheiro.
   - Painéis ripados e texturas decorativas.
3. Escolha se deseja aplicar a pintura na **Face Interna**, **Face Externa** ou na **Parede Inteira**.
4. Clique na cor desejada: a viewport 3D e o motor de materiais para o renderizador Cycles são atualizados imediatamente.

---

## 6. Elevação Técnica 2D com Cotas

Para conferência de projeto executivo, detalhamento de montagem e impressão para a equipe de marcenaria ou cliente, o TrazoMob oferece a ferramenta de **Elevação Técnica 2D**.

### Como Operar:
1. Selecione a parede de fundo desejada na viewport 3D.
2. Na barra lateral, na seção de paredes, clique em **📐 Vista de Elevação 2D**.
3. A janela de desenho ortogonal técnico abre exibindo:
   - A silhueta precisa da alvenaria e dos móveis fixados nela (balcões, rodapés, aéreos, torres).
   - Linhas horizontais e verticais com réguas milimétricas.
   - **Cotas Automáticas de Vãos:** Largura de cada módulo e espaço livre residual restante na parede.
   - **Cotas Verticais de Níveis:** Altura do rodapé, altura da caixa do balcão, espessura da pedra da bancada, vão livre entre bancada e aéreo, e fechamento até o teto.
4. **Controles:**
   - Role a roda do mouse para **Zoom** e arraste com o botão direito ou do meio para **Pan**.
   - Clique em **Salvar Imagem (PNG)** para exportar a elevação em alta definição.
   - Clique em **Imprimir / PDF** para enviar diretamente para a prancha do projeto executivo.

---

## 7. Esquadrias Paramétricas (Portas e Janelas)

As esquadrias no TrazoMob possuem recorte automático de alvenaria (*Boolean Hole Cutting*) totalmente dinâmico e reversível.

### 7.1 Modelos Disponíveis no Catálogo
- **Porta de Giro com Batente:** Folha de madeira com maçaneta e guarnição.
- **Porta de Alumínio e Vidro:** Perfil metálico contemporâneo para varandas e lavanderias.
- **Porta Pivotante de Vidro:** Ideal para halls e entradas sociais.
- **Porta Balcão de Correr (Vidro 170x215 cm):** Folhas de correr para sacadas e áreas gourmet.
- **Janelas de Correr (2 Folhas 130x120 cm / 4 Folhas 190x120 cm):** Para salas e cozinhas.
- **Janelas Maxim-Ar e Basculantes:** Para lavabos, banheiros e lavanderias.

### 7.2 Inserção e Funcionamento do Recorte
1. Na aba **Portas & Janelas** do catálogo ou da ribbon bar, clique na esquadria desejada.
2. Posicione o mouse sobre a parede hospedeira no 3D: a esquadria alinha-se automaticamente à rotação da alvenaria.
3. Ao soltar com o clique, o TrazoMob **fura a parede na hora**, gerando as faces internas da boneca e do vão sem quebras de malha.
4. **Reposicionamento:** Ao mover a esquadria com a ferramenta Mover (**M**), o furo na parede acompanha a posição em tempo real.
5. **Ajuste de Peitoril e Medidas:** Com a janela selecionada, altere a largura, altura ou a altura do **Peitoril (mm)** na barra lateral: a abertura na alvenaria se reajusta instantaneamente.
6. **Desfazer (Ctrl+Z):** Totalmente integrado ao histórico — desfazer a colocação ou movimentação restaura a parede sólida original sem resíduos.

---

## 8. Réguas de Altura e Linhas-Guia Magnéticas

Para manter o alinhamento arquitetônico impecável entre módulos distintos (ex.: alinhar o topo de uma torre quente ao topo de um armário aéreo), o TrazoMob utiliza **Réguas de Altura Inteligentes**.

### 8.1 Presets Padrão do Sistema
- **Nível Rodapé:** 100 mm a 150 mm do piso acabado.
- **Nível Balcão (Corpo):** 820 mm a 850 mm.
- **Nível Bancada Acabada (Tampo de Pedra):** 900 mm.
- **Nível Inferior do Aéreo (Vão Backsplash):** 1.500 mm (geralmente 600 mm acima da bancada).
- **Nível Superior do Aéreo / Torre:** 2.100 mm a 2.300 mm.
- **Nível Fechamento / Teto:** Conforme o pé-direito do ambiente (ex.: 2.600 mm).

### 8.2 Personalização de Réguas
1. Clique no botão **Réguas de Altura** na barra superior.
2. No diálogo de configuração:
   - Adicione, edite ou remova níveis milimétricos.
   - Crie novos presets (ex.: *Linha Cozinha Baixa 85cm*, *Linha Gourmet Alta 92cm*).
3. Ao arrastar um módulo no eixo Z próximo a um desses níveis, o objeto atrai magneticamente para a linha-guia correspondente.

---

## 9. Catálogo e Inserção de Módulos

O TrazoMob possui uma biblioteca completa de módulos paramétricos organizados por tipologias:

### 9.1 Tipos de Módulos Disponíveis
- **Cozinha — Inferiores:**
  - *Balcão com Portas:* portas de giro em regra de 400 mm; largura e divisórias ajustadas automaticamente a partir da 3ª porta.
  - *Balcão Gaveteiro:* 2, 3 ou 4 gavetas com laterais rebaixadas e desconto técnico real de 26 mm para corrediças telescópicas ou invisíveis.
  - *Balcão Misto:* Gaveteiro acoplado + vão com portas.
  - *Balcão de Canto Reto (Cego / L Cego):* Montante frontal cego para junções perpendiculares.
  - *Balcão Canto L (90°):* Duas portas articuladas em ângulo, sobrepostas às laterais; opcionalmente, **batente de quina interna** com a espessura das frentes. Medida padrão: 1000 × 1000 mm.
  - *Porta-Tempero / Toalheiro:* Módulo estreito deslizante de 150 mm a 250 mm.
  - *Balcão Forno Embutido:* Vão ventilado para forno e gavetão inferior.
- **Cozinha — Aéreos:**
  - *Aéreo com Portas:* Portas de giro tradicionais.
  - *Aéreo Basculante Simples:* Porta única com pistão a gás.
  - *Aéreo Basculante Duplo:* 2 portas sobrepostas basculantes.
  - *Aéreo Nicho Micro-ondas:* Vão frontal aberto com prateleira de apoio.
- **Cozinha — Torres de Eletrodomésticos:**
  - *Torre Quente:* Nichos para forno elétrico, micro-ondas e despensas superior e inferior.
  - *Caixa para Geladeira:* Nicho aéreo com fechamento lateral para embutir geladeiras side-by-side.
- **Dormitórios & Armários (Roupeiros):**
  - *Roupeiro Portas de Correr (2 e 3 Vãos):* Trilho superior e inferior embutidos com rodízios.
  - *Armários Cabideiros e Prateleiros:* Opções de 1, 2 e 3 portas de giro com divisórias internas.
- **Banheiro:**
  - *Gabinete Suspenso:* Sem rodapé, gavetão com recorte para sifão e toalheiro.
- **Marmoraria, Bancadas e Tampos:**
  - *Bancada Reta de Pedra:* Com saia frontal e frontispício (rodabanca).
  - *Bancada de Pia com Cuba:* Cuba de inox ou louça esculpida embutida no granito.
  - *Bancada Canto em L:* Bancada inteiriça para cantos de cozinha.
  - *Ilha / Bancada Gourmet:* Balcão em balanço com apoio para banquetas.
- **Peças Avulsas e Componentes:**
  - Laterais avulsas, bases/tampos, réguas de travamento horizontais e verticais, prateleiras e pilares de quina para montagens sob medida especiais.

### 9.2 Como Inserir na Cena
1. Abra a janela principal do TrazoMob ou ative a **Ribbon Bar de Módulos**.
2. Navegue até a categoria desejada e dê um duplo clique no card do módulo (ou clique em **Inserir no Projeto**).
3. O móvel surgirá na viewport 3D na coordenada da câmera ou na parede ativa.

### 9.3 Preenchimento Automático de Parede
Cria uma fileira de módulos contíguos que fecha exatamente um vão da parede selecionada.

1. Selecione uma **face de parede** no 3D.
2. Na seção **🧱 Construtor de Paredes**, ajuste o campo **Comprimento**.
   - Ele já vem preenchido com o comprimento do segmento selecionado.
   - Se você informar um vão menor, o preenchimento fica centralizado na face.
3. Em **Preenchimento Automático**, para os inferiores escolha a composição:
   - **Balcões com portas**
   - **Balcões + gaveteiros**
   - **Somente gaveteiros**
4. Clique em **Preencher Inferiores** ou **Preencher Aéreos**.
5. Os módulos são gerados encostados na parede, contíguos e com a sobra distribuída entre eles, sem ultrapassar os limites técnicos.
6. Todo o preenchimento entra como **um único passo de Desfazer (Ctrl+Z)**.

Observações:
- Inferiores usam balcões de até 4 portas, com divisórias automáticas a partir da 3ª porta.
- Aéreos usam sempre armários com portas (até 2 portas por módulo).
- A composição mista e gaveteiros valem apenas para os inferiores.
- O comando não remove nem desloca móveis já existentes na parede; se ela já estiver ocupada, os novos módulos podem sobrepor os anteriores. Desfaça com **Ctrl+Z** se necessário.

---

## 10. Edição Paramétrica na Barra Lateral

Ao clicar em qualquer armário da cena, a barra lateral direita ativa suas 5 abas de personalização:

```
┌──────────────────────────────────────────────┐
│  🪵 TrazoMob — Balcão com Portas             │
├──────────────────────────────────────────────┤
│ [📐 Medidas] [🪚 Estrutura] [🔘 Puxadores]   │
│ [🎨 Materiais] [⚙️ Avançado]                  │
├──────────────────────────────────────────────┤
│ Largura (mm):      [  800  ] [ -50 ] [ +50 ] │
│ Altura (mm):       [  720  ] [ -50 ] [ +50 ] │
│ Profundidade (mm): [  550  ] [ -50 ] [ +50 ] │
│ Altura Rodapé:     [  100  ]                 │
│ Elevação (Z):      [    0  ]                 │
└──────────────────────────────────────────────┘
```

### 10.1 Aba 1: Medidas Principais
- **Largura, Altura e Profundidade (mm):** Controle milimétrico com botões de incremento rápido (+/- 50 mm e +/- 100 mm).
- **Altura do Rodapé (mm):** Define a altura do recuo inferior (ex.: 100 mm). Se for um módulo suspenso, desmarque a opção de rodapé.
- **Recuo Frontal do Rodapé:** Afastamento da testeira do rodapé em relação ao alinhamento da frente das portas.
- **Elevação Z (Cota do Piso):** Altura da base do móvel em relação ao chão (essencial para aéreos, normalmente em Z = 1.500 mm).

### 10.2 Aba 2: Frentes & Estrutura
- **Controle de Portas:**
  - Habilitar/Desabilitar portas.
  - Quantidade de portas (1, 2, 3...).
  - Sentido de abertura (Giro para Esquerda, Giro para Direita ou Basculante).
- **Controle de Gavetas:**
  - Quantidade de gavetas (1 a 6 gavetas).
  - Distribuição automática de altura das frentes ou gavetão inferior expandido.
- **Prateleiras Internas:** Número de prateleiras internas com cálculo equidistante automático.
- **Travessas Superiores:** Opção de travessa deitada (padrão) ou travessa em pé (para travamento sob cubas pesadas de granito).
- **Vão Cego / Canto:** Configuração da largura da frente cega para módulos de canto reto.

### 10.3 Aba 3: Puxadores & Perfis
- Escolha entre puxadores convencionais ou sistemas sem puxador aparente (Perfil Gola de alumínio, Cava usinada a 45°, Puxador de Alça Metálica ou Sistema Fecho-Toque / Tip-on).

### 10.4 Aba 4: Materiais & Fitas
- **Chapa da Caixa:** Padrão de MDF da carcaça interna (ex.: MDF Branco TX 15mm ou 18mm).
- **Chapa das Frentes:** Padrão de acabamento das portas e gavetas (ex.: MDF Louro Freijó, Cinza Sagrado, Laca).
- **Chapa do Fundo:** Espessura do fundo (6mm ranurado ou 15mm parafusado por trás).
- **Fita de Borda Padrão:** Seleção de espessura de fita (0.45 mm para interiores; 1.0 mm ou 2.0 mm de alto impacto para portas e frentes).

### 10.5 Aba 5: Ajustes Especiais e Avançados
- **Espessura das Chapas (mm):** Alterne entre 15mm, 18mm ou 25mm para laterais, bases e prateleiras.
- **Recuo Superior da Porta (mm):** Folga necessária entre o topo da porta e a pedra da bancada para abertura sem puxador (ex.: 25mm a 35mm para puxadores perfil Gola).
- **Ajuste Fino de Folgas:** Folga perimetral entre portas vizinhas (padrão: 3 mm).

---

## 11. Perfis e Puxadores de Alumínio

O TrazoMob possui um **Motor de Extrusão Paramétrica de Perfis de Alumínio** (definido em `perfis.py` e `perfis_editor.py`), permitindo detalhamento milimétrico de perfis Gola, perfis puxadores lineares e cavas.

### Como Operar a Biblioteca de Perfis:
1. Na barra lateral (Aba *Puxadores & Perfis*), clique em **📂 Biblioteca de Perfis...**.
2. O diálogo abre a biblioteca gráfica vetorial dos perfis:
   - **Perfil Gola Superior (L):** Para balcões logo abaixo do tampo.
   - **Perfil Gola Central (C / Duplo):** Entre gavetas para abertura dupla.
   - **Perfil Cava J:** Puxador de alumínio fixado no topo da chapa de 18mm.
   - **Perfil Alça / Concha Embutida:** Usinagens rentes à face.
3. Cada perfil exibe o desenho técnico de corte transversal (seção paramétrica milimétrica), espessura de encaixe e peso por metro linear.
4. Clique em **Aplicar ao Módulo Selecionado** para reconstruir o armário com os descontos exatos nas travessas e laterais para alojar o alumínio.

---

## 12. Snapping Magnético e Posicionamento

A movimentação de módulos no TrazoMob utiliza um algoritmo de colisão e atração vetorial em tempo real (`magnetic_drag.py`).

### 12.1 Aderência a Paredes (Wall Snapping)
- Ao arrastar um balcão ou aéreo em direção a uma parede, o módulo **gira automaticamente** para alinhar suas costas com a superfície da parede.
- O móvel cola na face interna da parede sem atravessar a alvenaria.

### 12.2 Encaixe Módulo a Módulo (Edge Snapping)
- Aproxime um balcão da lateral de outro balcão já posicionado: a uma distância de até 80 mm, o sistema gera uma **atração magnética**, encostando perfeitamente as laterais e nivelando as frentes e alturas.

### 12.3 Cotas Dinâmicas Projetadas
- Durante o arraste, linhas pontilhadas de cota aparecem na viewport 3D exibindo em tempo real:
  - Distância do móvel até o canto esquerdo da parede.
  - Distância do móvel até o canto direito da parede.
  - Vão livre até o armário vizinho mais próximo.

### 12.4 Rotação Rápida
- Pressione os botões **↺ Girar 90° Anti-horário** ou **↻ Girar 90° Horário** na barra de ferramentas para rotacionar o armário ortogonalmente em torno do seu centro de massa sem perder o alinhamento.

---

## 13. Alinhamento, Distribuição e Grupos (Assemblies)

Quando mais de um módulo é selecionado simultaneamente na cena (usando a tecla **Ctrl** ou a ferramenta de seleção por janela), o painel lateral exibe a central de alinhamento em lote (`align_tools.py` e `assembly.py`):

### 13.1 Centralização Automática
- **✛ Centro (XY):** Centraliza o módulo secundário perfeitamente no centro de largura e profundidade do móvel base (ex.: centralizar um cooktop ou uma cuba sobre um balcão).
- **↔ Largura (X):** Centraliza no eixo horizontal.
- **↕ Profundidade (Y):** Centraliza no sentido frente-fundo.
- **⬍ Altura (Z):** Alinha os centros verticais.

### 13.2 Distribuir Módulos no Vão
- Selecione 3 ou mais módulos colocados entre duas paredes ou extremidades:
- Clique em **↔ Distribuir Módulos no Vão**: o TrazoMob calcula o vão residual livre e divide os módulos com espaçamento rigorosamente uniforme ou preenche o vão contiguamente com ajustes de arremate/fechamento.

### 13.3 Agrupamento Inteligente (Assembly)
- **📦 Agrupar Módulos Selecionados:** Transforma vários módulos avulsos (ex.: bancada + 3 balcões + torre) em um conjunto único coeso (*Assembly*).
  - O grupo pode ser movido ou duplicado como um único bloco.
  - Os módulos internos continuam **100% paramétricos** (dê duplo clique para editar um armário interno).
- **📤 Desagrupar:** Dissolve o grupo devolvendo os móveis soltos ao modelo sem perder nenhuma medida ou acabamento.

---

## 14. Cinemática 3D e Detecção de Colisões

O TrazoMob possui cinemática real de ferragens para verificar interferências antes da fabricação (`interact.py` e `collision.py`).

### 14.1 Interação Dinâmica
- **Atalho no Teclado (Tecla I):** Ativa a ferramenta interativa de clique. Clique diretamente na porta ou gaveta na viewport 3D para abri-la ou fechá-la.
- **Slider Contínuo (0% a 100%):** No painel lateral (cartão *Abertura Dinâmica 3D*), deslize a barra para abrir progressivamente todas as portas e gavetas em conjunto.
- **Botões Rápidos:** Clique em **Fechar (0%)**, **50%** ou **100%** para conferência visual rápida da cena.

### 14.2 Teste Automático de Colisões
- Com as portas ou gavetas abertas, clique no botão **⚠️ Testar Colisões**:
- O algoritmo calcula as caixas delimitadoras colidentes (AABB / OBB) entre:
  - Frentes de gavetas abertas e puxadores de armários vizinhos em L.
  - Portas basculantes abertas batendo no teto ou luminárias pendentes.
  - Portas de canto batendo na alvenaria ou bancadas.
- Caso haja interferência, um banner vermelho alerta o usuário e destaca as peças colidentes na tela.

---

## 15. Luminotécnica e Spots Físicos

O sistema luminotécnico do TrazoMob (`light_tools.py`) simula física real de luz para projetos de interiores e marcenaria de alto padrão.

### 15.1 Inserção de Luminárias
1. Clique no botão de **Iluminação** na barra superior para abrir o gerenciador.
2. Escolha o tipo de fonte de luz:
   - **Spot Direcionável:** Emite cone de luz cônico para iluminação pontual de bancadas, nichos ou quadros.
   - **Fita LED Linear:** Perfil retangular de iluminação contínua (ex.: sob armários aéreos ou painéis ripados).
   - **Ponto Omni (360°):** Lâmpada esférica para plafons, pendentes e arandelas.
3. Clique na cena 3D para posicionar a luminária.

### 15.2 Ajustes Fotométricos e Mira 3D
- **Temperatura de Cor (Kelvin):**
  - *2400K - 2700K:* Branco Muito Quente / Âmbar (dormitórios e cabeceiras).
  - *3000K:* Branco Quente (salas e aconchego).
  - *4000K:* Branco Neutro (cozinhas, bancadas e áreas de corte).
  - *6500K:* Luz Fria do Dia (corporativo).
- **Potência (Watts / Lúmens):** Ajuste de intensidade de emissão.
- **🎯 Mirar Spot no 3D:** Clique neste botão e em seguida clique sobre o ponto exato da bancada, pia ou fogão onde o centro do facho luminoso deve atingir. O spot orienta seu vetor angular automaticamente.
- **Fotometria IES:** Carregue arquivos `.ies` de fabricantes (Stella, Brilia, Philips) para reproduzir curvas reais de emissão ótica no renderizador.

---

## 16. Materiais PBR e Render Foto-Realista

O TrazoMob possui integração nativa com o **Blender Cycles / EEVEE** (`render_engine.py` e `render_dialog.py`) para renderizar imagens de catálogo foto-realistas diretamente do projeto.

### 16.1 Editor de Materiais PBR (`material_editor_dialog.py`)
1. No menu TrazoMob, abra o **Editor de Materiais**.
2. Cada material da cena (Madeiras, Chapas de MDF, Granitos, Metais, Vidros) pode ser calibrado com propriedades físicas reais:
   - **Rugosidade (Roughness):** De 0.05 (espelhado/alto brilho) a 0.80 (fosco/acetinado).
   - **Relevo (Bump / Normal Map):** Simula os veios em relevo da madeira e poros de pedras.
   - **Especular e Verniz (Clearcoat):** Camada de reflexo vítreo sobre lacas automotivas.
   - **Transmissão (Vidros e Espelhos):** Transparência e índice de refração (IOR).

### 16.2 Executando o Render Foto-Realista
1. Posicione a câmera do IngeTrazo no ângulo desejado.
2. Clique no botão **Render Foto-Realista** na barra superior.
3. No painel de renderização:
   - Escolha o motor: **Blender Cycles** (máxima fidelidade física de raios) ou **EEVEE** (renderização rápida em tempo real).
   - Escolha a resolução (Full HD 1080p, 2K ou 4K).
   - Selecione a qualidade de amostragem (*Samples* e Denoiser OpenImageDenoise).
4. Clique em **Renderizar**: o TrazoMob exporta a geometria sem oclusões de malha e gera a imagem com sombras suaves, reflexos e iluminação global.

---

## 17. Cutlist, Fitamento e Furações

O motor de fabricação (`dialog_cutlist_tab.py`, `parts.py` e `machining.py`) analisa toda a montagem para extrair a lista completa de produção.

### 17.1 Extração Automática de Peças
A lista de peças identifica automaticamente cada componente:
- Laterais (esquerda e direita)
- Base inferior e Tampo superior
- Prateleiras móveis e fixas
- Travessas de sustentação (deitadas e em pé)
- Divisórias internas
- Fundo do armário
- Frentes de gavetas e caixas internas
- Portas de giro ou basculantes

### 17.2 Controle de Fitamento de Borda
Para cada peça, é exibido o mapa de fitas nos 4 lados:
- **C1 e C2:** Bordas dos dois comprimentos da chapa.
- **L1 e L2:** Bordas das duas larguras da chapa.
- **Botões de Aplicação Rápida:**
  - *4 Lados:* Aplica fita em todo o contorno (padrão para frentes e portas).
  - *1 Comp.:* Aplica fita apenas na face frontal aparente (padrão para prateleiras e laterais).
  - *2 Comp.:* Aplica nas duas bordas longitudinais.
  - *Limpar:* Remove fitamento da peça selecionada.
- **Espessura da Fita:** Alterne com um clique entre 0.45 mm, 1.0 mm ou 2.0 mm.

### 17.3 Veio da Madeira e Furações Técnicas
- **Sentido do Veio:** Marque a caixa de seleção de veio para garantir que as portas e painéis amadeirados sejam cortados com as fibras alinhadas vertical ou horizontalmente.
- **Furações Automatizadas (`machining.py`):** Gera automaticamente a furação para caneco de dobradiças de 35 mm (com distâncias de 100 mm das pontas), furos de corrediças nos passos padrão do sistema 32 mm, e furações para dispositivos Minifix / Cavilhas.

---

## 18. Otimizador de Corte 2D (Nesting)

O módulo `optimizer.py` e `cut_plan_viewer.py` realiza o aproveitamento otimizado de chapas de MDF.

### Como Gerar e Analisar o Plano de Corte:
1. Na barra superior ou no diálogo principal, clique em **Plano de Corte 2D**.
2. O otimizador calcula o arranjo das peças considerando:
   - Tamanho bruto da chapa (padrão: 2.750 x 1.830 mm ou personalizável).
   - Espessura de corte do disco da serra (*Kerf*, padrão: 4 mm).
   - Refilo perimetral de limpeza das bordas (padrão: 10 a 15 mm).
   - Respeito obrigatório ao sentido do veio da madeira.
3. O visualizador gráfico exibe cada chapa numerada com cores distintas por módulo.
4. **Métricas de Eficiência:** Exibe a porcentagem de aproveitamento útil da chapa (ex.: 89,4% de aproveitamento) e metragem linear total de cortes da serra.

---

## 19. Etiquetas Técnicas com Código de Barras

Para uso na marcenaria ou fábrica de corte, o TrazoMob possui um gerador nativo de **Etiquetas Técnicas** (`production_labels.py`).

### Recursos das Etiquetas:
- **Tamanho Padrão:** Compatível com impressoras térmicas (ex.: Zebra, Argox, Elgin nos formatos 100x60mm ou folhas A4).
- **Conteúdo da Etiqueta:**
  - Nome da Peça e Nome do Armário Pai.
  - Medida final acabada (Comprimento x Largura x Espessura em mm).
  - Medida de corte bruto na serra.
  - Indicadores gráficos das 4 bordas para fitamento (C1, C2, L1, L2).
  - Padrão de acabamento do MDF.
  - **Código de Barras Code 128 / Code 39:** Desenhado nativamente para leitura ótica por leitores de código de barras na linha de montagem e etiquetagem da chapa.
- **Operação:** Na aba de Cutlist, clique em **🏷️ Etiquetas de Produção** e escolha entre imprimir a lista completa ou apenas as peças do módulo selecionado.

---

## 20. Precificação e Propostas Comerciais

O TrazoMob inclui um **Motor Completo de Orçamentação e Precificação** (`pricing.py` e `production_report.py`).

### 20.1 Itens Calculados Automaticamente
- **Chapas de MDF:** Custo fracionado proporcional à área consumida e perda de retalhos.
- **Fitas de Borda:** Metragem linear consumida multiplicada pelo valor do metro linear da fita.
- **Ferragens:** Dobradiças com amortecedor, corrediças telescópicas, puxadores, pistões a gás, cantoneiras e dispositivos de união.
- **Mão de Obra e Fabricação:** Taxa horária ou percentual configurável de fabricação e montagem.
- **Markup, Impostos, Frete e Descontos:** Aplicação direta de margem de lucro operacional e tributos.

### 20.2 Geração de Documentos Executivos
Na aba da Cutlist, você pode gerar:
1. **📄 Relatório Executivo HTML:** Documento técnico completo com tabela de materiais, área em m², metros de fita e lista analítica de peças.
2. **💼 Proposta Comercial (PDF / HTML):** Proposta formal pronta para entrega ao cliente final, contendo dados da empresa de marcenaria, dados do cliente, discriminação dos ambientes (Cozinha, Quarto, etc.), valores consolidados, condições de pagamento e campos de assinatura de contrato.

---

## 21. Exportação, Integrações Externas e Atalhos

### 21.1 Exportação e Integrações
- **Copiar p/ TrazoMob (Ctrl+V):** Copia os dados da cutlist para a área de transferência no formato aceito pelo software TrazoMob de fábrica.
- **Exportar CSV:** Gera arquivo de planilha compatível com Microsoft Excel, LibreOffice Calc, CorteCloud e Promob Cut.
- **Exportar JSON:** Exporta toda a árvore de dados paramétricos para automações e ERPs industriais.

### 21.2 Tabela Resumida de Teclas de Atalho

| Atalho | Função | Descrição |
| :---: | :--- | :--- |
| **W** | **Construir Paredes** | Abre o editor de Planta Baixa 2D para alvenaria |
| **I** | **Interagir** | Ativa o cursor para abrir e fechar portas e gavetas no 3D |
| **M** | **Mover** | Movimenta móveis, esquadrias e lâmpadas no 3D |
| **R** | **Rotacionar** | Rotaciona objetos manualmente |
| **Alt + X** | **Modo Raio-X** | Alterna transparência para visualização de interiores |
| **Ctrl + Z** | **Desfazer** | Desfaz a última ação (incluindo recortes de alvenaria) |
| **Ctrl + Y** | **Refazer** | Refaz a ação desfeita no histórico |
| **Ctrl + Clique** | **Seleção Múltipla** | Seleciona vários armários para alinhamento ou agrupamento |
| **Delete** | **Excluir** | Remove o módulo, parede ou luminária selecionada |

---

## 22. Biblioteca de Componentes do Usuário

O TrazoMob não hospeda, baixa nem redistribui modelos de terceiros. O que
existe aqui é um **índice dos arquivos que o próprio usuário já possui** —
uma geladeira baixada do 3D Warehouse, o catálogo de um fabricante, um
modelo comprado de um artista. O aplicativo apenas registra onde o arquivo
está, o que ele é e como deve ser lido; a coleção continua sendo do usuário.

### 22.1 Onde a biblioteca aparece
- **Painel Componentes → Minha biblioteca…:** grade com busca e filtros por
  categoria, tipo e marca; inserir, editar e remover.
- **Painel Componentes → Importar componente…:** abre a ficha de importação
  de um arquivo e, ao confirmar, já o coloca na cena.
- **Aba Decoração → ⭐ Meus Componentes:** um botão por marca, com a
  quantidade (`Brastemp (4)`); o clique abre a biblioteca já filtrada por
  aquela marca. Há também `Todos`, `Importar…` e `Gerenciar…`.

### 22.2 Ficha de importação
Preencha o que ajuda a achar o modelo depois: **nome, categoria, tipo**
(geladeira, fogão, sofá…), **marca, modelo, tags, fonte, licença, autor** e
**notas**. As medidas **L × P × A** podem ser tiradas do próprio arquivo
(botão *Medir*) e são usadas para ajustar o modelo ao tamanho real.

Como o formato não declara unidade nem eixo vertical, informe a **unidade do
arquivo** (m, cm, mm, in, ft) e o **eixo vertical**: *Z up* para IngeTrazo e
SketchUp, *Y up* para Blender e boa parte do 3D Warehouse. A escolha fica
gravada com o componente, então as próximas inserções não perguntam nada.

### 22.3 Gerenciado ou referência
- **Copiar para a biblioteca (gerenciado):** o arquivo e seus anexos (MTL,
  texturas, `.bin`) são copiados para dentro da biblioteca. Mover ou apagar o
  original não quebra o componente. É o modo de um arquivo avulso.
- **Apenas indexar (referência):** só o caminho é guardado; nada é copiado.
  É o modo de **Adicionar pasta…**, que percorre a pasta (e as subpastas) e
  transforma os nomes das pastas em tags. Se o arquivo sumir, a ficha avisa
  *(missing)* e continua lá para ser relocalizada ou removida — o original
  nunca é apagado.

### 22.4 Formatos e onde ficam os arquivos
Formatos lidos: **OBJ, GLB, DAE, STL, SKP e IGZ**. As miniaturas são
desenhadas a partir da geometria, uma por vez, conforme você rola a grade.

A biblioteca é global (compartilhada por todos os documentos) e fica em:

| Sistema | Pasta |
| :--- | :--- |
| Windows | `%LOCALAPPDATA%\IngeTrazo\components` |
| macOS | `~/Library/Application Support/IngeTrazo/components` |
| Linux | `~/.local/share/ingetrazo/components` |

A variável de ambiente `INGETRAZO_COMPONENTS` aponta para outra pasta (outro
disco, uma pasta de rede). O botão **Abrir pasta** leva direto ao local.

### 22.5 Licenças
O aplicativo apenas indexa o que já é seu. A licença de origem continua
valendo: modelos do 3D Warehouse, por exemplo, podem ser usados em projetos,
mas não podem ser agregados, redistribuídos nem revendidos como catálogo.
Registre a licença e o autor na ficha — é o que permite provar a procedência
depois.

---

*Manual elaborado para o TrazoMob — IngeTrazo CAD 3D.*


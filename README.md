# LABRA-AGU: Agente de IA Pericial e Investigativo

O **Laboratório de Recuperação de Ativos (LABRA)**, vinculado à Advocacia-Geral da União (AGU), tem como missão o rastreamento, asfixia financeira e recuperação de bens e direitos desviados da União (corrupção, fraudes fiscais, lavagem de dinheiro, improbidade). 

Este repositório contém a implementação em Python do **Agente de IA Pericial**, projetado especificamente para combater a **blindagem patrimonial** automatizando a análise de dados jurídicos caóticos (juntas comerciais, cartórios, COAF, etc.).

## O que este Agente faz?

O Agente atua como um sistema investigativo proativo baseado em quatro diretrizes centrais e um motor de ingestão multimodal:

1. **Ingestão Multimodal (Os Olhos e Ouvidos)**: O Agente processa praticamente qualquer tipo de prova material. Ele extrai texto, CPFs, e transações de PDFs (processos), DOCX (contratos), CSV/TXT (extratos), arquivos ZIP, e até transcreve áudios e vídeos (MP3, MP4, WAV) de escutas telefônicas ou depoimentos.
2. **Parsing Estruturado (As Mãos)**: Recebe documentos não estruturados da ingestão, usa Modelos de Linguagem (LLMs) via `Pydantic` e extrai entidades normatizadas (CPFs, CNPJs, Relações Societárias e Transações).
3. **Investigação Contínua (O Cérebro)**: Rastreia nexo causal e descobre anomalias complexas (ex: triangulação cíclica de quotas transferidas para offshores administradas por parentes).
4. **Filtro Sub-simbólico ACT-R (O Filtro)**: Avalia milhares de movimentações e aplica a fórmula de ativação de memória matemática (ACT-R). Eventos altamente conectados aos devedores e temporalmente recentes ganham score alto, evitando que a IA sofra "alucinação" com dados inúteis.
5. **Relatório Pericial com Rastreabilidade**: Traduz o achado em uma narrativa jurídica conclusiva, listando os documentos que deram origem ao alerta (cadeia de custódia da prova).

## Como ele interage com o HeraclitusDB?

A genialidade da arquitetura reside em sua separação de papéis. O Agente é puramente analítico (Python) e roda desacoplado do banco de dados vetorial de topologia geométrica (HeraclitusDB, feito em Rust).

**O fluxo de integração segue 3 etapas via gRPC:**

### 1. Conexão Bidirecional
O Agente abre uma conexão de alta performance com o **HeraclitusDB** utilizando `grpcio` nativo (na porta `:7474`). Ele utiliza a função `Subscribe(from_lsn)` para ouvir eventos financeiros fluindo dos sistemas da União para o Log Central do banco em tempo real.

### 2. Eventos Imutáveis
O Agente **jamais altera ou exclui** um registro. Ao constatar uma fraude através de sua motor cognitivo, ele forja um payload JSON estruturado (`INSIGHT_PERICIAL_FRAUDE`) e devolve para o banco via gRPC `AppendRequest()`.

Para manter a causalidade forense, o agente passa no campo `parents` os identificadores geográficos dos eventos-fonte que basearam a descoberta.

### 3. Absorção Geométrica (Magia do HeraclitusDB)
O HeraclitusDB armazena esse novo `Episódio`. Durante a compactação LSM em background:
- O banco lê as chaves do Insight.
- Reposiciona as coordenadas do Devedor, da Empresa Laranja e da Offshore, **aproximando-os radicalmente** nas geometrias hiperbólicas e esféricas contidas na sua `Product Manifold`.
- Quando o dashboard do **Power BI** da Procuradoria-Geral da União consulta as Visualizações (`Read Views`), a fraude surge como um hub de grafos altamente correlacionado e pronto para pedido judicial de bloqueio patrimonial.

---

## Como Rodar o Agente

### Pré-requisitos
- Python 3.9+
- HeraclitusDB rodando na porta local `:7474` com protocolo gRPC ativo.

### Instalação
```bash
# Clone e entre no projeto
git clone https://github.com/JoseRFJuniorLLMs/LABRA-AGU.git
cd LABRA-AGU

# Instale os requerimentos
pip install -r requirements.txt

# Compile os stubs do gRPC caso não os tenha no SO
python build.py
```

### Executando a Investigação
```bash
python main.py
```
O console exibirá o loop conectando-se ao HeraclitusDB, analisando sub-grafos e disparando sentenças de fraude para o banco quando limites geométricos forem violados.

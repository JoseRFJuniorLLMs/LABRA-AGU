<p align="center">
  <img src="img/logo_labra.svg" alt="Logo LABRA-AGU" width="300">
</p>

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

**Modo one-shot** (analisa um documento e termina):
```bash
python main.py                      # simulação embutida
python main.py --file extrato.pdf   # PDF, DOCX, CSV, TXT, ZIP, MP3, MP4
```

**Modo daemon** (o agente vive subscrito ao log e reage a tudo que entra):
```bash
python main.py --daemon
```

### Como interagir com o agente em execução

Toda interação acontece **através do log** — nunca por canal lateral. A
tua ordem é, ela própria, um evento imutável e auditável:

```bash
# Chegou um banco novo? Deposita os documentos no rio; o daemon analisa:
python ingest.py --file extrato_banco_novo.pdf --ref "OFICIO_1234/2026"

# Queres que ele olhe para algo específico? Envia uma DIRETRIZ:
python directive.py --alvo CPF_645.254.302-49 \
    --foco "transferencias para offshores" \
    --padrao fracionamento --padrao vespera_constricao --boost 8
```

A DIRETRIZ dá **boost de ativação ACT-R** aos alvos (o agente passa a
"pensar mais" neles) e pode restringir o catálogo de padrões. Todo insight
influenciado por uma diretriz carrega o ULID dela em `parents` — fica
provado *quem mandou investigar o quê, e o que resultou disso*.

### Catálogo de Padrões de Fraude (`agent/patterns.py`)

| Padrão | O que deteta | Severidade |
|---|---|---|
| `triangulacao_offshore` | Quotas vendidas a entidade que nomeia procurador com plenos poderes | ALTA (CRITICA se familiar) |
| `fracionamento` | ≥3 transferências abaixo do limiar COAF somando valor relevante (smurfing) | ALTA |
| `laranja_familiar` | Plenos poderes outorgados a familiar do devedor (interposta pessoa) | ALTA |
| `vespera_constricao` | Dissipação patrimonial até 30 dias antes de penhora/citação/bloqueio | CRITICA |

Padrão novo = uma função e uma entrada no catálogo. Nada mais muda.

### Teste de Integração (end-to-end, local)

Com o `heraclitus-server` rodando em `localhost:7474`:

```bash
# No repositório HeraclitusDB:
cargo run --release -p heraclitus-server

# Neste repositório:
python test_integration.py
```

O teste percorre o ciclo completo da **cadeia de custódia**:

1. O documento-fonte é gravado como evento imutável no log (`Append`);
2. O LSN é resolvido para o **ULID real** atribuído pelo banco (`Query`);
3. O motor investigativo detecta a triangulação e gera o insight;
4. O insight entra no log com `parents = [ULID do documento]`;
5. `PROVENANCE(insight)` devolve exatamente o documento-fonte;
6. O insight é consultável por GQL e o payload pericial sobrevive intacto;
7. `AS OF LSN` prova que o insight é invisível em snapshots do passado.

> **Nota de integridade:** o HeraclitusDB rejeita `parents` que não sejam
> ULIDs válidos. Referências documentais humanas (números de processo,
> protocolos de junta) não vão em `parents` — vão em `attrs.source_refs`.
> A proveniência criptográfica usa sempre os ULIDs reais do log.

<p align="center">
  <img src="img/logo_labra.svg" alt="Logo LABRA-AGU" width="300">
</p>

# LABRA-AGU: Agente de IA Pericial e Investigativo

O **Laboratório de Recuperação de Ativos (LABRA)**, vinculado à Advocacia-Geral da União (AGU), tem como missão o rastreamento, asfixia financeira e recuperação de bens e direitos desviados da União (corrupção, fraudes fiscais, lavagem de dinheiro, improbidade).

Este repositório contém a implementação em Python do **Agente de IA Pericial**, projetado para combater a **blindagem patrimonial** automatizando a análise de dados jurídicos caóticos (juntas comerciais, cartórios, COAF, extratos bancários, escutas).

> 📖 **Novo por aqui? Comece pelo [TUTORIAL completo](docs/TUTORIAL.md)** — do zero ao primeiro insight pericial em 10 minutos.

## Arquitetura — sentidos, rio e cérebro

![Diagrama de Arquitetura LABRA-AGU](img/arquitetura.png)

```
Bancos da AGU (Oracle, MSSQL, Postgres...) ──┐
Pasta de depósito (PDF, DOCX, MP3, MP4...) ──┤
                                             ▼
                                       pipeline.py            ← OS SENTIDOS (ingere, sem opinar)
                                             │ Append (gRPC :7474)
                                             ▼
                                  ┌─────────────────────┐
                                  │    HeraclitusDB     │     ← O RIO (log imutável, custódia
                                  │  log append-only    │        criptográfica, proveniência)
                                  └──────────┬──────────┘
                          Subscribe │        │ Append (insights)
                                    ▼        │
                              main.py --daemon               ← O CÉREBRO (investiga, sem tocar
                          parser → padrões → ACT-R              nas fontes)
                                    ▲
                              directive.py                   ← A PROCURADORIA (ordens são
                          (DIRETRIZ como evento no log)         eventos auditáveis)
```

A separação de papéis é estrita: o pipeline **ingere sem opinar**; o agente **investiga sem tocar nas fontes**; a Procuradoria **ordena através do log**. Os três só se falam pelo rio — toda interação é um evento imutável, auditável e com proveniência.

## O que este Agente faz?

1. **Ingestão Multimodal (Os Olhos e Ouvidos)**: processa praticamente qualquer prova material — PDFs (processos), DOCX (contratos), CSV/TXT (extratos), ZIP, e transcreve áudios e vídeos (MP3, MP4, WAV) de escutas e depoimentos. Via `pipeline.py`, conecta **qualquer banco de dados** da AGU (qualquer dialeto SQLAlchemy) com sincronização incremental e checkpoints idempotentes.
2. **Parsing Estruturado (As Mãos)**: extrai entidades normatizadas (CPFs, CNPJs), relações societárias, transações e marcos judiciais (`agent/parser.py`). Há **resolução de entidades** (`agent/entities.py`) — o mesmo CPF escrito de formas diferentes vira um único nó, com validação de dígitos verificadores — e um **parser por LLM opcional** (`agent/llm_parser.py`, Claude com saída estruturada) que cai graciosamente para o determinístico.
3. **Correlação Multi-Fonte (O Cérebro)**: o daemon acumula entidades e relações num **grafo de caso** (`agent/graph.py`) e corre os padrões sobre o grafo consolidado. A fraude espalhada por **vários bancos E documentos em simultâneo** — venda de quotas no banco da Junta, procuração no banco do Cartório, transferências no banco do COAF, vínculo familiar num PDF — é detectada como um todo, e a proveniência do alerta aponta para **todas** as fontes que o sustentam. Um único `pipeline.py --config sources.json` ingere de todos os bancos e pastas ao mesmo tempo. CPF/CNPJ crus dos bancos (`52998224725`) e tokens de documentos (`CPF_xxx`) resolvem para o **mesmo nó**.
4. **Filtro Sub-simbólico ACT-R (O Filtro)**: a fórmula de ativação de memória ACT-R prioriza entidades recorrentes e recentes; **DIRETRIZes da Procuradoria dão boost dirigido** aos alvos de interesse.
5. **Relatório Pericial com Rastreabilidade**: cada insight carrega narrativa jurídica conclusiva, severidade, ativações ACT-R reais e `parents` apontando para os ULIDs de **todos** os documentos-fonte e diretrizes que o sustentam. O `relatorio.py` gera o laudo em Markdown; a cadeia de custódia é verificável por `PROVENANCE`. Insights são **deduplicados** (não há alertas repetidos) e o dedup é reconstruído do próprio log a cada arranque.

## Início rápido

```bash
# 1. HeraclitusDB (o rio) — em github.com/JoseRFJuniorLLMs/HeraclitusDB:
cargo run --release -p heraclitus-server     # gRPC :7474, REST :7475

# 2. O agente:
git clone https://github.com/JoseRFJuniorLLMs/LABRA-AGU.git && cd LABRA-AGU
pip install -r requirements.txt
python build.py                              # gera os stubs gRPC

# 3. O cérebro, vivo:
python main.py --daemon

# 4. Noutro terminal — alimenta o rio e dá ordens:
python ingest.py --file extrato.pdf --ref "OFICIO_1234/2026"
python directive.py --alvo CPF_645.254.302-49 --foco "offshores" --boost 8
python pipeline.py --db "sqlite:///legado.db" --table movs --incremental id --once
```

Guia passo a passo, com exemplos de saída, consultas GQL, como criar padrões novos e resolução de problemas: **[docs/TUTORIAL.md](docs/TUTORIAL.md)**.

## Catálogo de Padrões de Fraude (`agent/patterns.py`)

| Padrão | O que deteta | Severidade |
|---|---|---|
| `triangulacao_offshore` | Quotas vendidas a entidade que nomeia procurador com plenos poderes | ALTA (CRITICA se familiar) |
| `fracionamento` | ≥3 transferências abaixo do limiar COAF somando valor relevante (smurfing) | ALTA |
| `laranja_familiar` | Plenos poderes outorgados a familiar do devedor (interposta pessoa) | ALTA |
| `vespera_constricao` | Dissipação patrimonial até 30 dias antes de penhora/citação/bloqueio (por devedor) | CRITICA |
| `suborno` | Pagamento de propina / vantagem indevida a agente público (corrupção ativa) | CRITICA |
| `antedatacao` | Data de um registo **retroagida** para antes do marco, mas a edição feita **depois** dele | CRITICA |
| `registro_apagado` | Registo **apagado** (DELETE no change-log) em/após o marco judicial — destruição de prova | CRITICA |

Os três últimos juntam-se aos esquemas avançados de `agent/asset_shield.py` (doação cruzada, holding/usufruto, offshore em cascata, beneficiário final…) e à cobertura do contexto BR em `agent/coverage.py` (renda×patrimônio, contrato direcionado, cripto, mula financeira…). Padrão novo = uma função e uma entrada no catálogo. Nada mais muda ([tutorial, secção 8](docs/TUTORIAL.md#8-criando-um-padrão-de-fraude-novo)).

### Histórico de mudanças (CDC) — não só o estado atual

Além do estado das tabelas, o agente ingere **trilhas de auditoria / change-log** (`UPDATE`/`DELETE` por registo, com *quem*, *quando* e *de→para*). É o histórico — não a foto atual — que denuncia **antedatação** e **destruição de prova**: uma venda que *parece* anterior à penhora, mas cujo registo foi editado depois dela, só aparece **cruzando o banco com o log**. A demo isolada [`demo/demo_antedatacao.py`](demo/demo_antedatacao.py) sobe um servidor temporário, cruza um `junta.db` com um change-log e mostra a proveniência a apontar para as duas fontes (`['alteracoes', 'file']`); ao correr, gera um log de exemplo em `demo/exemplo_audit_junta.log`.

## Componentes

| Ficheiro | Papel |
|---|---|
| `main.py` | One-shot (`--file`) ou daemon (`--daemon`); flags `--tls`, `--llm` |
| `pipeline.py` | Conector universal: qualquer banco SQL + pasta vigiada de ficheiros |
| `ingest.py` | Depósito manual de um documento no rio |
| `directive.py` | Envia DIRETRIZ (ordem auditável) ao agente |
| `relatorio.py` | Gera o laudo pericial em Markdown (com cadeia de custódia) |
| `consulta.py` | Consulta GQL **auditada** (LGPD): a leitura vira evento no log |
| `agent/parser.py` | Extração determinística de entidades/relações/transações/marcos |
| `agent/llm_parser.py` | Parser por LLM opcional (Claude), com fallback determinístico |
| `agent/entities.py` | Resolução de entidades: normaliza e valida CPF/CNPJ |
| `agent/graph.py` | **Grafo de caso acumulativo** — correlação multi-documento |
| `agent/patterns.py` | Catálogo de padrões de fraude (operam sobre o grafo) |
| `agent/investigator.py` | Motor de padrões + diretrizes + ACT-R + dedup |
| `agent/act_r.py` | Ativação de memória ACT-R (com boost dirigido) |
| `agent/daemon.py` | Loop event-sourcing (reconstrói → reconcilia → vive), robusto a falhas |
| `agent/report.py` | Gerador do relatório pericial |
| `agent/client.py` | SDK gRPC do HeraclitusDB (custódia por ULID, TLS, consulta auditada) |
| `agent/anomaly_engine.py` | Deteção **indutiva** (z-scores, pontos de articulação, estruturação) |
| `agent/evidence_scorer.py` | Força probatória por qualidade da fonte (rastreada por ULID) |
| `agent/legal_mapper.py` | Subsunção do fato à norma (tipificação + dispositivo legal) |
| `agent/theory_builder.py` | Sintetiza a Teoria do Caso (narrativa + matriz + minuta) |
| `agent/network_analysis.py` | **Redes entre casos**: facilitador partilhado + anéis (comunidades) |
| `agent/recovery.py` | **Quantificação** do valor dissipado + fila priorizada |
| `agent/feedback.py` | **Loop de feedback**: aprende a precisão de cada padrão pelo veredicto |
| `agent/entity_resolution.py` | **ER fuzzy**: sugere entidades quase-idênticas para revisão |
| `evaluation/` | **Harness de avaliação**: cenários rotulados + precisão/recall/F1 |
| `dashboard/` | Dashboard React/Vite (timeline, grafo causal, alertas) |

## Testes

**Unitários** (`tests/`, sem servidor — `pytest`):

| Teste | O que prova |
|---|---|
| `test_entities.py` | Normalização e validação de CPF/CNPJ; o mesmo CPF colapsa num id |
| `test_multidoc.py` | **Correlação multi-documento**, dedup, proveniência composta, boost de diretriz |
| `test_parser_patterns.py` | Parser robusto a quebras de linha; cada padrão (incl. suborno, antedatação, registo apagado); ACT-R; relatório |
| `test_eval_gate.py` | **Gate de acurácia**: corre o harness e falha se a deteção degradar (zero FP, recall ≥ 0.90) |
| `test_phase3.py` | Redes entre casos (facilitador/anel), valor dissipado + fila, feedback e ER fuzzy |

**End-to-end** (contra servidor real; cada um sobe o seu próprio servidor isolado):

| Teste | O que prova |
|---|---|
| `test_integration.py` | Custódia ponta a ponta: doc → ULID real → insight → `PROVENANCE` → `AS OF` |
| `test_daemon.py` | Daemon reage a DIRETRIZ + documento; proveniência composta; **idempotência no re-arranque** |
| `test_pipeline.py` | Banco SQL + ficheiro → rio → deteção nas duas fontes; checkpoints idempotentes |
| `test_multibank.py` | **DOIS bancos + documento em simultâneo**: triangulação com as pernas em três fontes fecha-se em CRÍTICA; CPF cru do banco unifica com o token do documento |

Cada e2e sobe o seu próprio `heraclitus-server` isolado (localizado por `HERACLITUS_SERVER_BIN` ou ao lado do repo HeraclitusDB):

```bash
pytest tests/             # 63 unitários, em qualquer máquina
python test_multibank.py  # e2e multi-fonte (sobe o servidor automaticamente)
```

## Fase 3 — inteligência de rede, priorização e aprendizado

Três capacidades que vão além de detetar um caso isolado (demo: `py demo/demo_fase3.py`):

- **Redes entre casos** (`agent/network_analysis.py`) — olha o grafo **global** e
  acha o **facilitador partilhado** (a mesma offshore/laranja/procurador a servir
  vários devedores — a "fábrica de laranjas") e os **anéis** (comunidades por
  *label propagation*). Apanhar o operador vale mais do que apanhar um peão.
- **Quantificação + fila priorizada** (`agent/recovery.py`) — estima o **valor
  dissipado** por caso e ordena por prioridade (valor × severidade × prova).
  Transforma 5.000 alertas "todos críticos" numa ordem de ataque com cifras.
- **Loop de feedback + ER fuzzy** (`agent/feedback.py`, `agent/entity_resolution.py`)
  — cada alerta confirmado/refutado recalibra a **precisão empírica** do padrão
  (Bayes com suavização, reconstruível por replay); e a resolução **fuzzy** sugere
  laranjas com o nome ligeiramente alterado que escapariam à correspondência exata.

A Fase 3 está **integrada no painel** (`demo/run.py`): a **Fila Priorizada** no topo
(clique numa linha para abrir o caso), as **Redes** (facilitadores partilhados) e os
**possíveis duplicados** (ER fuzzy) no fim. Para ver um facilitador a ligar vários
casos, gere um anel: `py demo/adicionar_caso.py --n 3 --operador-comum` e depois
`py demo/run.py --keep`.

## Avaliação — a deteção é medida, não afirmada

A pasta `evaluation/` torna a deteção **verificável**: cenários rotulados (positivos *e* negativos) com o conjunto de padrões que cada um deve disparar, e um harness que calcula **precisão / recall / F1 por padrão** — 100% offline (sem servidor), via `Investigator` em memória.

```bash
python evaluation/run_eval.py        # tabela de métricas
python evaluation/run_eval.py -v     # + cada cenário (FP/FN)
```

Os **negativos** (atividade legítima) medem falsos positivos/especificidade. O `tests/test_eval_gate.py` transforma isto num **gate de regressão** no CI: qualquer alteração que baixe a qualidade quebra o build. Para cobrir um padrão novo, acrescente um cenário em `evaluation/scenarios.py`.

## Qualidade / CI

O [CI](.github/workflows/ci.yml) corre em cada push/PR: **lint** (`ruff`, bloqueante), **testes + cobertura** (`pytest-cov`) + a **avaliação de detectores**, e ainda **type-check** (`mypy`) e **auditoria de dependências** (`pip-audit`) em modo informativo. Localmente: `ruff check .` e `pytest tests/`.

## Produção (AGU/INSS)

- **TLS** no gRPC: `python main.py --daemon --tls` (canal seguro; trafega CPF e dados financeiros — LGPD).
- **Auditoria de leitura**: `python consulta.py --autor procurador.silva --motivo "Ofício 9" 'MATCH (n) RETURN n'` — a consulta fica registada como evento imutável.
- **Parser por LLM**: `export ANTHROPIC_API_KEY=...` e `python main.py --daemon --llm` (Claude com saída estruturada; cai para o determinístico se indisponível).

> **Nota de integridade:** o HeraclitusDB rejeita `parents` que não sejam ULIDs válidos. Referências documentais humanas (números de processo, protocolos) vão em `attrs.source_refs` / `attrs.doc_ref`; a proveniência criptográfica usa sempre os ULIDs reais do log.

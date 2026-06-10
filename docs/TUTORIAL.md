# TUTORIAL — Do zero ao primeiro insight pericial

Este guia leva-te do clone ao primeiro alerta de fraude com cadeia de
custódia verificável, e depois ao modo de operação contínua com bancos
reais. Tempo estimado: 10 minutos para o básico, 30 para tudo.

## Índice

1. [Conceitos em 2 minutos](#1-conceitos-em-2-minutos)
2. [Instalação](#2-instalação)
3. [Subir o HeraclitusDB](#3-subir-o-heraclitusdb)
4. [Primeiro contacto — modo one-shot](#4-primeiro-contacto--modo-one-shot)
5. [O agente vivo — modo daemon](#5-o-agente-vivo--modo-daemon)
6. [Alimentar o rio — ficheiros, áudio, vídeo e bancos SQL](#6-alimentar-o-rio--ficheiros-áudio-vídeo-e-bancos-sql)
7. [Dar ordens ao agente — DIRETRIZes](#7-dar-ordens-ao-agente--diretrizes)
8. [Criando um padrão de fraude novo](#8-criando-um-padrão-de-fraude-novo)
9. [Consultando resultados — GQL e proveniência](#9-consultando-resultados--gql-e-proveniência)
10. [Operação contínua (produção)](#10-operação-contínua-produção)
11. [Resolução de problemas](#11-resolução-de-problemas)

---

## 1. Conceitos em 2 minutos

O sistema tem três peças que **só se falam através do log** do
HeraclitusDB (o "rio"):

| Peça | Comando | Papel |
|---|---|---|
| **Pipeline** (sentidos) | `pipeline.py` | Liga bancos SQL e pastas de ficheiros ao rio. Ingere, não opina. |
| **Agente** (cérebro) | `main.py --daemon` | Subscrito ao rio; analisa cada documento contra o catálogo de padrões. Não toca nas fontes. |
| **Procuradoria** (vontade) | `directive.py` | Ordena. A ordem é um evento imutável — fica provado quem mandou o quê. |

Regras de ouro:

- **Nada é alterado ou apagado, nunca.** Documentos, ordens e insights
  são eventos append-only com timestamp híbrido (HLC).
- **Todo insight tem `parents`**: os ULIDs do documento-fonte e da
  diretriz que o influenciou. `PROVENANCE(insight)` reconstrói a cadeia
  de custódia — isto é prova, não metadado decorativo.
- **ULIDs são atribuídos pelo banco.** O agente descobre o ULID de um
  evento resolvendo o LSN devolvido pelo `Append` (o cliente faz isso
  por ti: `resolve_event_id`).

## 2. Instalação

Pré-requisitos: Python 3.10+ e Rust (para o HeraclitusDB).

```bash
git clone https://github.com/JoseRFJuniorLLMs/LABRA-AGU.git
cd LABRA-AGU
pip install -r requirements.txt
python build.py        # compila os stubs gRPC para o teu protobuf local
```

Dependências mínimas para começar: `grpcio`, `pydantic`, `numpy`.
Opcionais conforme o uso: `pdfplumber` (PDF), `python-docx` (DOCX),
`SpeechRecognition`/`pydub`/`moviepy` (áudio/vídeo), `SQLAlchemy` +
driver do teu banco (`oracledb`, `pyodbc`, `psycopg2`, `pymysql`...).

> **Sempre que atualizares o protobuf/grpcio, corre `python build.py` de
> novo** — os stubs são gerados para a tua versão local.

## 3. Subir o HeraclitusDB

```bash
git clone https://github.com/JoseRFJuniorLLMs/HeraclitusDB.git
cd HeraclitusDB
cargo run --release -p heraclitus-server
```

Verifica: `curl http://127.0.0.1:7475/healthz` deve responder
`panta rhei`. O gRPC fica em `:7474` (o agente usa este).

O diretório de dados é `./data` por omissão — define
`HERACLITUS_DATA_DIR` para outro caminho em produção.

## 4. Primeiro contacto — modo one-shot

Sem argumentos, o agente corre uma simulação embutida (um relatório COAF
com triangulação societária):

```bash
python main.py
```

Saída esperada (resumida):

```
[INFO] Documento-fonte no log: LSN=0 ULID=01KTS0M7Y7XVGER2PCFNRK1P93
[INFO] ALERTA [CRITICA]: triangulacao_offshore
[INFO] Conclusão: Evidência robusta de esvaziamento patrimonial...
[INFO] Insight pericial salvo. LSN=1 ULID=01KTS0M7YV7J95SHEBWC9ZKQ09
[INFO] Cadeia de custódia (PROVENANCE): ['01KTS0M7Y7XVGER2PCFNRK1P93']
```

Lê esta saída com atenção, porque é o contrato do sistema inteiro:
o **documento entrou primeiro** no log (custódia), o insight veio
**depois**, e a `PROVENANCE` do insight devolve exatamente o ULID do
documento. Com um ficheiro teu:

```bash
python main.py --file processo_4512.pdf
```

## 5. O agente vivo — modo daemon

```bash
python main.py --daemon
```

A partir daqui o agente:

- subscreve o log a partir do último LSN processado (checkpoint em
  `agent_state.json` — sobrevive a restarts sem repetir nem perder);
- analisa cada evento `Observation` que entrar no rio, venha de onde
  vier (ingest manual, pipeline SQL, pasta vigiada);
- acolhe cada `DIRETRIZ` no momento em que ela entra;
- grava insights com proveniência composta;
- reconecta com backoff se o servidor cair; `Ctrl+C` para parar limpo.

Deixa-o correr num terminal e usa outro para os passos seguintes.

## 6. Alimentar o rio — ficheiros, áudio, vídeo e bancos SQL

### 6.1 Um documento avulso

```bash
python ingest.py --file extrato_banco_novo.pdf --ref "OFICIO_1234/2026"
python ingest.py --texto "O devedor CPF_111... transferiu R$ 9.000,00 para CNPJ_X em 01/06/2026"
```

O `--ref` é a referência documental humana (nº de ofício, protocolo) —
fica em `attrs.doc_ref`, não em `parents` (que são só ULIDs).

### 6.2 Pasta vigiada (PDFs, áudios e vídeos a entrar sozinhos)

```bash
python pipeline.py --watch-dir ./entrada --interval 30
```

Qualquer ficheiro novo em `./entrada` (PDF, DOCX, CSV, TXT, ZIP, MP3,
MP4, WAV) é extraído/transcrito e depositado no rio. Idempotência por
SHA-256 do conteúdo: o mesmo ficheiro nunca entra duas vezes, e o hash
fica nos attrs (custódia da prova material).

### 6.3 Qualquer banco da AGU (Oracle, SQL Server, Postgres, ...)

```bash
python pipeline.py \
  --db "oracle+oracledb://usuario:senha@host:1521/?service_name=FINANC" \
  --table movimentacoes \
  --incremental id \
  --template "{origem} transferiu R$ {valor} para {destino} em {data}" \
  --interval 60
```

Como funciona:

- `--db` aceita **qualquer URL SQLAlchemy** (instala o driver do banco);
- `--incremental` é a coluna de avanço (id sequencial, rowversion,
  updated_at). O pipeline guarda o último valor visto por
  (banco, tabela) em `pipeline_state.json` e só busca o que é novo;
- **um lote = um documento** no log — padrões como fracionamento
  precisam de ver as transações juntas, como num relatório COAF;
- `--template` traduz cada linha para a frase canónica que o parser do
  agente entende. Os placeholders são os nomes das colunas; números
  saem como `R$ 9.500,00` e datas como `dd/mm/aaaa` automaticamente;
- as credenciais **nunca** entram no log (apenas o dialeto vai nos attrs).

Para agendar via cron/Task Scheduler em vez de loop: acrescenta `--once`.

## 7. Dar ordens ao agente — DIRETRIZes

Chegou uma denúncia sobre um CPF específico? Ordena o foco:

```bash
python directive.py \
  --alvo CPF_645.254.302-49 --alvo CNPJ_OFFSHORE_01 \
  --foco "blindagem patrimonial via offshores" \
  --padrao fracionamento --padrao vespera_constricao \
  --boost 8 \
  --autor "procurador.silva"
```

Efeitos imediatos no daemon:

1. **Boost ACT-R**: os alvos recebem `--boost` acessos sintéticos de
   memória — o agente passa a "pensar mais" neles (a ativação aparece
   nos payloads em `ativacao_act_r`, são números reais, não decorativos);
2. **Foco de padrões**: com `--padrao`, o catálogo vigiado restringe-se
   à união dos padrões das diretrizes ativas; sem `--padrao`, vigia tudo;
3. **Proveniência**: todo insight que envolver um alvo (ou um padrão
   focado) carrega o ULID da diretriz em `parents` e em
   `payload.diretrizes_aplicadas` — auditável: *quem ordenou, o que
   resultou*.

Padrões disponíveis para `--padrao`: `triangulacao_offshore`,
`fracionamento`, `laranja_familiar`, `vespera_constricao`.

## 8. Criando um padrão de fraude novo

Todo o conhecimento pericial vive em `agent/patterns.py`. Um padrão é
uma função pura `detect(doc) -> Optional[dict]`. Exemplo — detetar
doações suspeitas a pessoa politicamente exposta:

```python
def detect_doacao_pep(doc: ParsedDocument) -> Optional[dict]:
    for t in doc.transactions:
        if t.target_id.upper().startswith("CPF_PEP"):
            return {
                "pattern": "doacao_pep",
                "severidade": "ALTA",
                "envolvidos": [t.source_id, t.target_id],
                "devedor_alvo": t.source_id,
                "descricao": f"{t.source_id} transferiu R$ {t.value:,.2f} "
                             f"para pessoa politicamente exposta {t.target_id}.",
                "conclusao_juridica": "Indício de vantagem indevida (Lei 8.429/92).",
            }
    return None

PATTERNS["doacao_pep"] = detect_doacao_pep   # regista no catálogo
```

Só isso. O daemon passa a vigiar o padrão novo, o `directive.py` ganha-o
no `--padrao`, e os insights dele saem com a mesma custódia. O `doc` que
a função recebe tem: `entities` (CPF/CNPJ), `relations` (VENDEDOR_QUOTAS,
PROCURADOR_COM_PODERES, FAMILIAR), `transactions` (origem, destino,
valor, data ISO) e `marcos_judiciais` (datas de penhora/citação).

## 9. Consultando resultados — GQL e proveniência

O cliente Python expõe o GQL do HeraclitusDB:

```python
from agent.client import HeraclitusClient
c = HeraclitusClient("localhost:7474")

# Todos os insights do agente, mais recentes primeiro:
c.query('MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC')

# De onde veio este insight? (cadeia de custódia inversa)
c.provenance("01KTS27MABCDEF...")          # -> [ULID do doc, ULID da diretriz]

# O que o sistema sabia ANTES do documento X entrar? (viagem no tempo)
c.query("MATCH (n) AS OF LSN 42 RETURN n")

# Busca textual com retrieval em dois estágios:
c.query('RECALL ("offshore quotas cunhado", 5)')
```

O payload de cada insight (campo `content`, JSON) traz: `tipo_fraude`,
`severidade`, `descricao`, `conclusao_juridica`, `envolvidos`,
`ativacao_act_r` (score real por entidade) e `diretrizes_aplicadas`.

## 10. Operação contínua (produção)

Topologia recomendada:

```
[cron/serviço]  pipeline.py --db ... --once          (cada banco, no seu ritmo)
[serviço]       pipeline.py --watch-dir /depósito    (ficheiros)
[serviço]       main.py --daemon                     (o cérebro, sempre vivo)
[sob demanda]   directive.py ...                     (ordens da Procuradoria)
```

- Cada fonte SQL pode ter o seu próprio agendamento (`--once` + cron);
- O daemon retoma do checkpoint após qualquer restart — zero perda,
  zero reprocessamento;
- `agent_state.json` e `pipeline_state.json` são os únicos estados
  locais; tudo o mais vive no rio (e o rio tem backup, Merkle e replay
  determinístico do lado do HeraclitusDB);
- Vários daemons? Dá a cada um o seu `state_path` e divide por
  `agent_id`/tipo de documento se precisares de paralelismo.

## 11. Resolução de problemas

| Sintoma | Causa | Solução |
|---|---|---|
| `'NoneType' object has no attribute 'Append'` | Stubs gRPC não gerados/incompatíveis com o teu protobuf | `python build.py` |
| `ModuleNotFoundError: heraclitus_pb2` | Stub gerado com import absoluto | `python build.py` (o build pós-processa para import relativo) |
| `StatusCode.UNAVAILABLE` | HeraclitusDB não está de pé em :7474 | sobe o `heraclitus-server`; testa `curl :7475/healthz` |
| `invalid_argument: bad parent ULID` | Tentaste pôr referência humana em `parents` | usa `attrs.source_refs`; `parents` só aceita ULIDs reais do log |
| Daemon não reage a nada | checkpoint à frente do head (ex.: log recriado) | apaga `agent_state.json` para reprocessar do zero |
| Fracionamento não dispara em dados de banco | linhas viraram documentos separados | usa o `pipeline.py` (1 lote = 1 documento), não `ingest.py` linha a linha |
| Mesmo ficheiro ingerido 2× | conteúdo mudou (hash novo) | é por desenho: idempotência é por SHA-256 do conteúdo |
| `instale o conector universal` | SQLAlchemy/driver em falta | `pip install sqlalchemy` + driver do teu banco |

### Verificar a instalação inteira

```bash
# Com o heraclitus-server de pé:
python test_integration.py   # custódia ponta a ponta (7 passos)
python test_daemon.py        # daemon + diretriz + proveniência composta
python test_pipeline.py      # banco SQL + ficheiro -> deteção nas duas fontes
```

Os três a verde = o sistema completo está operacional.

---

*"Panta rhei. O documento entra no rio, a ordem entra no rio, o insight
nasce do rio — e o rio lembra-se de tudo, para sempre."*

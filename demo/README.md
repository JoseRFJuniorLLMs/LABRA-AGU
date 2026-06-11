# Demo LABRA-AGU — Caça à Fraude Multi-Fonte com HeraclitusDB

Cenário **100% fictício e juridicamente seguro** (LGPD), mas com CPF/CNPJ de
**dígitos verificadores válidos**. Uma triangulação de blindagem patrimonial
deliberadamente **partida por quatro fontes** — nenhuma sozinha contém a
fraude; só o grafo de caso consolidado a fecha:

| Fonte | Tipo | O que carrega |
|---|---|---|
| `junta.db` | SQL | devedor **vende quotas** para a offshore |
| `cartorio.db` | SQL | a offshore **nomeia o cunhado** como procurador |
| `coaf.db` | SQL | **3 transferências fracionadas** (smurfing) |
| `entrada/vinculos.txt` | documento | o **vínculo familiar** + a **véspera da penhora** |

O agente fecha **quatro fraudes**, duas CRÍTICAS:
`triangulacao_offshore` (CRÍTICA) · `vespera_constricao` (CRÍTICA) ·
`fracionamento` (ALTA) · `laranja_familiar` (ALTA).

---

## Modo A — Um comando (à prova de nervoso) — RECOMENDADO

Sobe um HeraclitusDB **limpo e isolado**, gera o cenário, emite a diretriz,
ingere as 4 fontes e mostra o agente fechar as fraudes com proveniência. Tudo
determinístico, sem setup.

```bash
python demo/run.py
```

Para correr **contra o serviço Windows** (mostrar o HeraclitusDB a sério, em
`127.0.0.1:7474`):

```bash
python demo/run.py --live
```

## Modo B — Fluxo ao vivo, em terminais separados (mais "real")

Mostra as peças a conversarem pelo log. Requer o HeraclitusDB a correr
(o serviço Windows já está; senão `cargo run --release -p heraclitus-server`).
**Corra a partir da raiz do repositório** (os caminhos do `sources.json` são
relativos a ela).

```bash
# 1. Gera os bancos + o documento da demo
python demo/gerar_cenario.py

# 2. (Terminal 2) O cérebro, vivo
python main.py --daemon

# 3. (Terminal 3) A ordem da Procuradoria — o comando exato fica gravado
#    em demo/demo_data/diretriz_pronta.txt
python directive.py --alvo CPF_<devedor> --foco "offshores" --boost 10

# 4. Ingestão das 4 fontes de uma só vez
python pipeline.py --config demo/sources.json --once
```

O daemon (Terminal 2) imprime os `INSIGHT [.../CRITICA] gravado` à medida que
correlaciona as fontes.

---

## O roteiro de 12 minutos (o que dizer)

1. **O problema (1 min).** "A blindagem patrimonial é multi-fonte: o fraudador
   vende quotas na Junta, passa procuração no Cartório e fraciona no COAF.
   Sistemas tradicionais olham isto isolado. O meu agente unifica tudo pelo
   HeraclitusDB."

2. **`python demo/run.py` (4 min).** Deixe correr e narre os blocos 1–5.
   No bloco 5, aponte:
   - **Resolução de entidades** — "o CPF formatado da Junta e o cru do COAF
     colapsaram no mesmo nó; sem isto, a fraude some entre duplicados."
   - **Correlação cruzada** — "nenhuma fonte sozinha tinha a fraude; o grafo
     de caso fechou a triangulação CRÍTICA."

3. **A cadeia de custódia (3 min).** "Cada alerta aponta, por **ULID real**,
   para os documentos-fonte que o sustentam — e a própria DIRETRIZ da
   Procuradoria entra na proveniência. É segurança jurídica: a verdade não se
   edita, o log é imutável e consultável **AS OF** qualquer ponto do passado."

4. **A IA (3 min).** "O filtro é o **ACT-R**: em vez de inundar o procurador
   com milhares de alertas, a ativação sub-simbólica prioriza o recente,
   frequente e relevante; a DIRETRIZ dá um *boost* de atenção ao alvo. O
   parsing é determinístico (regex dirigida) com *fallback* para LLM (Claude)
   quando `--llm` está ativo."

5. **Resiliência (1 min).** "Se o servidor cair, o daemon reconstrói o estado
   do grafo a partir do log imutável e **deduplica** — nenhum alerta perdido
   ou duplicado."

### Perguntas difíceis (respostas prontas)
- *"Por que um banco próprio e não Postgres/Neo4j?"* — porque correlação
  pericial exige **proveniência verificável** e **reconstrução determinística
  do estado** a partir de um log imutável; é uma propriedade do substrato, não
  um plugin.
- *"Os dados são reais?"* — "Fictícios, de propósito. Mostrar dados reais de
  pessoas numa demo seria, ele próprio, a primeira infração de LGPD. O pipeline
  conecta qualquer banco real (Receita/CNPJ, COAF, Juntas) via SQLAlchemy."

---

## Ficheiros

| Ficheiro | Papel |
|---|---|
| `run.py` | Demo completa num comando (servidor limpo ou `--live`) |
| `gerar_cenario.py` | Gera os bancos + documento (dígitos válidos) |
| `sources.json` | Config multi-fonte para `pipeline.py --config` (Modo B) |
| `demo_data/` | Gerado em runtime (bancos, documento, diretriz pronta) |

> As frases dos `template` e do documento seguem **exatamente** o que o
> `agent/parser.py` reconhece; alterá-las pode silenciar um padrão. O cenário
> foi validado de ponta a ponta (os 4 padrões disparam).

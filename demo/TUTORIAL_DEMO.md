# Tutorial — Executar a Demo Completa do LABRA-AGU

Passo a passo para correr a demonstração de caça à fraude multi-fonte e para
**adicionar mais casos**. Tudo com dados fictícios (LGPD), mas com CPF/CNPJ de
dígitos válidos.

> **Comando de Python:** use `py` (o lançador aponta para o Python 3.14, que tem
> `grpcio` e `sqlalchemy` instalados). O `python` simples pode ser o atalho da
> Microsoft Store e não funcionar. Corra sempre **a partir da raiz do repo**
> (`D:\DEV\LABRA-AGU`).

---

## 0. Pré-requisitos (uma vez)

- **HeraclitusDB**: o binário do servidor existe em
  `..\HeraclitusDB\target\release\heraclitus-server.exe` (o Modo A usa-o
  sozinho). Para o Modo B/`--live`, o serviço Windows `HeraclitusDB` deve estar
  a correr: `Get-Service HeraclitusDB` (instala-se via
  `..\HeraclitusDB\windows\heraclitus-service.ps1 install`).
- **Dependências Python** (já instaladas): `grpcio`, `sqlalchemy`. Se faltarem:
  `py -m pip install grpcio sqlalchemy`.

---

## 1. A demo completa — UM comando (recomendado)

```powershell
py demo\run.py
```

O que acontece, em ~10 segundos:
1. Sobe um HeraclitusDB **limpo e isolado** (determinístico, sem mexer no resto).
2. Gera o cenário de fraude (3 bancos SQL + 1 documento).
3. Emite uma **DIRETRIZ da Procuradoria** (boost ACT-R no devedor).
4. Ingere as 4 fontes pelo pipeline.
5. O agente **fecha 4 fraudes** (2 CRÍTICAS) e imprime a narrativa com proveniência.
6. **Abre no browser** um painel único e interativo (`demo_data/painel_demo.html`)
   com a **barra de tempo lateral** (AS OF), o grafo, os alertas e a cadeia de custódia.

Para correr contra o **serviço Windows** do HeraclitusDB (mostrá-lo a sério):

```powershell
py demo\run.py --live
```

---

## 2. A demo ao vivo — terminais separados (mais "real")

Mostra as peças a conversarem só pelo log imutável.

```powershell
# Terminal 1 — gera os dados da demo
py demo\gerar_cenario.py

# Terminal 2 — o cérebro, vivo (fica a correr)
py main.py --daemon

# Terminal 3 — a ordem da Procuradoria
#   (o comando exato fica gravado em demo\demo_data\diretriz_pronta.txt)
py directive.py --alvo CPF_<devedor> --foco "offshores" --boost 10

# Terminal 3 — ingestão das 4 fontes de uma vez
py pipeline.py --config demo\sources.json --once
```

No Terminal 2, o daemon imprime `INSIGHT [.../CRITICA] gravado` à medida que
correlaciona as fontes.

---

## 3. O que vais ver

- **No terminal:** os 4 alertas (TRIANGULAÇÃO e VÉSPERA = CRÍTICAS;
  FRACIONAMENTO e LARANJA = ALTAS), cada um com a proveniência (de que fontes
  veio a prova) e a nota de que o CPF formatado e o cru colapsaram num só nó.
- **No browser:** o painel único (cores da AGU) com a **barra de tempo lateral**
  (arraste para reconstruir o caso AS OF qualquer instante), os cartões de
  alerta, o grafo de relações devedor→offshore→laranja, o rio de eventos e a
  cadeia de custódia.

---

## 4. Quero MAIS casos — é só inserir no banco certo?

**Sim** — desde que respeite o *contrato* (tabela, colunas e a **frase** que o
agente lê). O parser é determinístico e reage a frases específicas; pôr o dado
na coluna errada ou com outra frase faz o alerta não disparar.

### 4a. O jeito fácil — um comando por caso, e ver no painel

```powershell
py demo\adicionar_caso.py            # +1 caso novo (CPF/CNPJ válidos, tudo certo)
py demo\adicionar_caso.py --n 5      # +5 casos

py demo\run.py --keep                # detecta TODOS os casos e abre o painel
```

A flag **`--keep`** diz ao `run.py` para **não regenerar** o cenário base e usar
os casos já em `demo_data` (incluindo os que adicionaste). O painel passa a ter
um **seletor de casos** no topo — escolhes o caso e arrastas a barra de tempo
dele. Os números (casos, fraudes, críticas) refletem o total real detectado.

> Sem `--keep`, `py demo\run.py` **regenera** o cenário base (1 caso,
> determinístico) — ideal para a demo principal. Use `--keep` para mostrar que
> o sistema escala para muitos casos.

### 4a-bis. Casos COMPLEXOS — esquemas avançados (Fase 2)

Para impressionar com esquemas sofisticados (não só a triangulação base), gere
casos que disparam as heurísticas avançadas — **doação cruzada**,
**holding/usufruto** e **offshore em cascata**:

```powershell
py demo\gerar_complexos.py --n 6     # 6 casos complexos (limpa demo_data)
py demo\run.py --keep                # detecta e abre o painel
```

Cada caso é um **superconjunto**: a triangulação base (que renderiza no grafo)
**+** esquemas avançados declarados no documento de vínculos. Os perfis variam
(`completo` · `cascata` · `doacao_holding`), então o seletor mostra casos com
**4 a 7 esquemas** cada. No painel, o caso complexo aparece inteiro: os cartões
de alerta (todos os tipos), a **matriz de evidências** com a força probatória,
e a **minuta** a citar os dispositivos novos (CC 158 — fraude contra credores;
Lei 9.613/98 — cascata; CC 50 — holding).

> Os esquemas avançados só disparam porque o `asset_shield` está registado no
> catálogo do agente. Frases-gatilho: "X **doou** ... para Y" (doação),
> "X é **usufrutuário vitalício** de Y" (holding), "X **controla** Y" (cascata).

### 4b. O contrato — onde e como inserir à mão

| Fonte | Banco / pasta | Tabela | Colunas (exatas) | Frase que o agente reconhece |
|---|---|---|---|---|
| Venda de quotas | `junta.db` | `alteracoes` | `socio, destino, data` | `<socio> transferiu/vendeu/cedeu **quotas** ... <destino>` |
| Procuração | `cartorio.db` | `procuracoes` | `outorgante, procurador, data` | `<outorgante> **nomeou/constituiu** <procurador> ... **poderes**` |
| Transferência (COAF) | `coaf.db` | `movimentacoes` | `origem, destino, valor, data` | `<origem> **transferiu R$** <valor> **para** <destino> em <data>` |
| Vínculo / marco | `demo_data/entrada/*.txt` | — | — | `<laranja> é **cunhado** do **devedor** <devedor>` + marco |

**Palavras-gatilho** que o parser procura (`agent/parser.py`):
- **Venda:** `transferiu` / `vendeu` / `cedeu` + a palavra `quotas`.
- **Procuração:** `nomeou` / `constituiu` + a palavra `poderes`.
- **Transferência:** `transferiu` / `depositou` / `remeteu` / `enviou` + `R$ <valor> para <id>`.
- **Família:** `cunhado` / `irmão` / `irmã` / `esposa` / `parente`… seguido de `devedor <id>`.
- **Marco judicial:** `penhora` / `citação` / `bloqueio judicial` / `arresto` / `indisponibilidade` + uma data `DD/MM/AAAA`.

**Regras de ouro:**
- **CPF/CNPJ têm de ser válidos** (o agente valida os dígitos). Gere com
  `adicionar_caso.py`, ou valide com `agent/entities.py`. O **mesmo** CPF
  formatado (`529.982.247-25`) e cru (`52998224725`) viram o **mesmo nó**.
- **Fracionamento** exige **≥3** transferências, cada uma **abaixo de R$ 10.000**,
  somando ≥ R$ 10.000 (use valores distintos, ex.: 9.500 / 8.700 / 9.200).
- **Véspera de constrição**: a venda/transferência tem de cair **até 30 dias
  antes** da data do marco judicial do documento.
- A triangulação fecha **CRÍTICA** só com o vínculo familiar; sem ele, fica ALTA.

### 4c. Exemplo — inserir um caso à mão (SQL)

```sql
-- junta.db
INSERT INTO alteracoes (socio, destino, data)
VALUES ('111.444.777-35', '04.252.011/0001-10', '2026-05-12');

-- cartorio.db
INSERT INTO procuracoes (outorgante, procurador, data)
VALUES ('04.252.011/0001-10', '52998224725', '2026-05-13');

-- coaf.db  (3 transferências < R$ 10.000)
INSERT INTO movimentacoes (origem, destino, valor, data) VALUES
 ('11144477735', '52998224725', 9500.00, '2026-05-14'),
 ('11144477735', '52998224725', 8700.00, '2026-05-15'),
 ('11144477735', '52998224725', 9200.00, '2026-05-16');
```

E um ficheiro `demo_data/entrada/vinculos_novo.txt`:

```
Apurou-se que 52998224725 é cunhado do devedor 11144477735.
Consta ordem de bloqueio judicial (penhora) prevista para 05/06/2026.
```

Depois re-ingira (Modo B). O agente fecha o caso novo.

---

## 5. Resolução de problemas

| Sintoma | Causa provável | Correção |
|---|---|---|
| Nenhum alerta aparece | Frase/coluna fora do contrato, ou falta `template` | Use os templates de `sources.json`; veja a tabela 4b |
| Triangulação fica ALTA (não CRÍTICA) | Vínculo familiar não foi lido | Texto tem de ser `<laranja> é cunhado do **devedor** <devedor>` |
| Fracionamento não dispara | Valores ≥ R$ 10.000, ou < 3 transferências | 3+ valores **abaixo** de 10.000 |
| `python` não encontrado | Atalho da Microsoft Store | Use `py` |
| `heraclitus-server não encontrado` | Binário ausente | Compile o HeraclitusDB ou use `--live` com o serviço a correr |

---

## Resumo dos comandos

```powershell
py demo\run.py                         # demo completa (1 comando) + relatório no browser
py demo\run.py --live                  # idem, contra o serviço Windows
py demo\adicionar_caso.py --n 3        # +3 casos de fraude
py pipeline.py --config demo\sources.json --once   # re-ingerir (Modo B)
```

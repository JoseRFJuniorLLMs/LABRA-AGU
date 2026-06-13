# LABRA-AGU — Documento-fonte para vídeo explicativo (NotebookLM)

> **Como usar:** carregue este ficheiro como *fonte* no NotebookLM e gere um
> **Vídeo Overview** (ou Áudio Overview). Sugestão de instrução de foco para o
> NotebookLM: *"Explique de forma acessível o que é o LABRA-AGU, o problema da
> blindagem patrimonial, como o agente cruza várias fontes para achar a fraude,
> e por que o histórico de mudanças (change-log) é o grande diferencial. Público:
> juristas e gestores públicos, não programadores. Tom: claro, com analogias,
> ~8 minutos."*

---

## 1. A frase de uma linha

O **LABRA-AGU** é um agente de inteligência artificial que caça **blindagem
patrimonial** — o conjunto de manobras que devedores usam para esconder bens e
não pagar o que devem à União. Ele lê dados espalhados por vários bancos e
documentos, junta as peças que ninguém via juntas, e aponta a fraude **com
prova rastreável**.

---

## 2. O problema: a fraude mora nos vãos entre as fontes

Imagine um devedor de milhões à Fazenda Nacional. Ele não esconde o dinheiro
num lugar só — isso seria fácil de achar. Ele **fatia o esquema** por muitos
lugares:

- na **Junta Comercial**, vende as quotas da sua empresa para uma *offshore*;
- num **cartório**, essa offshore nomeia o cunhado dele como procurador "com
  plenos poderes" — ou seja, o cunhado controla tudo, mas no papel o devedor
  não tem nada;
- no **COAF**, aparecem três transferências de R$ 9.000 — cada uma logo abaixo
  do limite de R$ 10.000 que obrigaria a comunicar ao governo (isto chama-se
  *fracionamento* ou *smurfing*);
- e tudo isso acontece **dias antes de uma penhora** que ele sabia que vinha.

Olhe cada fonte **isolada** e não vê crime nenhum: uma venda de quotas é legal,
uma procuração é legal, transferências pequenas são legais. **A fraude só
existe quando você junta tudo.** E é exatamente isso que ninguém consegue fazer
à mão, em escala, com milhões de registos.

Esse é o trabalho do LABRA-AGU.

---

## 3. A grande ideia: um "rio" de eventos que nunca esquece

O coração do sistema é uma base de dados especial chamada **HeraclitusDB**.
Pense nela como um **rio** que só corre para a frente: tudo o que entra vira um
**evento permanente e imutável** — nada se apaga, nada se reescreve. Se algo
estava errado, você **acrescenta** uma correção; o original continua lá, visível.

Isto tem três consequências poderosas, todas cruciais para a Justiça:

1. **Cadeia de custódia.** Cada conclusão do agente aponta, por uma "impressão
   digital" única (um identificador chamado *ULID*), para os documentos exatos
   que a sustentam. Nada é "achismo": toda acusação tem prova rastreável até à
   origem.
2. **Viagem no tempo (consulta "AS OF").** Você pode perguntar ao sistema "como
   é que isto estava em tal data?" e reconstruir o passado exatamente como era.
3. **Auditoria total.** Até a *leitura* de dados pessoais fica registada (quem
   consultou, o quê e por quê) — fundamental para a LGPD.

O nome não é por acaso: Heráclito é o filósofo do *"tudo flui"*. A verdade não
se edita; ela se acumula.

---

## 4. A arquitetura: três papéis que só se falam pelo rio

O sistema separa funções de forma estrita — como numa investigação séria, quem
coleta a prova não é quem julga:

- **Os Sentidos (`pipeline.py`)** — ingerem dados de **qualquer** fonte: bancos
  SQL da AGU (Oracle, SQL Server, Postgres…), PDFs de processos, contratos em
  Word, planilhas, e até **áudio e vídeo** de escutas e depoimentos
  (transcritos localmente, sem nada sair da máquina — LGPD). Eles **ingerem sem
  opinar**.
- **O Cérebro (`main.py --daemon`)** — o agente vivo, que fica "escutando o rio"
  e, a cada novo documento, reavalia o caso inteiro. Ele **investiga sem tocar
  nas fontes originais**: só conhece o rio.
- **A Procuradoria (`directive.py`)** — o procurador pode dar **ordens** ("foco
  em offshores", "prioridade para este CPF"). Mas até a ordem é um evento
  auditável no rio: fica registado *quem mandou investigar o quê*.

Nenhum dos três fala diretamente com o outro. Toda interação passa pelo rio,
toda interação é auditável.

---

## 5. Como o agente pensa, passo a passo

1. **Ler o caos.** Um documento chega (um PDF, uma linha de banco). O agente
   extrai entidades (CPFs, CNPJs), relações (quem vendeu o quê a quem),
   transações, datas e **marcos judiciais** (penhora, citação, bloqueio).
   Quando o texto é "limpo", uma extração por regras resolve; quando é caótico
   (um processo escaneado com OCR), um **modelo de linguagem (Claude)** entra —
   e, se ele falhar, o sistema cai graciosamente de volta para as regras. Nunca
   fica sem análise.

2. **Resolver identidades.** O mesmo CPF aparece de mil formas: `645.254.302-49`,
   `64525430249`, `CPF_645...`. O agente **funde tudo num único nó**, validando
   os dígitos verificadores. Sem isto, a fraude se esconderia entre duplicatas.

3. **Montar o grafo do caso.** Documento após documento, o agente acumula um
   **mapa de relações** — pessoas, empresas, bens e dinheiro, todos ligados.
   É aqui que as peças de fontes diferentes finalmente se encontram.

4. **Correr os detectores sobre o grafo inteiro.** Não sobre um documento de
   cada vez — sobre o caso consolidado. É por isso que ele vê a triangulação
   que estava partida em quatro lugares.

5. **Filtrar com atenção (ACT-R).** Inspirado na ciência cognitiva, o agente dá
   mais peso a quem aparece com frequência e recentemente — e a quem o
   procurador mandou priorizar. É o foco de um investigador experiente,
   formalizado em matemática.

6. **Concluir com prova e com a lei.** Cada alerta traz: a narrativa do que
   aconteceu, a **severidade**, os ULIDs de **todas** as fontes que o sustentam,
   e o **enquadramento legal** (qual artigo do Código Penal, do CPC, da Lei de
   Lavagem). O sistema chega a montar uma **minuta jurídica** — uma "Teoria do
   Caso" — pronta para o procurador revisar.

---

## 6. O catálogo de fraudes que ele reconhece

O agente combina dois modos de pensar:

**Dedutivo** (procura esquemas conhecidos):
- **Triangulação com offshore** — vende quotas para uma empresa que põe um
  laranja no comando. (Crítico se o laranja for da família.)
- **Laranja familiar** — plenos poderes a um parente: testa-de-ferro.
- **Fracionamento** — várias transferências pequenas para fugir ao radar.
- **Véspera da constrição** — mover bens dias antes da penhora que se sabia vir.
- **Suborno** — propina a agente público (corrupção ativa).
- **Doação cruzada, holding com usufruto, offshore em cascata, beneficiário
  final oculto, contrato público direcionado, cripto, mula financeira…** — toda
  uma biblioteca do contexto brasileiro.

**Indutivo** (acha o que *destoa*, mesmo sem padrão conhecido): usando análise
de grafos e estatística, encontra "hubs" suspeitos, contas que recebem de
muitas origens, e o **ponto de articulação** — aquele nó que, se removido,
parte o esquema em dois. É o elo insubstituível da ocultação.

---

## 7. O grande diferencial: o histórico de mudanças (CDC)

Aqui está a inovação que separa o LABRA-AGU de uma simples consulta a bancos.

A maioria dos sistemas olha só o **estado atual** das tabelas — a foto de agora.
O LABRA-AGU também lê o **change-log**: o *histórico de alterações* das fontes
(o que foi criado, editado ou apagado, por quem e quando).

Por que isto importa? Um exemplo real do sistema:

> Uma venda de quotas, no banco, aparece datada de **1 de maio** — antes da
> penhora de 5 de junho. Parece perfeitamente legítima.
>
> Mas o **log de mudanças** revela a verdade: essa data foi **editada em 10 de
> junho** — *depois* da penhora — de "8 de junho" para "1 de maio". Ou seja, o
> negócio foi **antedatado** para fingir que aconteceu antes da execução. E,
> dois dias depois, um registo do COAF foi **apagado**.

A fraude — **antedatação** e **destruição de prova** — é **invisível na foto
atual**. Ela só aparece quando você cruza o **banco** com o **log**. O
LABRA-AGU faz exatamente isso, e a prova que ele gera aponta para as duas
fontes ao mesmo tempo.

É a filosofia do rio levada ao limite: *a verdade está nas mudanças, não só no
estado final.*

---

## 8. Como sabemos que ele acerta (a parte científica)

Um sistema que "acha fraude" mas nunca mede se acerta é perigoso. Por isso o
LABRA-AGU tem um **harness de avaliação**: um conjunto de cenários **rotulados**
— casos de fraude *e* casos de atividade legítima — com a resposta certa
conhecida de antemão. O sistema é medido por **precisão, recall e F1** (as
métricas-padrão de qualidade): acerta as fraudes? Inventa fraudes onde não há?

Os casos legítimos são tão importantes quanto os fraudulentos: eles medem se o
agente **não levanta falso alarme** sobre cidadãos inocentes. Hoje, no conjunto
de testes, o sistema acerta tudo sem nenhum falso positivo — e essa medição roda
automaticamente a cada alteração no código, impedindo que uma "melhoria" piore a
qualidade sem ninguém perceber.

---

## 9. Por que isto importa

- **Recupera dinheiro público.** Cada esquema de blindagem desmontado é um bem
  que volta para a União.
- **Transforma semanas em segundos.** O que um perito levaria semanas cruzando
  planilhas, o agente faz continuamente, em escala, sem cansar.
- **É prova, não palpite.** Tudo é rastreável até a fonte, auditável, e já vem
  com o enquadramento legal — pronto para o processo.
- **Respeita a lei e a privacidade.** Dados sensíveis são tratados localmente,
  toda leitura é registada, e o histórico imutável é a própria garantia de
  integridade.

O LABRA-AGU não substitui o procurador. Ele faz o que a máquina faz melhor —
cruzar montanhas de dados sem perder um detalhe — para que o procurador faça o
que só ele pode fazer: julgar e agir.

---

## 10. Roteiro sugerido para o vídeo (arco narrativo)

1. **Gancho** (15s): "Como é que um devedor de milhões fica, no papel, sem nada?"
2. **O problema** (1min): a fraude fatiada entre fontes; ninguém vê o todo.
3. **A ideia do rio** (1min): event sourcing, a verdade que não se apaga.
4. **Os três papéis** (1min): sentidos, cérebro, procuradoria.
5. **O agente em ação** (2min): ler → resolver identidades → grafo → detectar →
   provar com a lei. Usar o caso da triangulação como fio condutor.
6. **O diferencial** (1,5min): o change-log e a antedatação — a foto mente, o
   histórico não.
7. **Confiança** (1min): como medimos que ele acerta; sem falsos alarmes.
8. **Fecho** (30s): recuperar o público, em escala, com prova. A máquina cruza;
   o humano decide.

---

### Glossário rápido (para a narração)

- **Blindagem patrimonial:** esconder bens para não pagar dívidas/execuções.
- **Offshore:** empresa em paraíso fiscal usada para ocultar a titularidade.
- **Laranja / testa-de-ferro:** pessoa que figura como dona no lugar do real dono.
- **Fracionamento (smurfing):** dividir valores para fugir à comunicação obrigatória.
- **Penhora / constrição:** ato judicial que bloqueia/toma bens do devedor.
- **Event sourcing:** guardar tudo como eventos imutáveis, em vez de sobrescrever.
- **Proveniência:** a trilha que liga cada conclusão às suas provas de origem.
- **CDC (Change Data Capture):** captura do histórico de mudanças de uma base.

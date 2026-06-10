# Especificação: Agente de IA Pericial e Investigativo (LABRA/AGU)

## 1. O que é o LABRA/AGU? (Mapeamento de Contexto)

O **Laboratório de Recuperação de Ativos (LABRA)** é a unidade de elite da **Procuradoria-Geral da União (PGU)**, vinculada à **Advocacia-Geral da União (AGU)**.

* **Missão Principal:** Rastrear, asfixiar financeiramente e recuperar bens e direitos desviados da União por meio de corrupção, fraudes fiscais, lavagem de dinheiro e improbidade administrativa.
* **O Grande Desafio:** Combater a **blindagem patrimonial**. Grandes devedores utilizam engenharia jurídica e societária reversa (offshores, holdings em cascata, contratos de gaveta e múltiplos laranjas) para ocultar a real propriedade dos ativos.
* **O Papel da Ciência de Dados e IA:** Transformar terabytes de dados brutos e caóticos (advindos de quebras de sigilo, bases do INSS, cartórios, COAF e juntas comerciais) em inteligência jurídica acionável. O objetivo final é dar subsídio técnico para que os Procuradores consigam medidas judiciais de arresto e bloqueio de bens com alta taxa de sucesso.

---

## 2. Diretrizes do Agente de IA Pericial e Investigativo

Para operar nesse cenário, o Agente de IA não pode ser um chatbot passivo. Ele deve seguir quatro diretrizes rígidas de operação autônoma (Loop Agêntico):

### I. Parsing Estruturado e Extração de Entidades (As Mãos)

* O agente deve receber documentos desestruturados (PDFs de juntas comerciais, escrituras de imóveis, relatórios do COAF) processados por trabalhadores externos.
* Sua missão é ler o texto e extrair entidades-chave em formato JSON: CPFs, CNPJs, valores de transações, datas e o *tipo de relação* (ex: sócio, comprador, procurador).

### II. Rastreamento de Nexo Causal e Vínculos Ocultos (O Cérebro)

* O agente deve buscar ativamente por anomalias societárias e financeiras.
* Ele deve monitorar se uma empresa de fachada (com capital social baixo) adquiriu um bem de luxo, ou se o devedor principal transferiu ativos para parentes de primeiro grau logo após ser citado em um processo judicial.

### III. Análise de Relevância e Retenção de Foco via ACT-R (O Filtro)

* Ao analisar redes com milhares de transações, o agente deve utilizar o motor subsimbólico do **ACT-R** para não sofrer desvio de foco e nem estourar a janela de contexto da LLM.
* O agente calcula o peso de ativação de cada transação: eventos recentes e diretamente ligados ao devedor ganham alta prioridade; dados históricos sem relação atual são de-indexados para o armazenamento frio.

### IV. Geração de Relatório Pericial Automatizado com Rastreabilidade (A Foz)

* O agente deve traduzir a fraude encontrada em uma narrativa jurídica clara.
* Toda conclusão emitida pelo agente deve obrigatoriamente apontar para os identificadores de eventos originais (`EventId`), garantindo que o Procurador possa provar em juízo a origem exata daquela prova.

---

## 3. Conexão e Persistência no HeraclitusDB

O Agente de IA funciona de forma externa ao banco. A comunicação e o salvamento dos achados periciais seguem uma arquitetura moderna e blindada contra falhas.

### Como ele se conecta?

A conexão é feita via **gRPC estável na porta `:7474`**. O Agente de IA abre um canal de *streaming* bidirecional com o HeraclitusDB.

1. O banco empurra novos eventos de transações (capturados via CDC dos sistemas da AGU) para o agente.
2. O agente processa a informação e devolve os seus insights diretamente para o mesmo canal de escrita gRPC.

### Como e onde ele salva o que encontrou?

O agente **nunca altera dados existentes**. Tudo o que ele descobre é salvo como um **novo evento imutável (Episódio)** no fim do log central (`/data/log`) do HeraclitusDB.

Para manter a causalidade, o agente preenche o campo `parents` do novo evento com o ID (`EventId`) dos logs brutos que ele utilizou para descobrir a fraude.

#### Exemplo Prático de Payload Salvo pelo Agente (JSON do Evento):

```json
{
  "event_type": "INSIGHT_PERICIAL_FRAUDE",
  "timestamp_hlc": "2026-06-10T13:20:00.000Z",
  "agent_id": "agente_pericial_labra_v1",
  "parents": [
    "01JX_TRANS_BANCO_AGU_102", 
    "01JX_CONTRATO_JUNTA_504"
  ],
  "payload": {
    "devedor_alvo": "CPF_645.254.302-49",
    "tipo_fraude": "Blindagem Patrimonial por Triangulação Cíclica",
    "descricao": "O agente identificou que o devedor transferiu quotas da empresa mãe para uma offshore, que por sua vez nomeou o cunhado do devedor como administrador com plenos poderes financeiros.",
    "metricas_geometricas": {
      "distorcao_hiperbolica": 0.0012,
      "raio_ciclo_esferico": 0.89
    },
    "conclusao_juridica": "Evidência robusta de esvaziamento patrimonial planejado para frustrar a execução fiscal da União."
  }
}
```

### O Destino Geométrico após o Salvamento

Assim que o agente faz o *append* desse evento via gRPC, o HeraclitusDB assume o controle no background:

1. **Compactação LSM (Sono do Banco):** Durante o processo assíncrono de compactação, o HeraclitusDB pega esse insight e reajusta o índice no **Manifold de Produto**:

$$\mathcal{P} = \mathcal{H}^a(\kappa_1) \times \mathcal{S}^b(\kappa_2) \times \mathcal{E}^c$$

2. **Organização Espacial:** O devedor, a offshore e o cunhado (laranja) são empurrados matematicamente para coordenadas extremamente próximas no **Espaço Hiperbólico** (pela relação hierárquica de controle) e no **Espaço Esférico** (pelo comportamento cíclico do dinheiro).
3. **Visão Materializada para o Power BI:** O banco consolida essa nova coordenada em uma tabela plana de leitura (`Read View`). Quando o dashboard do Power BI do LABRA atualiza, a fraude aparece mapeada em um gráfico de rede relacional instantaneamente, pronta para o clique do Procurador.

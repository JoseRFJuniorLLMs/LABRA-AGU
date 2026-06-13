"""
Cenários ROTULADOS (ground truth) para medir a acurácia dos detectores.

Cada cenário declara o texto de um documento e o CONJUNTO de padrões que
DEVEM ser detectados nele. Inclui NEGATIVOS (atividade legítima, expected
vazio) — essenciais para medir falsos positivos / especificidade.

É a fonte de verdade verificável: o harness corre os detectores sobre estes
textos e compara com o esperado, produzindo precisão/recall/F1 por padrão.
Para cobrir um padrão novo, acrescente um cenário positivo aqui (e, de
preferência, um negativo próximo que NÃO o deva disparar).
"""
from dataclasses import dataclass, field
from typing import Set


@dataclass(frozen=True)
class Scenario:
    nome: str
    texto: str
    esperado: Set[str] = field(default_factory=set)
    nota: str = ""


# ── POSITIVOS — cada um deve disparar exatamente os padrões em `esperado` ──
POSITIVOS = [
    Scenario(
        "triangulacao_com_familiar",
        "CPF_DEV1 transferiu quotas para CNPJ_OFF1, que nomeou o cunhado "
        "CPF_LAR1 com plenos poderes.",
        {"triangulacao_offshore", "laranja_familiar"},
        "venda + procuração a familiar = triangulação CRÍTICA + laranja",
    ),
    Scenario(
        "triangulacao_sem_familiar",
        "CPF_DEV2 transferiu quotas para CNPJ_OFF2, que nomeou CPF_PROC2 "
        "com plenos poderes.",
        {"triangulacao_offshore"},
        "procurador sem vínculo familiar = triangulação (ALTA), sem laranja",
    ),
    Scenario(
        "fracionamento_smurfing",
        "CPF_DEV3 transferiu R$ 9.000,00 para CNPJ_X3 em 01/02/2026. "
        "CPF_DEV3 transferiu R$ 9.200,00 para CNPJ_X3 em 02/02/2026. "
        "CPF_DEV3 transferiu R$ 8.800,00 para CNPJ_X3 em 03/02/2026.",
        {"fracionamento"},
        "3 transferências < R$ 10k, longe de qualquer marco",
    ),
    Scenario(
        "vespera_constricao",
        "Consta penhora em 10/06/2026. CPF_DEV4 transferiu R$ 50.000,00 "
        "para CNPJ_X4 em 01/06/2026.",
        {"vespera_constricao"},
        "1 transferência (acima do limiar) na véspera da penhora",
    ),
    Scenario(
        "suborno_agente_publico",
        "CPF_DEV5 pagou propina de R$ 100.000,00 ao agente público CPF_AG5 "
        "em 01/03/2026.",
        {"suborno"},
        "corrupção ativa",
    ),
    Scenario(
        "antedatacao_registro",
        "Consta penhora em 05/06/2026. "
        "2026-06-10 14:32:11 UPDATE alteracoes registro de CPF_DEV6 "
        "campo=data de=08/06/2026 para=01/05/2026 por=op_47",
        {"antedatacao"},
        "data retroagida (para antes do marco) por edição feita após o marco",
    ),
    Scenario(
        "registro_apagado",
        "Consta penhora em 05/06/2026. "
        "2026-06-12 09:15:02 DELETE coaf registro de CPF_DEV7 "
        "campo=movimentacao por=op_12",
        {"registro_apagado"},
        "DELETE após o marco judicial = destruição de prova",
    ),
]

# ── NEGATIVOS — atividade legítima; NÃO deve disparar nada (mede FP) ──
NEGATIVOS = [
    Scenario(
        "venda_quotas_isolada_antiga",
        "CPF_HON1 transferiu quotas para CNPJ_LIMP1 em 12/01/2019.",
        set(),
        "venda sem procuração e sem marco — não é triangulação",
    ),
    Scenario(
        "transferencia_unica_grande",
        "CPF_HON2 transferiu R$ 500.000,00 para CNPJ_LIMP2 em 10/02/2020.",
        set(),
        "1 transferência alta, longe de marco — sem fracionamento",
    ),
    Scenario(
        "duas_transferencias_abaixo",
        "CPF_HON3 transferiu R$ 5.000,00 para CNPJ_L3 em 01/01/2020. "
        "CPF_HON3 transferiu R$ 5.000,00 para CNPJ_L3 em 02/01/2020.",
        set(),
        "só 2 (< 3) — abaixo do gatilho de fracionamento",
    ),
    Scenario(
        "tres_transferencias_acima_limiar",
        "CPF_HON4 transferiu R$ 50.000,00 para CNPJ_L4 em 01/01/2020. "
        "CPF_HON4 transferiu R$ 50.000,00 para CNPJ_L4 em 02/01/2020. "
        "CPF_HON4 transferiu R$ 50.000,00 para CNPJ_L4 em 03/01/2020.",
        set(),
        "3 transferências mas ACIMA de R$ 10k — não é estruturação",
    ),
    Scenario(
        "movimentacao_sem_marco",
        "CPF_HON5 transferiu R$ 5.000,00 para CNPJ_L5 em 01/06/2026.",
        set(),
        "sem penhora/citação no contexto — sem véspera",
    ),
    Scenario(
        "update_sem_marco",
        "2026-06-10 14:32:11 UPDATE alteracoes registro de CPF_HON6 "
        "campo=data de=08/06/2026 para=01/05/2026 por=op_9",
        set(),
        "edição de data sem marco judicial conhecido — não há antedatação a aferir",
    ),
]

TODOS = POSITIVOS + NEGATIVOS

"""
Testes UNITÁRIOS (offline) dos 7 vetores de cobertura ampliada (coverage.py):
renda×patrimônio, atributo partilhado, passivo simulado, contrato direcionado,
off-ramp cripto, anomalia judiciária (com salvaguardas) e mula financeira.
"""
from agent.coverage import (
    detect_anomalia_judiciaria,
    detect_contrato_direcionado,
    detect_mula_financeira,
    detect_offramp_cripto,
    detect_passivo_simulado,
    detect_patrimonio_incompativel,
    detect_vinculo_por_atributo,
)
from agent.graph import CaseGraph
from agent.parser import parse_document


def _g(text, ev="EV"):
    g = CaseGraph()
    g.ingest(parse_document(text, ev))
    return g


# 1 ── renda × patrimônio ───────────────────────────────────────────────
def test_patrimonio_incompativel():
    g = _g("CPF_SERV declara renda anual de R$ 100.000,00. "
           "CPF_OUTRO transferiu o IMOVEL_X para CPF_SERV por R$ 5.000.000,00. "
           "O IMOVEL_X esta avaliado em R$ 5.000.000,00.")
    ach = detect_patrimonio_incompativel(g)
    assert ach and ach[0]["devedor_alvo"] == "CPF_SERV"
    assert ach[0]["severidade"] == "CRITICA"  # 50x a renda


# 2 ── vínculo por atributo partilhado ──────────────────────────────────
def test_vinculo_por_atributo():
    g = _g("CNPJ_A e CNPJ_B compartilham o mesmo endereço. "
           "CNPJ_A transferiu R$ 50.000,00 para CNPJ_B em 01/01/2024.")
    ach = detect_vinculo_por_atributo(g)
    assert ach and ach[0]["severidade"] == "CRITICA"  # há fluxo entre eles


# 3 ── passivo simulado / credor amigo ──────────────────────────────────
def test_passivo_simulado_familiar():
    g = _g("CPF_DEV confessou dívida de R$ 1.000.000,00 a CPF_CREDOR. "
           "CPF_CREDOR é irmão do devedor CPF_DEV.")
    ach = detect_passivo_simulado(g)
    assert ach and ach[0]["devedor_alvo"] == "CPF_DEV"


# 4 ── contrato público direcionado / fornecedor de fachada ─────────────
def test_contrato_direcionado():
    g = _g("CNPJ_FORN foi constituída em 01/06/2024. "
           "O CNPJ_ORGAO contratou CNPJ_FORN por R$ 9.000.000,00 em 10/06/2024.")
    ach = detect_contrato_direcionado(g)
    assert ach and ach[0]["severidade"] == "CRITICA"  # criada às vésperas


# 5 ── off-ramp em criptoativos ─────────────────────────────────────────
def test_offramp_cripto():
    g = _g("CPF_DEV converteu R$ 2.000.000,00 em criptomoedas e repassou a "
           "CPF_LAR. CPF_LAR é irmão do devedor CPF_DEV.")
    ach = detect_offramp_cripto(g)
    assert ach and ach[0]["severidade"] == "CRITICA"  # destino familiar


# 6 ── anomalia judiciária (salvaguardas) ───────────────────────────────
def test_anomalia_judiciaria_e_salvaguarda():
    # cada decisão é um evento distinto (uma linha do DataJud)
    g = CaseGraph()
    for i in range(3):
        g.ingest(parse_document(
            "O advogado CPF_ADV obteve decisão favorável na VARA_1.", f"EV{i}"))
    ach = detect_anomalia_judiciaria(g)
    assert ach, "esperava sinalizar concentração atípica"
    # NUNCA CRÍTICA — é sinal a apurar, não imputação
    assert ach[0]["severidade"] in ("MEDIA", "ALTA")
    assert "NÃO PROVA" in ach[0]["conclusao_juridica"]


# 7 ── conta de passagem / mula financeira ──────────────────────────────
def test_mula_financeira():
    g = _g("CPF_A transferiu R$ 1.000,00 para CPF_M em 01/01/2024. "
           "CPF_B transferiu R$ 1.000,00 para CPF_M em 02/01/2024. "
           "CPF_C transferiu R$ 1.000,00 para CPF_M em 03/01/2024. "
           "CPF_M transferiu R$ 1.000,00 para CPF_X em 04/01/2024. "
           "CPF_M transferiu R$ 1.000,00 para CPF_Y em 05/01/2024. "
           "CPF_M transferiu R$ 1.000,00 para CPF_Z em 06/01/2024.")
    ach = detect_mula_financeira(g)
    assert ach and ach[0]["devedor_alvo"] == "CPF_M"

"""Parser determinístico + padrões individuais + ACT-R + relatório."""
from agent.graph import CaseGraph
from agent.parser import parse_document
from agent.patterns import (
    detect_fracionamento,
    detect_laranja_familiar,
    detect_triangulacao_offshore,
    detect_vespera_constricao,
)
from agent.act_r import ACTREngine
from agent.report import gerar_relatorio_md
import json


def _g(text):
    g = CaseGraph()
    g.ingest(parse_document(text, "EV"))
    return g


def test_parser_extrai_transacoes_e_datas():
    doc = parse_document(
        "CPF_111 transferiu R$ 9.500,00 para CNPJ_222 em 01/06/2026.", "EV")
    assert len(doc.transactions) == 1
    t = doc.transactions[0]
    assert t.value == 9500.0
    assert t.date == "2026-06-01"


def test_parser_robusto_a_quebras_de_linha():
    # CPFs têm pontos; split ingénuo por '.' destrói tudo. Não deve.
    doc = parse_document(
        "O devedor CPF_645.254.302-49\ntransferiu quotas para a offshore\n"
        "CNPJ_OFFSHORE_01, que nomeou o cunhado CPF_CUNHADO_001 com plenos poderes.",
        "EV")
    tipos = {r.relation_type for r in doc.relations}
    assert "VENDEDOR_QUOTAS" in tipos
    assert "PROCURADOR_COM_PODERES" in tipos


def test_triangulacao_critica_com_familiar():
    g = _g("CPF_645.254.302-49 transferiu quotas para CNPJ_OFF_1, que nomeou "
           "o cunhado CPF_CUNHADO_9 com plenos poderes.")
    achados = detect_triangulacao_offshore(g)
    assert achados and achados[0]["severidade"] == "CRITICA"


def test_laranja_familiar():
    g = _g("CPF_DEV transferiu quotas para CNPJ_OFF, que nomeou o irmão "
           "CPF_IRMAO com plenos poderes.")
    assert detect_laranja_familiar(g)


def test_vespera_constricao():
    g = _g("Houve penhora em 10/06/2026. CPF_DEV transferiu R$ 5.000,00 para "
           "CNPJ_X em 01/06/2026.")
    achados = detect_vespera_constricao(g)
    assert achados and achados[0]["severidade"] == "CRITICA"


def test_fracionamento_nao_dispara_com_duas():
    g = _g("CPF_A transferiu R$ 9.000,00 para CNPJ_B em 01/06/2026. "
           "CPF_A transferiu R$ 9.000,00 para CNPJ_B em 02/06/2026.")
    assert detect_fracionamento(g) == []  # só 2 < 3


def test_act_r_recencia_e_frequencia():
    m = ACTREngine()
    m.record_access("X", 9000)
    fraco = m.calculate_activation("X", 10000)
    for t in range(1000, 9000, 1000):
        m.record_access("Y", t)
    forte = m.calculate_activation("Y", 10000)
    assert forte > fraco  # frequência sobe a ativação


def test_act_r_boost():
    m = ACTREngine()
    base = m.calculate_activation("Z", 10000)  # -inf, nunca visto
    m.boost("Z", tick=10, weight=5)
    apos = m.calculate_activation("Z", 10000)
    assert apos > base


def test_act_r_deterministico():
    # O MESMO log (mesmos ticks) tem de dar a MESMA ativação — sem wall-clock.
    def corre():
        m = ACTREngine()
        for t in (1, 3, 7, 12):
            m.record_access("CPF:1", t)
        return m.calculate_activation("CPF:1", 20)
    assert corre() == corre()


def test_relatorio_contem_custodia():
    insight_row = {
        "id": "01ABC", "lsn": 42, "kind": "INSIGHT_PERICIAL_FRAUDE",
        "content": json.dumps({
            "devedor_alvo": "CPF:1", "tipo_fraude": "triangulacao_offshore",
            "severidade": "CRITICA", "descricao": "desc", "conclusao_juridica": "lei",
            "envolvidos": ["CPF:1", "CNPJ:2"], "ativacao_act_r": {"CPF:1": 1.2},
            "diretrizes_aplicadas": ["DIR1"],
        }),
    }
    md = gerar_relatorio_md(insight_row, ["DOC_A", "DIR1"],
                            fontes={"DOC_A": {"kind": "Observation",
                                              "attrs": {"doc_ref": "OFICIO_9"}}})
    assert "RELATÓRIO PERICIAL" in md
    assert "01ABC" in md
    assert "PROVENANCE" in md
    assert "OFICIO_9" in md
    assert "CRITICA" in md

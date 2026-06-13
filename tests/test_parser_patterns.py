"""Parser determinístico + padrões individuais + ACT-R + relatório."""
from agent.graph import CaseGraph
from agent.parser import parse_document
from agent.patterns import (
    detect_antedatacao,
    detect_fracionamento,
    detect_laranja_familiar,
    detect_registro_apagado,
    detect_suborno,
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


def test_vespera_por_devedor_nao_colapsa():
    # Dois devedores distintos movimentando na véspera → DOIS achados, cada um
    # atribuído ao seu devedor (regressão: antes colapsava num só).
    g = _g("Houve penhora em 10/06/2026. "
           "CPF_DEV1 transferiu R$ 5.000,00 para CNPJ_X em 01/06/2026. "
           "CPF_DEV2 transferiu R$ 7.000,00 para CNPJ_Y em 02/06/2026.")
    achados = detect_vespera_constricao(g)
    alvos = {a["devedor_alvo"] for a in achados}
    assert alvos == {"CPF_DEV1", "CPF_DEV2"}, alvos


def test_parser_extrai_suborno_valor_e_data():
    doc = parse_document(
        "CPF_DEV pagou propina de R$ 250.000,00 ao agente público "
        "CPF_AGENTE em 20/05/2026.", "EV")
    subs = [r for r in doc.relations if r.relation_type == "SUBORNO"]
    assert len(subs) == 1
    assert subs[0].value == 250000.0
    assert subs[0].date == "2026-05-20"


def test_suborno_critico():
    g = _g("CPF_DEV pagou suborno de R$ 80.000,00 ao agente público "
           "CPF_AGENTE em 03/06/2026.")
    achados = detect_suborno(g)
    assert achados and achados[0]["severidade"] == "CRITICA"
    # devedor_alvo é o pagador (agrupa no caso do devedor, não do agente)
    assert achados[0]["devedor_alvo"] == achados[0]["envolvidos"][0]


def test_suborno_nao_dispara_sem_gatilho():
    # transferência comum (sem "propina/suborno") não é corrupção ativa
    g = _g("CPF_DEV transferiu R$ 80.000,00 para CPF_AGENTE em 03/06/2026.")
    assert detect_suborno(g) == []


_LOG_UPDATE = ("2026-06-10 14:32:11 UPDATE alteracoes registro de CPF_DEV "
               "campo=data de=08/06/2026 para=01/05/2026 por=op_47")
_LOG_DELETE = ("2026-06-12 09:15:02 DELETE coaf registro de CPF_DEV "
               "campo=movimentacao por=op_12")
_PENHORA = "Consta ordem de penhora em 05/06/2026 sobre os bens do executado."


def test_parser_extrai_alteracao_update_e_delete():
    doc = parse_document(_LOG_UPDATE + "\n" + _LOG_DELETE, "EV")
    ops = {a.operacao for a in doc.alteracoes}
    assert ops == {"UPDATE", "DELETE"}
    up = next(a for a in doc.alteracoes if a.operacao == "UPDATE")
    assert up.campo == "data" and up.para == "2026-05-01" and up.em == "2026-06-10"


def test_antedatacao_cruza_log_e_marco():
    # data nova (01/05) ANTES do marco (05/06), mas editada (10/06) DEPOIS dele
    g = _g(_PENHORA + "\n" + _LOG_UPDATE)
    achados = detect_antedatacao(g)
    assert achados and achados[0]["severidade"] == "CRITICA"


def test_antedatacao_nao_dispara_sem_marco():
    g = _g(_LOG_UPDATE)  # sem penhora não há antedatação a aferir
    assert detect_antedatacao(g) == []


def test_registro_apagado_apos_marco():
    g = _g(_PENHORA + "\n" + _LOG_DELETE)  # DELETE 12/06 >= penhora 05/06
    achados = detect_registro_apagado(g)
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

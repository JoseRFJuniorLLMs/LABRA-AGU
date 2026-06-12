"""
Testes UNITÁRIOS (offline, sem servidor) dos módulos da Fase 2.

Os testes na raiz (test_phase2_*.py) são de INTEGRAÇÃO — sobem um HeraclitusDB
real. Estes cobrem a lógica pura sobre um CaseGraph construído à mão, logo
correm em CI sem infra. Complementam a separação dedutivo/indutivo/litígio.
"""
import json

from agent.anomaly_engine import AnomalyEngine
from agent.case_memory import CaseMemory
from agent.causal_chain import CausalChainBuilder
from agent.counterfactual import CounterfactualEngine
from agent.evidence_scorer import EvidenceScorer
from agent.graph import CaseGraph
from agent.legal_mapper import LegalMapper
from agent.litigator import Litigator
from agent.parser import parse_document
from agent.theory_builder import TheoryBuilder

DEV = "CPF_645.254.302-49"
TRIANGULACAO = (
    "CPF_645.254.302-49 transferiu quotas para CNPJ_OFF_1, que nomeou o "
    "cunhado CPF_CUNHADO_9 com plenos poderes em 15/03/2024.")


def _g(text, ev="EV1"):
    g = CaseGraph()
    g.ingest(parse_document(text, ev))
    return g


# ── nexo causal: ordena por DATA declarada ─────────────────────────────
def test_causal_chain_ordena_por_data():
    g = CaseGraph()
    g.ingest(parse_document(
        "CPF_DEV transferiu quotas para CNPJ_OFF em 10/01/2024.", "EV_A"))
    g.ingest(parse_document(
        "A CNPJ_OFF nomeou CPF_LAR com plenos poderes em 05/02/2024.", "EV_B"))
    chain = CausalChainBuilder(g).build_chain("CPF_DEV")
    assert chain, "esperava um elo de causalidade pela entidade partilhada"
    # a venda (jan) tem de vir ANTES da procuração (fev)
    primeiro = chain[0]
    assert primeiro["from_ulid"] == "EV_A" and primeiro["to_ulid"] == "EV_B"


# ── contrafactual: a prova única é essencial ───────────────────────────
def test_counterfactual_prova_essencial():
    g = _g(TRIANGULACAO)
    cf = CounterfactualEngine(g)
    essenciais = cf.essential_ulids("CPF_645.254.302-49", "CPF_CUNHADO_9")
    assert "EV1" in essenciais  # removê-la desconecta devedor↔laranja


# ── evidence_scorer: pondera por qualidade da fonte ────────────────────
def test_evidence_scorer_pesos_por_fonte():
    sc = EvidenceScorer(source_map={
        "U_BANCO": {"source": "sql", "table": "movimentacoes_coaf"},
        "U_FILE": {"source": "file", "doc_ref": "contrato.txt"},
    })
    assert sc.weight_of("U_BANCO") == 1.0        # bancária/oficial
    assert sc.weight_of("U_FILE") == 0.6         # documento particular
    assert sc.weight_of("U_INEXISTENTE") is None  # sem proveniência → não pontua
    s = sc.score(["U_BANCO", "U_FILE", "U_INEXISTENTE"])
    assert s["n_provas"] == 2 and 0.7 < s["score"] < 0.85
    assert s["ignorados_sem_proveniencia"] == ["U_INEXISTENTE"]


# ── legal_mapper: subsunção da fraude do INSS ──────────────────────────
def test_legal_mapper_inss():
    enq = LegalMapper().subsume(["fraude_inss"])
    disp = enq["dispositivos"]
    assert any("171" in d for d in disp)   # estelionato previdenciário
    assert any("8.213" in d for d in disp)  # Lei de Benefícios


# ── anomaly_engine: coletor (fan-in alto) ──────────────────────────────
def test_anomaly_coletor_fan_in():
    g = CaseGraph()
    g.ingest(parse_document(
        "CPF_A1 transferiu R$ 1.000,00 para CNPJ_HUB em 01/01/2024. "
        "CPF_B2 transferiu R$ 1.000,00 para CNPJ_HUB em 02/01/2024. "
        "CPF_C3 transferiu R$ 1.000,00 para CNPJ_HUB em 03/01/2024.", "EV"))
    kinds = {a["kind"] for a in AnomalyEngine(g).detect_all()}
    assert "coletor_fan_in" in kinds


# ── case_memory: ator reincidente entre casos ──────────────────────────
def test_case_memory_reincidencia():
    def insight(dev, env):
        return {"id": f"i_{dev}", "kind": "INSIGHT_PERICIAL_FRAUDE",
                "content": json.dumps({"devedor_alvo": dev, "envolvidos": env,
                                       "tipo_fraude": "triangulacao_offshore"})}
    mem = CaseMemory(client=None).load_from_rows([
        insight("CPF:1", ["CPF:1", "CNPJ:9"]),
        insight("CPF:2", ["CPF:2", "CNPJ:9"]),
    ])
    cross = mem.cross_case_actors()
    assert "CNPJ:9" in cross and set(cross["CNPJ:9"]) == {"CPF:1", "CPF:2"}


# ── parser: sinal de confiança (revisão humana) ────────────────────────
def test_parser_baixa_confianca_marca_revisao():
    # vários identificadores, redação fora dos gatilhos → sem fatos extraídos
    texto = ("Os autos mencionam CPF_111.111.111-11 e CNPJ_22.222.222/0001-00 "
             "em circunstâncias que o relatório descreve longamente sem nunca "
             "indicar transferência, doação, procuração ou parentesco. " * 3)
    doc = parse_document(texto, "EV")
    assert doc.needs_review is True and doc.confidence < 1.0


def test_parser_alta_confianca_quando_extrai():
    doc = parse_document(TRIANGULACAO, "EV1")
    assert doc.needs_review is False and doc.confidence == 1.0


# ── theory_builder: montagem completa OFFLINE (grafo + linhas dadas) ────
def test_theory_builder_offline():
    g = _g(TRIANGULACAO)
    rows = [{"id": "EV1", "kind": "Observation", "content": "",
             "attrs": {"source": "file", "doc_ref": "contrato.txt"}}]
    teorias = TheoryBuilder(client=None).build_all(graph=g, rows=rows)
    assert teorias, "esperava ao menos uma teoria do caso"
    t = teorias[0]
    patterns = [a["pattern"] for a in t.matriz_evidencias]
    assert "triangulacao_offshore" in patterns
    assert all(a["evidence_score"] > 0 for a in t.matriz_evidencias)
    # minuta com Fatos e nota de rodapé por ULID
    assert "DOS FATOS" in t.minuta and "[Prova: EV1]" in t.minuta


# ── litigator: minuta golden (estrutura e custódia) ────────────────────
def test_litigator_minuta_estrutura():
    achados = [{
        "tipo_fraude": "triangulacao_offshore", "severidade": "CRITICA",
        "evidence_score": 0.9, "descricao": "Triangulação detectada.",
        "source_events": ["EV1"],
    }]
    md = Litigator().minuta(devedor="CPF:1", devedor_nome="Fulano",
                            achados=achados, causal=[], essenciais=["EV1"])
    for marca in ("## I — DOS FATOS", "## II — DO DIREITO",
                  "## III — DO PEDIDO", "[Prova: EV1]", "CPC, art. 792"):
        assert marca in md, f"minuta sem '{marca}'"

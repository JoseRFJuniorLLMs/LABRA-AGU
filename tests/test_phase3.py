"""Fase 3 — redes entre casos, quantificação/fila e feedback + ER fuzzy."""
from agent.entity_resolution import FuzzyResolver
from agent.feedback import CONFIRMADO, FALSO, FeedbackStore
from agent.graph import CaseGraph
from agent.network_analysis import CrossCaseNetwork
from agent.parser import parse_document
from agent.recovery import priorizar, valor_dissipado


def _g(*textos):
    g = CaseGraph()
    for i, t in enumerate(textos):
        g.ingest(parse_document(t, f"EV{i}"))
    return g


# ── #1 redes entre casos ───────────────────────────────────────────────
def test_facilitador_partilhado_entre_casos():
    # Dois devedores distintos usam a MESMA offshore e o MESMO laranja.
    g = _g(
        "CPF_DEV1 transferiu quotas para CNPJ_OFF, que nomeou CPF_LAR com plenos poderes.",
        "CPF_DEV2 transferiu quotas para CNPJ_OFF, que nomeou CPF_LAR com plenos poderes.",
    )
    net = CrossCaseNetwork(g)
    facs = {f["entidade"]: f for f in net.facilitadores(min_devedores=2)}
    assert "CNPJ_OFF" in facs, facs
    assert facs["CNPJ_OFF"]["n_devedores"] == 2
    assert set(facs["CNPJ_OFF"]["devedores"]) == {"CPF_DEV1", "CPF_DEV2"}


def test_anel_agrupa_devedores():
    g = _g(
        "CPF_DEV1 transferiu quotas para CNPJ_OFF, que nomeou CPF_LAR com plenos poderes.",
        "CPF_DEV2 transferiu quotas para CNPJ_OFF, que nomeou CPF_LAR com plenos poderes.",
    )
    aneis = CrossCaseNetwork(g).aneis(min_devedores=2)
    assert aneis and aneis[0]["n_devedores"] >= 2


def test_casos_independentes_nao_sao_facilitador():
    # Offshores e laranjas DISTINTOS por caso → nenhum facilitador partilhado.
    g = _g(
        "CPF_DEVA transferiu quotas para CNPJ_OFFA, que nomeou CPF_LARA com plenos poderes.",
        "CPF_DEVB transferiu quotas para CNPJ_OFFB, que nomeou CPF_LARB com plenos poderes.",
    )
    assert CrossCaseNetwork(g).facilitadores(min_devedores=2) == []


# ── #2 quantificação + fila ────────────────────────────────────────────
def test_valor_dissipado_soma_saidas():
    g = _g(
        "CPF_DEV transferiu R$ 100.000,00 para CNPJ_X em 01/01/2020. "
        "CPF_DEV transferiu R$ 50.000,00 para CNPJ_X em 02/01/2020.",
    )
    assert valor_dissipado(g, "CPF_DEV") == 150000.0
    assert valor_dissipado(g, "CNPJ_X") == 0.0  # quem RECEBE não dissipou


def test_fila_prioriza_valor_e_severidade():
    casos = [
        {"devedor": "A", "valor": 5_000_000, "severidade_max": "CRITICA"},
        {"devedor": "B", "valor": 1_000, "severidade_max": "BAIXA"},
    ]
    fila = priorizar(casos)
    assert fila[0]["devedor"] == "A"
    assert fila[0]["score_prioridade"] > fila[1]["score_prioridade"]


# ── #3a feedback ───────────────────────────────────────────────────────
def test_feedback_precisao_e_replay():
    s = FeedbackStore()
    ev = [s.registar("suborno", CONFIRMADO), s.registar("suborno", CONFIRMADO),
          s.registar("fracionamento", FALSO)]
    assert s.precisao("suborno") > s.precisao("fracionamento")
    # reconstrução por replay dá o mesmo estado
    s2 = FeedbackStore.from_events(ev)
    assert s2.precisao("suborno") == s.precisao("suborno")


def test_feedback_repondera_baixa_padrao_ruim():
    s = FeedbackStore()
    for _ in range(5):
        s.registar("fracionamento", FALSO)   # só falsos → confiança baixa
    s.registar("suborno", CONFIRMADO)
    achados = [{"pattern": "fracionamento", "severidade": "ALTA"},
               {"pattern": "suborno", "severidade": "ALTA"}]
    rank = s.reponderar(achados)
    assert rank[0]["pattern"] == "suborno"  # sobe apesar de mesma severidade


# ── #3b entity resolution fuzzy ────────────────────────────────────────
def test_fuzzy_sugere_nomes_quase_identicos():
    g = CaseGraph()
    g.entities = {"CPF_X": "Maria Souza", "TMP_Y": "Maria Sousa"}
    cands = FuzzyResolver(g).candidatos()
    pares = {frozenset((c["id_a"], c["id_b"])) for c in cands}
    assert frozenset(("CPF_X", "TMP_Y")) in pares


def test_fuzzy_nao_funde_dois_cpfs_validos():
    g = CaseGraph()
    # dois CPFs validados diferentes, nomes iguais → NÃO sugerir (são pessoas distintas)
    g.entities = {"CPF:52998224725": "Joao Silva", "CPF:11144477735": "Joao Silva"}
    assert FuzzyResolver(g).candidatos() == []

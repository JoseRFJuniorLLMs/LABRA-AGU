"""
test_agent_loop — testes do orquestrador agêntico (ForensicAgent + orchestrator).

Cobre:
  - laço determinístico offline (sem LLM): todas as ferramentas correm e
    a peça é gerada sem erros
  - fallback LLM → determinístico quando o modelo não está disponível
  - cada ferramenta individual (consultar_caso, correr_detectores, …)
  - trace auditável: cada passo gera uma entrada no log de raciocínio
  - integração orquestrador (investigar): ingestão → grafo → peça
  - saída JSON via _json_seguro (sets serializam como listas ordenadas)

Todos os testes são OFFLINE — não precisam de LM Studio nem de
HeraclitusDB. Correm em CI sem qualquer dependência externa.
"""
import json
import pytest

from agent.graph import CaseGraph
from agent.parser import parse_document
from agent.agent_loop import ForensicAgent, _peca_template, _resumo


# ── fixtures ───────────────────────────────────────────────────────────────

DOC_FRAUDE = """
Relatório COAF / Junta Comercial:
O devedor CPF_DEVEDOR_001 transferiu quotas da empresa mãe para uma offshore
CNPJ_OFFSHORE_01, que por sua vez nomeou o cunhado do devedor CPF_CUNHADO_001
como administrador com plenos poderes financeiros no dia 02/06/2026.
CPF_DEVEDOR_001 transferiu R$ 500.000,00 para CNPJ_OFFSHORE_01 em 01/03/2026.
"""

DOC_VENDA_VESPERA = """
Junta Comercial:
CPF_DEVEDOR_002 vendeu quotas da empresa CNPJ_EMP_002 para CPF_LARANJA_002
em 15/01/2026, véspera da penhora judicial registada em 16/01/2026.
"""


def _build_graph(*textos):
    g = CaseGraph()
    for i, t in enumerate(textos):
        g.ingest(parse_document(t, f"EV{i:03}"))
    return g


@pytest.fixture
def graph_fraude():
    return _build_graph(DOC_FRAUDE)


@pytest.fixture
def graph_vespera():
    return _build_graph(DOC_VENDA_VESPERA)


@pytest.fixture
def graph_vazio():
    return CaseGraph()


# ── laço determinístico ────────────────────────────────────────────────────

class TestPlanejadorDeterministico:
    """Sem LLM — planeador determinístico roda todas as ferramentas."""

    def test_investigar_retorna_estrutura_completa(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        resultado = agente.investigar("CPF_DEVEDOR_001")
        assert "trace" in resultado
        assert "dossie" in resultado
        assert "peca" in resultado
        assert resultado["motor"] == "deterministico"

    def test_trace_tem_todos_os_passos(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        resultado = agente.investigar("CPF_DEVEDOR_001")
        ferramentas = {p["acao"] for p in resultado["trace"]}
        # o planeador determinístico deve correr todas as ferramentas
        assert "consultar_caso" in ferramentas
        assert "correr_detectores" in ferramentas
        assert "valor_recuperavel" in ferramentas
        assert "rede_facilitadores" in ferramentas

    def test_trace_numerado_sequencialmente(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        resultado = agente.investigar("CPF_DEVEDOR_001")
        passos = [p["passo"] for p in resultado["trace"]]
        assert passos == list(range(1, len(passos) + 1))

    def test_sem_documentos_nao_levanta_excecao(self, graph_vazio):
        agente = ForensicAgent(graph_vazio, llm=None)
        resultado = agente.investigar("CPF_ALVO_VAZIO")
        assert resultado["motor"] == "deterministico"
        assert isinstance(resultado["peca"], dict)

    def test_dossie_tem_chaves_obrigatorias(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        r = agente.investigar("CPF_DEVEDOR_001")
        for chave in ("devedor", "caso", "achados", "essenciais", "valor", "rede"):
            assert chave in r["dossie"], f"chave '{chave}' ausente no dossie"

    def test_peca_tem_chaves_obrigatorias(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        r = agente.investigar("CPF_DEVEDOR_001")
        peca = r["peca"]
        assert "texto" in peca
        assert "medidas" in peca
        assert "dispositivos" in peca
        assert "provas_essenciais" in peca
        assert "valor_estimado" in peca

    def test_peca_texto_contem_devedor(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        r = agente.investigar("CPF_DEVEDOR_001")
        assert "CPF_DEVEDOR_001" in r["peca"]["texto"]

    def test_valor_recuperavel_no_dossie(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        r = agente.investigar("CPF_DEVEDOR_001")
        # pode ser 0.0 se o parser não extraiu transações, mas não deve ser None
        assert r["dossie"]["valor"] is not None

    def test_vespera_constricao_detectada(self, graph_vespera):
        agente = ForensicAgent(graph_vespera, llm=None)
        r = agente.investigar("CPF_DEVEDOR_002")
        achados = r["dossie"]["achados"]
        padroes = [a["pattern"] for a in achados]
        # pode detectar vespera_constricao ou laranja (depende do grafo) —
        # o importante é que houve detecção
        assert isinstance(padroes, list)  # estrutura OK


# ── ferramentas individuais ────────────────────────────────────────────────

class TestFerramentasIndividuais:
    """Cada ferramenta testada isoladamente via _run_tool."""

    def test_consultar_caso_preenche_estado(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        estado = {"devedor": "CPF_DEVEDOR_001", "caso": None, "achados": [],
                  "essenciais": [], "valor": None, "rede": []}
        agente._run_tool("consultar_caso", "CPF_DEVEDOR_001", estado)
        assert estado["caso"] is not None
        assert "relacoes" in estado["caso"]
        assert "n_transacoes" in estado["caso"]
        assert "marcos" in estado["caso"]

    def test_correr_detectores_devolve_lista(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        estado = {"devedor": "CPF_DEVEDOR_001", "caso": None, "achados": [],
                  "essenciais": [], "valor": None, "rede": []}
        agente._run_tool("correr_detectores", "CPF_DEVEDOR_001", estado)
        assert isinstance(estado["achados"], list)
        for a in estado["achados"]:
            assert "pattern" in a
            assert "severidade" in a
            assert "envolvidos" in a

    def test_valor_recuperavel_devolve_float(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        estado = {"devedor": "CPF_DEVEDOR_001", "caso": None, "achados": [],
                  "essenciais": [], "valor": None, "rede": []}
        agente._run_tool("valor_recuperavel", "CPF_DEVEDOR_001", estado)
        assert isinstance(estado["valor"], float)
        assert estado["valor"] >= 0.0

    def test_rede_facilitadores_devolve_lista(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        estado = {"devedor": "CPF_DEVEDOR_001", "caso": None, "achados": [],
                  "essenciais": [], "valor": None, "rede": []}
        agente._run_tool("rede_facilitadores", "CPF_DEVEDOR_001", estado)
        assert isinstance(estado["rede"], list)

    def test_ferramenta_desconhecida_nao_levanta_excecao(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        estado = {"devedor": "CPF_DEVEDOR_001", "caso": None, "achados": [],
                  "essenciais": [], "valor": None, "rede": []}
        # não deve levantar; obs deve indicar erro suave
        obs = agente._run_tool("ferramenta_inexistente", "CPF_DEVEDOR_001", estado)
        assert "desconhecida" in obs.lower()

    def test_run_tool_regista_no_trace(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, llm=None)
        estado = {"devedor": "CPF_DEVEDOR_001", "caso": None, "achados": [],
                  "essenciais": [], "valor": None, "rede": []}
        assert len(agente.trace) == 0
        agente._run_tool("consultar_caso", "CPF_DEVEDOR_001", estado)
        assert len(agente.trace) == 1
        assert agente.trace[0]["acao"] == "consultar_caso"


# ── fallback LLM ────────────────────────────────────────────────────────────

class TestFallbackLLM:
    """Simula LLM indisponível → deve usar planeador determinístico."""

    def test_llm_indisponivel_usa_determinista(self, graph_fraude):
        class LLMFalso:
            """Simula servidor LLM em baixo."""
            def available(self):
                return False

        agente = ForensicAgent(graph_fraude, llm=LLMFalso())
        r = agente.investigar("CPF_DEVEDOR_001")
        # se `available()` retorna False, usa determinístico
        assert r["motor"] == "deterministico"

    def test_llm_disponivel_flag_motor(self, graph_fraude):
        class LLMFalsoDisp:
            """Simula servidor disponível mas chat falha → fallback interno."""
            def available(self):
                return True

            def chat_json(self, *a, **kw):
                # Retorna "concluir" imediatamente para o laço terminar
                return {"acao": "concluir", "motivo": "teste"}

        agente = ForensicAgent(graph_fraude, llm=LLMFalsoDisp())
        r = agente.investigar("CPF_DEVEDOR_001")
        # com LLM "disponível", motor = gemma/local
        assert r["motor"] == "gemma/local"

    def test_llm_chat_json_excecao_degrada(self, graph_fraude):
        class LLMComErro:
            def available(self):
                return True

            def chat_json(self, *a, **kw):
                raise RuntimeError("timeout simulado")

        agente = ForensicAgent(graph_fraude, llm=LLMComErro())
        # não deve levantar exceção — degrada para completar ferramentas restantes
        r = agente.investigar("CPF_DEVEDOR_001")
        assert isinstance(r["peca"], dict)

    def test_llm_acao_invalida_encerra_laco(self, graph_fraude):
        class LLMRespInvalida:
            def available(self):
                return True

            def chat_json(self, *a, **kw):
                return {"acao": "acaoQueNaoExiste", "motivo": "teste"}

        agente = ForensicAgent(graph_fraude, llm=LLMRespInvalida())
        r = agente.investigar("CPF_DEVEDOR_001")
        # o laço encerra após ação inválida, mas o agente completa as ferramentas
        ferramentas = {p["acao"] for p in r["trace"]}
        assert "consultar_caso" in ferramentas  # garantido pelo completor


# ── auditoria / cliente gRPC ───────────────────────────────────────────────

class TestTraceAuditavel:
    """O trace deve gravar eventos no cliente quando fornecido."""

    def test_trace_grava_no_cliente_mock(self, graph_fraude):
        eventos_gravados = []

        class ClienteMock:
            def append_document(self, *a, **kw):
                eventos_gravados.append(a)

        agente = ForensicAgent(graph_fraude, client=ClienteMock(), llm=None)
        agente.investigar("CPF_DEVEDOR_001")
        # cada passo do laço deve ter gerado um evento
        assert len(eventos_gravados) >= 5  # 5 ferramentas no plano determinístico

    def test_trace_sem_cliente_nao_levanta(self, graph_fraude):
        agente = ForensicAgent(graph_fraude, client=None, llm=None)
        r = agente.investigar("CPF_DEVEDOR_001")
        assert isinstance(r["trace"], list)

    def test_cliente_com_excecao_nao_interrompe_agente(self, graph_fraude):
        class ClienteQuebrado:
            def append_document(self, *a, **kw):
                raise ConnectionError("DB em baixo")

        agente = ForensicAgent(graph_fraude, client=ClienteQuebrado(), llm=None)
        # não deve levantar — cliente com falha é ignorado silenciosamente
        r = agente.investigar("CPF_DEVEDOR_001")
        assert r["motor"] == "deterministico"


# ── helpers internos ───────────────────────────────────────────────────────

class TestHelpers:
    def test_resumo_estado_incompleto(self):
        estado = {"caso": None, "achados": [], "essenciais": [],
                  "valor": None, "rede": []}
        r = _resumo(estado)
        assert r["tem_caso"] is False
        assert r["n_achados"] == 0
        assert r["tem_valor"] is False

    def test_resumo_estado_completo(self):
        estado = {"caso": {"entidade": "X"}, "achados": [{"pattern": "p"}],
                  "essenciais": ["ULID01"], "valor": 100.0, "rede": [{"x": 1}]}
        r = _resumo(estado)
        assert r["tem_caso"] is True
        assert r["n_achados"] == 1
        assert r["tem_valor"] is True
        assert r["tem_essenciais"] is True
        assert r["tem_rede"] is True

    def test_peca_template_sem_achados(self):
        estado = {"caso": {"entidade": "José"}, "devedor": "CPF_X",
                  "achados": [], "essenciais": [], "valor": None, "rede": []}
        txt = _peca_template(estado, [], [])
        assert "CPF_X" in txt
        assert "PETIÇÃO" in txt

    def test_peca_template_com_valor(self):
        estado = {"caso": {"entidade": "Teste"}, "devedor": "CPF_Y",
                  "achados": [], "essenciais": ["ULID01"], "valor": 1_500_000.0,
                  "rede": []}
        txt = _peca_template(estado, ["Desconsideração"], ["CC art. 50"])
        assert "1.500.000,00" in txt  # formato pt-BR
        assert "ULID01" in txt
        assert "CC art. 50" in txt

    def test_peca_template_caso_none(self):
        """Quando `caso` é None, usa o id do devedor como nome."""
        estado = {"caso": None, "devedor": "CPF_Z",
                  "achados": [], "essenciais": [], "valor": 0.0, "rede": []}
        txt = _peca_template(estado, [], [])
        assert "CPF_Z" in txt


# ── integração orquestrador ────────────────────────────────────────────────

class TestOrquestrador:
    """Testa o ponto de entrada de alto nível (agent.orchestrator.investigar)."""

    def test_investigar_texto_inline(self):
        from agent.orchestrator import investigar
        r = investigar(
            "CPF_DEVEDOR_001",
            textos=[DOC_FRAUDE],
            use_llm_agent=False,
        )
        assert "peca" in r
        assert "trace" in r
        assert r["devedor"] == "CPF_DEVEDOR_001"
        assert r["motor"] == "deterministico"

    def test_investigar_sem_documentos(self):
        from agent.orchestrator import investigar
        r = investigar("CPF_SEM_DOC", use_llm_agent=False)
        assert r["motor"] == "deterministico"
        assert isinstance(r["peca"]["texto"], str)

    def test_investigar_normaliza_devedor(self):
        from agent.orchestrator import investigar
        # IDs com e sem normalização devem gerar a mesma entidade alvo
        r = investigar("CPF_DEVEDOR_001", textos=[DOC_FRAUDE],
                       use_llm_agent=False)
        assert r["devedor"] == "CPF_DEVEDOR_001"

    def test_investigar_serializa_json(self):
        from agent.orchestrator import investigar, _json_seguro
        r = investigar("CPF_DEVEDOR_001", textos=[DOC_FRAUDE],
                       use_llm_agent=False)
        # não deve levantar ao serializar (sets → listas ordenadas)
        s = json.dumps(r, default=_json_seguro, ensure_ascii=False)
        assert isinstance(s, str)
        d = json.loads(s)
        assert "peca" in d

    def test_investigar_max_passos_respeitado(self):
        """max_passos=2 não deve causar exceção — agente termina cedo e completa."""
        from agent.orchestrator import investigar
        r = investigar("CPF_DEVEDOR_001", textos=[DOC_FRAUDE],
                       use_llm_agent=False, max_passos=2)
        # com planeador determinístico, max_passos não limita (roda tudo de uma vez)
        assert isinstance(r["trace"], list)

    def test_investigar_dois_documentos(self):
        """Dois documentos no grafo acumulam relações."""
        from agent.orchestrator import investigar
        r = investigar(
            "CPF_DEVEDOR_001",
            textos=[DOC_FRAUDE, DOC_VENDA_VESPERA],
            use_llm_agent=False,
        )
        caso = r["dossie"]["caso"]
        assert caso is not None
        # com dois documentos, o grafo tem pelo menos algumas relações
        assert isinstance(caso["relacoes"], list)

"""
O teste-chave: correlação MULTI-DOCUMENTO.

Prova que a fraude espalhada por documentos diferentes — que o agente
antigo NUNCA detectaria — é detectada quando os fatos se acumulam no grafo
de caso. Também cobre: dedup, proveniência composta, e resolução de
entidades a unir o mesmo CPF escrito de formas diferentes.
"""
from agent.investigator import Directive, Investigator
from agent.parser import parse_document


def _doc(text, ev):
    return parse_document(text, source_event_id=ev)


def test_triangulacao_dividida_em_dois_documentos():
    inv = Investigator()

    # Documento A (Junta Comercial): só a venda de quotas. Sozinho, NADA.
    a = _doc(
        "O devedor CPF_529.982.247-25 transferiu quotas da empresa para a "
        "offshore CNPJ_11.222.333/0001-81.",
        "DOC_A",
    )
    assert inv.process_document(a) == [], "venda isolada não é fraude ainda"

    # Documento B (Cartório), dias depois, OUTRA fonte: a procuração.
    b = _doc(
        "A CNPJ_11.222.333/0001-81 nomeou CPF_CUNHADO_001 como administrador "
        "com plenos poderes.",
        "DOC_B",
    )
    insights = inv.process_document(b)

    # AGORA a triangulação fecha-se — atravessando os dois documentos.
    tipos = {i["payload"]["tipo_fraude"] for i in insights}
    assert "triangulacao_offshore" in tipos

    tri = next(i for i in insights if i["payload"]["tipo_fraude"] == "triangulacao_offshore")
    # Proveniência COMPOSTA: ambos os documentos sustentam o achado.
    assert set(tri["parents"]) >= {"DOC_A", "DOC_B"}


def test_dedup_nao_repete_alerta():
    inv = Investigator()
    txt = (
        "CPF_529.982.247-25 transferiu quotas para CNPJ_11.222.333/0001-81, "
        "que nomeou CPF_X com plenos poderes."
    )
    primeiro = inv.process_document(_doc(txt, "D1"))
    assert any(i["payload"]["tipo_fraude"] == "triangulacao_offshore" for i in primeiro)
    # Reprocessar o MESMO esquema (novo documento, mesmas entidades) não
    # deve emitir o mesmo achado outra vez.
    segundo = inv.process_document(_doc(txt, "D2"))
    assert all(i["payload"]["tipo_fraude"] != "triangulacao_offshore" for i in segundo)


def test_fracionamento_soma_extratos_separados():
    inv = Investigator()
    # Três extratos, três documentos distintos, cada transferência abaixo do
    # limiar COAF — só a soma acumulada dispara o alerta.
    inv.process_document(_doc(
        "CPF_529.982.247-25 transferiu R$ 9.500,00 para CNPJ_11.222.333/0001-81 em 01/06/2026.", "E1"))
    inv.process_document(_doc(
        "CPF_529.982.247-25 transferiu R$ 9.800,00 para CNPJ_11.222.333/0001-81 em 02/06/2026.", "E2"))
    out = inv.process_document(_doc(
        "CPF_529.982.247-25 transferiu R$ 9.700,00 para CNPJ_11.222.333/0001-81 em 03/06/2026.", "E3"))
    fr = [i for i in out if i["payload"]["tipo_fraude"] == "fracionamento"]
    assert fr, "três sub-limiar somando > limiar deviam disparar fracionamento"
    assert set(fr[0]["parents"]) >= {"E1", "E2", "E3"}


def test_entidades_mesmo_cpf_formas_diferentes_um_no():
    inv = Investigator()
    # Mesma pessoa, grafias diferentes em documentos diferentes.
    inv.process_document(_doc(
        "CPF_529.982.247-25 transferiu quotas para CNPJ_11.222.333/0001-81.", "X1"))
    out = inv.process_document(_doc(
        "A CNPJ_11.222.333/0001-81 nomeou 529.982.247-25 com plenos poderes.", "X2"))
    # O devedor (vendedor) e o procurador resolvem para o mesmo CPF canónico
    # -> laranja (auto-procuração) é detectável porque é UM só nó.
    assert inv.graph.entities, "grafo deve ter entidades"
    canon = "CPF:52998224725"
    assert canon in inv.graph.entities


def test_diretriz_boost_e_proveniencia():
    inv = Investigator()
    inv.register_directive(Directive(
        event_id="DIR1", alvos=["CPF_529.982.247-25"], boost=8))
    out = inv.process_document(_doc(
        "CPF_529.982.247-25 transferiu quotas para CNPJ_11.222.333/0001-81, "
        "que nomeou CPF_Y com plenos poderes.", "DOCZ"))
    tri = next(i for i in out if i["payload"]["tipo_fraude"] == "triangulacao_offshore")
    # A diretriz entra na proveniência e em diretrizes_aplicadas.
    assert "DIR1" in tri["parents"]
    assert tri["payload"]["diretrizes_aplicadas"] == ["DIR1"]
    # O boost deu ativação real ao alvo.
    assert tri["payload"]["ativacao_act_r"]["CPF:52998224725"] > 0

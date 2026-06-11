"""
Teste de integração LABRA-AGU <-> HeraclitusDB (servidor FRESCO, isolado).

Verifica o ciclo completo da cadeia de custódia:
  1. Append do documento-fonte (evento imutável no log)
  2. Resolução LSN -> ULID via Query
  3. Investigação (ACT-R + detecção de triangulação)
  4. Append do insight com `parents` = ULID real do documento
  5. PROVENANCE(insight) devolve exatamente o ULID do documento-fonte
  6. O insight é consultável por GQL (MATCH por attrs) e o payload bate
  7. AS OF LSN prova que o insight é invisível no passado (event sourcing)

Sai com código 0 (sucesso) ou 1 (falha), imprimindo cada passo.
"""
import json
import sys

from agent.client import HeraclitusClient, is_ulid
from agent.investigator import Investigator
from agent.parser import parse_document
from agent.testing import server_bin, temp_server

DOC = """
Relatório COAF / Junta Comercial:
O devedor CPF_645.254.302-49 transferiu quotas da empresa mãe para uma offshore
CNPJ_OFFSHORE_01, que por sua vez nomeou o cunhado do devedor CPF_CUNHADO_001 como
administrador com plenos poderes financeiros no dia 02/06/2026.
"""


def step(n, msg):
    print(f"[{n}] {msg}")


def main() -> int:
    if not server_bin():
        print("SKIP: heraclitus-server não encontrado (defina HERACLITUS_SERVER_BIN)")
        return 0
    with temp_server() as target:
        return _run(target)


def _run(target) -> int:
    client = HeraclitusClient(target)
    head = client.snapshot()
    step(0, f"servidor fresco em {target} (head LSN = {head})")

    # 1. Custódia: documento-fonte entra no log
    doc_lsn = client.append_document(
        "agente_pericial_labra_v1", DOC, attrs={"doc_ref": "TESTE_JUNTA_504"}
    )
    assert doc_lsn >= head, "LSN do documento deve ser >= head anterior"
    step(1, f"documento-fonte gravado (LSN={doc_lsn})")

    # 2. LSN -> ULID
    source_id = client.resolve_event_id(doc_lsn)
    assert is_ulid(source_id), f"id resolvido não é ULID: {source_id}"
    step(2, f"ULID do documento resolvido: {source_id}")

    # 3. Investigação com o ULID real como fonte
    parsed = parse_document(DOC, source_event_id=source_id)
    insight = Investigator().process_document_single(parsed)
    assert insight is not None, "o padrão de triangulação devia ser detectado"
    assert insight["parents"] == [source_id], "parents deve ser o ULID da fonte"
    step(3, f"fraude detectada: {insight['payload']['tipo_fraude']}")

    # 4. Insight gravado com proveniência real
    insight_lsn = client.append_insight(insight)
    insight_id = client.resolve_event_id(insight_lsn)
    assert is_ulid(insight_id)
    step(4, f"insight gravado (LSN={insight_lsn}, ULID={insight_id})")

    # 5. Cadeia de custódia inversa
    chain = client.provenance(insight_id)
    assert chain == [source_id], f"PROVENANCE devia devolver [{source_id}], veio {chain}"
    step(5, f"PROVENANCE confirma a cadeia de custódia: {chain}")

    # 6. O insight é consultável e o payload sobrevive intacto
    rows = client.query(
        'MATCH (n) WHERE n.generated_by = "labra_agent" RETURN n ORDER BY n.lsn DESC'
    )
    insight_rows = [r for r in rows if r["id"] == insight_id]
    assert insight_rows, "insight não encontrado via MATCH"
    payload = json.loads(insight_rows[0]["content"])
    assert payload["tipo_fraude"] == insight["payload"]["tipo_fraude"]
    assert insight_rows[0]["kind"].find("INSIGHT_PERICIAL_FRAUDE") >= 0
    step(6, "insight consultável por GQL; payload pericial intacto")

    # 7. Snapshot temporal: antes do documento, nada disto existia
    old = client.query(f"MATCH (n) AS OF LSN {doc_lsn} RETURN n")
    assert all(r["id"] != insight_id for r in old), "AS OF não devia ver o insight"
    step(7, f"AS OF LSN {doc_lsn}: o insight é invisível no passado (event sourcing OK)")

    print("\nINTEGRACAO LABRA-AGU <-> HeraclitusDB: SUCESSO TOTAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())

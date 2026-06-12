"""
Teste e2e do graph_timeline — reconstrução do CaseGraph AS OF LSN sobre o log
real do HeraclitusDB (servidor fresco, isolado).

Prova:
  1. AS OF um ponto do passado NÃO vê eventos posteriores (event sourcing);
  2. o estado atual contém a triangulação inteira (venda + procuração + vínculo);
  3. diff(passado, agora) revela exatamente as arestas surgidas entretanto;
  4. frames() devolve estados monotonicamente crescentes;
  5. o snapshot é serializável e cada aresta cita ULIDs de origem (proveniência).
"""
import json
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.client import HeraclitusClient
from agent.graph_timeline import GraphTimeline
from agent.testing import server_bin, temp_server

DEV = "52998224725"                       # CPF cru válido
OFF = "CNPJ_11.222.333/0001-81"           # offshore
LAR = "CPF_BENEFICIARIO_07"               # laranja (placeholder simbólico)


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
    tl = GraphTimeline(client)
    step(0, f"servidor fresco em {target} (head={tl.head()})")

    # Perna 1 — venda de quotas (Junta). `pos_*` = posição do log (head) após
    # o evento; at_lsn(pos) inclui esse evento (AS OF LSN é exclusivo no topo).
    client.append_document(
        "pipeline", f"{DEV} transferiu quotas da empresa para a offshore {OFF} "
        "em 01/06/2026", attrs={"source": "sql", "table": "alteracoes"})
    pos_venda = tl.head()
    g1 = tl.at_lsn(pos_venda)
    assert g1.rels("VENDEDOR_QUOTAS"), "venda devia existir AS OF pos_venda"
    assert not g1.rels("PROCURADOR_COM_PODERES"), "procuração ainda não existe"
    step(1, f"AS OF LSN {pos_venda}: só a venda no grafo {g1.stats()}")

    # Perna 2 — procuração (Cartório).
    client.append_document(
        "pipeline", f"A {OFF} nomeou {LAR} com plenos poderes em 03/06/2026",
        attrs={"source": "sql", "table": "procuracoes"})
    pos_proc = tl.head()
    # O passado é imutável: AS OF pos_venda continua a NÃO ver a procuração.
    assert not tl.at_lsn(pos_venda).rels("PROCURADOR_COM_PODERES"), \
        "AS OF passado não pode ver evento posterior"
    g2 = tl.at_lsn(pos_proc)
    assert g2.rels("PROCURADOR_COM_PODERES"), "procuração visível AS OF pos_proc"
    step(2, f"AS OF passado intacto; AS OF LSN {pos_proc}: venda+procuração")

    # Perna 3 — vínculo familiar (documento).
    client.append_document("pipeline", f"{LAR} é cunhado do devedor {DEV}",
                           attrs={"source": "file"})
    head = tl.head()
    gf = tl.at_lsn(head)
    assert gf.rels("FAMILIAR"), "vínculo familiar no estado atual"
    step(3, f"estado atual (head={head}): triangulação completa {gf.stats()}")

    # 4. diff passado -> agora
    d = tl.diff(pos_venda, head)
    rtypes = {r["type"] for r in d["relations"]}
    assert "PROCURADOR_COM_PODERES" in rtypes and "FAMILIAR" in rtypes, rtypes
    step(4, f"diff(LSN {pos_venda} → {head}): arestas novas = {sorted(rtypes)}")

    # 5. frames monotonicamente crescentes
    fr = tl.frames([pos_venda, pos_proc, head])
    counts = [g.stats()["relations"] for _, g in fr]
    assert counts == sorted(counts) and counts[0] < counts[-1], counts
    step(5, f"frames: relações por checkpoint = {counts}")

    # 6. snapshot serializável + proveniência por aresta (ULIDs reais)
    snap = tl.snapshot_dict(gf)
    json.dumps(snap)  # tem de ser serializável
    assert snap["relations"], "snapshot deve ter relações"
    for r in snap["relations"]:
        assert r["events"], f"aresta sem proveniência: {r}"
    step(6, f"snapshot serializável; {len(snap['relations'])} arestas com ULID")

    print("\nGRAPH_TIMELINE (AS OF LSN) <-> HeraclitusDB: SUCESSO TOTAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())

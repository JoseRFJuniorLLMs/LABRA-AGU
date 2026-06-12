"""
Teste e2e do case_memory — inteligência cross-case sobre o log do HeraclitusDB.

Dois casos com devedores distintos que partilham o MESMO laranja. A memória,
reconstruída do log (event sourcing), deve:
  - reconhecer o laranja como ator reincidente (em 2 casos);
  - avisar, ao analisar o caso B, que aquele laranja já operou no caso A;
  - pontuar a similaridade estrutural entre os dois casos (Jaccard).
"""
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.case_memory import CaseMemory
from agent.client import HeraclitusClient
from agent.testing import server_bin, temp_server

DEV_A = "CPF:11111111111"
DEV_B = "CPF:22222222222"
OFF_A = "CNPJ:11111111111111"
OFF_B = "CNPJ:22222222222222"
LAR = "CPF:99999999999"           # o laranja partilhado pelos dois casos


def _insight(devedor, envolvidos, tipo):
    return {
        "agent_id": "agente_pericial_labra_v1",
        "event_type": "INSIGHT_PERICIAL_FRAUDE",
        "parents": [],
        "payload": {
            "devedor_alvo": devedor, "tipo_fraude": tipo,
            "severidade": "CRITICA", "envolvidos": envolvidos,
            "descricao": "x", "conclusao_juridica": "y",
        },
    }


def main() -> int:
    if not server_bin():
        print("SKIP: heraclitus-server não encontrado")
        return 0
    with temp_server() as target:
        client = HeraclitusClient(target)
        # Caso A e Caso B, partilhando o laranja LAR.
        client.append_insight(_insight(DEV_A, [DEV_A, OFF_A, LAR], "triangulacao_offshore"))
        client.append_insight(_insight(DEV_A, [DEV_A, LAR], "laranja_familiar"))
        client.append_insight(_insight(DEV_B, [DEV_B, OFF_B, LAR], "triangulacao_offshore"))

        mem = CaseMemory(client).load()
        assert mem.stats()["casos"] == 2, mem.stats()
        print(f"[0] memória reconstruída do log: {mem.stats()}")

        cross = mem.cross_case_actors()
        assert LAR in cross and set(cross[LAR]) == {DEV_A, DEV_B}, cross
        assert OFF_A not in cross, "offshore de um só caso não é reincidente"
        print(f"[1] ator reincidente: {LAR} aparece nos casos {cross[LAR]}")

        rec = mem.recurring_entities([DEV_B, OFF_B, LAR], exclude_devedor=DEV_B)
        assert rec.get(LAR) == [DEV_A], rec
        assert DEV_B not in rec and OFF_B not in rec
        print(f"[2] ao analisar o caso B, o laranja já operava no caso {rec[LAR]}")

        sim = mem.similar_cases(DEV_B)
        assert sim and sim[0]["devedor"] == DEV_A and sim[0]["similaridade"] > 0, sim
        assert LAR in sim[0]["entidades_comuns"]
        print(f"[3] similaridade estrutural caso B↔A = {sim[0]['similaridade']} "
              f"(comuns: {sim[0]['entidades_comuns']})")

        aviso = mem.check_new_case([DEV_B, OFF_B, LAR], devedor=DEV_B)
        assert aviso["alerta"] and LAR in aviso["atores_reincidentes"]
        print(f"[4] check_new_case(B): alerta={aviso['alerta']}, "
              f"reincidentes={list(aviso['atores_reincidentes'])}")

        print("\nFASE 2 — MEMÓRIA CROSS-CASE (case_memory): SUCESSO TOTAL")
        return 0


if __name__ == "__main__":
    sys.exit(main())

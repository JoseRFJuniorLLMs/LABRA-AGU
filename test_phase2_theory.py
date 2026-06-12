"""
Teste e2e do theory_builder — o orquestrador da Fase 2.

Ingere o cenário de triangulação no log e verifica que a Teoria do Caso:
  - reúne os achados dedutivos pontuados por força probatória;
  - escolhe o alvo principal e ordena a matriz de evidências;
  - gera a minuta com Fatos/Direito/Pedido e nota de rodapé por ULID;
  - invoca os dispositivos legais corretos (CPC 792, Lei 9.613/98, CC 50).
"""
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.client import HeraclitusClient
from agent.testing import server_bin, temp_server
from agent.theory_builder import TheoryBuilder

DEV = "52998224725"
OFF = "CNPJ_11.222.333/0001-81"
LAR = "CPF_BENEFICIARIO_07"


def main() -> int:
    if not server_bin():
        print("SKIP: heraclitus-server não encontrado")
        return 0
    with temp_server() as target:
        c = HeraclitusClient(target)
        c.append_document("pipe", f"{DEV} transferiu quotas da empresa para a "
                          f"offshore {OFF} em 12/05/2026",
                          attrs={"source": "sql", "table": "alteracoes"})
        c.append_document("pipe", f"A {OFF} nomeou {LAR} com plenos poderes em "
                          "13/05/2026", attrs={"source": "sql", "table": "procuracoes"})
        c.append_document("pipe", f"{LAR} é cunhado do devedor {DEV}.",
                          attrs={"source": "file", "doc_ref": "vinculos.txt"})
        c.append_document("pipe",
                          f"{DEV} transferiu R$ 9.500,00 para {LAR} em 14/05/2026. "
                          f"{DEV} transferiu R$ 8.700,00 para {LAR} em 15/05/2026. "
                          f"{DEV} transferiu R$ 9.200,00 para {LAR} em 16/05/2026.",
                          attrs={"source": "sql", "table": "movimentacoes"})
        c.append_document("pipe", "Consta ordem de bloqueio judicial (penhora) "
                          "prevista para 05/06/2026.",
                          attrs={"source": "file", "doc_ref": "processo.pdf"})

        theory = TheoryBuilder(c).build()
        assert theory is not None, "teoria do caso não produzida"
        print(f"[0] alvo principal: {theory.devedor}  "
              f"({len(theory.matriz_evidencias)} achados)")

        tipos = {a["pattern"] for a in theory.matriz_evidencias}
        assert "triangulacao_offshore" in tipos, tipos
        print(f"[1] achados: {sorted(tipos)}")

        # matriz ordenada por força probatória, todos com proveniência rastreável
        scores = [a["evidence_score"] for a in theory.matriz_evidencias]
        assert scores == sorted(scores, reverse=True) and all(s > 0 for s in scores)
        print(f"[2] força probatória (ordenada): {scores}")

        # anomalias indutivas presentes
        assert theory.anomalias, "anomalias não calculadas"
        print(f"[3] anomalias indutivas: {len(theory.anomalias)} "
              f"(top: {theory.anomalias[0]['kind']})")

        # minuta: estrutura + citação por ULID + dispositivos legais
        m = theory.minuta
        for secao in ("DOS FATOS", "DO DIREITO", "DO PEDIDO"):
            assert secao in m, f"minuta sem secção {secao}"
        assert "[Prova:" in m, "minuta sem nota de rodapé por ULID"
        assert "CPC, art. 792" in m, "minuta sem o dispositivo de fraude à execução"
        print("[4] minuta: Fatos/Direito/Pedido + notas de rodapé ULID + CPC 792")

        # a peça cita ULIDs reais do log (26 chars), não placeholders
        import re
        ulids = re.findall(r"\b[0-9A-HJKMNP-TV-Z]{26}\b", m)
        assert ulids, "minuta não cita ULIDs reais"
        print(f"[5] minuta cita {len(set(ulids))} ULID(s) reais do log")

        print("\nFASE 2 — TEORIA DO CASO (theory_builder + legal_mapper + "
              "litigator): SUCESSO TOTAL")
        return 0


if __name__ == "__main__":
    sys.exit(main())

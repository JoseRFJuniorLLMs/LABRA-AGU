"""
Teste unitário do passo 2 (Motor de Captura Avançado) — sem servidor.

Constrói um CaseGraph a partir de documentos sintéticos (via o parser real) e
verifica:
  - asset_shield: holding_usufruto, doacao_cruzada e offshore_cascata disparam;
  - anomaly_engine: deteta hub/ponte (estrutural) e estruturação + véspera
    (comportamental) sem nenhuma regra de limiar fixa.
"""
import sys

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agent.anomaly_engine import AnomalyEngine
from agent.asset_shield import SHIELD_PATTERNS
from agent.graph import CaseGraph
from agent.parser import parse_document

DEV = "52998224725"        # devedor (CPF cru válido)


def _graph(docs):
    g = CaseGraph()
    for i, text in enumerate(docs):
        g.ingest(parse_document(text, source_event_id=f"01EV{i:026d}"[:26]))
    return g


def _run(detector_name, graph):
    return SHIELD_PATTERNS[detector_name](graph)


def main() -> int:
    # ── asset_shield ──────────────────────────────────────────────────
    g = _graph([
        # holding/usufruto: devedor administra empresa sem quotas aparentes
        f"O devedor {DEV} é usufrutuário vitalício do imóvel da empresa "
        "CNPJ_HOLDING_07, sem deter quotas.",
        # doação cruzada: devedor -> intermediário -> laranja final
        f"{DEV} doou um apartamento para CPF_INTERM_03.",
        "CPF_INTERM_03 doou o mesmo apartamento para CPF_LARANJA_09.",
        f"CPF_LARANJA_09 é cunhado do devedor {DEV}.",
        # offshore em cascata: controle indireto em camadas
        f"{DEV} controla a offshore CNPJ_OFF_AA.",
        "CNPJ_OFF_AA controla a offshore CNPJ_OFF_BB.",
    ])

    hold = _run("holding_usufruto", g)
    assert hold and hold[0]["severidade"] == "CRITICA", hold
    print(f"[1] holding_usufruto: {hold[0]['severidade']} — {hold[0]['envolvidos']}")

    doac = _run("doacao_cruzada", g)
    assert doac and any(d["severidade"] == "CRITICA" for d in doac), doac
    crit = next(d for d in doac if d["severidade"] == "CRITICA")
    assert len(crit["envolvidos"]) == 3, crit
    print(f"[2] doacao_cruzada: {crit['severidade']} — cadeia {crit['envolvidos']}")

    casc = _run("offshore_cascata", g)
    assert casc, "cascata de controle devia disparar"
    print(f"[3] offshore_cascata: {casc[0]['envolvidos']}")

    # proveniência: todo achado cita ULIDs de origem
    for name in SHIELD_PATTERNS:
        for a in _run(name, g):
            assert a["source_events"], f"{name} sem proveniência"
    print("[4] todos os achados do asset_shield citam ULIDs de origem")

    # ── anomaly_engine (estrutural) ───────────────────────────────────
    # Um hub que recebe de muitas origens + é ponte entre clusters.
    gh = _graph([
        f"{DEV} doou para CPF_HUB_01.",
        "CPF_OUTRO_A doou para CPF_HUB_01.",
        "CPF_OUTRO_B doou para CPF_HUB_01.",
        "CPF_HUB_01 controla a CNPJ_FINAL_Z.",
    ])
    estru = AnomalyEngine(gh).detect_structural_anomalies()
    kinds = {a["kind"] for a in estru}
    assert "coletor_fan_in" in kinds, kinds
    assert "ponte_articulacao" in kinds, kinds
    top = max(estru, key=lambda a: a["score"])
    print(f"[5] estrutural: {sorted(kinds)} (top score {top['score']})")

    # ── anomaly_engine (comportamental) ───────────────────────────────
    gb = _graph([
        # 3 transferências sub-limiar, variância baixa (estruturação)
        f"{DEV} transferiu R$ 9.500,00 para CPF_BENEF_1 em 14/05/2026.",
        f"{DEV} transferiu R$ 9.200,00 para CPF_BENEF_1 em 15/05/2026.",
        f"{DEV} transferiu R$ 9.800,00 para CPF_BENEF_1 em 16/05/2026.",
        # marco judicial próximo -> timing de véspera
        "Consta ordem de bloqueio judicial (penhora) prevista para 05/06/2026.",
    ])
    comp = AnomalyEngine(gb).detect_behavioral_anomalies()
    bkinds = {a["kind"] for a in comp}
    assert "estruturacao_sub_limiar" in bkinds, bkinds
    assert "timing_vespera" in bkinds, bkinds
    print(f"[6] comportamental: {sorted(bkinds)}")

    print("\nFASE 2 — MOTOR DE CAPTURA (asset_shield + anomaly_engine): SUCESSO TOTAL")
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Harness de avaliação — corre os detectores sobre cenários rotulados e calcula
precisão / recall / F1 por padrão (e agregados micro/macro).

100% offline e determinístico: usa o Investigator em memória (sem servidor),
logo corre em CI. É a peça que torna a deteção VERIFICÁVEL — sem isto, o
sistema afirma fraudes mas não mede se acerta.

Definições por padrão p (sobre o conjunto de cenários):
  TP = cenários onde p era esperado E foi detectado
  FP = cenários onde p NÃO era esperado mas foi detectado (falso alarme)
  FN = cenários onde p era esperado mas NÃO foi detectado (omissão)
  precisão = TP/(TP+FP)   recall = TP/(TP+FN)   F1 = 2PR/(P+R)
"""
from collections import defaultdict
from typing import Dict, List, Set

from agent.investigator import Investigator
from agent.parser import parse_document


def detectar(texto: str) -> Set[str]:
    """Padrões detectados num texto — Investigator fresco, em memória."""
    inv = Investigator()
    insights = inv.process_document(parse_document(texto, "EV"))
    return {i["payload"]["tipo_fraude"] for i in insights}


def _prf(tp: int, fp: int, fn: int) -> Dict[str, float]:
    prec = tp / (tp + fp) if (tp + fp) else 1.0
    rec = tp / (tp + fn) if (tp + fn) else 1.0
    f1 = (2 * prec * rec / (prec + rec)) if (prec + rec) else 0.0
    return {"precision": round(prec, 3), "recall": round(rec, 3),
            "f1": round(f1, 3), "tp": tp, "fp": fp, "fn": fn}


def avaliar(scenarios) -> dict:
    tp: Dict[str, int] = defaultdict(int)
    fp: Dict[str, int] = defaultdict(int)
    fn: Dict[str, int] = defaultdict(int)
    universo: Set[str] = set()
    detalhe: List[dict] = []

    for s in scenarios:
        detectado = detectar(s.texto)
        esperado = set(s.esperado)
        universo |= esperado | detectado
        for p in esperado & detectado:
            tp[p] += 1
        for p in detectado - esperado:
            fp[p] += 1
        for p in esperado - detectado:
            fn[p] += 1
        detalhe.append({
            "nome": s.nome, "esperado": sorted(esperado),
            "detectado": sorted(detectado),
            "fp": sorted(detectado - esperado),
            "fn": sorted(esperado - detectado),
            "ok": detectado == esperado,
        })

    por_padrao = {p: _prf(tp[p], fp[p], fn[p]) for p in sorted(universo)}
    TP, FP, FN = sum(tp.values()), sum(fp.values()), sum(fn.values())
    micro = _prf(TP, FP, FN)
    # macro = média simples dos F1 por padrão
    f1s = [m["f1"] for m in por_padrao.values()]
    macro_f1 = round(sum(f1s) / len(f1s), 3) if f1s else 0.0
    return {
        "por_padrao": por_padrao,
        "micro": micro,
        "macro_f1": macro_f1,
        "detalhe": detalhe,
        "n_cenarios": len(scenarios),
    }

"""
feedback — aprendizado pelo veredicto do procurador (Fase 3).

Fecha o ciclo que faltava: cada alerta CONFIRMADO ou REFUTADO pelo analista é
um EVENTO (cabe naturalmente no log append-only — event sourcing). A precisão
empírica de cada PADRÃO é recalculada e re-pondera a confiança dos alertas
futuros. Sem ML pesado: é Bayes empírico com suavização de Laplace (prior 0.5),
honesto e auditável — um padrão que só dá falso alarme perde confiança sozinho.

Reconstruível por replay: `from_events()` recria o estado a partir dos eventos
de feedback do log, igual ao resto do sistema.
"""
from collections import defaultdict
from typing import Dict, List

CONFIRMADO = "confirmado"
FALSO = "falso"
_VEREDICTOS = (CONFIRMADO, FALSO)


class FeedbackStore:
    def __init__(self):
        self._conf: Dict[str, int] = defaultdict(int)   # padrão -> confirmados
        self._falso: Dict[str, int] = defaultdict(int)  # padrão -> refutados

    def registar(self, pattern: str, veredicto: str) -> dict:
        """Regista um veredicto. Devolve o evento (pronto a persistir no log)."""
        if veredicto not in _VEREDICTOS:
            raise ValueError(f"veredicto inválido: {veredicto!r} (use "
                             f"{CONFIRMADO!r} ou {FALSO!r})")
        if veredicto == CONFIRMADO:
            self._conf[pattern] += 1
        else:
            self._falso[pattern] += 1
        return {"tipo": "FEEDBACK_PERICIAL", "pattern": pattern,
                "veredicto": veredicto}

    @classmethod
    def from_events(cls, eventos: List[dict]) -> "FeedbackStore":
        """Reconstrói o estado a partir de eventos de feedback (replay)."""
        store = cls()
        for e in eventos:
            p, v = e.get("pattern"), e.get("veredicto")
            if p and v in _VEREDICTOS:
                store.registar(p, v)
        return store

    def precisao(self, pattern: str) -> float:
        """Precisão empírica do padrão (Laplace: prior 0.5 sem dados)."""
        c, f = self._conf[pattern], self._falso[pattern]
        return (c + 1) / (c + f + 2)

    def amostras(self, pattern: str) -> int:
        return self._conf[pattern] + self._falso[pattern]

    def reponderar(self, achados: List[dict]) -> List[dict]:
        """Anota cada achado com `confianca_aprendida` (precisão empírica do
        padrão) e reordena por severidade × confiança. Não apaga nada — só
        re-prioriza com base na experiência acumulada."""
        sev = {"CRITICA": 1.0, "ALTA": 0.7, "MEDIA": 0.4, "BAIXA": 0.2}
        for a in achados:
            conf = self.precisao(a.get("pattern", ""))
            a["confianca_aprendida"] = round(conf, 3)
            a["amostras_feedback"] = self.amostras(a.get("pattern", ""))
            a["_rank"] = sev.get(a.get("severidade"), 0.3) * conf
        return sorted(achados, key=lambda a: a["_rank"], reverse=True)

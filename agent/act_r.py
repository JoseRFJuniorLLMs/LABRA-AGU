"""
ACT-R base-level activation — com RELÓGIO LÓGICO (não wall-clock).

Num sistema event-sourced cuja tese é o replay determinístico ("a verdade não
se edita"), a ativação tem de ser REPRODUZÍVEL: o mesmo log tem de produzir a
mesma ativação em qualquer replay, em qualquer máquina. Por isso o "tempo" aqui
é o TICK LÓGICO do evento (a sua ordem no log), nunca `time.time()`. Assim a
relevância sub-simbólica que entra no insight pericial é determinística e
auditável — não muda conforme o momento em que o daemon processou o evento.

Equação ACT-R (base-level):  A_i = ln( Σ_j (now - t_j)^(-d) )
onde `now` e `t_j` são ticks lógicos (posições no log), e `d` o decaimento.
"""
import math
from typing import Dict, List


class ACTREngine:
    def __init__(self, decay_rate: float = 0.5):
        self.decay_rate = decay_rate
        # entidade -> lista de ticks lógicos de acesso
        self.memory_activations: Dict[str, List[int]] = {}

    def record_access(self, entity_id: str, tick: int):
        """Regista um acesso à entidade no tick lógico `tick` (posição no log)."""
        self.memory_activations.setdefault(entity_id, []).append(int(tick))

    def boost(self, entity_id: str, tick: int, weight: int = 5):
        """
        Reforço dirigido: uma DIRETRIZ da Procuradoria injeta `weight` acessos
        sintéticos no tick lógico atual, elevando a base-level activation do
        alvo — o agente "pensa mais" nessa entidade, de forma reproduzível.
        """
        for _ in range(max(1, weight)):
            self.record_access(entity_id, tick)

    def calculate_activation(self, entity_id: str, now: int) -> float:
        """Base-level activation da entidade avaliada no tick lógico `now`."""
        accesses = self.memory_activations.get(entity_id)
        if not accesses:
            return float("-inf")
        soma = 0.0
        for t_j in accesses:
            # Distância em ticks lógicos. Piso de 1 evita divisão por zero e
            # mantém o determinismo: um acesso no próprio tick atual conta como
            # recência máxima (1), em vez de explodir para infinito.
            dt = max(now - int(t_j), 1)
            soma += dt ** (-self.decay_rate)
        return math.log(soma) if soma > 0 else float("-inf")

    def filter_relevant_entities(self, entity_ids: list, now: int,
                                 threshold: float = -2.0) -> list:
        """Entidades cuja ativação (avaliada em `now`) supera o limiar."""
        return [eid for eid in entity_ids
                if self.calculate_activation(eid, now) >= threshold]

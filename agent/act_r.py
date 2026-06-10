import time
import numpy as np
from typing import Dict

class ACTREngine:
    def __init__(self, decay_rate: float = 0.5):
        self.decay_rate = decay_rate
        self.memory_activations: Dict[str, list] = {}
        
    def record_access(self, entity_id: str, timestamp: float = None):
        if timestamp is None:
            timestamp = time.time()

        if entity_id not in self.memory_activations:
            self.memory_activations[entity_id] = []
        self.memory_activations[entity_id].append(timestamp)

    def boost(self, entity_id: str, weight: int = 5):
        """
        Reforço dirigido: uma DIRETRIZ da Procuradoria injeta `weight`
        acessos sintéticos na memória do alvo, elevando sua base-level
        activation — o agente passa a "pensar mais" nessa entidade sem
        alterar a fórmula ACT-R.
        """
        now = time.time()
        for _ in range(max(1, weight)):
            self.record_access(entity_id, now)
        
    def calculate_activation(self, entity_id: str, current_time: float = None) -> float:
        """
        Calcula a base-level activation de acordo com a equação de ACT-R:
        A_i = ln( sum( (t_current - t_j)^(-d) ) )
        """
        if current_time is None:
            current_time = time.time()
            
        if entity_id not in self.memory_activations:
            return -np.inf
            
        accesses = self.memory_activations[entity_id]
        sum_decay = 0.0
        
        for t_j in accesses:
            time_diff = max(current_time - t_j, 1e-5) # evita div por zero
            sum_decay += time_diff ** (-self.decay_rate)
            
        if sum_decay <= 0:
            return -np.inf
            
        return np.log(sum_decay)

    def filter_relevant_entities(self, entity_ids: list, threshold: float = -2.0) -> list:
        """
        Filtra e retorna apenas as entidades com ativação acima do threshold.
        """
        relevant = []
        for eid in entity_ids:
            act = self.calculate_activation(eid)
            if act >= threshold:
                relevant.append(eid)
        return relevant

"""
entity_resolution — resolução de entidades FUZZY (Fase 3).

A normalização exata (`entities.py`) une o mesmo CPF escrito de formas
diferentes. Mas um laranja com o nome ligeiramente diferente, ou um id sem
CPF/CNPJ validável, escapa — e o grafo fragmenta-se exatamente onde o fraudador
quer.

Este módulo PROPÕE (não funde automaticamente) pares provavelmente iguais:
  - por similaridade de NOME (difflib, biblioteca-padrão, sem dependências);
  - reforçada por ATRIBUTO partilhado (mesmo endereço/telefone/contador/conta).

Conservador por desenho: ids com CPF/CNPJ válidos (`CPF:`/`CNPJ:`) são tratados
como definitivos — dois CPFs válidos diferentes são pessoas diferentes, nunca se
sugerem para fusão. O resto vai para REVISÃO HUMANA (a fusão automática de
pessoas é perigosa). É uma rede de segurança contra a evasão por grafia, não um
substituto da validação por dígitos.
"""
from difflib import SequenceMatcher
from itertools import combinations
from typing import List

from .graph import CaseGraph

_ATTR_RELS = ("MESMO_ENDERECO", "MESMO_TELEFONE", "MESMO_CONTADOR", "MESMA_CONTA")


def _sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _validado(cid: str) -> bool:
    """True se o id já tem dígitos verificadores validados (definitivo)."""
    return cid.startswith(("CPF:", "CNPJ:"))


class FuzzyResolver:
    def __init__(self, graph: CaseGraph):
        self.g = graph
        self._attr_pairs = self._build_attr_pairs()

    def _build_attr_pairs(self):
        pares = set()
        for rt in _ATTR_RELS:
            for r in self.g.rels(rt):
                pares.add(frozenset((r["src"], r["dst"])))
        return pares

    def candidatos(self, limiar_nome: float = 0.86,
                   limiar_com_atributo: float = 0.60) -> List[dict]:
        """Pares de ids provavelmente a MESMA entidade, para revisão humana.
        Sugere quando: nome muito similar (>= limiar_nome), OU atributo
        partilhado + nome ao menos parecido (>= limiar_com_atributo)."""
        nomes = {cid: (self.g.entities.get(cid) or cid) for cid in self.g.entities}
        out = []
        for a, b in combinations(sorted(nomes), 2):
            # dois ids definitivos diferentes = pessoas distintas: não sugerir.
            if _validado(a) and _validado(b):
                continue
            sim = _sim(nomes[a], nomes[b])
            attr = frozenset((a, b)) in self._attr_pairs
            if sim >= limiar_nome:
                motivo = "nome quase idêntico"
            elif attr and sim >= limiar_com_atributo:
                motivo = "atributo partilhado + nome similar"
            else:
                continue
            out.append({
                "id_a": a, "id_b": b,
                "nome_a": nomes[a], "nome_b": nomes[b],
                "similaridade": round(sim, 3),
                "atributo_partilhado": attr,
                "motivo": motivo,
                "confianca": round(min(1.0, sim + (0.1 if attr else 0.0)), 3),
            })
        return sorted(out, key=lambda x: x["confianca"], reverse=True)

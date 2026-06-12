"""
legal_mapper — subsunção do fato econômico à norma (Fase 2, passo 5).

Traduz cada padrão de fraude detectado num enquadramento legal (tipificação +
dispositivo + sugestão de ementa). Mapeamento estático determinístico — a base
jurídica não pode alucinar; é uma tabela curada, não geração livre.
"""
from typing import Dict, List

# pattern -> lista de enquadramentos legais.
MAPPING: Dict[str, List[dict]] = {
    "fracionamento": [
        {"tipo": "Lavagem de dinheiro (estruturação)",
         "dispositivo": "Lei 9.613/98, art. 1º",
         "ementa": "Fracionamento de valores para evadir comunicação obrigatória "
                   "configura ocultação (estruturação/smurfing)."},
    ],
    "triangulacao_offshore": [
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792",
         "ementa": "Alienação de bens na pendência de demanda capaz de reduzir o "
                   "devedor à insolvência é ineficaz perante o exequente."},
        {"tipo": "Fraude à execução (penal)",
         "dispositivo": "CP, art. 179",
         "ementa": "Fraudar execução alienando ou desviando bens."},
    ],
    "vespera_constricao": [
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792"},
        {"tipo": "Presunção de fraude fiscal",
         "dispositivo": "CTN, art. 185",
         "ementa": "Presume-se fraudulenta a alienação de bens por sujeito passivo "
                   "em débito inscrito em dívida ativa."},
    ],
    "laranja_familiar": [
        {"tipo": "Desconsideração da personalidade jurídica / interposição",
         "dispositivo": "CC, art. 50",
         "ementa": "Abuso da personalidade caracterizado por confusão patrimonial "
                   "autoriza estender obrigações aos bens dos administradores/sócios."},
    ],
    "holding_usufruto": [
        {"tipo": "Confusão patrimonial",
         "dispositivo": "CC, art. 50",
         "ementa": "Controle de fato dissociado da titularidade formal revela "
                   "confusão patrimonial e abuso da personalidade."},
    ],
    "doacao_cruzada": [
        {"tipo": "Fraude contra credores",
         "dispositivo": "CC, art. 158",
         "ementa": "Transmissão gratuita de bens por devedor insolvente é anulável "
                   "por fraude contra credores."},
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792"},
    ],
    "offshore_cascata": [
        {"tipo": "Ocultação de beneficiário efetivo",
         "dispositivo": "Lei 9.613/98, art. 1º",
         "ementa": "Estrutura multipartite para ocultar o beneficiário efetivo "
                   "configura ocultação dolosa de patrimônio."},
    ],
}


class LegalMapper:
    def map(self, pattern: str) -> List[dict]:
        """Enquadramentos legais de um padrão (vazio se não mapeado)."""
        return MAPPING.get(pattern, [])

    def subsume(self, patterns) -> dict:
        """Subsunção agregada de um conjunto de padrões. Devolve a lista de
        dispositivos (sem repetição, ordem estável) e o detalhe por padrão."""
        detalhe: Dict[str, List[dict]] = {}
        dispositivos: List[str] = []
        for p in dict.fromkeys(patterns):  # ordem, sem duplicados
            enq = self.map(p)
            if not enq:
                continue
            detalhe[p] = enq
            for e in enq:
                if e["dispositivo"] not in dispositivos:
                    dispositivos.append(e["dispositivo"])
        return {"dispositivos": dispositivos, "por_padrao": detalhe}

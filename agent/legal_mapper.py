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
    "fraude_inss": [
        {"tipo": "Estelionato previdenciário",
         "dispositivo": "CP, art. 171, § 3º",
         "ementa": "Obtenção de vantagem ilícita em prejuízo do INSS, com "
                   "pena majorada por lesão a entidade de previdência."},
        {"tipo": "Crime previdenciário / lesão ao erário",
         "dispositivo": "Lei 8.213/91",
         "ementa": "Apropriação e desvio de benefícios da Previdência Social, "
                   "com ressarcimento ao erário e improbidade administrativa."},
    ],
    "bem_preco_vil": [
        {"tipo": "Negócio jurídico simulado",
         "dispositivo": "CC, art. 167",
         "ementa": "Alienação por preço vil revela simulação; o negócio é nulo, "
                   "subsistindo o que se dissimulou (o bem permanece no devedor)."},
        {"tipo": "Fraude contra credores",
         "dispositivo": "CC, art. 158",
         "ementa": "Transmissão por preço incompatível, insolvente o devedor, é "
                   "anulável por fraude contra credores."},
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792"},
    ],
    "bem_a_interposto": [
        {"tipo": "Desconsideração da personalidade / interposição",
         "dispositivo": "CC, art. 50",
         "ementa": "Transferência de bem a interposta pessoa mantendo o controle "
                   "de fato configura confusão patrimonial."},
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792"},
        {"tipo": "Presunção de fraude fiscal",
         "dispositivo": "CTN, art. 185",
         "ementa": "Presume-se fraudulenta a alienação de bens por sujeito "
                   "passivo em débito inscrito em dívida ativa."},
    ],
    "ubo_cadeia_profunda": [
        {"tipo": "Ocultação de beneficiário efetivo",
         "dispositivo": "Lei 9.613/98, art. 1º",
         "ementa": "Estrutura multicamada para ocultar o beneficiário final "
                   "configura ocultação dolosa de patrimônio."},
    ],
    "controle_circular": [
        {"tipo": "Confusão patrimonial / abuso da personalidade",
         "dispositivo": "CC, art. 50",
         "ementa": "Participação societária circular dissolve a titularidade "
                   "real e revela abuso da personalidade jurídica."},
        {"tipo": "Ocultação de beneficiário efetivo",
         "dispositivo": "Lei 9.613/98, art. 1º"},
    ],
    "patrimonio_incompativel": [
        {"tipo": "Enriquecimento ilícito",
         "dispositivo": "Lei 8.429/92, art. 9º",
         "ementa": "Aquisição de bens em valor desproporcional à renda lícita "
                   "do agente caracteriza enriquecimento ilícito (improbidade)."},
        {"tipo": "Ocultação patrimonial",
         "dispositivo": "Lei 9.613/98, art. 1º"},
    ],
    "vinculo_por_atributo": [
        {"tipo": "Interposição / confusão patrimonial",
         "dispositivo": "CC, art. 50",
         "ementa": "Atributos compartilhados (endereço, telefone, contador, "
                   "conta) revelam controlador comum e confusão patrimonial."},
    ],
    "passivo_simulado": [
        {"tipo": "Negócio simulado",
         "dispositivo": "CC, art. 167",
         "ementa": "Dívida confessada a credor com vínculo é simulação para "
                   "preterir o crédito da Fazenda; nula de pleno direito."},
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792"},
    ],
    "contrato_direcionado": [
        {"tipo": "Frustração da licitação / direcionamento",
         "dispositivo": "Lei 14.133/21, art. 337-F (CP)",
         "ementa": "Direcionamento de contratação e fornecedor de fachada "
                   "frustram o caráter competitivo da licitação."},
        {"tipo": "Improbidade administrativa",
         "dispositivo": "Lei 8.429/92, arts. 9º e 10",
         "ementa": "Dano ao erário e enriquecimento ilícito na contratação "
                   "pública direcionada."},
    ],
    "offramp_cripto": [
        {"tipo": "Lavagem de dinheiro (ocultação)",
         "dispositivo": "Lei 9.613/98, art. 1º",
         "ementa": "Conversão em criptoativos para ocultar origem e "
                   "titularidade quebra dolosamente a rastreabilidade."},
    ],
    "anomalia_judiciaria": [
        {"tipo": "Anomalia a apurar (NÃO é tipificação)",
         "dispositivo": "—",
         "ementa": "Sinal estatístico que requer apuração, assegurados "
                   "contraditório, ampla defesa e presunção de inocência. Não "
                   "imputa ilícito a pessoa determinada."},
    ],
    "mula_financeira": [
        {"tipo": "Lavagem de dinheiro (dispersão)",
         "dispositivo": "Lei 9.613/98, art. 1º",
         "ementa": "Conta de passagem para fracionar e dispersar recursos, "
                   "típica de redes de mulas financeiras."},
    ],
    "antedatacao": [
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792",
         "ementa": "Ato de disposição patrimonial retroagido após a constrição "
                   "para simular anterioridade é ineficaz perante o exequente."},
        {"tipo": "Falsidade documental",
         "dispositivo": "CP, arts. 297 e 299",
         "ementa": "Adulteração da data de registro (público ou particular) "
                   "para alterar fato juridicamente relevante."},
    ],
    "registro_apagado": [
        {"tipo": "Supressão de documento",
         "dispositivo": "CP, art. 305",
         "ementa": "Destruir, suprimir ou ocultar registro de que não podia "
                   "dispor, em benefício próprio, após o marco da execução."},
        {"tipo": "Fraude à execução",
         "dispositivo": "CPC, art. 792"},
    ],
    "suborno": [
        {"tipo": "Corrupção ativa",
         "dispositivo": "CP, art. 333",
         "ementa": "Oferecer ou prometer vantagem indevida a funcionário "
                   "público para determiná-lo a praticar, omitir ou retardar "
                   "ato de ofício."},
        {"tipo": "Improbidade administrativa",
         "dispositivo": "Lei 8.429/92, arts. 9º e 11",
         "ementa": "Vantagem indevida a agente público configura "
                   "enriquecimento ilícito e viola os princípios da "
                   "administração pública."},
        {"tipo": "Responsabilização da pessoa jurídica",
         "dispositivo": "Lei 12.846/13 (Lei Anticorrupção), art. 5º",
         "ementa": "Prometer ou dar vantagem indevida a agente público "
                   "responsabiliza objetivamente a pessoa jurídica."},
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

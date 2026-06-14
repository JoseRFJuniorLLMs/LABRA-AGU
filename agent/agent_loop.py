"""
Orquestrador AGÊNTICO — investiga um devedor de ponta a ponta e rascunha a peça.

Em vez de só reagir a documentos, o agente PERSEGUE um alvo: reúne provas via
FERRAMENTAS (que já existem: detectores, counterfactual, recovery, redes),
decide quando tem caso e REDIGE a petição — tudo com proveniência por ULID.

Cérebro: um LLM LOCAL (Gemma 4 via LM Studio/Ollama — LGPD, nada sai da máquina)
que escolhe o próximo passo e redige. O LLM NÃO lê o log cru: raciocina sobre os
fatos ESTRUTURADOS que as ferramentas extraem (ancorado, sem alucinar, e escala
seja o log de 8 mil ou 8 milhões de eventos). Sem LLM, um planeador
DETERMINÍSTICO corre o mesmo ciclo (offline, em CI).

Cada passo do agente é registado (trace) e, com `client`, vira EVENTO no log —
a "cadeia de raciocínio" auditável que a IA agêntica regulada exige (XAI).
O humano fica no circuito: o agente RECOMENDA e RASCUNHA; o procurador assina.
"""
import datetime
import json
from typing import List

from .counterfactual import CounterfactualEngine
from .investigator import CATALOG
from .legal_mapper import LegalMapper
from .network_analysis import CrossCaseNetwork
from .recovery import valor_dissipado

# padrão de fraude -> medida processual recomendada (curada, não gerada)
_MEDIDAS = {
    "triangulacao_offshore": "Desconsideração da personalidade jurídica (CC art. 50)",
    "laranja_familiar": "Desconsideração da personalidade jurídica (CC art. 50)",
    "holding_usufruto": "Desconsideração da personalidade jurídica (CC art. 50)",
    "controle_circular": "Desconsideração da personalidade jurídica (CC art. 50)",
    "vespera_constricao": "Declaração de ineficácia do ato e indisponibilidade de bens (CPC art. 792)",
    "antedatacao": "Declaração de ineficácia e perícia documental (CPC art. 792; CP arts. 297/299)",
    "registro_apagado": "Recomposição do registro e preservação de prova (CP art. 305)",
    "bem_a_interposto": "Indisponibilidade e penhora do bem em poder de terceiro",
    "bem_preco_vil": "Anulação da alienação por preço vil (CC art. 167)",
    "suborno": "Representação ao Ministério Público por corrupção ativa (CP art. 333)",
    "fracionamento": "Comunicação ao COAF e pedido de quebra de sigilo bancário",
    "offshore_cascata": "Identificação compulsória do beneficiário final (Lei 9.613/98)",
    "ubo_cadeia_profunda": "Identificação compulsória do beneficiário final (Lei 9.613/98)",
    "patrimonio_incompativel": "Apuração de enriquecimento ilícito (Lei 8.429/92, art. 9º)",
    "contrato_direcionado": "Representação por frustração de licitação (Lei 14.133/21)",
}
_TOOLS = ["consultar_caso", "correr_detectores", "prova_essencial",
          "valor_recuperavel", "rede_facilitadores"]


class ForensicAgent:
    def __init__(self, graph, client=None, llm=None, max_passos: int = 10):
        self.g = graph
        self.client = client
        self.llm = llm
        self.max_passos = max_passos
        self.trace: List[dict] = []

    # ── registo / audit trail ──────────────────────────────────────────
    def _log(self, acao, obs):
        e = {"passo": len(self.trace) + 1, "acao": acao, "obs": obs}
        self.trace.append(e)
        if self.client is not None:  # cada passo do agente = evento auditável
            try:
                self.client.append_document(
                    "agente_investigador_labra",
                    f"PASSO {e['passo']} · {acao} · {obs}",
                    attrs={"generated_by": "labra_agent_trace", "acao": acao})
            except Exception:
                pass
        return e

    # ── ferramentas (operam sobre o grafo; devolvem fatos pequenos) ─────
    def t_consultar_caso(self, dev):
        rels = sorted({rt for rt, lst in self.g.relations.items()
                       for r in lst if dev in (r["src"], r["dst"])})
        n_tx = sum(1 for t in self.g.transactions if dev in (t["src"], t["dst"]))
        return {"entidade": self.g.entities.get(dev, dev), "relacoes": rels,
                "n_transacoes": n_tx, "marcos": self.g.marcos_datas()}

    def t_correr_detectores(self, dev):
        out, vistos = [], set()
        for fn in CATALOG.values():
            for a in fn(self.g):
                if a.get("devedor_alvo") != dev:
                    continue
                # dedup: eventos repetidos no log (re-ingestões) geram condutas
                # idênticas — colapsa por (padrão + descrição) para a peça não
                # repetir o mesmo fato.
                chave = (a["pattern"], a.get("descricao", ""))
                if chave in vistos:
                    continue
                vistos.add(chave)
                out.append({"pattern": a["pattern"],
                            "severidade": a["severidade"],
                            "envolvidos": a["envolvidos"],
                            "descricao": a.get("descricao", ""),
                            "conclusao_juridica": a.get("conclusao_juridica", ""),
                            "source_events": sorted(a.get("source_events", set()))})
        return out

    def _beneficiario(self, estado):
        for a in estado.get("achados", []):
            if a["pattern"] == "triangulacao_offshore" and len(a["envolvidos"]) > 1:
                return a["envolvidos"][1]
        return None

    def t_prova_essencial(self, dev, estado):
        benef = self._beneficiario(estado)
        if not benef:
            return []
        return CounterfactualEngine(self.g).essential_ulids(dev, benef)

    def t_rede_facilitadores(self, dev):
        return [f for f in CrossCaseNetwork(self.g).facilitadores()
                if dev in f["devedores"]]

    # ── executor de uma ferramenta (partilhado pelos dois planeadores) ──
    def _run_tool(self, name, dev, estado):
        if name == "consultar_caso":
            v = self.t_consultar_caso(dev); estado["caso"] = v
            obs = f"{len(v['relacoes'])} tipo(s) de relação, {v['n_transacoes']} transação(ões)"
        elif name == "correr_detectores":
            v = self.t_correr_detectores(dev); estado["achados"] = v
            obs = f"{len(v)} fraude(s): " + ", ".join(sorted({a['pattern'] for a in v}))
        elif name == "prova_essencial":
            v = self.t_prova_essencial(dev, estado); estado["essenciais"] = v
            obs = f"{len(v)} ULID essencial(is)"
        elif name == "valor_recuperavel":
            v = valor_dissipado(self.g, dev); estado["valor"] = v
            obs = f"R$ {v:,.2f}"
        elif name == "rede_facilitadores":
            v = self.t_rede_facilitadores(dev); estado["rede"] = v
            obs = f"{len(v)} facilitador(es) partilhado(s)"
        else:
            obs = "(ferramenta desconhecida)"
        self._log(name, obs)
        return obs

    # ── planeadores ────────────────────────────────────────────────────
    def _plano_determinista(self, dev, estado):
        for name in _TOOLS:
            self._run_tool(name, dev, estado)

    def _plano_llm(self, dev, estado):
        sys = {"role": "system", "content": (
            "Você é um investigador forense da AGU que recupera ativos desviados. "
            "A cada passo escolha UMA ferramenta para reunir prova sobre o devedor. "
            "Responda APENAS com JSON: {\"acao\": <ferramenta_ou_concluir>, \"motivo\": <frase curta>}. "
            f"Ferramentas: {', '.join(_TOOLS)}, concluir. "
            "Conclua quando já tiver consultado o caso, corrido os detectores, "
            "obtido a prova essencial e o valor.")}
        hist = [sys]
        feitas = set()
        for _ in range(self.max_passos):
            hist.append({"role": "user", "content":
                         "Estado: " + json.dumps(_resumo(estado), ensure_ascii=False) +
                         "\nPróxima ação?"})
            try:
                dec = self.llm.chat_json(hist)
            except Exception:
                break
            acao = (dec or {}).get("acao", "")
            if acao == "concluir":
                break
            if acao in _TOOLS:
                self._run_tool(acao, dev, estado)
                feitas.add(acao)
                hist.append({"role": "assistant", "content": json.dumps(dec, ensure_ascii=False)})
            else:
                break  # ação inválida → encerra o laço, completa abaixo
        # garante dossiê completo (o que o LLM não tenha pedido)
        for name in _TOOLS:
            if name not in feitas:
                self._run_tool(name, dev, estado)

    # ── ponto de entrada ───────────────────────────────────────────────
    def investigar(self, devedor: str) -> dict:
        estado = {"devedor": devedor, "caso": None, "achados": [],
                  "essenciais": [], "valor": None, "rede": []}
        usou_llm = bool(self.llm and self.llm.available())
        if usou_llm:
            self._plano_llm(devedor, estado)
        else:
            self._plano_determinista(devedor, estado)
        peca = self._redigir(estado, usou_llm)
        return {"trace": self.trace, "dossie": estado, "peca": peca,
                "motor": "gemma/local" if usou_llm else "deterministico"}

    # ── redação da peça ────────────────────────────────────────────────
    def _redigir(self, estado, usou_llm: bool) -> dict:
        patterns = list(dict.fromkeys(a["pattern"] for a in estado["achados"]))
        medidas = list(dict.fromkeys(_MEDIDAS[p] for p in patterns if p in _MEDIDAS))
        sub = LegalMapper().subsume(patterns)
        base = {"medidas": medidas, "dispositivos": sub["dispositivos"],
                "provas_essenciais": estado["essenciais"],
                "valor_estimado": estado["valor"]}
        if usou_llm:
            try:
                base["texto"] = self._redigir_llm(estado, medidas, sub)
                return base
            except Exception:
                pass
        base["texto"] = _peca_template(estado, medidas, sub["dispositivos"])
        return base

    def _redigir_llm(self, estado, medidas, sub) -> str:
        """Gemma redige a PETIÇÃO COMPLETA, ancorada só nos achados (sem inventar)."""
        dados = {
            "devedor": (estado.get("caso") or {}).get("entidade") or estado["devedor"],
            "inscricao": estado["devedor"],
            "fatos": [{"conduta": (a.get("descricao") or a["pattern"]),
                       "gravidade": a.get("severidade"),
                       "fundamento": a.get("conclusao_juridica", "")}
                      for a in estado["achados"]],
            "enquadramento_legal": sub.get("por_padrao", {}),
            "medidas_requeridas": medidas,
            "provas_ulid": estado["essenciais"],
            "valor_a_recuperar": estado["valor"],
        }
        msg = [
            {"role": "system", "content": (
                "Você é Procurador(a) da Fazenda Nacional. Redija uma PETIÇÃO completa, "
                "formal e coesa, em português jurídico, dirigida ao Juízo da Execução "
                "Fiscal, com as seções, nesta ordem: (1) endereçamento ao Juízo; "
                "(2) qualificação da União/Fazenda Nacional e do executado; "
                "(3) 'I – DOS FATOS', narrando o esquema de blindagem com base nas "
                "condutas fornecidas; (4) 'II – DO DIREITO', subsumindo cada conduta ao "
                "respectivo dispositivo; (5) 'III – DAS PROVAS', citando os ULIDs do log "
                "imutável (cadeia de custódia, reconstrução AS OF); (6) 'IV – DOS "
                "PEDIDOS', numerados; (7) valor da causa e fecho ('Nestes termos, pede "
                "deferimento'). Baseie-se SOMENTE nos dados fornecidos — NÃO invente "
                "fatos, nomes, valores ou dispositivos. Não use placeholders vazios.")},
            {"role": "user", "content": json.dumps(dados, ensure_ascii=False)},
        ]
        return self.llm.chat(msg, max_tokens=2200)


def _resumo(estado):
    return {"tem_caso": estado["caso"] is not None,
            "n_achados": len(estado["achados"]),
            "tem_essenciais": bool(estado["essenciais"]),
            "tem_valor": estado["valor"] is not None,
            "tem_rede": bool(estado["rede"])}


def _brl(v) -> str:
    return f"{(v or 0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _peca_template(estado, medidas, dispositivos) -> str:
    """PETIÇÃO formal completa (modo determinístico, sem LLM). Estrutura de peça
    real: endereçamento, qualificação, FATOS, DIREITO, PROVAS, PEDIDOS, valor."""
    from .legal_mapper import LegalMapper
    nome = (estado.get("caso") or {}).get("entidade") or estado["devedor"]
    dev = estado["devedor"]
    achados = estado["achados"]
    val = estado["valor"] or 0.0
    hoje = datetime.date.today().strftime("%d/%m/%Y")
    patterns = list(dict.fromkeys(a["pattern"] for a in achados))
    por_padrao = LegalMapper().subsume(patterns).get("por_padrao", {})

    L = ["EXCELENTÍSSIMO(A) SENHOR(A) DOUTOR(A) JUIZ(A) DE DIREITO DA VARA DE "
         "EXECUÇÕES FISCAIS", "", "Processo de Execução Fiscal nº _______________", ""]
    L.append(
        "A UNIÃO (FAZENDA NACIONAL), pessoa jurídica de direito público, representada "
        "pela Procuradoria-Geral da Fazenda Nacional, nos autos da execução fiscal em "
        "epígrafe, vem, respeitosamente, à presença de Vossa Excelência, com fundamento "
        "nos arts. 50 do Código Civil, 792 do CPC e 185 do CTN, requerer a instauração "
        "de INCIDENTE DE DESCONSIDERAÇÃO DA PERSONALIDADE JURÍDICA c/c MEDIDA DE "
        f"INDISPONIBILIDADE DE BENS em face de {nome} (inscrição nº {dev}), pelos fatos "
        "e fundamentos a seguir expostos (PETIÇÃO gerada pelo agente LABRA-AGU para "
        "revisão e subscrição).")
    L += ["", "I – DOS FATOS"]
    L.append(
        "Da análise cruzada de fontes oficiais (Junta Comercial, Cartório de Notas, "
        "COAF e respectivos extratos), com prova preservada em log imutável e auditável, "
        "apurou-se esquema de blindagem patrimonial estruturado pelo executado, "
        "consubstanciado nas seguintes condutas:")
    if achados:
        for i, a in enumerate(achados, 1):
            desc = (a.get("descricao") or a["pattern"].replace("_", " ")).strip().rstrip(".")
            L.append(f"  {i}. {desc} (gravidade: {a.get('severidade', '?')}).")
    else:
        L.append("  (nenhuma conduta detectada nos dados analisados)")
    L.append(f"O montante dissipado em prejuízo da Fazenda Pública é estimado em "
             f"R$ {_brl(val)}.")

    L += ["", "II – DO DIREITO"]
    if por_padrao:
        for p, enqs in por_padrao.items():
            for e in enqs:
                L.append(f"  • {p.replace('_', ' ')} — {e['tipo']} ({e['dispositivo']}): "
                         + (e.get("ementa") or "").strip())
    L.append("Dispositivos aplicáveis: " + (", ".join(dispositivos) or "—") + ".")

    L += ["", "III – DAS PROVAS (CADEIA DE CUSTÓDIA)"]
    L.append(
        "A prova é rastreável por identificador único e imutável (ULID) no log "
        "append-only do HeraclitusDB, admitindo reconstrução do estado AS OF de "
        "qualquer data:")
    for u in (estado["essenciais"] or ["a proveniência consta dos eventos-fonte nos autos"]):
        L.append(f"  • {u}")

    L += ["", "IV – DOS PEDIDOS", "Ante o exposto, requer a Vossa Excelência:"]
    letras = "abcdefghijklmno"
    ped = list(medidas) or ["a apuração e responsabilização pelas condutas descritas"]
    k = 0
    for m in ped:
        L.append(f"  {letras[k]}) {m};")
        k += 1
    L.append(f"  {letras[k]}) a decretação de indisponibilidade de bens até o limite de "
             f"R$ {_brl(val)};")
    k += 1
    L.append(f"  {letras[k]}) a citação dos envolvidos para, querendo, manifestarem-se.")

    L += ["", f"Dá-se à causa o valor de R$ {_brl(val)}.", "",
          "Nestes termos, pede deferimento.", f"Brasília/DF, {hoje}.", "",
          "PROCURADOR(A) DA FAZENDA NACIONAL"]
    return "\n".join(L)

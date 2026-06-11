"""
Modo daemon (Investigação Contínua): o agente vive subscrito ao log do
HeraclitusDB e reage a cada evento novo — sem polling, sem cron.

Modelo event-sourcing (correto a reinícios e falhas):

  1. RECONSTRUÇÃO  — ao arrancar, relê o log do LSN 0 e reconstrói o grafo
     de caso, as diretrizes ativas e o conjunto de achados já emitidos
     (lendo os próprios insights existentes). Nada é emitido nesta fase.
  2. RECONCILIAÇÃO — corre os padrões sobre o grafo consolidado e emite
     qualquer fraude que ainda NÃO tenha insight no log (recupera de
     crashes entre o match e a gravação). Idempotente: re-arrancar não
     duplica nada, porque o dedup vem do próprio log.
  3. AO VIVO       — subscreve a partir do head e processa cada evento novo
     incrementalmente, emitindo insights conforme a fraude se completa
     (mesmo que as pernas venham de documentos e fontes diferentes).

Interação é sempre via log: kind="Observation" (documento a analisar),
kind="DIRETRIZ" (ordem da Procuradoria). Insights nunca têm kind
Observation, logo não há auto-loop.

Robustez: cada evento é tratado em isolamento; um documento malformado é
registado numa dead-letter e NÃO derruba o daemon.
"""
import json
import logging
import threading
import time
from typing import Optional

import grpc

from .client import HeraclitusClient
from .investigator import Directive, Investigator
from .parser import parse_document


class AgentDaemon:
    def __init__(self, target: str = "localhost:7474",
                 deadletter_path: str = "agent_deadletter.jsonl",
                 client: Optional[HeraclitusClient] = None,
                 use_llm: bool = False):
        self.client = client or HeraclitusClient(target)
        self.investigator = Investigator()
        self.deadletter_path = deadletter_path
        # Parser plugável: LLM (opt-in) com fallback determinístico, ou
        # determinístico direto. Resolvido uma vez no arranque.
        if use_llm:
            from .llm_parser import parse_document_llm
            self._parse = parse_document_llm
        else:
            self._parse = parse_document
        self.stop_event = threading.Event()
        self._stream = None
        self.metrics = {
            "events_seen": 0,
            "documents": 0,
            "directives": 0,
            "insights_emitted": 0,
            "errors": 0,
            "head_lsn": 0,
        }

    # compat com código/teste que lê estes atributos
    @property
    def processed(self) -> int:
        return self.metrics["events_seen"]

    @property
    def insights_emitted(self) -> int:
        return self.metrics["insights_emitted"]

    # ── dead-letter ───────────────────────────────────────────────────
    def _deadletter(self, lsn: int, reason: str, ep: dict):
        self.metrics["errors"] += 1
        try:
            with open(self.deadletter_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(
                    {"lsn": lsn, "reason": reason, "id": ep.get("id")},
                    ensure_ascii=False) + "\n")
        except OSError:
            pass
        logging.warning(f"dead-letter LSN={lsn} ({reason})")

    # ── reconstrução de estado (fase 1) ───────────────────────────────
    def _rebuild_state(self) -> int:
        """Relê o log do 0: grafo, diretrizes e dedup-de-emitidos. Devolve
        o head em que parou (cursor para a fase ao vivo)."""
        head = 0
        for lsn, ep in self.client.iter_log(from_lsn=0):
            head = lsn + 1
            kind = ep.get("kind", "")
            try:
                if "DIRETRIZ" in kind:
                    self._register_directive(ep)
                elif kind == "Observation":
                    text = ep.get("content", "")
                    if text.strip():
                        doc = self._parse(text, source_event_id=ep["id"])
                        # acumula no grafo SEM emitir (reconstrução)
                        touched = self.investigator.graph.ingest(doc)
                        for cid in touched:
                            self.investigator.memory.record_access(cid)
                elif "INSIGHT_PERICIAL_FRAUDE" in kind:
                    # marca a assinatura como já emitida (dedup do log)
                    from .investigator import signature
                    payload = json.loads(ep.get("content", "{}"))
                    self.investigator._emitted.add(signature(
                        payload.get("tipo_fraude"),
                        payload.get("envolvidos", []),
                        payload.get("severidade", "")))
            except Exception as e:  # noqa: BLE001 — reconstrução nunca derruba
                self._deadletter(lsn, f"rebuild:{type(e).__name__}:{e}", ep)
        self.metrics["head_lsn"] = head
        return head

    def _register_directive(self, ep: dict):
        body = json.loads(ep.get("content", "{}"))
        d = Directive(
            event_id=ep["id"],
            alvos=body.get("alvos", []),
            foco=body.get("foco", ""),
            padroes=body.get("padroes", []),
            boost=int(body.get("boost", 5)),
        )
        self.investigator.register_directive(d)
        return d

    # ── reconciliação (fase 2) ────────────────────────────────────────
    def _reconcile(self):
        """Emite insights para fraude já completa no grafo que ainda não
        tenha registo no log (recupera crashes). Idempotente."""
        from .patterns import PATTERNS
        from .investigator import signature
        inv = self.investigator
        for name in inv._active_patterns():
            for achado in PATTERNS[name](inv.graph):
                sig = signature(achado["pattern"], achado["envolvidos"],
                                achado["severidade"])
                if sig in inv._emitted:
                    continue
                inv._emitted.add(sig)
                self._emit(inv._build_insight(achado))

    # ── ao vivo (fase 3) ──────────────────────────────────────────────
    def _handle_event(self, lsn: int, ep: dict):
        self.metrics["events_seen"] += 1
        self.metrics["head_lsn"] = lsn + 1
        kind = ep.get("kind", "")
        try:
            if "DIRETRIZ" in kind:
                d = self._register_directive(ep)
                self.metrics["directives"] += 1
                logging.info(f"DIRETRIZ acolhida {d}")
                # uma diretriz nova pode revelar fraude já no grafo
                self._reconcile()
            elif kind == "Observation":
                text = ep.get("content", "")
                if text.strip():
                    self.metrics["documents"] += 1
                    doc = self._parse(text, source_event_id=ep["id"])
                    for insight in self.investigator.process_document(doc):
                        self._emit(insight)
        except Exception as e:  # noqa: BLE001 — um doc ruim não derruba o daemon
            self._deadletter(lsn, f"live:{type(e).__name__}:{e}", ep)

    def _emit(self, insight: dict):
        lsn = self.client.append_insight(insight)
        self.metrics["insights_emitted"] += 1
        logging.info(
            f"INSIGHT [{insight['payload']['tipo_fraude']}/"
            f"{insight['payload']['severidade']}] gravado (LSN={lsn}); "
            f"proveniência={insight['parents']}"
        )

    # ── loop principal ────────────────────────────────────────────────
    def run(self):
        logging.info("Reconstruindo estado a partir do log (LSN 0)...")
        head = self._rebuild_state()
        logging.info(f"Grafo reconstruído: {self.investigator.graph.stats()}; "
                     f"reconciliando a partir do head={head}")
        self._reconcile()

        from_lsn = head
        logging.info(f"Agente ao vivo. Subscribe(from_lsn={from_lsn})")
        backoff = 1.0
        while not self.stop_event.is_set():
            try:
                self._stream = self.client.subscribe(from_lsn=from_lsn)
                backoff = 1.0
                for msg in self._stream:
                    ep = json.loads(msg.episode_json)
                    self._handle_event(msg.lsn, ep)
                    from_lsn = msg.lsn + 1
                    if self.stop_event.is_set():
                        break
            except grpc.RpcError as e:
                if self.stop_event.is_set():
                    break
                logging.warning(f"Stream interrompido ({e.code()}); retry em {backoff:.0f}s")
                time.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
        logging.info(f"Daemon encerrado. Métricas: {self.metrics}")

    def stop(self):
        self.stop_event.set()
        if self._stream is not None:
            try:
                self._stream.cancel()
            except Exception:
                pass

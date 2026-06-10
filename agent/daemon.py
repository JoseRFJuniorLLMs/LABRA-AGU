"""
Modo daemon (Diretriz de Investigação Contínua): o agente vive subscrito
ao log do HeraclitusDB e reage a cada evento novo — sem polling, sem cron.

Como interagir com o agente em execução: NUNCA por canal lateral. Toda
interação é um evento no próprio log:

  - kind="Observation"  -> documento-fonte: o agente analisa e, se houver
                           fraude, devolve INSIGHT_PERICIAL_FRAUDE com
                           proveniência completa;
  - kind="DIRETRIZ"     -> ordem da Procuradoria (alvos, foco, padrões):
                           o agente regista, dá boost ACT-R aos alvos e
                           liga o ULID da diretriz aos insights que ela
                           influenciar (auditável: quem mandou, quando).

Estado: o último LSN processado é persistido em agent_state.json — o
daemon retoma exatamente de onde parou (idempotência por checkpoint).
"""
import json
import logging
import threading
import time

import grpc

from .client import HeraclitusClient
from .investigator import Directive, Investigator
from .parser import parse_document


class AgentDaemon:
    def __init__(self, target: str = "localhost:7474",
                 state_path: str = "agent_state.json"):
        self.client = HeraclitusClient(target)
        self.investigator = Investigator()
        self.state_path = state_path
        self.stop_event = threading.Event()
        self._stream = None
        self.processed = 0
        self.insights_emitted = 0

    # ── checkpoint ────────────────────────────────────────────────────
    def _load_checkpoint(self) -> int:
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                return int(json.load(f)["last_lsn"]) + 1
        except (OSError, ValueError, KeyError):
            return 0

    def _save_checkpoint(self, lsn: int):
        with open(self.state_path, "w", encoding="utf-8") as f:
            json.dump({"last_lsn": lsn}, f)

    # ── dispatch ──────────────────────────────────────────────────────
    def _handle_directive(self, ep: dict):
        try:
            body = json.loads(ep.get("content", "{}"))
        except json.JSONDecodeError:
            logging.warning(f"DIRETRIZ ilegível em {ep.get('id')}")
            return
        d = Directive(
            event_id=ep["id"],
            alvos=body.get("alvos", []),
            foco=body.get("foco", ""),
            padroes=body.get("padroes", []),
            boost=int(body.get("boost", 5)),
        )
        self.investigator.register_directive(d)
        logging.info(f"DIRETRIZ acolhida {d} (boost ACT-R aplicado aos alvos)")

    def _handle_document(self, ep: dict):
        text = ep.get("content", "")
        if not text.strip():
            return
        doc = parse_document(text, source_event_id=ep["id"])
        insights = self.investigator.process_document(doc)
        for insight in insights:
            lsn = self.client.append_insight(insight)
            self.insights_emitted += 1
            logging.info(
                f"INSIGHT [{insight['payload']['tipo_fraude']}/"
                f"{insight['payload']['severidade']}] gravado (LSN={lsn}); "
                f"proveniência={insight['parents']}"
            )

    def _handle_event(self, lsn: int, ep: dict):
        kind = ep.get("kind", "")
        if "DIRETRIZ" in kind:
            self._handle_directive(ep)
        elif kind == "Observation":
            self._handle_document(ep)
        # INSIGHT_PERICIAL_* e demais kinds são ignorados (sem auto-loop:
        # insights nunca têm kind Observation).
        self.processed += 1
        self._save_checkpoint(lsn)

    # ── loop principal ────────────────────────────────────────────────
    def run(self):
        from_lsn = self._load_checkpoint()
        logging.info(f"Agente em modo daemon. Subscribe(from_lsn={from_lsn})")
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
        logging.info(
            f"Daemon encerrado: {self.processed} eventos, "
            f"{self.insights_emitted} insights emitidos."
        )

    def stop(self):
        self.stop_event.set()
        if self._stream is not None:
            try:
                self._stream.cancel()
            except Exception:
                pass

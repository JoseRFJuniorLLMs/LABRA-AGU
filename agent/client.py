import datetime
import json
import logging
import os
import re

import grpc

try:
    from . import heraclitus_pb2
    from . import heraclitus_pb2_grpc
except ImportError:
    pass  # Falhará apenas antes da compilação dos protobuffers

# ULID: 26 caracteres Crockford base32. O HeraclitusDB REJEITA qualquer
# parent que não seja um ULID válido (Status: invalid_argument).
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$", re.IGNORECASE)


def is_ulid(value: str) -> bool:
    return bool(_ULID_RE.match(value or ""))


class HeraclitusClient:
    def __init__(self, target: str | None = None, tls: bool | None = None,
                 ca_cert: str | None = None, token: str | None = None):
        """
        Conexão gRPC ao HeraclitusDB.

        Produção (AGU/INSS): trafega CPF e dados financeiros sob sigilo (LGPD),
        logo TLS + autenticação deviam ser OBRIGATÓRIOS. Configurável por env
        para ativar em produção sem tocar no código:
          HERACLITUS_ADDR     (default localhost:7474)
          HERACLITUS_TLS      (1/true → canal seguro)
          HERACLITUS_CA_CERT  (PEM da CA que valida o servidor)
          HERACLITUS_TOKEN    (bearer token → metadata 'authorization')

        `tls`/`token` explícitos têm precedência sobre o env. Sem TLS o canal é
        inseguro — aceitável apenas em desenvolvimento local (loopback).
        """
        target = target or os.environ.get("HERACLITUS_ADDR", "localhost:7474")
        if tls is None:
            tls = os.environ.get("HERACLITUS_TLS", "").lower() in ("1", "true", "yes")
        ca_cert = ca_cert or os.environ.get("HERACLITUS_CA_CERT")
        token = token or os.environ.get("HERACLITUS_TOKEN")

        # Limite de mensagem gRPC. O default (4 MB) estoura em consultas amplas
        # (ex.: MATCH (n) RETURN n sobre um log de produção já com dezenas de
        # milhares de eventos) com RESOURCE_EXHAUSTED. O log é append-only e só
        # cresce, logo elevamos o teto de RECEÇÃO (e envio) para 256 MB.
        _MAX_MSG = int(os.environ.get(
            "HERACLITUS_MAX_MSG_BYTES", str(256 * 1024 * 1024)))
        _opts = [("grpc.max_receive_message_length", _MAX_MSG),
                 ("grpc.max_send_message_length", _MAX_MSG)]

        if tls:
            creds_kwargs = {}
            if ca_cert:
                with open(ca_cert, "rb") as f:
                    creds_kwargs["root_certificates"] = f.read()
            creds = grpc.ssl_channel_credentials(**creds_kwargs)
            self.channel = grpc.secure_channel(target, creds, options=_opts)
        else:
            self.channel = grpc.insecure_channel(target, options=_opts)

        # Autenticação por bearer token (metadata em cada chamada). Nunca enviar
        # credenciais em claro: se há token mas o canal é inseguro, avisa.
        self._md = [("authorization", f"Bearer {token}")] if token else None
        if token and not tls:
            logging.warning("HERACLITUS_TOKEN definido sobre canal SEM TLS — "
                            "o token viaja em claro. Ative HERACLITUS_TLS em produção.")

        try:
            self.stub = heraclitus_pb2_grpc.HeraclitusStub(self.channel)
        except NameError as e:
            raise RuntimeError(
                "Stubs gRPC do HeraclitusDB ausentes — gere-os com `py build.py` "
                "(grpcio-tools) antes de usar o cliente."
            ) from e

    def subscribe(self, from_lsn=0):
        req = heraclitus_pb2.SubscribeRequest(from_lsn=from_lsn)
        return self.stub.Subscribe(req, metadata=self._md)

    def snapshot(self) -> int:
        return self.stub.Snapshot(heraclitus_pb2.SnapshotRequest(),
                                  metadata=self._md).lsn

    def query(self, gql: str):
        """Executa GQL (MATCH/RECALL/NEAREST/PROVENANCE/EXPLAIN/AS OF)."""
        resp = self.stub.Query(heraclitus_pb2.QueryRequest(gql=gql),
                               metadata=self._md)
        return json.loads(resp.json)

    def query_auditada(self, gql: str, autor: str, motivo: str = ""):
        """
        Consulta com trilha de auditoria LGPD: a LEITURA de dados pessoais
        é, ela própria, um evento imutável no log (kind=ACESSO_LEITURA),
        registando QUEM consultou O QUÊ e POR QUÊ. A filosofia do projeto
        — a verdade não se edita — aplicada também ao acesso.
        """
        self.stub.Append(heraclitus_pb2.AppendRequest(
            agent_id=autor,
            session_id="labra_session_01",
            kind="ACESSO_LEITURA",
            content=json.dumps(
                {"gql": gql, "motivo": motivo,
                 "ts": datetime.datetime.now(datetime.timezone.utc).isoformat()},
                ensure_ascii=False).encode("utf-8"),
            attrs={"generated_by": "labra_audit", "autor": autor},
        ), metadata=self._md)
        return self.query(gql)

    def iter_log(self, from_lsn: int = 0):
        """
        Itera os eventos do log a partir de `from_lsn`, em ordem de LSN.
        Usado pelo daemon para reconstruir o grafo (materialized view).
        Devolve tuplos (lsn, episode_dict).
        """
        rows = self.query("MATCH (n) RETURN n ORDER BY n.lsn")
        for r in rows:
            lsn = r.get("lsn", 0)
            if lsn >= from_lsn:
                yield lsn, r

    def append_document(self, agent_id: str, text: str, attrs: dict | None = None) -> int:
        """
        Cadeia de custódia: o documento-fonte é ele próprio um evento
        imutável no log ANTES de qualquer análise. Retorna o LSN.
        """
        req = heraclitus_pb2.AppendRequest(
            agent_id=agent_id,
            session_id="labra_session_01",
            kind="Observation",
            content=text.encode("utf-8"),
            attrs={"generated_by": "labra_agent", "role": "documento_fonte",
                   **(attrs or {})},
        )
        return self.stub.Append(req, metadata=self._md).lsn

    def resolve_event_id(self, lsn: int) -> str:
        """
        O servidor atribui o ULID do episódio; o cliente só conhece o LSN.
        Resolve LSN -> ULID via Query (campo `lsn` é consultável).
        """
        rows = self.query(f"MATCH (n) WHERE n.lsn = {lsn} RETURN n")
        if not rows:
            raise LookupError(f"nenhum evento com lsn={lsn}")
        return rows[0]["id"]

    def append_insight(self, insight: dict) -> int:
        """
        Grava o insight pericial como evento imutável. `parents` DEVE conter
        apenas ULIDs reais de eventos do log (proveniência verificável);
        referências documentais humanas vão para attrs["source_refs"].
        """
        parents = [p for p in insight.get("parents", []) if is_ulid(p)]
        loose_refs = [p for p in insight.get("parents", []) if not is_ulid(p)]
        attrs = {"generated_by": "labra_agent"}
        if loose_refs:
            attrs["source_refs"] = ";".join(loose_refs)

        req = heraclitus_pb2.AppendRequest(
            agent_id=insight["agent_id"],
            session_id="labra_session_01",
            kind=insight["event_type"],
            content=json.dumps(insight["payload"], ensure_ascii=False).encode("utf-8"),
            parents=parents,
            attrs=attrs,
        )
        return self.stub.Append(req, metadata=self._md).lsn

    def provenance(self, event_id: str):
        """Cadeia de custódia inversa: de onde veio este insight?"""
        return self.query(f'PROVENANCE ("{event_id}")')

    def append_directive(self, alvos, foco: str = "", padroes=None, boost: int = 5,
                         autor: str = "procuradoria") -> int:
        """
        Interação com o agente daemon: a ordem é ela própria um evento
        imutável (kind=DIRETRIZ). Fica registado quem ordenou o quê e
        quando — e os insights influenciados apontarão para este ULID.
        """
        body = {"alvos": list(alvos or []), "foco": foco,
                "padroes": list(padroes or []), "boost": boost}
        req = heraclitus_pb2.AppendRequest(
            agent_id=autor,
            session_id="labra_session_01",
            kind="DIRETRIZ",
            content=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            attrs={"generated_by": "labra_directive_cli"},
        )
        return self.stub.Append(req, metadata=self._md).lsn

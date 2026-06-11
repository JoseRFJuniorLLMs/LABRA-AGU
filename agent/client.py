import datetime
import json
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
    def __init__(self, target="localhost:7474", tls: bool = False,
                 ca_cert: str | None = None):
        """
        Conexão gRPC ao HeraclitusDB.

        Produção (AGU/INSS): use TLS. `tls=True` abre um canal seguro; se
        `ca_cert` for dado, valida o servidor contra essa CA (cert PEM).
        Sem TLS, o canal é inseguro — aceitável apenas em desenvolvimento
        local, pois trafega CPF e dados financeiros sensíveis (LGPD).
        """
        if tls:
            creds_kwargs = {}
            if ca_cert:
                with open(ca_cert, "rb") as f:
                    creds_kwargs["root_certificates"] = f.read()
            creds = grpc.ssl_channel_credentials(**creds_kwargs)
            self.channel = grpc.secure_channel(target, creds)
        else:
            self.channel = grpc.insecure_channel(target)
        try:
            self.stub = heraclitus_pb2_grpc.HeraclitusStub(self.channel)
        except NameError:
            self.stub = None

    def subscribe(self, from_lsn=0):
        req = heraclitus_pb2.SubscribeRequest(from_lsn=from_lsn)
        return self.stub.Subscribe(req)

    def snapshot(self) -> int:
        return self.stub.Snapshot(heraclitus_pb2.SnapshotRequest()).lsn

    def query(self, gql: str):
        """Executa GQL (MATCH/RECALL/NEAREST/PROVENANCE/EXPLAIN/AS OF)."""
        resp = self.stub.Query(heraclitus_pb2.QueryRequest(gql=gql))
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
        ))
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
        return self.stub.Append(req).lsn

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
        return self.stub.Append(req).lsn

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
        return self.stub.Append(req).lsn

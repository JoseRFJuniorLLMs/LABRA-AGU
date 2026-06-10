import json
import grpc
try:
    from . import heraclitus_pb2
    from . import heraclitus_pb2_grpc
except ImportError:
    pass # Falhará apenas antes da compilação dos protobuffers

class HeraclitusClient:
    def __init__(self, target='localhost:7474'):
        self.channel = grpc.insecure_channel(target)
        try:
            self.stub = heraclitus_pb2_grpc.HeraclitusStub(self.channel)
        except NameError:
            self.stub = None

    def subscribe(self, from_lsn=0):
        req = heraclitus_pb2.SubscribeRequest(from_lsn=from_lsn)
        return self.stub.Subscribe(req)

    def append_insight(self, insight: dict):
        req = heraclitus_pb2.AppendRequest(
            agent_id=insight["agent_id"],
            session_id="labra_session_01",
            kind=insight["event_type"],
            content=json.dumps(insight["payload"]).encode('utf-8'),
            parents=insight["parents"],
            attrs={"generated_by": "labra_agent"}
        )
        response = self.stub.Append(req)
        return response.lsn

"""
Utilitário de teste: sobe um heraclitus-server fresco numa porta livre, com
diretório de dados temporário, e devolve o endereço. Garante isolamento
total entre testes e2e (cada um com o seu próprio rio).

O binário é localizado por HERACLITUS_SERVER_BIN ou no caminho-padrão do
repositório HeraclitusDB ao lado deste. Se não existir, os testes que o
usam devem ser saltados.
"""
import contextlib
import os
import socket
import subprocess
import tempfile
import time
import urllib.request

import grpc

_DEFAULT_BIN = os.path.join(
    os.path.dirname(__file__), "..", "..", "HeraclitusDB",
    "target", "release", "heraclitus-server.exe",
)


def server_bin() -> str | None:
    cand = os.environ.get("HERACLITUS_SERVER_BIN", _DEFAULT_BIN)
    return cand if os.path.exists(cand) else None


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextlib.contextmanager
def temp_server(boot_timeout: float = 15.0):
    """Context manager: yields o endereço gRPC de um servidor fresco."""
    binpath = server_bin()
    if not binpath:
        raise FileNotFoundError(
            "heraclitus-server não encontrado; defina HERACLITUS_SERVER_BIN")
    grpc_port = _free_port()
    rest_port = _free_port()
    data_dir = tempfile.mkdtemp(prefix="labra_srv_")
    env = dict(os.environ,
               HERACLITUS_DATA_DIR=data_dir,
               HERACLITUS_GRPC_ADDR=f"127.0.0.1:{grpc_port}",
               HERACLITUS_REST_ADDR=f"127.0.0.1:{rest_port}")
    proc = subprocess.Popen([binpath], env=env,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        deadline = time.time() + boot_timeout
        ok = False
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        f"http://127.0.0.1:{rest_port}/healthz", timeout=1) as r:
                    if r.read():
                        ok = True
                        break
            except Exception:
                time.sleep(0.3)
        if not ok:
            raise RuntimeError("servidor não respondeu ao healthz a tempo")
        # garante o gRPC pronto
        ch = grpc.insecure_channel(f"127.0.0.1:{grpc_port}")
        grpc.channel_ready_future(ch).result(timeout=5)
        ch.close()
        yield f"127.0.0.1:{grpc_port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

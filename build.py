import os
from grpc_tools import protoc

def build_protos():
    proto_dir = "proto"
    out_dir = "agent"

    # Certifique-se de que o diretório de saída existe
    os.makedirs(out_dir, exist_ok=True)

    # Criar __init__.py no diretório agent se não existir para reconhecer como módulo
    init_file = os.path.join(out_dir, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            f.write("")

    proto_file = os.path.join(proto_dir, "heraclitus.proto")

    command = [
        "grpc_tools.protoc",
        f"--proto_path={proto_dir}",
        f"--python_out={out_dir}",
        f"--grpc_python_out={out_dir}",
        proto_file
    ]

    print(f"Compilando proto: {' '.join(command)}")
    status = protoc.main(command)

    if status == 0:
        # protoc gera `import heraclitus_pb2` absoluto; dentro do pacote
        # `agent/` o import precisa de ser relativo.
        grpc_stub = os.path.join(out_dir, "heraclitus_pb2_grpc.py")
        with open(grpc_stub, "r", encoding="utf-8") as f:
            src = f.read()
        src = src.replace(
            "import heraclitus_pb2 as heraclitus__pb2",
            "from . import heraclitus_pb2 as heraclitus__pb2",
        )
        with open(grpc_stub, "w", encoding="utf-8") as f:
            f.write(src)
        print("Stubs gRPC gerados com sucesso no diretório 'agent/'.")
    else:
        print("Falha ao compilar os arquivos proto.")

if __name__ == "__main__":
    build_protos()

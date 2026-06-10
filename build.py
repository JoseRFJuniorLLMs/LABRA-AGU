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
        print("Stubs gRPC gerados com sucesso no diretório 'agent/'.")
    else:
        print("Falha ao compilar os arquivos proto.")

if __name__ == "__main__":
    build_protos()

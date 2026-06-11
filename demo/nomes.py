"""
Nomes fictícios DETERMINÍSTICOS a partir de um id canónico (CPF:/CNPJ:).

Numa AGU real, o nome viria de um join com o cadastro (Receita Federal). Na
demo, derivamos um nome estável do próprio número — o mesmo CPF/CNPJ devolve
sempre o mesmo nome, inclusive no modo --keep (que só conhece os números). É,
de propósito, fictício (LGPD-safe); o identificador forense continua a ser o
CPF/CNPJ.
"""

_FIRST = ["João", "Carlos", "Maria", "Ana", "Pedro", "Lucas", "Rafael",
          "Bruno", "Tiago", "Marcos", "Paulo", "Rui", "Sofia", "Inês",
          "Miguel", "André", "Fernando", "Ricardo", "Sérgio", "Hugo",
          "Diogo", "Vítor", "Helena", "Beatriz", "Cláudia", "Nuno"]
_SUR = ["Ribeiro", "Silva", "Costa", "Pereira", "Santos", "Ferreira",
        "Oliveira", "Rodrigues", "Martins", "Sousa", "Gomes", "Lopes",
        "Marques", "Almeida", "Carvalho", "Teixeira", "Fonseca", "Moreira",
        "Cardoso", "Nunes"]
_PAT = ["{w} Holdings", "Construtora {w} Lda", "{w} Participações SA",
        "Grupo {w}", "{w} Investimentos", "{w} Trading", "{w} Capital"]
_W = ["Atlantic", "Horizonte", "Vega", "Âncora", "Meridiano", "Aurora",
      "Pinheiro", "Lusitânia", "Oceânica", "Setúbal", "Boreal", "Cascata",
      "Fênix", "Lobo", "Tejo", "Douro", "Sirius", "Orion"]


def _seed(d):
    return int(d) if d.isdigit() else sum(ord(c) for c in d)


def nome_de(canonical):
    if not canonical:
        return "—"
    if canonical.startswith("CPF:"):
        n = _seed(canonical[4:])
        return f"{_FIRST[n % len(_FIRST)]} {_SUR[(n // 7) % len(_SUR)]}"
    if canonical.startswith("CNPJ:"):
        n = _seed(canonical[5:])
        return _PAT[n % len(_PAT)].format(w=_W[(n // 11) % len(_W)])
    return canonical

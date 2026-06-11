"""
Resolução de entidades (Entity Resolution).

`CPF_645.254.302-49`, `645.254.302-49` e `64525430249` são a MESMA pessoa.
Sem normalização canónica, o grafo de investigação fragmenta e a fraude
some entre nós duplicados. Este módulo dá a cada CPF/CNPJ uma identidade
única e estável, validando dígitos verificadores quando possível.

IDs reais (com dígitos válidos) viram `CPF:64525430249` / `CNPJ:...`.
Placeholders simbólicos de protótipo (`CPF_CUNHADO_001`) são preservados
em forma limpa e maiúscula — continuam a funcionar, sem falsa validação.
"""
import re

_DIGITS = re.compile(r"\d")


def _only_digits(s: str) -> str:
    return "".join(_DIGITS.findall(s))


def valida_cpf(cpf: str) -> bool:
    """Validação dos dois dígitos verificadores do CPF."""
    n = _only_digits(cpf)
    if len(n) != 11 or n == n[0] * 11:
        return False
    for i in (9, 10):
        soma = sum(int(n[j]) * ((i + 1) - j) for j in range(i))
        dv = (soma * 10) % 11 % 10
        if dv != int(n[i]):
            return False
    return True


def valida_cnpj(cnpj: str) -> bool:
    """Validação dos dois dígitos verificadores do CNPJ."""
    n = _only_digits(cnpj)
    if len(n) != 14 or n == n[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1
    for pesos, pos in ((pesos1, 12), (pesos2, 13)):
        soma = sum(int(n[i]) * pesos[i] for i in range(pos))
        dv = soma % 11
        dv = 0 if dv < 2 else 11 - dv
        if dv != int(n[pos]):
            return False
    return True


def normalize_id(raw: str) -> str:
    """
    Forma canónica e estável de um identificador. Idempotente:
    normalize_id(normalize_id(x)) == normalize_id(x).
    """
    if not raw:
        return raw
    s = raw.strip()
    # Já canónico?
    if s.startswith(("CPF:", "CNPJ:")):
        return s

    upper = s.upper()
    kind = None
    rest = s
    if upper.startswith("CPF"):
        kind = "CPF"
        rest = s[3:]
    elif upper.startswith("CNPJ"):
        kind = "CNPJ"
        rest = s[4:]

    digits = _only_digits(rest if kind else s)

    # CPF real (11 dígitos válidos) -> canónico por dígitos
    if (kind in (None, "CPF")) and len(digits) == 11 and valida_cpf(digits):
        return f"CPF:{digits}"
    # CNPJ real (14 dígitos válidos) -> canónico por dígitos
    if (kind in (None, "CNPJ")) and len(digits) == 14 and valida_cnpj(digits):
        return f"CNPJ:{digits}"

    # Placeholder simbólico (protótipo) ou id não-validável: forma limpa,
    # determinística, maiúscula — preserva o prefixo declarado.
    cleaned = re.sub(r"\s+", "", upper)
    return cleaned


def entity_kind(canonical_id: str) -> str:
    """'PESSOA_FISICA' | 'PESSOA_JURIDICA' a partir do id canónico."""
    up = canonical_id.upper()
    if up.startswith("CPF"):
        return "PESSOA_FISICA"
    if up.startswith("CNPJ"):
        return "PESSOA_JURIDICA"
    return "DESCONHECIDO"

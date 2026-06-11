"""Resolução de entidades: normalização e validação de CPF/CNPJ."""
from agent.entities import normalize_id, valida_cpf, valida_cnpj, entity_kind


def test_cpf_valido():
    # CPF com dígitos verificadores corretos
    assert valida_cpf("529.982.247-25")
    assert valida_cpf("52998224725")
    assert not valida_cpf("111.111.111-11")  # sequência repetida
    assert not valida_cpf("529.982.247-26")  # DV errado


def test_cnpj_valido():
    assert valida_cnpj("11.222.333/0001-81")
    assert not valida_cnpj("11.222.333/0001-99")


def test_normalize_mesma_pessoa_varias_formas():
    # O ponto-chave: as três formas têm de colapsar no MESMO id canónico.
    a = normalize_id("CPF_529.982.247-25")
    b = normalize_id("529.982.247-25")
    c = normalize_id("52998224725")
    assert a == b == c == "CPF:52998224725"
    assert entity_kind(a) == "PESSOA_FISICA"


def test_normalize_idempotente():
    once = normalize_id("CPF_529.982.247-25")
    assert normalize_id(once) == once


def test_placeholder_preservado():
    # IDs simbólicos de protótipo (não-validáveis) ficam estáveis, sem
    # falsa validação.
    p = normalize_id("CPF_CUNHADO_001")
    assert normalize_id(p) == p
    assert "CUNHADO" in p

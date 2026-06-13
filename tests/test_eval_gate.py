"""
Gate de regressão de ACURÁCIA — corre o harness de avaliação sobre os cenários
rotulados e falha o CI se a deteção degradar. É o que impede uma alteração de
um detector de baixar silenciosamente a qualidade.

Critérios (com os cenários atuais o sistema está em 1.00):
  - ZERO falsos positivos (especificidade: os negativos não podem disparar);
  - recall >= 0.90 (sensibilidade: não pode omitir fraudes esperadas).
"""
from evaluation.harness import avaliar
from evaluation.scenarios import NEGATIVOS, TODOS


def test_sem_falsos_positivos_nos_negativos():
    # Nenhum cenário legítimo pode gerar alerta.
    r = avaliar(NEGATIVOS)
    assert r["micro"]["fp"] == 0, r["detalhe"]


def test_gate_global_recall_e_precisao():
    r = avaliar(TODOS)
    assert r["micro"]["fp"] == 0, [d for d in r["detalhe"] if d["fp"]]
    assert r["micro"]["recall"] >= 0.90, r["por_padrao"]
    assert r["micro"]["f1"] >= 0.90, r["micro"]

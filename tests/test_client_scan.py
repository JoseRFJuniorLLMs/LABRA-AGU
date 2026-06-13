"""Paginação por cursor (scan_all) e fetch por id (get_events) — sem servidor.

Substituem o antigo `MATCH (n) RETURN n` (full scan numa só mensagem, que
estoura em produção) por varredura paginada e busca pontual. Testados com a
`query` simulada, validando a LÓGICA do cursor."""
import re

from agent.client import HeraclitusClient


def _cliente_fake(log):
    """HeraclitusClient sem conexão, com `query` que simula o motor GQL sobre
    `log` (lista de nós com lsn/id), suportando o cursor e o fetch por id."""
    c = HeraclitusClient.__new__(HeraclitusClient)
    c.SCAN_BATCH = 2

    def query(gql):
        m_id = re.search(r'n\.id = "([^"]+)"', gql)
        if m_id:
            return [r for r in log if r["id"] == m_id.group(1)]
        m = re.search(r"n\.lsn > (-?\d+).*LIMIT (\d+)", gql, re.DOTALL)
        cur, lim = int(m.group(1)), int(m.group(2))
        return sorted([r for r in log if r["lsn"] > cur],
                      key=lambda r: r["lsn"])[:lim]

    c.query = query
    return c


def test_scan_all_pagina_todo_o_log():
    log = [{"id": f"E{i}", "lsn": i} for i in range(5)]
    c = _cliente_fake(log)
    got = list(c.scan_all())
    assert [r["lsn"] for r in got] == [0, 1, 2, 3, 4]  # cobre tudo, em ordem


def test_scan_all_respeita_from_lsn():
    log = [{"id": f"E{i}", "lsn": i} for i in range(5)]
    c = _cliente_fake(log)
    assert [r["lsn"] for r in c.scan_all(from_lsn=3)] == [3, 4]


def test_scan_all_vazio():
    assert list(_cliente_fake([]).scan_all()) == []


def test_iter_log_usa_paginacao():
    log = [{"id": f"E{i}", "lsn": i} for i in range(5)]
    pares = list(_cliente_fake(log).iter_log(from_lsn=2))
    assert [lsn for lsn, _ in pares] == [2, 3, 4]


def test_get_events_so_os_pedidos():
    log = [{"id": f"E{i}", "lsn": i, "attrs": {"k": i}} for i in range(5)]
    got = _cliente_fake(log).get_events(["E1", "E3", "NAO_EXISTE"])
    assert set(got) == {"E1", "E3"}  # ignora o inexistente
    assert got["E1"]["attrs"]["k"] == 1

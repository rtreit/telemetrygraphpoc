import pytest
from fastapi.testclient import TestClient

from api.main import app, load_graph


@pytest.fixture(scope="module")
def client():
    """Provide a TestClient with graph data loaded."""
    load_graph()
    return TestClient(app)


def test_get_graph(client):
    response = client.get("/api/graph")
    assert response.status_code == 200
    data = response.json()
    assert "nodes" in data
    assert "edges" in data
    assert len(data["nodes"]) > 0


def test_get_graph_filter_by_type(client):
    response = client.get("/api/graph?type=host")
    assert response.status_code == 200
    data = response.json()
    assert all(n["type"] == "host" for n in data["nodes"])


def test_get_summary(client):
    response = client.get("/api/graph/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_nodes" in data
    assert "node_types" in data
    assert "countries" in data
    assert data["total_nodes"] > 0


def test_get_node(client):
    graph = client.get("/api/graph").json()
    node_id = graph["nodes"][0]["id"]

    response = client.get(f"/api/nodes/{node_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["node"]["id"] == node_id


def test_get_node_not_found(client):
    response = client.get("/api/nodes/nonexistent-node-id-12345")
    assert response.status_code == 404


def test_get_neighbors(client):
    graph = client.get("/api/graph?type=campaign").json()
    if graph["nodes"]:
        node_id = graph["nodes"][0]["id"]
        response = client.get(f"/api/nodes/{node_id}/neighbors")
        assert response.status_code == 200
        data = response.json()
        assert len(data["nodes"]) > 0
        assert len(data["edges"]) > 0


def test_search(client):
    response = client.get("/api/search?q=a")
    assert response.status_code == 200
    data = response.json()
    assert "results" in data
    assert "total" in data
    assert data["total"] <= 50


def test_search_empty_query(client):
    response = client.get("/api/search?q=")
    assert response.status_code == 422

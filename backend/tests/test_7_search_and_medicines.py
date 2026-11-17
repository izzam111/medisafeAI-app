"""TC-7  Search, NIH label database, medicines and unknown products."""


def test_search_list_has_local_and_nih_products(client):
    names = client.get("/products").json()["products"]
    assert "Neurobion" in names and "Centrum" in names
    assert len(names) > 500                        # 80 local + ~700 NIH labels


def test_nih_product_has_its_real_label(search):
    s = search("Fresh Nutrition Vitamin D3 + K2")
    assert s and s["label"]["amounts"].get("vitamin_d")


def test_medicine_cannot_be_searched(client):
    assert client.post("/search-product", json={"name": "Panadol"}).status_code == 404


def test_typed_medicine_name_is_flagged(client):
    assert client.post("/check-name", json={"name": "Klaricid"}).json()["status"] == "medicine"


def test_unknown_product_is_flagged(client):
    assert client.post("/check-name", json={"name": "Xyzabc"}).json()["status"] == "unknown"


def test_typed_medicine_gets_no_report(client, scan):
    s = scan([("blurry", 8)])
    r = client.post("/safety-report", json={"scan_id": s["scan_id"], "age": 30, "sex": "male", "supplement_name": "Panadol"})
    assert r.status_code == 422 and "medicine" in r.json()["detail"]

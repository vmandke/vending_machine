from unittest import TestCase
import pytest

from fastapi.testclient import TestClient

from vending_machine.models import Money, MachineException
from vending_machine.api import app

client = TestClient(app)


class TestVendingMachine(TestCase):
    """
    The tests are meant to be run selectively, and not all at once. For example purposes.
    """

    def test_buying(self):
        client.post("/users/", json={"name": "seller-buy", "role": "seller", "password": "seller"})
        client.post("/users/", json={"name": "buyer", "role": "buyer", "password": "buyer"})
        client.put(
            "/products/",
            auth=("seller-buy", "seller"),
            json={"name": "cola", "price": 15, "stock": 10, "seller": "seller"}
        )
        # Deposit Money
        client.put(
            "/users/deposit",
            auth=("buyer", "buyer"),
            json={"n5": 0, "n10": 0, "n20": 1, "n50": 0, "n100": 0}
        )
        # Buy a product
        response = client.post(f"/products/buy?product_name=cola&count=1", auth=("buyer", "buyer"))
        assert response.json() == {'error': 'Not enough change in Machine'}
        # Deposit more Money
        client.put(
            "/users/deposit",
            auth=("buyer", "buyer"),
            json={"n5": 1, "n10": 0, "n20": 0, "n50": 0, "n100": 0}
        )
        response = client.post(f"/products/buy?product_name=cola&count=1", auth=("buyer", "buyer"))
        assert response.json() == {'error': 'Not enough change in Machine'}
        # Deposit more Money
        client.put(
            "/users/deposit",
            auth=("buyer", "buyer"),
            json={"n5": 0, "n10": 1, "n20": 0, "n50": 0, "n100": 0}
        )
        response = client.post(f"/products/buy?product_name=cola&count=1", auth=("buyer", "buyer"))
        # 20 coin returned; in wallet
        assert response.json() == {"n5": 0, "n10": 0, "n20": 1, "n50": 0, "n100": 0}
        response = client.get("/users/", auth=("buyer", "buyer"))
        assert response.json() == {"n5": 0, "n10": 0, "n20": 1, "n50": 0, "n100": 0}

    def test_products(self):
        # Add a seller
        response = client.post("/users/", json={"name": "seller", "role": "seller", "password": "seller"})
        assert response.status_code == 200
        # Add a product
        response = client.put(
            "/products/",
            auth=("seller", "seller"),
            json={"name": "cola", "price": 15, "stock": 10, "seller": "seller"}
        )
        # Add more
        response = client.put(
            "/products/",
            auth=("seller", "seller"),
            json={"name": "cola", "price": 15, "stock": 10, "seller": "seller"}
        )
        assert response.status_code == 200
        # View product
        assert client.get("/products/cola").json() == {'name': 'cola', 'price': 15.0, 'stock': 20, 'seller': 'seller'}
        assert client.get("/products/pepsi").json() == {}
        # Add a product with wrong price
        response = client.put(
            "/products/",
            auth=("seller", "seller"),
            json={"name": "cola", "price": 27, "stock": 10, "seller": "seller"}
        )
        assert response.json() == {"error": "Invalid Price; Needs to be a multiple of 5"}
        # Add a product with wrong seller
        client.post("/users/", json={"name": "seller1", "role": "seller", "password": "seller1"})
        response = client.put(
            "/products/",
            auth=("seller1", "seller1"),
            json={"name": "cola", "price": 15, "stock": 10, "seller": "seller"}
        )
        assert response.json() == {"error": "Product Seller Mismatch"}

    def test_user(self):
        test_data = {
            "name": "abc",
            "role": "buyer",
            "password": "secret"
        }
        # Add user
        response = client.post("/users/", json=test_data)
        assert response.status_code == 200
        assert response.json() == test_data
        # View Wallet
        response = client.get("/users/", auth=("abc", "secret"))
        assert response.status_code == 200
        assert response.json() == {"n5": 0, "n10": 0, "n20": 0, "n50": 0, "n100": 0}
        # View Wallet with wrong password
        response = client.get("/users/", auth=("abc", "wrong"))
        assert response.status_code == 200
        assert response.json() == {"error": "Invalid Password"}
        coins = {"n5": 1, "n10": 2, "n20": 3, "n50": 4, "n100": 5}
        # Deposit Money
        response = client.put("/users/deposit", auth=("abc", "secret"), json=coins)
        assert response.status_code == 200
        assert response.json() == coins
        # Deposit Money with wrong denomination
        response = client.put("/users/deposit", auth=("abc", "secret"), json={"n2": 1})
        assert response.status_code == 422

    def test_money(self):
        m = Money(n5=0, n10=0, n20=0, n50=0, n100=0)
        m.add({5: 1, 10: 2, 20: 3, 50: 4, 100: 5})
        self.assertEquals(m.get_total(), 785)
        m.sub({5: 1, 10: 2, 20: 3, 50: 4, 100: 5})
        self.assertEquals(m.get_total(), 0)
        m.add({5: 1, 10: 2, 20: 0, 50: 0, 100: 0})
        self.assertEquals(m.get_total(), 25)
        m.remove(15)
        self.assertEquals(m.get_total(), 10)
        self.assertEquals(m.coins, {5: 0, 10: 1, 20: 0, 50: 0, 100: 0})
        with pytest.raises(MachineException):
            m.remove(100)
        with pytest.raises(MachineException):
            m.remove(2)

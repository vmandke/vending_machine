from fastapi import Depends, FastAPI
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from typing_extensions import Annotated
import uvicorn

from vending_machine.models import VendingMachine, User, MachineException, Money, Product

machine = VendingMachine()

app = FastAPI()
security = HTTPBasic()


@app.post("/users/")
def create_user(user: User):
    machine.add_user(user)
    return user


@app.get("/users/")
def get_wallet(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    return machine.view_wallet(credentials.username, credentials.password)


@app.get("/users/")
def get_wallet(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    return machine.view_wallet(credentials.username, credentials.password)


@app.put("/users/deposit")
def deposit(credentials: Annotated[HTTPBasicCredentials, Depends(security)], money: Money):
    return machine.user_deposit(credentials.username, credentials.password, money)


@app.put("/products/")
def add_product(credentials: Annotated[HTTPBasicCredentials, Depends(security)], product: Product):
    return machine.add_product(credentials.username, credentials.password, product)


@app.delete("/products/")
def delete_product(credentials: Annotated[HTTPBasicCredentials, Depends(security)], product_name: str, count: int):
    return machine.delete_product(credentials.username, credentials.password, product_name, count)


@app.get("/products/{product_name}")
def get_products(product_name: str):
    return machine.products.get(product_name, {})


@app.post("/products/buy")
def buy(credentials: Annotated[HTTPBasicCredentials, Depends(security)], product_name: str, count: int):
    return machine.user_buy(credentials.username, credentials.password, product_name, count)


if __name__ == "__main__":
    print("Running vending machine API")
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=7878,
        reload=False,
        log_level="debug",
        # This should always be 1, to mimic a VendingMachine
        workers=1,
        # TODO(vin): Somehow setting it to 1 does not work
        limit_concurrency=5,
    )

import sys
from threading import Lock
from functools import wraps
import bcrypt
import hmac
from pydantic import BaseModel
from typing import Literal


class MachineException(Exception):
    pass


lock = Lock()


def locked_handling(func):
    """
    This decorator is used to lock the vending machine (threaded) and handle exceptions
    As could not figure out FastAPI single threaded runs in the short time
    :param func:
    :return:
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            with lock:
                return func(*args, **kwargs)
        except Exception as e:
            if not isinstance(e, MachineException):
                print(f"Unhandled Exception: {e}")
                # Mimic the vending machine shutting down
                sys.exit()
            else:
                return {"error": str(e)}
    return wrapper


class Money(BaseModel):
    n5: int
    n10: int
    n20: int
    n50: int
    n100: int

    @property
    def coins(self):
        return {
            5: self.n5, 10: self.n10, 20: self.n20, 50: self.n50, 100: self.n100
        }

    def reset(self):
        self.n5 = 0
        self.n10 = 0
        self.n20 = 0
        self.n50 = 0
        self.n100 = 0

    @coins.setter
    def coins(self, value):
        raise NotImplemented

    def get_total(self):
        return sum([k * v for k, v in self.coins.items()])

    def sub(self, money: dict) -> None:
        if not all([k in self.coins for k in money]):
            raise MachineException("Invalid Coins")
        coins = self.coins
        for k, v in money.items():
            if coins[k] < v:
                raise MachineException("Not enough money")
            self.__setattr__(f"n{k}", coins[k] - v)

    def add(self, money: dict) -> None:
        if not all([k in self.coins for k in money]):
            raise MachineException("Invalid Coins")
        coins = self.coins
        for k, v in money.items():
            self.__setattr__(f"n{k}", coins[k] + v)

    def remove(self, amt) -> "Money":
        removals = {
            100: 0, 50: 0, 20: 0, 10: 0, 5: 0
        }
        if amt > self.get_total():
            raise MachineException("Not enough money")
        denominations = [100, 50, 20, 10, 5]
        for d in denominations:
            if amt >= d and self.coins[d] > 0:
                used = min(int(amt // d), self.coins[d])
                removals[d] += used
                amt -= d * used
                if amt == 0:
                    break
        if amt > 0:
            raise MachineException("Not enough money")
        self.sub(removals)
        return Money(
            n5=removals[5], n10=removals[10], n20=removals[20], n50=removals[50], n100=removals[100]
        )


class User(BaseModel):
    name: str
    role: Literal["seller", "buyer"]
    password: str

    def get_pwd_hash(self):
        pwd_str = bytes(self.password, "utf-8")
        return bcrypt.hashpw(pwd_str, bcrypt.gensalt())


class MachineUser(BaseModel):
    name: str
    role: str
    password_hash: str
    wallet: Money

    def compare_password(self, pwd_str):
        pw_hash = bytes(self.password_hash, "utf-8")
        pwd_str = bytes(pwd_str, "utf-8")
        return hmac.compare_digest(bcrypt.hashpw(pwd_str, pw_hash), pw_hash)


class Product(BaseModel):
    name: str
    price: float
    stock: int


class MachineProduct(BaseModel):
    name: str
    price: float
    stock: int
    seller: str


class VendingMachine:
    def __init__(self):
        self.lock = Lock()
        self.products = {}
        self.users = {}
        self.machine_balance = Money(n5=0, n10=0, n20=0, n50=0, n100=0)

    @locked_handling
    def add_user(self, user: User):
        if user.name in self.users:
            raise MachineException("User already exists")
        self.users[user.name] = MachineUser(
            name=user.name,
            role=user.role,
            password_hash=user.get_pwd_hash(),
            wallet=Money(n5=0, n10=0, n20=0, n50=0, n100=0)
        )

    def get_and_verify_user(self, username: str, password: str):
        if username not in self.users:
            raise MachineException("User does not exist")
        if not self.users[username].compare_password(password):
            raise MachineException("Invalid Password")
        return self.users[username]

    def get_verify_product_seller(self, username: str, password: str, product_name: str):
        user = self.get_and_verify_user(username, password)
        if user.role != "seller":
            raise MachineException("Only sellers can handle products")
        product = self.products.get(product_name)
        if product and product.seller != username:
            raise MachineException("Product Seller Mismatch")
        return user, product

    @locked_handling
    def view_wallet(self, username: str, password: str):
        user = self.get_and_verify_user(username, password)
        return user.wallet

    @locked_handling
    def delete_product(self, username: str, password: str, product_name: str, count: int):
        seller, product = self.get_verify_product_seller(username, password, product_name)
        if not product:
            raise MachineException("Product does not exist")
        product.stock -= min(count, product.stock)
        return product

    @locked_handling
    def add_product(self, username: str, password: str, product: Product):
        seller, machine_product = self.get_verify_product_seller(username, password, product.name)
        if product.price < 0 or product.price % 5 != 0:
            raise MachineException("Invalid Price; Needs to be a multiple of 5")
        if product.stock < 0:
            raise MachineException("Invalid Stock")
        elif machine_product:
            machine_product.stock += product.stock
        else:
            self.products[product.name] = MachineProduct(
                name=product.name,
                price=product.price,
                stock=product.stock,
                seller=seller.name
            )

    @locked_handling
    def user_deposit(self, username: str, password: str, money: Money):
        user = self.get_and_verify_user(username, password)
        if user.role != "buyer":
            raise MachineException("Only buyers can deposit money")
        user.wallet.add(money.coins)
        return user.wallet

    @locked_handling
    def user_buy(self, username: str, password: str, product_name: str, count: int):
        user = self.get_and_verify_user(username, password)
        product = self.products.get(product_name)
        if not product:
            raise MachineException("Product does not exist")
        if product.stock < count:
            raise MachineException("Not enough stock")
        cost = product.price * count
        if user.wallet.get_total() < cost:
            raise MachineException("Not enough money in wallet")
        change = user.wallet.get_total() - cost
        try:
            # Dry Run
            money = Money(n5=0, n10=0, n20=0, n50=0, n100=0)
            money.add(user.wallet.coins)
            money.add(self.machine_balance.coins)
            money.remove(change)
        except MachineException:
            raise MachineException("Not enough change in Machine")
        self.machine_balance.add(user.wallet.coins)
        removed_money = self.machine_balance.remove(change)
        user.wallet.reset()
        user.wallet.add(removed_money.coins)
        return user.wallet



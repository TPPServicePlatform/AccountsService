from lib.models.account import Account


class AccountService:
    def __init__(self,):
        self.account = Account()

    def get_account(self, accountId):
        return self.account.get_account(accountId)

    def create(self, accountDict):
        return self.account.create(accountDict)

    def update(self, accountId, newAccountDict):
        return self.account.update(accountId, newAccountDict)

    def delete(self, accountId):
        return self.account.delete(accountId)

from lib.database.database import Database


class Account:
    def __init__(self, db):
        self.db = db

    def get_account(self, account_id):
        return self.db.get_account(account_id)

    def update_account(self, account_id, account):
        return self.db.update_account(account_id, account)

    def delete_account(self, account_id):
        return self.db.delete_account(account_id)

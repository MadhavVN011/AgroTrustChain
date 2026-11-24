"""Hash any plain-text passwords left in the Users table.

Run once after restoring an old database:
    python upgrade_passwords.py
Docker runs it on every start (it does nothing once all passwords are hashed).
Plain-text passwords are also upgraded one by one as users log in.
"""
from UsersModel import UsersModel

if __name__ == "__main__":
    count = UsersModel.hash_plaintext_passwords()
    print("Hashed " + str(count) + " plain-text password(s).")

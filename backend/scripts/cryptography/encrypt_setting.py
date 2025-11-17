import sys

from cryptography.fernet import Fernet

if __name__ == "__main__":
    fernet = Fernet(sys.argv[1].encode("utf-8"))
    print(fernet.encrypt(sys.argv[2].encode("utf-8")))

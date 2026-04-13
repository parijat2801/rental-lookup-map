import sys
from rental_lookup.run import main

if __name__ == "__main__":
    cookie = ""
    if len(sys.argv) > 1:
        cookie = sys.argv[1]
    main(cookie=cookie)

import httpx
BASE = "http://127.0.0.1:8000"

def main()-> None:
    account = input("Account ID [ACC-88392]: ").strip() or "ACC-88392"
    r = httpx.post(f"{BASE}/calls", json={"account_id":account}, timeout=30)
    r.raise_for_status() #shows server errors clearly
    data = r.json()
    sid = data["session_id"]
    print(f"Agent: {data['reply']}")
    while True:
        text = input("Customer: ")
        r = httpx.post(f"{BASE}/calls/{sid}/turn", json={"text":text}, timeout=60)
        r.raise_for_status()
        data = r.json()
        print(f"Agent: {data['reply']}   [{data['state']}]")
        if data["ended"]:
            print(f"Call ended: {data['disposition']}")
            break

if __name__ == "__main__":
    main()


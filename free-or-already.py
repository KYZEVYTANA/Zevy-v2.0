#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import sys
import requests
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed

BATCH_SIZE = 1000
MAX_WORKERS = 5  # количество параллельных потоков

API_LIST_MAIN = [
    "https://blockchain.info/q/addressbalance/{}",
    "https://api.blockcypher.com/v1/btc/main/addrs/{}/balance",
    "https://sochain.com/api/v2/get_address_balance/BTC/{}"
    "https://blockstream.info/api/address/{}"
    "https://insight.bitpay.com/api/addr/{}/balance"
    "https://mempool.space/api/address/{}"
]

API_LIST_TEST = [
    "https://api.blockcypher.com/v1/btc/test3/addrs/{}/balance",
    "https://sochain.com/api/v2/get_address_balance/BTC/{}"
]

def ask_list():
    while True:
        ans = input("Выберите список для проверки (main/test): ").strip().lower()
        if ans in ("main", "test"):
            return ans

def ask_start():
    while True:
        ans = input("Начать проверку кошельков? (Y/N): ").strip().upper()
        if ans in ("Y", "N"):
            return ans == "Y"

def check_balance(address, network="main"):
    apis = API_LIST_MAIN if network=="main" else API_LIST_TEST
    for api in apis:
        try:
            r = requests.get(api.format(address), timeout=10)
            if r.status_code != 200:
                continue
            ct = r.headers.get('Content-Type', '')
            data = r.json() if 'json' in ct else r.text
            if isinstance(data, dict):
                if 'final_balance' in data:
                    return int(data['final_balance']) / 1e8
                if 'balance' in data:
                    return float(data['balance'])
            else:
                return int(data)/1e8
        except Exception:
            continue
    return None

def append_record(file_path, record, first=False):
    mode = 'w' if first else 'a'
    with open(file_path, mode, encoding='utf-8') as f:
        if first:
            f.write("[\n")
        else:
            f.write(",\n")
        json.dump(record, f, ensure_ascii=False)

def finalize_file(file_path):
    with open(file_path, 'a', encoding='utf-8') as f:
        f.write("\n]")

def load_existing_addresses(file_path):
    addresses = set()
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            try:
                for r in json.load(f):
                    addresses.add(r["address"])
            except Exception:
                pass
    return addresses

def process_wallets_parallel(list_file, network="main"):
    free_file = f"free-{network}.json"
    cash_file = f"cash-{network}.json"

    free_addresses = load_existing_addresses(free_file)
    cash_addresses = load_existing_addresses(cash_file)

    free_first = not os.path.exists(free_file) or os.path.getsize(free_file)==0
    cash_first = not os.path.exists(cash_file) or os.path.getsize(cash_file)==0

    temp_free_fd, temp_free_path = tempfile.mkstemp()
    temp_cash_fd, temp_cash_path = tempfile.mkstemp()
    os.close(temp_free_fd)
    os.close(temp_cash_fd)

    with open(list_file, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except Exception:
            print("Ошибка чтения списка адресов")
            return

    # Фильтруем новые адреса
    new_records = [r for r in data if r.get("address") and r["address"] not in free_addresses and r["address"] not in cash_addresses]

    processed = 0
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_record = {executor.submit(check_balance, r["address"], network): r for r in new_records}
        for future in as_completed(future_to_record):
            record = future_to_record[future]
            balance = future.result()
            if balance is None:
                continue

            out_record = {
                "mnemonic": record.get("mnemonic"),
                "wif": record.get("wif"),
                "address": record["address"],
                "balance": balance
            }

            if balance == 0:
                append_record(temp_free_path, out_record, first=free_first)
                free_first = False
                free_addresses.add(record["address"])
            else:
                append_record(temp_cash_path, out_record, first=cash_first)
                cash_first = False
                cash_addresses.add(record["address"])

            processed += 1
            if processed % 10 == 0:
                sys.stdout.write(f"\rОбработано: {processed}, новые free: {len(free_addresses)}, новые cash: {len(cash_addresses)}")
                sys.stdout.flush()

            if processed % BATCH_SIZE == 0:
                ans = input(f"\n{processed} кошельков обработано. Продолжить? (Y/N): ").strip().upper()
                if ans != "Y":
                    print("\nОстановка. Сохраняем прогресс.")
                    break

    finalize_file(temp_free_path)
    finalize_file(temp_cash_path)

    # Замена оригинальных файлов
    for tmp_path, final_file in [(temp_free_path, free_file), (temp_cash_path, cash_file)]:
        if os.path.exists(final_file):
            with open(final_file, 'r', encoding='utf-8') as f_old, open(tmp_path, 'r', encoding='utf-8') as f_new:
                old_data = f_old.read().rstrip(']')
                new_data = f_new.read().lstrip('[')
                with open(final_file, 'w', encoding='utf-8') as f_out:
                    f_out.write(old_data + ',' + new_data if old_data.strip() else new_data)
        else:
            os.replace(tmp_path, final_file)

    print(f"\nСессия завершена. Новых free: {len(free_addresses)}, новых cash: {len(cash_addresses)}")

def main():
    while True:
        network = ask_list()
        if not ask_start():
            continue
        list_file = "main_list.json" if network=="main" else "test_list.json"
        if not os.path.exists(list_file):
            print(f"Файл {list_file} не найден.")
            continue
        process_wallets_parallel(list_file, network)
        print("Возврат к выбору списка.\n")

if __name__ == "__main__":
    main()
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import requests
import hashlib

WORDLIST_URLS = {
    "english": "https://raw.githubusercontent.com/bitcoin/bips/master/bip-0039/english.txt"
}

VALID_ENT = {12: 128, 24: 256}


def download_wordlist(url):
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    return [w.strip() for w in r.text.splitlines() if w.strip()]


def generate_entropy(ent_bits):
    return os.urandom(ent_bits // 8)


def checksum_bits(entropy):
    ent_bits = len(entropy) * 8
    cs_len = ent_bits // 32
    h = hashlib.sha256(entropy).digest()
    hv = int.from_bytes(h, "big")
    return hv >> (256 - cs_len)


def entropy_to_mnemonic(entropy, wordlist):
    ent_bits = len(entropy) * 8
    cs_len = ent_bits // 32
    ent_int = int.from_bytes(entropy, "big")
    cs = checksum_bits(entropy)
    total_bits = ent_bits + cs_len
    combo = (ent_int << cs_len) | cs
    words_count = total_bits // 11
    words = []
    for i in range(words_count):
        shift = (total_bits - 11 * (i + 1))
        idx = (combo >> shift) & 0x7FF
        words.append(wordlist[idx])
    return words


def ask_phrase_length():
    while True:
        try:
            count = int(input("\nВведите количество слов (12 или 24): ").strip())
            if count in VALID_ENT:
                return VALID_ENT[count]
        except ValueError:
            pass
        print("Ошибка: можно выбрать только 12 или 24.")


def ask_number_of_phrases():
    while True:
        try:
            n = int(input("Сколько фраз сгенерировать на английском? ").strip())
            if n > 0:
                return n
        except ValueError:
            pass
        print("Введите положительное число.")


def main():
    while True:  # общий цикл — возвращение к выбору длины
        ent_bits = ask_phrase_length()
        num_phrases = ask_number_of_phrases()
        generated_count = 0

        with open("generations.txt", "a", encoding="utf-8") as f:
            try:
                print("\nЗагружаю английский словарь...")
                wl = download_wordlist(WORDLIST_URLS["english"])

                for _ in range(num_phrases):
                    entropy = generate_entropy(ent_bits)
                    phrase = entropy_to_mnemonic(entropy, wl)
                    f.write(" ".join(phrase) + "\n")
                    generated_count += 1

                    if generated_count % 1000000 == 0:
                        ans = input(f"\nСгенерировано {generated_count} фраз. Продолжить? (Y/N): ").strip().upper()
                        if ans == "N":
                            print("Возврат к выбору количества слов.")
                            break
                print(f"\nСгенерировано всего {generated_count} фраз, сохранено в файл generations.txt.")

            except Exception as e:
                print(f"✗ Ошибка: {e}")


if __name__ == "__main__":
    main()
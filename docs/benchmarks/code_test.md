# CODE-test (teste externo final, ECG)
_Rodado UMA vez em 2026-11-25, codigo 2be7b23 (regras ECG congeladas; nada foi ajustado a partir deste resultado). Marcador `data/bench/ecg/code_test.RUN` impede reexecucao._

Ribeiro et al., Nat Commun 2020 (Zenodo 3765780 v1.0.3, CC BY 4.0): 827 ECGs de 12 derivacoes, 400 Hz, gold por 2 cardiologistas + 3o em discordancia. Comando: `python -m bench.ecg_bench --source code_test --i-know-this-is-the-final-external-test --workers 8`. Unidade do sinal tratada como mV (ver bench/code_test.py). IC95% bootstrap.

| rótulo | nossa regra | N | N pos | TP | FP | Sens [IC95%] | Espec [IC95%] | VPP [IC95%] | Acc [IC95%] |
|---|---|---|---|---|---|---|---|---|---|
| 1dAVb | AV1 | 827 | 28 | 13 | 1 | 46,4% [27,8–65,6] | 99,9% [99,6–100,0] | 92,9% [75,0–100,0] | 98,1% [97,1–98,9] |
| RBBB | RBBB_any | 827 | 34 | 18 | 17 | 52,9% [35,7–70,3] | 97,9% [96,8–98,8] | 51,4% [34,4–67,7] | 96,0% [94,7–97,3] |
| LBBB | LBBB_any | 827 | 30 | 25 | 6 | 83,3% [69,6–96,2] | 99,2% [98,6–99,8] | 80,6% [65,4–93,3] | 98,7% [97,8–99,4] |
| SB | SBRAD | 827 | 16 | 15 | 4 | 93,8% [80,0–100,0] | 99,5% [99,0–99,9] | 78,9% [57,9–95,2] | 99,4% [98,8–99,9] |
| AF | AF | 827 | 13 | 12 | 10 | 92,3% [75,0–100,0] | 98,8% [97,9–99,5] | 54,5% [33,3–75,0] | 98,7% [97,8–99,4] |
| ST | STACH | 827 | 37 | 31 | 4 | 83,8% [71,4–94,6] | 99,5% [99,0–99,9] | 88,6% [76,9–97,4] | 98,8% [97,9–99,5] |

Leitura (sem ajuste de regra): BRE e taquicardia sinusal ~83%, bradicardia sinusal 94%, FA 92% de sensibilidade mas VPP 54% (10 FP em 814 negativos; N positivo = 13, IC largo); BRD 53% sens / 51% VPP (nossa RBBB_any inclui BRD incompleto, o que provavelmente explica parte dos 17 FP; o gold CODE rotula BRD); BAV1 46% sens / 93% VPP, coerente com PTB-XL (40%). Sem comparacao com a DNN do artigo (nao e meta; regras determinísticas).

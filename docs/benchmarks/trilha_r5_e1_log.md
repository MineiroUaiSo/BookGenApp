# Trilha R5 / lote E1: SVD e BRD (passo A) e PR acima de 200 ms (passo B)

Base: 60af7b7. Bench: PTB-XL dev ampliado, N=9183 (`--source ptbxl --split dev --set large`, tags R5E1A e R5E1B,
rodados separados, sem outro bench em paralelo). Referência "antes" = cache `ptbxl.jsonl` (mesmo código da base,
confere com `docs/benchmarks/ecg.md`). IC95% por bootstrap (mesma função do bench). O CODE-test não foi usado.

## Resultado

| Passo | Aceite | Resultado | Decisão |
|---|---|---|---|
| A (SVD só com QRS de decisão < 120 ms salvo eixo > 110°; QRS >= 120 ms + R dominante em V1 + sem BRE -> BRD provável) | RBBB_complete sens >= 75% e VPP >= 65%; RVH VPP >= 40%; NORM->normal >= 74,1%; LBBB_complete igual; STE_acute FP <= 310 | **REPROVADO**: sens 71,9% e RVH VPP 21,8% | regra NÃO commitada; só teste (xfail strict) + este log |
| B (achado borderline quando PR exibido > 200 ms sem critério completo de BAV1) | 0 registros com PR > 200 ms sem achado de PR; NORM->normal inalterado | **APROVADO**: 1187 -> 0; NORM 2101/2815 igual | regra commitada |

### Passo A (R5E1A), antes -> depois

| Métrica | Antes | Depois |
|---|---|---|
| RBBB_complete sens | 58,0% [53,4-62,8] (250/431) | **71,9% [67,6-76,1]** (310/431) |
| RBBB_complete VPP | 69,3% [64,6-73,9] (FP 111) | 71,4% [67,0-75,5] (FP 124) |
| RBBB_any sens / VPP | 47,2% [44,3-49,9] / 92,1% [89,8-94,2] | 52,9% [50,0-55,6] / 92,1% [90,0-94,1] |
| RVH sens / VPP | 47,8% [37,6-58,4] / 17,8% [12,9-22,9] (247 disparos) | 45,7% [35,4-55,7] / **21,8% [15,8-27,6]** (193 disparos) |
| NORM -> normal | 74,6% [73,0-76,2] (2101/2815) | 74,6% (2101/2815) |
| LBBB_complete | 78,5% / 49,0% (TP 336, FP 350) | idêntico |
| STE_acute FP | 310 | 310 |
| AF, AV1 | sem mudança | sem mudança |

Diagnóstico pós-bench (dev, não é calibração):
- Dos 193 disparos de `ecg.rvh` que restaram, **146 têm eixo > 110°** (a exceção do próprio passo A) e 130 têm
  BRD completo no gold. A exceção "salvo eixo > 110°" segura a maior parte do problema: BRD completo costuma vir com
  desvio do eixo para a direita.
- 39 disparos têm QRS global >= 120 ms e eixo <= 110° (QRS de decisão < 120 ms, pois é mediana por derivação
  + 0,25 x (global - mediana)); 27 desses têm BRD no gold.
- Fallback "BRD provável" criou 73 novos `ecg.rbbb`: 60 com CRBBB no gold, 7 com IRBBB, 6 outros (VPP do fallback ~82%).
- Falta para o aceite: ~+3 pp de sensibilidade e VPP de RVH quase dobrar (21,8% -> 40%). Variante a testar (decisão do dono,
  fora do escopo E1 "nenhum limiar novo"): não isentar o eixo > 110° quando o QRS de decisão >= 120 ms, ou exigir
  eixo > 110° + SVD só com QRS < 120 ms.
Patch do passo A (não aplicado; `git apply` sobre 60af7b7 em `backend/app/ecg/analysis/rules.py`):

```diff
backend/app/ecg/analysis/rules.py | 28 +++++++++++++++++++++++++---
 1 file changed, 25 insertions(+), 3 deletions(-)

--- Changes ---

backend/app/ecg/analysis/rules.py
  @@ -125,6 +125,16 @@ def rb_inc_lbbb_excl(v1):
  +def _v1_r_dominant(bd, ax):
  +    """Dominant R in V1: the condition that fires RVH (R >= 7 mm with R > S, or R > S with R >= 5 mm plus right axis
  +    > 110 deg). Shared by the RVH rule and the 'probable RBBB' fallback (E1)."""
  +    ld = bd.leads.get("V1")
  +    if ld is None:
  +        return False
  +    r1, s1 = ld.r_max, -ld.s_min
  +    return (r1 >= 0.7 and r1 > s1) or (r1 > s1 and r1 >= 0.5 and ax is not None and ax > 110)
  +
  +
   def _classify_bbb(bd, dur, fs_ms, L=None):
       """Returns (kind|None, evidence). kind in rbbb|lbbb|irbbb|ilbbb."""
       if dur < 100:
  @@ -406,10 +416,20 @@ def build_findings(c):
  -    if cbbb in ("lbbb", "rbbb", "ilbbb", "irbbb") and any(f.code == "ecg.preexcitation" for f in out):
  +    preexc = any(f.code == "ecg.preexcitation" for f in out)
  +    if cbbb in ("lbbb", "rbbb", "ilbbb", "irbbb") and preexc:
           cbbb = None  # delta wave widens the QRS and mimics a bundle branch block (AHA 2009 Part III, exclusions)
  +    # E1: wide QRS + dominant R in V1 (the condition that used to fire RVH) and no LBBB pattern is a probable RBBB
  +    # even when the delineator letters miss the wide lateral S (the RVH rule no longer fires with QRS >= 120 ms)
  +    rbbb_probable = (cbbb is None and not preexc and not c.get("paced") and _v1_r_dominant(bd, ax)
  +                     and 120 <= dur <= rules_lvh.QRS_IMPLAUSIBLE_MS)
  +    if rbbb_probable:
  +        cbbb, bbb_note = "rbbb", "R dominante em V1 com QRS largo, sem padrão de BRE e sem S larga lateral definida"
       ev = [f"QRS {dur:.0f} ms", f"V1 {v1 or '-'}", f"V6 {v6 or '-'}", f"D1 {d1 or '-'}"]
  -    if cbbb == "rbbb":
  +    if cbbb == "rbbb" and rbbb_probable:
  +        out.append(_f("ecg.rbbb", "Bloqueio de ramo direito provável", "abnormal",
  +                      ev + [bbb_note], [R_AHA, R_SBC], 0.5))
  +    elif cbbb == "rbbb":
           out.append(_f("ecg.rbbb", "Bloqueio completo de ramo direito (BRD)", "abnormal",
                         ev + [bbb_note], [R_AHA, R_SBC], 0.7))
       elif cbbb == "lbbb":
  @@ -505,7 +525,9 @@ def build_findings(c):
  -        if r1 >= 0.7 and r1 > s1 and rbbb_ok:
  +        # E1: with QRS >= 120 ms the dominant R in V1 is the RBBB terminal R' (right axis > 110 deg keeps RVH possible)
  +        wide_ok = dur < 120 or (ax is not None and ax > 110)
  +        if r1 >= 0.7 and r1 > s1 and rbbb_ok and wide_ok:
               rv.append(f"R em V1 {r1*10:.0f} mm (>=7 mm) com R/S {r1/max(s1, 1e-3):.1f} (>1)")
           elif r1 > s1 and r1 >= 0.5 and ax is not None and ax > 110:
               rv.append(f"R/S em V1 {r1/max(s1, 1e-3):.1f} (>1), R {r1*10:.0f} mm (>=5 mm)")
  +25 -3
```

### Passo B (R5E1B), antes -> depois

| Métrica | Antes | Depois |
|---|---|---|
| Registros com PR exibido > 200 ms | 1619 | 1619 |
| ... sem nenhum achado de PR (BAV1/2/3, pré-excitação, medida implausível) | 1187 | **0** |
| Achado novo `ecg.pr_gt200_unconfirmed` (borderline) | 0 | 1191 (4 a mais que 1187 porque o bench conta `implausible_measurement` de QRS como achado de PR) |
| NORM -> normal | 74,6% (2101/2815) | 74,6% (2101/2815), inalterado |
| AV1 sens / VPP | 40,1% [36,1-43,8] / 54,3% [49,7-59,0] | idêntico (TP 247, FP 208) |
| RBBB, RVH, LBBB, STE_acute, AF | | todos idênticos |

Observação: o achado novo é só `borderline`; não tira o laudo de "dentro do limite" (regra de achados limítrofes
isolados) e não muda `ecg.av_block_1` nem `AV1_*`.

Desvio de escopo (necessário): o teste `test_knowledge_cards_cobertura` exige um cartão para cada código emitido
por `rules.py`; o código novo foi adicionado como gatilho do cartão existente `conducao.bav1`
(`knowledge/ecg/cards/conducao.yaml`, +1 linha). O cartão continua `revisado_por_medico: false`.

## 3 linhas para o médico revisar a mudança de saída (passo B, a única commitada)

1. Todo ECG com PR exibido acima de 200 ms que não fecha o critério completo de BAV de 1º grau agora mostra, em
   "limítrofe", a frase: "PR medido acima de 200 ms sem critério completo de BAV de 1º grau: conferir no traçado"
   (1191 de 9183 registros do dev; antes, 1187 mostravam PR alto e nenhum achado).
2. O laudo não muda de classe: continua "dentro do limite" quando só há esse achado limítrofe; BAV de 1º grau
   só é dado como antes (mesmos limiares, mesma sensibilidade 40,1% e VPP 54,3%).
3. Decisão sua: aceitar a frase como está, ou trocar por texto mais curto na tela; e decidir se vale testar a
   variante do passo A sem a exceção de eixo > 110° (o passo A como especificado reprovou no aceite).

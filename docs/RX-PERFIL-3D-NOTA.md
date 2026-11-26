# Perfil (lateral) heurístico e reconstrução 3D: evidência e limites

Lote D3, 2026-11-26. Escopo: `backend/app/recon3d/`, ramo lateral de `seg_heuristic.py`, visualizador 3D.
Nenhum limiar foi alterado. Nenhuma imagem ou máscara foi copiada para o repositório.

## O que foi medido

Dados: 40 pares frontal+lateral do mesmo paciente (amostra aleatória, `--seed 0`) de
`data/datasets/rx_masks_other` (PAX-Ray++, CC BY-NC, só avaliação). **São radiografias sintéticas projetadas
de TC, com máscaras de pseudo-rótulo (não são ground truth de radiologista). RX clínico real PA+perfil ainda
NÃO foi testado.** Script: `backend/bench/rx_profile_pairs.py` (lê pelo caminho absoluto, sem cópia).
Pipeline completo via API (`/ingest` de PNG, `/rx/{id}/analyze`, `/rx/{id}/recon3d`).

| Medida (36 perfis classificados como lateral) | Resultado |
|---|---|
| Perfil classificado como lateral | 36/40 (4 viraram `OTHER`: ver abaixo) |
| Coração segmentado | 36/36; IoU médio 0,44 (mediana 0,46; IoU>=0,5 em 14; IoU<0,2 em 4); precisão 0,75, cobertura 0,51 |
| Coluna segmentada | 36/36; IoU médio 0,31 (IoU>=0,5 em 1; IoU<0,2 em 10); precisão 0,55, cobertura 0,39 |
| Traqueia segmentada | 16/36 (ausente em 20); IoU médio 0,04 (0,08 quando presente); precisão 0,29, cobertura 0,06 |
| Pulmão no perfil | sem máscara de pseudo-rótulo de pulmão lateral no conjunto: IoU não medido |
| 3D montado (`/recon3d` 200) | 36/40; os 4 restantes falham antes, na classificação da incidência |

Conjuntos de chaves observados no perfil: sempre `diaphragm, heart, lung_field, spine, sternum`; `trachea` em 16.

## Leitura

1. **Quando o perfil é classificado como lateral, coração e coluna quase sempre existem, mas cobrem pouco.**
   Cobertura média 0,51 (coração) e 0,39 (coluna) com precisão moderada: as máscaras de prior anatômico
   (`_LAT_PRIORS`, `_lateral_templates`, faixa posterior de 14% da largura) saem menores/deslocadas em
   relação ao pseudo-rótulo. Isso não é um bug pontual e sim erro sistemático de prior; ajustar os números
   com estas máscaras seria calibrar às cegas (imagens sintéticas, não clínicas). Não foi feito.
2. **Traqueia é o caso que "some" na maior parte das vezes (20/36) e, quando aparece, quase não se
   sobrepõe ao pseudo-rótulo (cobertura 0,06).** O detector procura um tubo escuro alto e fino fora da
   abertura morfológica do campo pulmonar; nestas imagens (projeção de TC) a coluna de ar do perfil
   fica sobreposta a outras estruturas e esse sinal não existe. Sem causa raiz simples e testável.
3. **4/40 perfis (10%) são rotulados `OTHER` por `view.py`/`classify_from_features`** (PSPNet: limiares
   `LATERAL_LUNG_MIN`, `LATERAL_MAXPROB_MIN`, `LATERAL_SPINE_MAX`, `LATERAL_GAP_MAX`). Aí o 3D nem é oferecido
   (`recon3d_available` falso, ou 422 "need a frontal (PA/AP) and a lateral image"). Arquivo fora do escopo
   do D3; fica como candidato para um lote próprio, com validação em perfis clínicos.
4. Em um perfil que não é lateral heurística (fantoma sem estruturas), o ramo lateral devolve `None` e o
   pipeline segue com `structures=[]`: o 3D agora responde 422 em pt-BR dizendo o que fazer.

## O que o 3D passou a fazer (sem inventar)

* Perfil parcial (por exemplo só pulmão): monta o que existe; cada estrutura que só tem máscara em uma
  incidência vira estimativa translúcida, rótulo "(estimativa, 1 incidência: ausente no perfil/na PA)", e o
  método lista "Estruturas ausentes no perfil: ...". Estrutura segmentada mas fina demais para o voxel é
  declarada como não reconstruída (antes sumia sem aviso).
* Orientação antero-posterior: coluna, depois coração, depois `quality["orientação"]` do perfil; se nada
  existe, o método diz que a orientação foi assumida.
* Sem máscaras: `Recon3DUnavailable` (ValueError + HTTP 422) com mensagem acionável.
* Modo "Imagem real": o GLB carrega (em `scenes[0].extras.medlens_texture`) a radiografia que já está no estudo
  e os coeficientes de projeção PA/perfil; a textura é montada em canvas no navegador e nunca sai do aparelho.
  Sem imagem do perfil: só a PA, com aviso.

## Pendências

* Validar em RX clínico real PA+perfil (nenhum disponível).
* `backend/app/api/analysis.py` ainda lança "need a frontal (PA/AP) and a lateral image" em inglês; fora do escopo.
* Candidatos de causa raiz (para lote próprio, com RX real): priors laterais de coração/coluna e a
  classificação de incidência em `view.py`.

## Lote D4: segmentação do perfil por sinal de imagem (2026-11-25)

Escopo: novo módulo `backend/app/rx/seg_lateral.py` (campo pulmonar por claridade, diafragma como contorno das duas
cúpulas, coluna/esterno por crista, coração por densidade, marca de estimativa), benches
`backend/bench/rx_profile_pairs.py --inproc` (40 pares sintéticos, mesma amostra do D3) e
`backend/bench/rx_profile_real.py` (5 pares reais Open-i, só avaliação local, overlays em `~/medlens-shots/d4-*.png`).
Nenhuma imagem foi copiada para o repositório.

### Resultado nos 40 pares sintéticos (36 perfis), antes e depois

| Medida | Antes (ramo legado) | Depois (seg_lateral) |
|---|---|---|
| Coração, IoU médio | 0,441 | 0,401 |
| Coluna, IoU médio | 0,308 | 0,286 |
| Traqueia, IoU médio | 0,036 (presente em 16/36) | 0,065 (35/36, quase sempre prior marcado como estimativa) |
| Campo pulmonar, IoU da extensão vertical vs pulmões da PA (proxy) | 0,651 | 0,757 |
| Campo pulmonar, IoU vs caixa coluna-esterno (proxy) | 0,306 | 0,438 |
| Campo pulmonar, área média | 0,119 | 0,194 |
| Cobertura (perfis com campo pulmonar) | 36/36 | 36/36 |

Não há máscara de pulmão lateral no pseudo-rótulo, então o pulmão só tem proxies fracos. O campo pulmonar melhora
nos dois proxies e visualmente (passa a incluir a área clara retroesternal e retrocardíaca). O critério do lote exigia
que coração e pulmão subissem sem perder cobertura: o coração NÃO subiu (0,441 para 0,401). Por isso a ligação do novo
módulo ao ramo lateral (`seg_heuristic.py` e `analyze.py`) não foi aplicada neste commit; o módulo, os benches e os
testes ficam disponíveis para um próximo ciclo.

### O que se viu nos 5 pares reais (perfil Indiana, coluna à direita em 4 e à esquerda em 1)

* O campo pulmonar acompanha bem o campo claro e as cúpulas diafragmáticas nos 5 casos; o diafragma sai como contorno
  duplo das cúpulas. Em CXR1521 o campo fica fragmentado por sobreposição de partes moles.
* A coluna ainda é o ponto fraco: a crista tracejada encontra a parede posterior do tórax, não o corpo vertebral. Por
  isso a coluna é sempre devolvida como ESTIMATIVA (faixa posicionada pelo contorno), com confiança 0,1 e rótulo
  "(estimativa geométrica, sem sinal na imagem)".
* O coração por densidade vaza para a parede anterior ou o abdome em vários casos reais, então a máscara só é
  aceita quando o contorno não é recorte reto da janela de busca; nos 5 reais acabou como elipse marcada estimativa.
* O lado posterior estimado pela faixa de intensidade acertou 34 de 40 perfis (5 reais mais 35 sintéticos; 1 dos reais, CXR3971, errou).

### Limites

* A heurística clássica não separa coluna e coração em RX real com segurança; só o campo pulmonar e o diafragma
  ganham sinal confiável. Próximo passo candidato: modelo treinado para perfil, validado em RX clínico.
* Marca de estimativa: não existe campo no schema `Structure`; a convenção é confiança <= 0,1 e o sufixo
  " (estimativa geométrica, sem sinal na imagem)" no rótulo (`marcar_estimativas`), no mesmo espírito do recon3d.

## Lote M1: pulmão e diafragma da `seg_lateral` ligados ao ramo lateral (2026-11-25)

Ligação parcial: em `seg_heuristic.segment_chest_lateral` o campo pulmonar e o diafragma passam a vir de
`seg_lateral.segment_lateral`; coração, coluna, esterno e traqueia ficam EXATAMENTE como no ramo legado (priors), sem a
heurística de coração do D4, que reduzira o IoU de 0,441 para 0,401. Sem campo claro, o ramo legado vale inteiro.
`analyze.py` chama `marcar_estimativas` com a chave `_estimativa` (coluna e esterno sempre; coração e traqueia quando vêm
de molde sobre a dica do modelo): confiança <= 0,1 e rótulo "(estimativa geométrica, sem sinal na imagem)".

Medido em `rx_profile_pairs.py --inproc --n 40` (36 perfis), antes e depois:

| Medida | Antes | Depois |
|---|---|---|
| Coração, IoU médio | 0,44 | 0,44 |
| Coluna, IoU médio | 0,31 | 0,31 |
| Traqueia, IoU médio | 0,04 (16/36) | 0,04 (16/36) |
| Pulmão, IoU da extensão vertical (proxy) | 0,65 | 0,76 |
| Pulmão, IoU vs caixa coluna-esterno (proxy) | 0,31 | 0,44 |
| Pulmão, área média | 0,119 | 0,194 |
| Perfis com estrutura marcada como estimativa | 0/36 | 36/36 |
| `recon3d` montado nos perfis detectados | - | 36/36 |

Nos 5 pares reais Open-i (só avaliação local) o overlay está em `~/medlens-shots/m1-lateral-overlay.png`.

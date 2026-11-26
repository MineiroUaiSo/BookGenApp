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

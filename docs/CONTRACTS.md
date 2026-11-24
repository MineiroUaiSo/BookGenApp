# Contratos

Modelos: `backend/app/schemas.py` (espelho TS: `frontend/src/types/api.ts`).

## Endpoints REST (prefixo `/api`)

| Método | Rota | Corpo | Resposta |
|---|---|---|---|
| GET | `/health` | – | `{"status":"ok","ai_available":bool,"models":{...}}` |
| POST | `/ingest` | multipart `files[]` (vários arquivos, inclusive pasta inteira; campo `relative_paths[]` opcional) | `IngestResponse` |
| GET | `/studies` | – | `StudyInfo[]` |
| GET | `/studies/{study_id}` | – | `StudyInfo` |
| GET | `/instances/{instance_id}/render.png?wc=&ww=` | – | PNG 8-bit |
| POST | `/ecg/{study_id}/analyze?ai=true` | `{"instance_id"?: str, "layout"?: "3x4+1"|"6x2"|"12x1"|"auto"}` | `ECGAnalysis` |
| POST | `/rx/{study_id}/analyze?ai=true` | `{"instance_ids"?: str[]}` | `RXAnalysis` |
| POST | `/rx/{study_id}/recon3d` | `{"frontal_id"?: str, "lateral_id"?: str}` | `Recon3DResult` |
| GET | `/recon3d/{study_id}/model.glb` | – | glb binário |

Imagens/fotos enviadas a `/ingest` viram um estudo com uma série `modality=UNKNOWN` até
que o usuário escolha ECG ou RX (ou a heurística decida); o frontend chama o analisador escolhido.

## Interfaces Python internas (para os agentes respeitarem)

```python
# app/store.py
class Store:
    def save_study(self, study: StudyInfo) -> None
    def get_study(self, study_id: str) -> StudyInfo | None
    def list_studies(self) -> list[StudyInfo]
    def instance_path(self, instance_id: str) -> Path      # arquivo original salvo
    def put_artifact(self, study_id: str, name: str, data: bytes) -> Path
    def get_artifact(self, study_id: str, name: str) -> Path | None
store: Store   # singleton, raiz em $MEDLENS_DATA (padrão ./data)

# app/dicom/render.py
def load_dicom(path) -> pydicom.Dataset
def render_to_uint8(ds, wc: float|None=None, ww: float|None=None) -> np.ndarray   # HxW uint8
def pixel_spacing_mm(ds) -> tuple[float,float] | None

# app/ecg/ingest/__init__.py
def load_ecg(path: Path) -> ECGSignal          # despacha por tipo (DICOM, XML, CSV, WFDB, imagem)
# app/ecg/digitize/__init__.py
def digitize_image(img: np.ndarray, layout: str = "auto") -> ECGSignal
# app/ecg/analysis/__init__.py
def analyze_signal(signal: ECGSignal, study_id: str) -> ECGAnalysis   # sem IA
# app/ecg/conduction.py
def conduction_timeline(gm: GlobalMeasurements, waves: list[Wave]) -> list[ConductionPhase]

# app/rx/__init__.py
def analyze_image(img_uint8: np.ndarray, instance_id: str, ds: pydicom.Dataset|None) -> RXImageAnalysis
def study_findings(images: list[RXImageAnalysis]) -> list[Finding]
# app/recon3d/__init__.py
def reconstruct(frontal: RXImageAnalysis, lateral: RXImageAnalysis) -> tuple[bytes, list[Recon3DMesh], str]  # glb, meshes, method

# app/llm/__init__.py
def ai_available() -> bool
def ecg_report(analysis: ECGAnalysis, image_png: bytes | None) -> AIReport
def rx_report(analysis: RXAnalysis) -> AIReport
# app/knowledge/__init__.py
def load_criteria(domain: Literal["ecg","rx"]) -> list[dict]
def reference(id: str) -> Reference
```

Dependências pesadas (torch, torchxrayvision, neurokit2, opencv) devem ser importadas
de forma preguiçosa e com fallback, para que os testes rodem sem elas.

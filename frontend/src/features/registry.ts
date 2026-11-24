import { lazy } from "react";
import type { ECGAnalysis, Recon3DResult } from "../types/api";

// Lazy import points for the feature modules owned by other agents.
export const ECGWorkspace = lazy(
  () => import("./ecg/ECGWorkspace"),
) as React.LazyExoticComponent<React.ComponentType<{ analysis: ECGAnalysis }>>;

export const Recon3DViewer = lazy(
  () => import("./recon3d/Recon3DViewer"),
) as React.LazyExoticComponent<React.ComponentType<{ result: Recon3DResult; apiBase: string }>>;

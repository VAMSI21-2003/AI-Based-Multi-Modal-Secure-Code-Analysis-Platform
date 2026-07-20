// Platform hub → Settings tab (Phase 5). Small, real, locally-persisted
// preferences -- not a placeholder screen. Currently: default detection
// model, consumed by Code Scanner and Live IDE as their initial selection.

const DEFAULT_MODEL_KEY = "securecode-ai:default-model";

export type ModelChoice = "XGBoost" | "Random Forest";

export function getDefaultModel(): ModelChoice {
  try {
    const v = localStorage.getItem(DEFAULT_MODEL_KEY);
    return v === "Random Forest" ? "Random Forest" : "XGBoost";
  } catch {
    return "XGBoost";
  }
}

export function setDefaultModel(model: ModelChoice) {
  try {
    localStorage.setItem(DEFAULT_MODEL_KEY, model);
  } catch {
    /* ignore (private browsing / storage disabled) */
  }
}

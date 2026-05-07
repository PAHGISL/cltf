"""Model adapters for the herbicide research workbench."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from workbench.config import ensure_pyclt_path
from workbench.contracts import FitResult, InputBundle, ModelResult, ParameterSpec

ensure_pyclt_path()
from pyclt.model import CLTParameters, run_series


class PyCLTAdapter:
    """Adapter that wraps the current two-layer PyCLT model."""

    name = "pyclt"

    def __init__(self, maxiter: int = 35, maxfun: int = 80):
        self.maxiter = maxiter
        self.maxfun = maxfun

    def parameter_specs(self) -> list[ParameterSpec]:
        return [
            ParameterSpec("mu", "Log-normal mu", 3.0, 0.1, 8.0, 0.1, "Mean of log travel-time distribution."),
            ParameterSpec("sigma", "Log-normal sigma", 1.0, 0.2, 3.0, 0.05, "Spread of log travel-time distribution."),
            ParameterSpec("effective_porosity", "Effective porosity", 0.2, 0.05, 0.6, 0.01, "Effective transport porosity."),
            ParameterSpec("retardation_top", "Top retardation", 6.0, 0.5, 20.0, 0.1, "Retardation factor in the top layer."),
            ParameterSpec("retardation_bottom", "Bottom retardation", 6.0, 0.5, 30.0, 0.1, "Retardation factor in the lower layer."),
            ParameterSpec("decay_top", "Top decay", 0.0015, 0.0, 0.05, 0.0005, "Daily decay rate in the top layer."),
            ParameterSpec("decay_bottom", "Bottom decay", 0.02, 0.0, 0.10, 0.001, "Daily decay rate in the lower layer."),
            ParameterSpec("et_factor", "ET factor", 1.0, 0.0, 2.0, 0.05, "Multiplier used when deriving cumulative infiltration."),
        ]

    def default_parameters(self) -> dict[str, float]:
        return {spec.name: spec.default for spec in self.parameter_specs()}

    def _geometry(self, bundle: InputBundle) -> pd.Series:
        return bundle.site_config.iloc[0]

    def _clt_parameters(self, bundle: InputBundle, parameters: dict[str, float]) -> CLTParameters:
        geometry = self._geometry(bundle)
        return CLTParameters(
            mu=float(parameters["mu"]),
            sigma=float(parameters["sigma"]),
            effective_porosity=float(parameters["effective_porosity"]),
            retardation_top=float(parameters["retardation_top"]),
            decay_top=float(parameters["decay_top"]),
            reference_depth=float(geometry["reference_depth_mm"]),
            retardation_bottom=float(parameters["retardation_bottom"]),
            decay_bottom=float(parameters["decay_bottom"]),
            top_thickness_mm=float(geometry["top_thickness_mm"]),
            bottom_depth_mm=float(geometry["bottom_depth_mm"]),
            dz=0.01,
            min_value=1e-4,
        )

    def simulate(self, bundle: InputBundle, parameters: dict[str, float], run_type: str = "manual") -> ModelResult:
        params = self._clt_parameters(bundle, parameters)
        climate = bundle.climate.sort_values("days_since_application").copy()
        top, bottom = run_series(
            times_days=climate["days_since_application"].to_numpy(dtype=float),
            cumulative_infiltration=climate["cumulative_infiltration_mm"].to_numpy(dtype=float),
            params=params,
        )
        predictions = pd.DataFrame(
            {
                "site_id": bundle.case.site_id,
                "soil_group": bundle.case.soil_group,
                "herbicide": bundle.case.herbicide,
                "date": climate["date"].to_numpy(),
                "days_since_application": climate["days_since_application"].to_numpy(dtype=int),
                "top_rel_conc": top,
                "subsoil_rel_conc": bottom,
                "run_type": run_type,
            }
        )
        return ModelResult(
            predictions=predictions,
            forcing=climate,
            warnings=[],
            metadata={"adapter": self.name, "run_type": run_type},
        )

    def fit(self, bundle: InputBundle, start_parameters: dict[str, float]) -> FitResult:
        fit_names = ["mu", "sigma", "retardation_top", "retardation_bottom", "decay_top", "decay_bottom"]
        specs = {spec.name: spec for spec in self.parameter_specs()}
        bounds = [(specs[name].minimum, specs[name].maximum) for name in fit_names]
        start = np.array([start_parameters[name] for name in fit_names], dtype=float)
        top_depth = float(self._geometry(bundle)["top_thickness_mm"])
        observations = (
            bundle.observations.groupby(["days_since_application", "depth_mm"], as_index=False)
            .agg(relative_concentration=("relative_concentration", "mean"))
            .sort_values(["days_since_application", "depth_mm"])
        )

        def unpack(values: np.ndarray) -> dict[str, float]:
            params = dict(start_parameters)
            params.update({name: float(value) for name, value in zip(fit_names, values)})
            return params

        def objective(values: np.ndarray) -> float:
            simulated = self.simulate(bundle, unpack(values), run_type="candidate").predictions
            lookup = simulated.set_index("days_since_application")
            predicted = np.where(
                observations["depth_mm"].to_numpy(dtype=float) == top_depth,
                lookup.loc[observations["days_since_application"], "top_rel_conc"].to_numpy(dtype=float),
                lookup.loc[observations["days_since_application"], "subsoil_rel_conc"].to_numpy(dtype=float),
            )
            residuals = np.log1p(observations["relative_concentration"].to_numpy(dtype=float)) - np.log1p(predicted)
            return float(np.sqrt(np.mean(np.square(residuals))))

        result = minimize(
            objective,
            np.clip(start, [low for low, _ in bounds], [high for _, high in bounds]),
            method="L-BFGS-B",
            bounds=bounds,
            options={"maxiter": self.maxiter, "maxfun": self.maxfun},
        )
        fitted = unpack(result.x)
        model_result = self.simulate(bundle, fitted, run_type="fitted")
        bound_hits = {name: False for name in start_parameters}
        for name, value, (low, high) in zip(fit_names, result.x, bounds):
            bound_hits[name] = bool(np.isclose(value, low) or np.isclose(value, high))
        return FitResult(
            parameters=fitted,
            objective_value=float(result.fun),
            success=bool(result.success),
            message=str(result.message),
            result=model_result,
            bound_hits=bound_hits,
        )

# Script: calibration.R
# Objective: Fit the two-layer CLTF model to replicate-level log concentrations.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-25
# Inputs: Prepared observations, cumulative infiltration, soil properties, and bounds.
# Outputs: Multistart parameter fits, predictions, bound flags, and objective profiles.
# Usage: Use fit_cltf() and profile_cltf_parameter() after library(cltf).
# Dependencies: stats

cltf_parameter_names <- function() {
  c("mu", "sigma", "R_top", "R_bottom", "k")
}

normalize_cltf_parameters <- function(parameters, argument = "parameters") {
  required <- cltf_parameter_names()
  if (!is.numeric(parameters) || length(parameters) != length(required)) {
    stop(argument, " must contain five numeric values.", call. = FALSE)
  }
  if (is.null(names(parameters))) {
    names(parameters) <- required
  }
  if (!all(required %in% names(parameters))) {
    stop(
      argument,
      " must contain named values: ",
      paste(required, collapse = ", "),
      ".",
      call. = FALSE
    )
  }
  parameters <- parameters[required]
  if (any(!is.finite(parameters))) {
    stop(argument, " must be finite.", call. = FALSE)
  }
  parameters
}

validate_calibration_data <- function(observations, forcing) {
  observation_columns <- c(
    "days_since_application",
    "depth_top_mm",
    "depth_bottom_mm",
    "analysis_concentration_ug_kg"
  )
  forcing_columns <- c(
    "time_days",
    "cumulative_infiltration_mm"
  )
  missing_observations <- setdiff(observation_columns, names(observations))
  missing_forcing <- setdiff(forcing_columns, names(forcing))
  if (length(missing_observations) > 0L) {
    stop(
      "observations are missing columns: ",
      paste(missing_observations, collapse = ", "),
      call. = FALSE
    )
  }
  if (length(missing_forcing) > 0L) {
    stop(
      "forcing is missing columns: ",
      paste(missing_forcing, collapse = ", "),
      call. = FALSE
    )
  }
  if (anyDuplicated(forcing$time_days)) {
    stop("forcing time_days values must be unique.", call. = FALSE)
  }
  invisible(TRUE)
}

cltf_predict_concentrations <- function(
  parameters,
  observations,
  forcing,
  application_rate_g_ha,
  top_bulk_density_g_cm3,
  bottom_bulk_density_g_cm3,
  top_thickness_mm    = 100,
  bottom_thickness_mm = 200,
  effective_porosity  = 0.2,
  method              = c("adaptive", "trapezoid"),
  n_steps             = 1001L,
  rel_tol             = 1e-8
) {
  validate_calibration_data(observations, forcing)
  parameters <- normalize_cltf_parameters(parameters)
  method <- match.arg(method)

  observation_times <- sort(unique(observations$days_since_application))
  forcing_index <- match(observation_times, forcing$time_days)
  if (anyNA(forcing_index)) {
    stop(
      "Every observation time must occur in forcing$time_days.",
      call. = FALSE
    )
  }
  simulation_forcing <- forcing[forcing_index, , drop = FALSE]

  simulation <- simulate_cltf(
    time_days                   = simulation_forcing$time_days,
    cumulative_infiltration_mm = simulation_forcing$cumulative_infiltration_mm,
    top_layer                  = cltf_layer(
      parameters["mu"],
      parameters["sigma"],
      parameters["R_top"],
      top_thickness_mm
    ),
    bottom_layer               = cltf_layer(
      parameters["mu"],
      parameters["sigma"],
      parameters["R_bottom"],
      bottom_thickness_mm
    ),
    decay_rate_day             = parameters["k"],
    application_rate_g_ha      = application_rate_g_ha,
    top_bulk_density_g_cm3     = top_bulk_density_g_cm3,
    bottom_bulk_density_g_cm3  = bottom_bulk_density_g_cm3,
    effective_porosity         = effective_porosity,
    method                      = method,
    n_steps                     = n_steps,
    rel_tol                     = rel_tol
  )
  time_index <- match(
    observations$days_since_application,
    simulation$time_days
  )

  tolerance <- sqrt(.Machine$double.eps)
  is_top <- abs(observations$depth_top_mm) <= tolerance &
    abs(observations$depth_bottom_mm - top_thickness_mm) <= tolerance
  is_bottom <- abs(observations$depth_top_mm - top_thickness_mm) <= tolerance &
    abs(
      observations$depth_bottom_mm -
        top_thickness_mm -
        bottom_thickness_mm
    ) <= tolerance
  if (any(!is_top & !is_bottom)) {
    stop(
      "Observation intervals must match the configured top or bottom model layer.",
      call. = FALSE
    )
  }

  prediction <- numeric(nrow(observations))
  prediction[is_top] <- simulation$concentration_top_ug_kg[
    time_index[is_top]
  ]
  prediction[is_bottom] <- simulation$concentration_bottom_ug_kg[
    time_index[is_bottom]
  ]
  prediction
}

#' Calculate the replicate-level CLTF calibration objective
#'
#' @param parameters Named `mu`, `sigma`, `R_top`, `R_bottom`, and `k` values.
#' @param observations Prepared observations containing analysis concentrations,
#'   elapsed days, and explicit depth intervals.
#' @param forcing Data frame containing `time_days` and cumulative infiltration.
#' @param application_rate_g_ha Applied herbicide mass in grams per hectare.
#' @param top_bulk_density_g_cm3,bottom_bulk_density_g_cm3 Layer bulk densities.
#' @param top_thickness_mm,bottom_thickness_mm Model layer thicknesses.
#' @param effective_porosity Empirical concentration scale.
#' @param method,n_steps,rel_tol Convolution settings passed to [simulate_cltf()].
#' @param penalty Finite objective returned for invalid model predictions.
#' @return Root mean squared log-concentration residual.
#' @export
cltf_objective <- function(
  parameters,
  observations,
  forcing,
  application_rate_g_ha,
  top_bulk_density_g_cm3,
  bottom_bulk_density_g_cm3,
  top_thickness_mm    = 100,
  bottom_thickness_mm = 200,
  effective_porosity  = 0.2,
  method              = c("adaptive", "trapezoid"),
  n_steps             = 1001L,
  rel_tol             = 1e-8,
  penalty             = 1e6
) {
  method <- match.arg(method)
  result <- tryCatch(
    {
      prediction <- cltf_predict_concentrations(
        parameters,
        observations,
        forcing,
        application_rate_g_ha,
        top_bulk_density_g_cm3,
        bottom_bulk_density_g_cm3,
        top_thickness_mm,
        bottom_thickness_mm,
        effective_porosity,
        method,
        n_steps,
        rel_tol
      )
      observed <- observations$analysis_concentration_ug_kg
      keep <- is.finite(observed) & observed > 0
      if (!any(keep) ||
          any(!is.finite(prediction[keep])) ||
          any(prediction[keep] <= 0)) {
        return(penalty)
      }
      sqrt(mean((log(observed[keep]) - log(prediction[keep]))^2))
    },
    error = function(...) penalty
  )
  if (!is.finite(result)) penalty else min(result, penalty)
}

generate_cltf_starts <- function(initial, lower, upper, n_starts, seed) {
  if (
    length(n_starts) != 1L ||
      !is.finite(n_starts) ||
      n_starts < 1 ||
      n_starts != as.integer(n_starts)
  ) {
    stop("n_starts must be a positive integer.", call. = FALSE)
  }
  n_starts <- as.integer(n_starts)
  starts <- matrix(
    NA_real_,
    nrow     = n_starts,
    ncol     = length(lower),
    dimnames = list(NULL, names(lower))
  )
  starts[1, ] <- initial
  if (n_starts == 1L) {
    return(starts)
  }

  had_seed <- exists(".Random.seed", envir = .GlobalEnv, inherits = FALSE)
  if (had_seed) {
    previous_seed <- get(".Random.seed", envir = .GlobalEnv, inherits = FALSE)
  }
  on.exit({
    if (had_seed) {
      assign(".Random.seed", previous_seed, envir = .GlobalEnv)
    } else if (exists(".Random.seed", envir = .GlobalEnv, inherits = FALSE)) {
      rm(".Random.seed", envir = .GlobalEnv)
    }
  }, add = TRUE)
  set.seed(seed)
  random <- matrix(
    stats::runif((n_starts - 1L) * length(lower)),
    nrow = n_starts - 1L
  )
  starts[-1, ] <- sweep(
    sweep(random, 2L, upper - lower, "*"),
    2L,
    lower,
    "+"
  )
  starts
}

cltf_fit_predictions <- function(fit_parameters, context) {
  prediction <- do.call(
    cltf_predict_concentrations,
    c(list(parameters = fit_parameters), context)
  )
  result <- context$observations
  result$predicted_concentration_ug_kg <- prediction
  observed <- result$analysis_concentration_ug_kg
  result$log_residual <- ifelse(
    is.finite(observed) &
      observed > 0 &
      is.finite(prediction) &
      prediction > 0,
    log(observed) - log(prediction),
    NA_real_
  )
  result
}

cltf_bound_hits <- function(parameters, lower, upper, tolerance) {
  scale <- pmax(1, abs(lower), abs(upper), abs(upper - lower))
  near_lower <- abs(parameters - lower) <= tolerance * scale
  near_upper <- abs(parameters - upper) <= tolerance * scale
  stats::setNames(near_lower | near_upper, names(parameters))
}

#' Fit the CLTF model with deterministic multistart optimization
#'
#' @inheritParams cltf_objective
#' @param lower,upper Named parameter bounds.
#' @param initial Optional first optimization start.
#' @param starts Optional matrix of explicit starts, one per row.
#' @param n_starts Number of starts generated when `starts` is absent.
#' @param seed Random seed for generated starts.
#' @param bound_tolerance Relative tolerance for reporting bound hits.
#' @param control Control list passed to [stats::optim()].
#' @return An `cltf_fit` list containing the best fit and all start results.
#' @export
fit_cltf <- function(
  observations,
  forcing,
  application_rate_g_ha,
  top_bulk_density_g_cm3,
  bottom_bulk_density_g_cm3,
  lower = c(
    mu       = 0.05,
    sigma    = 0.05,
    R_top    = 0.1,
    R_bottom = 0.1,
    k        = 0
  ),
  upper = c(
    mu       = 10,
    sigma    = 3,
    R_top    = 100,
    R_bottom = 100,
    k        = 0.1
  ),
  initial = c(
    mu       = 1,
    sigma    = 0.5,
    R_top    = 2,
    R_bottom = 3,
    k        = 0.005
  ),
  starts              = NULL,
  n_starts            = 6L,
  seed                = 42,
  top_thickness_mm    = 100,
  bottom_thickness_mm = 200,
  effective_porosity  = 0.2,
  method              = c("adaptive", "trapezoid"),
  n_steps             = 1001L,
  rel_tol             = 1e-8,
  penalty             = 1e6,
  bound_tolerance     = 1e-6,
  control             = list(maxit = 500)
) {
  method <- match.arg(method)
  validate_calibration_data(observations, forcing)
  lower <- normalize_cltf_parameters(lower, "lower")
  upper <- normalize_cltf_parameters(upper, "upper")
  initial <- normalize_cltf_parameters(initial, "initial")
  if (any(lower >= upper)) {
    stop("Every lower parameter bound must be below its upper bound.", call. = FALSE)
  }
  if (any(initial < lower) || any(initial > upper)) {
    stop("initial parameters must lie within bounds.", call. = FALSE)
  }

  if (is.null(starts)) {
    starts <- generate_cltf_starts(
      initial,
      lower,
      upper,
      n_starts,
      seed
    )
  } else {
    starts <- as.matrix(starts)
    if (ncol(starts) != length(lower)) {
      stop("starts must contain five parameter columns.", call. = FALSE)
    }
    if (is.null(colnames(starts))) {
      colnames(starts) <- names(lower)
    }
    starts <- starts[, names(lower), drop = FALSE]
    if (
      any(!is.finite(starts)) ||
        any(sweep(starts, 2L, lower, "<")) ||
        any(sweep(starts, 2L, upper, ">"))
    ) {
      stop("All starts must be finite and lie within bounds.", call. = FALSE)
    }
  }

  context <- list(
    observations               = observations,
    forcing                    = forcing,
    application_rate_g_ha      = application_rate_g_ha,
    top_bulk_density_g_cm3     = top_bulk_density_g_cm3,
    bottom_bulk_density_g_cm3  = bottom_bulk_density_g_cm3,
    top_thickness_mm           = top_thickness_mm,
    bottom_thickness_mm        = bottom_thickness_mm,
    effective_porosity         = effective_porosity,
    method                     = method,
    n_steps                    = n_steps,
    rel_tol                    = rel_tol
  )
  objective <- function(parameters) {
    do.call(
      cltf_objective,
      c(
        list(parameters = parameters),
        context,
        list(penalty = penalty)
      )
    )
  }

  results <- lapply(seq_len(nrow(starts)), function(index) {
    tryCatch(
      stats::optim(
        par     = starts[index, ],
        fn      = objective,
        method  = "L-BFGS-B",
        lower   = lower,
        upper   = upper,
        control = control
      ),
      error = function(error) {
        list(
          par         = starts[index, ],
          value       = penalty,
          convergence = 100L,
          message     = conditionMessage(error)
        )
      }
    )
  })
  objectives <- vapply(results, function(result) result$value, numeric(1))
  best_index <- which.min(objectives)
  best <- results[[best_index]]
  parameters <- normalize_cltf_parameters(best$par)

  start_rows <- lapply(seq_along(results), function(index) {
    result <- results[[index]]
    row <- data.frame(
      start_index = index,
      objective   = result$value,
      convergence = result$convergence,
      message     = if (is.null(result$message)) "" else result$message,
      stringsAsFactors = FALSE
    )
    for (parameter in names(lower)) {
      row[[paste0("start_", parameter)]] <- starts[index, parameter]
      row[[paste0("fitted_", parameter)]] <- result$par[parameter]
    }
    row
  })

  fit <- list(
    parameters  = parameters,
    objective   = best$value,
    convergence = best$convergence,
    message     = if (is.null(best$message)) "" else best$message,
    start_index = best_index,
    bound_hit   = cltf_bound_hits(
      parameters,
      lower,
      upper,
      bound_tolerance
    ),
    predictions = cltf_fit_predictions(parameters, context),
    all_starts  = do.call(rbind, start_rows),
    lower       = lower,
    upper       = upper,
    starts      = starts,
    context     = context,
    penalty     = penalty,
    control     = control,
    transport_scales = c(
      top = unname(parameters["mu"] * parameters["R_top"]),
      bottom = unname(parameters["mu"] * parameters["R_bottom"])
    ),
    identifiability_note = paste(
      "The current CLTF equations identify the products mu * R_top and",
      "mu * R_bottom, not mu and both retardation factors separately."
    )
  )
  class(fit) <- "cltf_fit"
  fit
}

#' Profile one fitted CLTF parameter
#'
#' @param fit Result returned by [fit_cltf()].
#' @param parameter Name of the parameter to hold fixed.
#' @param grid Finite profile values within the fitted bounds.
#' @param control Control list passed to [stats::optim()].
#' @return Data frame of fixed values, re-optimized parameters, and objectives.
#' @export
profile_cltf_parameter <- function(
  fit,
  parameter,
  grid,
  control = fit$control
) {
  if (!inherits(fit, "cltf_fit")) {
    stop("fit must be returned by fit_cltf().", call. = FALSE)
  }
  if (length(parameter) != 1L || !parameter %in% names(fit$parameters)) {
    stop("parameter must name one fitted CLTF parameter.", call. = FALSE)
  }
  if (
    !is.numeric(grid) ||
      length(grid) == 0L ||
      any(!is.finite(grid)) ||
      any(grid < fit$lower[parameter]) ||
      any(grid > fit$upper[parameter])
  ) {
    stop("grid must contain finite values within the parameter bounds.", call. = FALSE)
  }

  remaining <- setdiff(names(fit$parameters), parameter)
  rows <- lapply(seq_along(grid), function(index) {
    fixed_value <- grid[index]
    objective <- function(free_parameters) {
      parameters <- fit$parameters
      parameters[parameter] <- fixed_value
      parameters[remaining] <- free_parameters
      do.call(
        cltf_objective,
        c(
          list(parameters = parameters),
          fit$context,
          list(penalty = fit$penalty)
        )
      )
    }
    result <- tryCatch(
      stats::optim(
        par     = fit$parameters[remaining],
        fn      = objective,
        method  = "L-BFGS-B",
        lower   = fit$lower[remaining],
        upper   = fit$upper[remaining],
        control = control
      ),
      error = function(error) {
        list(
          par         = fit$parameters[remaining],
          value       = fit$penalty,
          convergence = 100L,
          message     = conditionMessage(error)
        )
      }
    )
    parameters <- fit$parameters
    parameters[parameter] <- fixed_value
    parameters[remaining] <- result$par
    row <- data.frame(
      parameter       = parameter,
      parameter_value = fixed_value,
      objective       = result$value,
      convergence     = result$convergence,
      message         = if (is.null(result$message)) "" else result$message,
      stringsAsFactors = FALSE
    )
    for (name in names(parameters)) {
      row[[name]] <- parameters[name]
    }
    row
  })
  do.call(rbind, rows)
}

profile_parameter_names <- function() {
  c("mu", "sigma", "R", "k")
}

normalize_profile_parameters <- function(parameters, argument = "parameters") {
  required <- profile_parameter_names()
  if (!is.numeric(parameters) || length(parameters) != length(required)) {
    stop(argument, " must contain four numeric values.", call. = FALSE)
  }
  if (is.null(names(parameters))) {
    names(parameters) <- required
  }
  if (!all(required %in% names(parameters))) {
    stop(
      argument,
      " must contain named values: ",
      paste(required, collapse = ", "),
      ".",
      call. = FALSE
    )
  }
  parameters <- parameters[required]
  if (any(!is.finite(parameters))) {
    stop(argument, " must be finite.", call. = FALSE)
  }
  parameters
}

profile_interval_density <- function(intervals, bulk_density) {
  if ("bulk_density_g_cm3" %in% names(intervals)) {
    return(as.numeric(intervals$bulk_density_g_cm3))
  }
  if ("bulk_density_g_cm3" %in% names(bulk_density)) {
    keys <- paste(intervals$depth_top_mm, intervals$depth_bottom_mm, sep = "|")
    density_keys <- paste(
      bulk_density$depth_top_mm,
      bulk_density$depth_bottom_mm,
      sep = "|"
    )
    matched <- match(keys, density_keys)
    if (!anyNA(matched)) {
      return(as.numeric(bulk_density$bulk_density_g_cm3[matched]))
    }
  }
  vapply(
    seq_len(nrow(intervals)),
    function(index) {
      weight_bulk_density(
        bulk_density,
        intervals$depth_top_mm[index],
        intervals$depth_bottom_mm[index]
      )$estimate_g_cm3
    },
    numeric(1)
  )
}

profile_predict_concentrations <- function(
  parameters,
  observations,
  forcing,
  application_rate_g_ha,
  bulk_density,
  effective_porosity = 0.2
) {
  validate_calibration_data(observations, forcing)
  parameters <- normalize_profile_parameters(parameters)
  observation_times <- sort(unique(observations$days_since_application))
  forcing_index <- match(observation_times, forcing$time_days)
  if (anyNA(forcing_index)) {
    stop(
      "Every observation time must occur in forcing$time_days.",
      call. = FALSE
    )
  }
  simulation_forcing <- forcing[forcing_index, , drop = FALSE]
  intervals <- unique(observations[c("depth_top_mm", "depth_bottom_mm")])
  intervals <- intervals[order(intervals$depth_top_mm, intervals$depth_bottom_mm), ]
  densities <- profile_interval_density(intervals, bulk_density)
  simulation <- simulate_cltf_intervals(
    time_days                   = simulation_forcing$time_days,
    cumulative_infiltration_mm = simulation_forcing$cumulative_infiltration_mm,
    intervals                  = intervals,
    mu                         = parameters["mu"],
    sigma                      = parameters["sigma"],
    retardation                = parameters["R"],
    decay_rate_day             = parameters["k"],
    application_rate_g_ha      = application_rate_g_ha,
    bulk_density_g_cm3         = densities,
    effective_porosity         = effective_porosity
  )
  keys <- paste(
    simulation$time_days,
    simulation$depth_top_mm,
    simulation$depth_bottom_mm,
    sep = "|"
  )
  values <- stats::setNames(simulation$concentration_ug_kg, keys)
  observation_keys <- paste(
    observations$days_since_application,
    observations$depth_top_mm,
    observations$depth_bottom_mm,
    sep = "|"
  )
  as.numeric(values[observation_keys])
}

#' Calculate the continuous one-layer CLTF profile objective
#'
#' @param parameters Named `mu`, `sigma`, `R`, and `k` values.
#' @inheritParams cltf_objective
#' @param bulk_density Data frame of interval or SLGA bulk-density bands.
#' @return Root mean squared log-concentration residual.
#' @export
cltf_profile_objective <- function(
  parameters,
  observations,
  forcing,
  application_rate_g_ha,
  bulk_density,
  effective_porosity = 0.2,
  penalty = 1e6
) {
  result <- tryCatch({
    prediction <- profile_predict_concentrations(
      parameters,
      observations,
      forcing,
      application_rate_g_ha,
      bulk_density,
      effective_porosity
    )
    observed <- observations$analysis_concentration_ug_kg
    keep <- is.finite(observed) & observed > 0
    if (!any(keep) ||
        any(!is.finite(prediction[keep])) ||
        any(prediction[keep] <= 0)) {
      return(penalty)
    }
    sqrt(mean((log(observed[keep]) - log(prediction[keep]))^2))
  }, error = function(error) penalty)
  if (is.finite(result)) {
    min(result, penalty)
  } else {
    penalty
  }
}

generate_profile_starts <- function(initial, lower, upper, n_starts, seed) {
  if (length(n_starts) != 1L || n_starts < 1L) {
    stop("n_starts must be a positive integer.", call. = FALSE)
  }
  starts <- matrix(NA_real_, nrow = n_starts, ncol = length(initial))
  colnames(starts) <- names(initial)
  starts[1, ] <- initial
  if (n_starts > 1L) {
    set.seed(seed)
    for (index in 2:n_starts) {
      starts[index, ] <- stats::runif(length(initial), lower, upper)
    }
  }
  starts
}

profile_bound_hits <- function(parameters, lower, upper, tolerance) {
  result <- logical(length(parameters))
  names(result) <- names(parameters)
  for (name in names(parameters)) {
    scale <- max(1, abs(lower[name]), abs(upper[name]), abs(upper[name] - lower[name]))
    result[name] <- abs(parameters[name] - lower[name]) <= tolerance * scale ||
      abs(parameters[name] - upper[name]) <= tolerance * scale
  }
  result
}

#' Fit the continuous one-layer CLTF profile model
#'
#' @inheritParams cltf_profile_objective
#' @param lower,upper,initial Parameter bounds and first start.
#' @param starts Optional matrix/data frame of starts.
#' @param n_starts Number of deterministic starts when `starts` is absent.
#' @param seed Random seed for generated starts.
#' @param bound_tolerance Tolerance for bound-hit flags.
#' @param control Control list passed to [stats::optim()].
#' @return A `cltf_fit` list.
#' @export
fit_cltf_profile <- function(
  observations,
  forcing,
  application_rate_g_ha,
  bulk_density,
  lower              = c(mu = 0.05, sigma = 0.05, R = 0.1, k = 0),
  upper              = c(mu = 10, sigma = 3, R = 100, k = 0.1),
  initial            = c(mu = 1, sigma = 0.5, R = 2, k = 0.005),
  starts             = NULL,
  n_starts           = 6L,
  seed               = 42L,
  effective_porosity = 0.2,
  penalty            = 1e6,
  bound_tolerance    = 1e-6,
  control            = list(maxit = 500)
) {
  validate_calibration_data(observations, forcing)
  lower <- normalize_profile_parameters(lower, "lower")
  upper <- normalize_profile_parameters(upper, "upper")
  initial <- normalize_profile_parameters(initial, "initial")
  if (any(lower >= upper)) {
    stop("Every lower parameter bound must be below its upper bound.", call. = FALSE)
  }
  if (any(initial < lower) || any(initial > upper)) {
    stop("initial parameters must lie within bounds.", call. = FALSE)
  }
  if (is.null(starts)) {
    start_values <- generate_profile_starts(initial, lower, upper, n_starts, seed)
  } else {
    start_values <- as.matrix(starts[, profile_parameter_names()])
  }
  if (any(!is.finite(start_values)) ||
      any(sweep(start_values, 2, lower, `<`)) ||
      any(sweep(start_values, 2, upper, `>`))) {
    stop("All starts must be finite and lie within bounds.", call. = FALSE)
  }
  context <- list(
    observations          = observations,
    forcing               = forcing,
    application_rate_g_ha = application_rate_g_ha,
    bulk_density          = bulk_density,
    effective_porosity    = effective_porosity
  )
  objective <- function(parameters) {
    do.call(
      cltf_profile_objective,
      c(list(parameters = parameters), context, list(penalty = penalty))
    )
  }
  results <- lapply(seq_len(nrow(start_values)), function(index) {
    start <- start_values[index, ]
    tryCatch(
      stats::optim(
        par     = start,
        fn      = objective,
        method  = "L-BFGS-B",
        lower   = lower,
        upper   = upper,
        control = control
      ),
      error = function(error) {
        list(
          par         = start,
          value       = penalty,
          convergence = 100L,
          message     = conditionMessage(error)
        )
      }
    )
  })
  objectives <- vapply(results, `[[`, numeric(1), "value")
  best_index <- which.min(objectives)
  best <- results[[best_index]]
  parameters <- normalize_profile_parameters(best$par)
  prediction <- do.call(
    profile_predict_concentrations,
    c(list(parameters = parameters), context)
  )
  predictions <- observations
  predictions$predicted_concentration_ug_kg <- prediction
  observed <- predictions$analysis_concentration_ug_kg
  keep <- is.finite(observed) & observed > 0 &
    is.finite(prediction) & prediction > 0
  predictions$log_residual <- NA_real_
  predictions$log_residual[keep] <- log(observed[keep]) - log(prediction[keep])

  all_starts <- do.call(rbind, lapply(seq_along(results), function(index) {
    result <- results[[index]]
    row <- data.frame(
      start_index = index,
      objective   = result$value,
      convergence = result$convergence,
      message     = if (is.null(result$message)) "" else result$message
    )
    for (name in profile_parameter_names()) {
      row[[paste0("start_", name)]] <- start_values[index, name]
      row[[paste0("fitted_", name)]] <- result$par[name]
    }
    row
  }))

  fit <- list(
    parameters          = parameters,
    objective           = best$value,
    convergence         = best$convergence,
    message             = if (is.null(best$message)) "" else best$message,
    start_index         = best_index,
    bound_hit           = profile_bound_hits(
      parameters,
      lower,
      upper,
      bound_tolerance
    ),
    predictions         = predictions,
    all_starts          = all_starts,
    lower               = lower,
    upper               = upper,
    starts              = start_values,
    transport_scales    = c(profile = parameters["mu"] * parameters["R"]),
    identifiability_note = paste(
      "The continuous one-layer CLTF equations identify the product mu * R;",
      "report both parameters with caution."
    ),
    context             = context,
    penalty             = penalty,
    control             = control
  )
  class(fit) <- "cltf_fit"
  fit
}

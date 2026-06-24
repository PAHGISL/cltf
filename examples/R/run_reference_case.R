#!/usr/bin/env Rscript
# Script: run_reference_case.R
# Objective: Build reproducible shared CLTF reference cases from normalized inputs.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Shared case JSON, observations, SILO forcing, and SLGA bulk density.
# Outputs: Prepared CSV/JSON artifacts and seven diagnostic PNG plots.
# Usage: Rscript examples/R/run_reference_case.R --case CASE --input-dir DIR --output-dir DIR
# Dependencies: R >= 4.2, jsonlite, and the source files under R/R.

script_path <- function() {
  argument <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(argument) != 1L) {
    stop("Could not determine the reference-runner path.", call. = FALSE)
  }
  normalizePath(sub("^--file=", "", argument), mustWork = TRUE)
}

package_dir <- normalizePath(
  file.path(dirname(script_path()), "..", "..", "R"),
  mustWork = TRUE
)
repository_dir <- normalizePath(file.path(package_dir, ".."), mustWork = TRUE)
r_sources <- sort(list.files(
  file.path(package_dir, "R"),
  pattern    = "\\.R$",
  full.names = TRUE
))
invisible(lapply(r_sources, source, local = .GlobalEnv))

allowed_cases <- c(
  "nsw_griffith_heavy_imazapic",
  "sa_minnipa_heavy_imazapic"
)

usage <- function() {
  paste(
    "Usage: Rscript examples/R/run_reference_case.R",
    "--case nsw_griffith_heavy_imazapic|sa_minnipa_heavy_imazapic",
    "[--input-dir DIR] [--output-dir DIR]\n"
  )
}

parse_arguments <- function(arguments) {
  defaults <- list(
    case       = "",
    input_dir  = "",
    output_dir = ""
  )
  option_names <- c(
    "--case"       = "case",
    "--input-dir"  = "input_dir",
    "--output-dir" = "output_dir"
  )
  index <- 1L
  while (index <= length(arguments)) {
    option <- arguments[index]
    if (option == "--help") {
      cat(usage())
      quit(save = "no", status = 0)
    }
    if (!option %in% names(option_names) || index == length(arguments)) {
      stop("Unknown or incomplete command-line option: ", option, call. = FALSE)
    }
    defaults[[option_names[[option]]]] <- arguments[index + 1L]
    index <- index + 2L
  }
  if (!defaults$case %in% allowed_cases) {
    stop(
      "--case must be one of: ",
      paste(allowed_cases, collapse = ", "),
      call. = FALSE
    )
  }
  if (!nzchar(defaults$input_dir)) {
    defaults$input_dir <- file.path(
      repository_dir,
      "examples",
      "data",
      defaults$case
    )
  }
  if (!nzchar(defaults$output_dir)) {
    defaults$output_dir <- file.path(repository_dir, "reference", defaults$case)
  }
  defaults
}

write_csv <- function(data, path) {
  utils::write.csv(
    data,
    path,
    row.names = FALSE,
    na        = ""
  )
}

write_png <- function(path, draw, width = 1200, height = 800) {
  grDevices::png(
    filename = path,
    width    = width,
    height   = height,
    res      = 140
  )
  device <- grDevices::dev.cur()
  on.exit({
    if (device %in% grDevices::dev.list()) {
      grDevices::dev.off(device)
    }
  }, add = TRUE)
  draw()
  invisible(grDevices::dev.off(device))
}

require_file <- function(path) {
  if (!file.exists(path)) {
    stop("Required input file does not exist: ", path, call. = FALSE)
  }
  path
}

repository_label <- function(path) {
  normalized <- normalizePath(path, mustWork = TRUE)
  prefix <- paste0(repository_dir, .Platform$file.sep)
  if (startsWith(normalized, prefix)) {
    substring(normalized, nchar(prefix) + 1L)
  } else {
    normalized
  }
}

read_site_registry <- function(site_id) {
  sites <- jsonlite::fromJSON(file.path(
    repository_dir,
    "examples",
    "data",
    "sites.json"
  ))
  selected <- sites$site_id == site_id
  if (sum(selected) != 1L) {
    stop("Shared site registry does not define one row for: ", site_id, call. = FALSE)
  }
  sites[selected, ]
}

read_inputs <- function(input_dir) {
  paths <- list(
    case          = require_file(file.path(input_dir, "case.json")),
    observations  = require_file(file.path(input_dir, "observations.csv")),
    silo          = require_file(file.path(input_dir, "silo.csv")),
    silo_metadata = require_file(file.path(input_dir, "silo_metadata.json")),
    bulk_density  = require_file(file.path(input_dir, "bulk_density.json"))
  )
  case <- jsonlite::fromJSON(paths$case)
  observations <- utils::read.csv(
    paths$observations,
    stringsAsFactors = FALSE
  )
  observations$sample_date <- as.Date(observations$sample_date)
  observations$application_date <- as.Date(observations$application_date)
  logical_columns <- c(
    "is_t0",
    "is_non_detect",
    "is_zero_reported",
    "lod_substituted",
    "excluded_zero",
    "used_for_calibration"
  )
  for (column in intersect(logical_columns, names(observations))) {
    observations[[column]] <- as.logical(observations[[column]])
  }
  climate <- parse_silo_csv(paths$silo)
  silo_metadata <- jsonlite::fromJSON(paths$silo_metadata)
  bulk_density <- parse_slga_bulk_density(paths$bulk_density)
  attr(bulk_density, "cache_path") <- paths$bulk_density

  list(
    paths         = paths,
    case          = case,
    observations  = observations,
    climate       = climate,
    silo_metadata = silo_metadata,
    bulk_density  = bulk_density
  )
}

build_parameter_table <- function(fit) {
  data.frame(
    parameter = names(fit$parameters),
    estimate  = as.numeric(fit$parameters),
    lower     = as.numeric(fit$lower),
    upper     = as.numeric(fit$upper),
    bound_hit = as.logical(fit$bound_hit),
    stringsAsFactors = FALSE
  )
}

build_profiles <- function(fit) {
  profiles <- lapply(names(fit$parameters), function(parameter) {
    span <- fit$upper[parameter] - fit$lower[parameter]
    lower <- max(
      fit$lower[parameter],
      fit$parameters[parameter] - 0.15 * span
    )
    upper <- min(
      fit$upper[parameter],
      fit$parameters[parameter] + 0.15 * span
    )
    grid <- unique(c(
      lower,
      (lower + fit$parameters[parameter]) / 2,
      fit$parameters[parameter],
      (fit$parameters[parameter] + upper) / 2,
      upper
    ))
    profile_cltf_parameter(
      fit,
      parameter = parameter,
      grid      = grid,
      control   = list(maxit = 35)
    )
  })
  do.call(rbind, profiles)
}

build_forcing <- function(climate, case, site) {
  application_date <- as.Date(case$application_date)
  final_date <- as.Date(case$final_date)
  selected <- climate$date >= application_date & climate$date <= final_date
  climate <- climate[selected, ]
  expected_days <- as.integer(final_date - application_date) + 1L
  if (nrow(climate) != expected_days) {
    stop("SILO forcing does not fully cover the configured case period.", call. = FALSE)
  }
  forcing <- data.frame(
    date          = climate$date,
    time_days     = as.integer(climate$date - application_date),
    jdays         = climate$jdays,
    rain_mm       = climate$rain_mm,
    Tmax          = climate$Tmax,
    Tmin          = climate$Tmin,
    pet_mm        = pet_from_temperature(
      climate$jdays,
      climate$Tmax,
      climate$Tmin,
      site$latitude
    ),
    irrigation_mm = rep(as.numeric(case$irrigation_mm), nrow(climate))
  )
  forcing$daily_infiltration_mm <- daily_infiltration(
    forcing$rain_mm,
    forcing$pet_mm,
    forcing$irrigation_mm,
    et_factor = as.numeric(case$et_factor)
  )
  forcing$cumulative_infiltration_mm <- cumsum(
    forcing$daily_infiltration_mm
  )
  forcing
}

run_case <- function(arguments) {
  input_dir <- normalizePath(arguments$input_dir, mustWork = TRUE)
  dir.create(arguments$output_dir, recursive = TRUE, showWarnings = FALSE)
  output_dir <- normalizePath(arguments$output_dir, mustWork = TRUE)
  inputs <- read_inputs(input_dir)
  case <- inputs$case
  if (!identical(arguments$case, basename(input_dir))) {
    warning(
      "--case does not match the input directory basename; using case.json values.",
      call. = FALSE
    )
  }
  site <- read_site_registry(case$site_id)
  observations <- inputs$observations
  selected <- observations$site_id == case$site_id &
    observations$soil_group == case$soil_group &
    observations$herbicide == case$herbicide
  observations <- observations[selected, ]
  if (nrow(observations) == 0L) {
    stop("No observations match the configured shared case.", call. = FALSE)
  }

  application_date <- as.Date(case$application_date)
  final_date <- as.Date(case$final_date)
  if (
    any(observations$sample_date < application_date) ||
      any(observations$sample_date > final_date)
  ) {
    stop("Observation dates fall outside the configured case period.", call. = FALSE)
  }

  top_thickness_mm <- as.numeric(case$top_depth_mm)
  bottom_thickness_mm <- as.numeric(case$bottom_depth_mm) - top_thickness_mm
  if (top_thickness_mm <= 0 || bottom_thickness_mm <= 0) {
    stop("Case depth configuration must define two positive layers.", call. = FALSE)
  }

  forcing <- build_forcing(inputs$climate, case, site)
  bulk_density <- inputs$bulk_density
  top_density <- weight_bulk_density(
    bulk_density,
    0,
    top_thickness_mm
  )$estimate_g_cm3
  bottom_density <- weight_bulk_density(
    bulk_density,
    top_thickness_mm,
    top_thickness_mm + bottom_thickness_mm
  )$estimate_g_cm3

  t0_top <- observations$is_t0 &
    observations$depth_top_mm == 0 &
    observations$depth_bottom_mm == top_thickness_mm &
    is.finite(observations$analysis_concentration_ug_kg) &
    observations$analysis_concentration_ug_kg > 0
  application_rate_g_ha <- infer_application_rate_g_ha(
    observations$analysis_concentration_ug_kg[t0_top],
    0,
    top_thickness_mm,
    top_density
  )

  calibration_observations <- observations[
    observations$used_for_calibration,
  ]
  lower <- c(
    mu       = 0.05,
    sigma    = 0.10,
    R_top    = 0.10,
    R_bottom = 0.10,
    k        = 0
  )
  upper <- c(
    mu       = 8,
    sigma    = 2.50,
    R_top    = 20,
    R_bottom = 30,
    k        = 0.05
  )
  fit <- fit_cltf(
    observations               = calibration_observations,
    forcing                    = forcing,
    application_rate_g_ha      = application_rate_g_ha,
    top_bulk_density_g_cm3     = top_density,
    bottom_bulk_density_g_cm3  = bottom_density,
    lower                      = lower,
    upper                      = upper,
    initial                    = c(
      mu       = 1,
      sigma    = 0.6,
      R_top    = 2,
      R_bottom = 3,
      k        = 0.005
    ),
    n_starts                   = 5,
    seed                       = 42,
    top_thickness_mm           = top_thickness_mm,
    bottom_thickness_mm        = bottom_thickness_mm,
    effective_porosity         = as.numeric(case$effective_porosity),
    method                     = case$convolution_method,
    n_steps                    = as.integer(case$convolution_steps),
    control                    = list(maxit = 250)
  )

  simulation <- simulate_cltf(
    time_days                   = forcing$time_days,
    cumulative_infiltration_mm = forcing$cumulative_infiltration_mm,
    top_layer                  = cltf_layer(
      fit$parameters["mu"],
      fit$parameters["sigma"],
      fit$parameters["R_top"],
      top_thickness_mm
    ),
    bottom_layer               = cltf_layer(
      fit$parameters["mu"],
      fit$parameters["sigma"],
      fit$parameters["R_bottom"],
      bottom_thickness_mm
    ),
    decay_rate_day             = fit$parameters["k"],
    application_rate_g_ha      = application_rate_g_ha,
    top_bulk_density_g_cm3     = top_density,
    bottom_bulk_density_g_cm3  = bottom_density,
    effective_porosity         = as.numeric(case$effective_porosity),
    method                     = case$convolution_method,
    n_steps                    = as.integer(case$convolution_steps)
  )
  predictions <- cbind(
    data.frame(date = forcing$date),
    simulation
  )
  parameter_table <- build_parameter_table(fit)
  fit_diagnostics <- fit$all_starts
  fit_diagnostics$selected <- fit_diagnostics$start_index == fit$start_index
  fit_diagnostics$start_transport_scale_top <- with(
    fit_diagnostics,
    start_mu * start_R_top
  )
  fit_diagnostics$start_transport_scale_bottom <- with(
    fit_diagnostics,
    start_mu * start_R_bottom
  )
  fit_diagnostics$fitted_transport_scale_top <- with(
    fit_diagnostics,
    fitted_mu * fitted_R_top
  )
  fit_diagnostics$fitted_transport_scale_bottom <- with(
    fit_diagnostics,
    fitted_mu * fitted_R_bottom
  )
  profiles <- build_profiles(fit)

  output_paths <- list(
    observations = file.path(output_dir, "observations_prepared.csv"),
    forcing      = file.path(output_dir, "climate_forcing.csv"),
    bulk_density = file.path(output_dir, "bulk_density.csv"),
    predictions  = file.path(output_dir, "predictions.csv"),
    parameters   = file.path(output_dir, "fit_parameters.csv"),
    diagnostics  = file.path(output_dir, "fit_diagnostics.csv"),
    profiles     = file.path(output_dir, "objective_profiles.csv"),
    metadata     = file.path(output_dir, "metadata.json")
  )
  write_csv(observations, output_paths$observations)
  write_csv(forcing, output_paths$forcing)
  write_csv(bulk_density, output_paths$bulk_density)
  write_csv(predictions, output_paths$predictions)
  write_csv(parameter_table, output_paths$parameters)
  write_csv(fit_diagnostics, output_paths$diagnostics)
  write_csv(profiles, output_paths$profiles)

  plot_paths <- list(
    bulk_density = file.path(output_dir, "plot_bulk_density.png"),
    climate      = file.path(output_dir, "plot_climate.png"),
    mass_balance = file.path(output_dir, "plot_mass_balance.png"),
    mass         = file.path(output_dir, "plot_mass_fractions.png"),
    observed     = file.path(output_dir, "plot_observed_fitted.png"),
    profiles     = file.path(output_dir, "plot_profiles.png"),
    residuals    = file.path(output_dir, "plot_residuals.png")
  )
  write_png(
    plot_paths$bulk_density,
    function() plot_bulk_density(bulk_density)
  )
  write_png(
    plot_paths$climate,
    function() plot_climate_forcing(forcing)
  )
  write_png(
    plot_paths$mass_balance,
    function() plot_mass_balance(simulation)
  )
  write_png(
    plot_paths$mass,
    function() plot_mass_fractions(simulation)
  )
  write_png(
    plot_paths$observed,
    function() plot_observed_fitted(fit$predictions)
  )
  write_png(
    plot_paths$profiles,
    function() plot_objective_profile(profiles),
    width  = 1400,
    height = 950
  )
  write_png(
    plot_paths$residuals,
    function() plot_residuals(fit$predictions)
  )

  description <- read.dcf(file.path(package_dir, "DESCRIPTION"))
  input_files <- unlist(inputs$paths)
  checksums <- as.list(as.character(tools::md5sum(input_files)))
  names(checksums) <- basename(input_files)
  metadata <- list(
    reference_case = paste(
      case$site_id,
      case$soil_group,
      case$herbicide,
      sep = " / "
    ),
    generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
    software = list(
      package_version = unname(description[1, "Version"]),
      r_version       = R.version.string
    ),
    source_input_dir = repository_label(input_dir),
    concentration = list(
      unit        = case$concentration_unit,
      unit_status = case$unit_status
    ),
    application_rate = list(
      value_g_ha = unname(application_rate_g_ha),
      source     = "inferred from the geometric mean of positive top-layer T0 replicates",
      t0_rows    = sum(t0_top)
    ),
    observations = list(
      total_rows               = nrow(observations),
      calibration_rows         = sum(observations$used_for_calibration),
      t0_rows_excluded         = sum(observations$is_t0),
      zero_rows_excluded       = sum(observations$excluded_zero),
      non_detect_substitutions = sum(observations$lod_substituted)
    ),
    silo = list(
      source             = inputs$silo_metadata$source,
      request_latitude   = inputs$silo_metadata$request_latitude,
      request_longitude  = inputs$silo_metadata$request_longitude,
      returned_latitude  = inputs$silo_metadata$grid_latitude,
      returned_longitude = inputs$silo_metadata$grid_longitude,
      cache_file         = basename(inputs$paths$silo)
    ),
    slga = list(
      product             = "SLGA Bulk Density (whole earth)",
      product_version     = "v2",
      latitude            = site$latitude,
      longitude           = site$longitude,
      cache_file          = basename(attr(bulk_density, "cache_path")),
      source_status       = unique(bulk_density$source),
      depth_bands_mm      = bulk_density[c("depth_top_mm", "depth_bottom_mm")],
      top_layer_g_cm3     = unname(top_density),
      bottom_layer_g_cm3  = unname(bottom_density)
    ),
    model = list(
      target_quantity     = "layer-average resident concentration",
      top_thickness_mm    = top_thickness_mm,
      bottom_thickness_mm = bottom_thickness_mm,
      effective_porosity  = as.numeric(case$effective_porosity),
      degradation_clock   = "total elapsed time",
      water_balance       = "max(rain + irrigation - PET, 0) accumulated daily",
      et_factor           = as.numeric(case$et_factor),
      irrigation_mm       = as.numeric(case$irrigation_mm),
      convolution_method  = case$convolution_method,
      convolution_steps   = as.integer(case$convolution_steps)
    ),
    calibration = list(
      objective             = "replicate-level root mean squared log residual",
      objective_value       = unname(fit$objective),
      convergence           = fit$convergence,
      message               = fit$message,
      selected_start        = fit$start_index,
      bounds                = parameter_table[c("parameter", "lower", "upper")],
      starts                = as.data.frame(fit$starts),
      bound_hits            = as.list(fit$bound_hit),
      transport_scales      = as.list(fit$transport_scales),
      identifiability_note  = fit$identifiability_note
    ),
    input_checksums = checksums
  )
  jsonlite::write_json(
    metadata,
    output_paths$metadata,
    pretty     = TRUE,
    auto_unbox = TRUE,
    dataframe  = "rows"
  )

  cat(
    "Wrote ",
    case$site_id,
    " ",
    case$soil_group,
    "/",
    case$herbicide,
    " reference outputs to ",
    output_dir,
    "\n",
    "Objective: ",
    format(fit$objective, digits = 8),
    "\n",
    sep = ""
  )
}

run_case(parse_arguments(commandArgs(trailingOnly = TRUE)))

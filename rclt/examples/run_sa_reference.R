#!/usr/bin/env Rscript
# Script: run_sa_reference.R
# Objective: Build the reproducible SA Minnipa Heavy/Imazapic RCLT reference case.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Herbicide workbook, cached or credentialed SILO/SLGA data, and CLI paths.
# Outputs: Prepared CSV/JSON artifacts and seven diagnostic PNG plots.
# Usage: Rscript rclt/examples/run_sa_reference.R --workbook <xlsx> --cache-dir <dir> --output-dir <dir>
# Dependencies: R >= 4.2, readxl, jsonlite, and the source files under rclt/R.

script_path <- function() {
  argument <- grep("^--file=", commandArgs(trailingOnly = FALSE), value = TRUE)
  if (length(argument) != 1L) {
    stop("Could not determine the reference-script path.", call. = FALSE)
  }
  normalizePath(sub("^--file=", "", argument), mustWork = TRUE)
}

package_dir <- normalizePath(
  file.path(dirname(script_path()), ".."),
  mustWork = TRUE
)
repo_dir <- normalizePath(file.path(package_dir, ".."), mustWork = TRUE)
r_sources <- sort(list.files(
  file.path(package_dir, "R"),
  pattern   = "\\.R$",
  full.names = TRUE
))
invisible(lapply(r_sources, source, local = .GlobalEnv))

parse_arguments <- function(arguments) {
  defaults <- list(
    workbook = "/g/data/ym05/herbicide/context/Herbicide Dissipation 2024.xlsx",
    cache_dir = file.path(package_dir, "reference", "cache"),
    output_dir = file.path(
      package_dir,
      "reference",
      "sa_minnipa_heavy_imazapic"
    ),
    climate_source = file.path(
      repo_dir,
      "apps",
      "herbicide_workbench",
      "sample_data",
      "daily_climate.csv"
    ),
    bulk_density_override = ""
  )
  option_names <- c(
    "--workbook"              = "workbook",
    "--cache-dir"             = "cache_dir",
    "--output-dir"            = "output_dir",
    "--climate-source"        = "climate_source",
    "--bulk-density-override" = "bulk_density_override"
  )
  index <- 1L
  while (index <= length(arguments)) {
    option <- arguments[index]
    if (option == "--help") {
      cat(
        paste(
          "Usage: Rscript rclt/examples/run_sa_reference.R",
          "[--workbook FILE] [--cache-dir DIR] [--output-dir DIR]",
          "[--climate-source CSV]",
          "[--bulk-density-override VALUE[,VALUE,VALUE]]\n"
        )
      )
      quit(save = "no", status = 0)
    }
    if (!option %in% names(option_names) || index == length(arguments)) {
      stop("Unknown or incomplete command-line option: ", option, call. = FALSE)
    }
    defaults[[option_names[[option]]]] <- arguments[index + 1L]
    index <- index + 2L
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

materialize_climate_cache <- function(
  climate_source,
  cache_dir,
  latitude,
  longitude,
  start_date,
  end_date
) {
  grid_latitude <- round_silo_coordinate(latitude)
  grid_longitude <- round_silo_coordinate(longitude)
  paths <- silo_cache_paths(
    cache_dir,
    grid_latitude,
    grid_longitude,
    start_date,
    end_date
  )
  if (!file.exists(paths$csv) || !file.exists(paths$metadata)) {
    if (file.exists(climate_source)) {
      source <- utils::read.csv(
        climate_source,
        stringsAsFactors = FALSE
      )
      require_plot_columns(
        source,
        c("site_id", "date", "rain_mm", "Tmax", "Tmin"),
        "climate_source"
      )
      source$date <- as.Date(source$date)
      selected <- source$site_id == "SA_Minnipa" &
        source$date >= start_date &
        source$date <= end_date
      source <- source[selected, ]
      if (nrow(source) != as.integer(end_date - start_date) + 1L) {
        stop(
          "The local SA climate source does not fully cover the reference period.",
          call. = FALSE
        )
      }
      raw <- data.frame(
        Date  = format(source$date, "%Y%m%d"),
        T.Max = source$Tmax,
        T.Min = source$Tmin,
        Rain  = source$rain_mm,
        check.names = FALSE
      )
      write_csv(raw, paths$csv)
      normalized_source <- normalizePath(climate_source, mustWork = TRUE)
      repo_prefix <- paste0(repo_dir, .Platform$file.sep)
      source_label <- if (startsWith(normalized_source, repo_prefix)) {
        substring(normalized_source, nchar(repo_prefix) + 1L)
      } else {
        normalized_source
      }
      metadata <- list(
        source = paste(
          "Existing PyCLT demo extraction from the SILO 2024 gridded archive;",
          "normalized to the SILO Data Drill cache schema"
        ),
        source_file        = source_label,
        request_latitude   = latitude,
        request_longitude  = longitude,
        grid_latitude      = grid_latitude,
        grid_longitude     = grid_longitude,
        start_date         = as.character(start_date),
        end_date           = as.character(end_date),
        materialized_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
        raw_cache_file     = basename(paths$csv)
      )
      jsonlite::write_json(
        metadata,
        paths$metadata,
        pretty     = TRUE,
        auto_unbox = TRUE
      )
    }
  }

  fetch_silo_point(
    latitude   = latitude,
    longitude  = longitude,
    start_date = start_date,
    end_date   = end_date,
    cache_dir  = cache_dir
  )
}

materialize_bulk_density <- function(
  cache_dir,
  latitude,
  longitude,
  override_text
) {
  cache_path <- slga_cache_path(cache_dir, latitude, longitude)
  if (file.exists(cache_path)) {
    result <- parse_slga_bulk_density(cache_path)
    attr(result, "cache_path") <- cache_path
    return(result)
  }

  if (nzchar(override_text)) {
    override <- as.numeric(strsplit(override_text, ",", fixed = TRUE)[[1]])
    result <- normalize_bulk_density_override(override)
    slga_write_cache(cache_path, latitude, longitude, result)
  } else if (nzchar(Sys.getenv("TERN_API_KEY"))) {
    return(fetch_slga_bulk_density(
      latitude  = latitude,
      longitude = longitude,
      cache_dir = cache_dir
    ))
  } else {
    fixture <- file.path(
      package_dir,
      "inst",
      "extdata",
      "slga_bulk_density_response.json"
    )
    result <- parse_slga_bulk_density(fixture)
    result$source <- "provisional SLGA v2-shaped offline fixture"
    slga_write_cache(cache_path, latitude, longitude, result)
  }
  result <- parse_slga_bulk_density(cache_path)
  attr(result, "cache_path") <- cache_path
  result
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
    profile_rclt_parameter(
      fit,
      parameter = parameter,
      grid      = grid,
      control   = list(maxit = 35)
    )
  })
  do.call(rbind, profiles)
}

arguments <- parse_arguments(commandArgs(trailingOnly = TRUE))
if (!file.exists(arguments$workbook)) {
  stop("Workbook does not exist: ", arguments$workbook, call. = FALSE)
}
dir.create(arguments$cache_dir, recursive = TRUE, showWarnings = FALSE)
dir.create(arguments$output_dir, recursive = TRUE, showWarnings = FALSE)

site <- list(
  id        = "SA_Minnipa",
  soil      = "Heavy",
  herbicide = "Imazapic",
  latitude  = -32.831016,
  longitude = 135.14494
)
top_thickness_mm <- 100
bottom_thickness_mm <- 200
effective_porosity <- 0.2
convolution_method <- "trapezoid"
convolution_steps <- 2001L

observations <- read_herbicide_workbook(
  arguments$workbook,
  sheets = "SA"
)
selected <- observations$site_id == site$id &
  observations$soil_group == site$soil &
  observations$herbicide == site$herbicide
observations <- observations[selected, ]
if (nrow(observations) == 0L) {
  stop("No SA Minnipa Heavy/Imazapic observations were found.", call. = FALSE)
}
observations$used_for_calibration <- !observations$is_t0 &
  is.finite(observations$analysis_concentration_ug_kg) &
  observations$analysis_concentration_ug_kg > 0

application_date <- min(observations$application_date)
end_date <- max(observations$sample_date)
climate <- materialize_climate_cache(
  arguments$climate_source,
  arguments$cache_dir,
  site$latitude,
  site$longitude,
  application_date,
  end_date
)
forcing <- data.frame(
  date                       = climate$date,
  time_days                  = as.integer(climate$date - application_date),
  jdays                      = climate$jdays,
  rain_mm                    = climate$rain_mm,
  Tmax                       = climate$Tmax,
  Tmin                       = climate$Tmin,
  pet_mm                     = pet_from_temperature(
    climate$jdays,
    climate$Tmax,
    climate$Tmin,
    site$latitude
  ),
  irrigation_mm              = 0
)
forcing$daily_infiltration_mm <- daily_infiltration(
  forcing$rain_mm,
  forcing$pet_mm,
  forcing$irrigation_mm,
  et_factor = 1
)
forcing$cumulative_infiltration_mm <- cumsum(
  forcing$daily_infiltration_mm
)

bulk_density <- materialize_bulk_density(
  arguments$cache_dir,
  site$latitude,
  site$longitude,
  arguments$bulk_density_override
)
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
fit <- fit_rclt(
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
  effective_porosity         = effective_porosity,
  method                     = convolution_method,
  n_steps                    = convolution_steps,
  control                    = list(maxit = 250)
)

simulation <- simulate_rclt(
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
  effective_porosity         = effective_porosity,
  method                     = convolution_method,
  n_steps                    = convolution_steps
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
  observations = file.path(arguments$output_dir, "observations_prepared.csv"),
  forcing      = file.path(arguments$output_dir, "climate_forcing.csv"),
  bulk_density = file.path(arguments$output_dir, "bulk_density.csv"),
  predictions  = file.path(arguments$output_dir, "predictions.csv"),
  parameters   = file.path(arguments$output_dir, "fit_parameters.csv"),
  diagnostics  = file.path(arguments$output_dir, "fit_diagnostics.csv"),
  profiles     = file.path(arguments$output_dir, "objective_profiles.csv"),
  metadata     = file.path(arguments$output_dir, "metadata.json")
)
write_csv(observations, output_paths$observations)
write_csv(forcing, output_paths$forcing)
write_csv(bulk_density, output_paths$bulk_density)
write_csv(predictions, output_paths$predictions)
write_csv(parameter_table, output_paths$parameters)
write_csv(fit_diagnostics, output_paths$diagnostics)
write_csv(profiles, output_paths$profiles)

plot_paths <- list(
  bulk_density = file.path(arguments$output_dir, "plot_bulk_density.png"),
  climate      = file.path(arguments$output_dir, "plot_climate.png"),
  mass_balance = file.path(arguments$output_dir, "plot_mass_balance.png"),
  mass         = file.path(arguments$output_dir, "plot_mass_fractions.png"),
  observed     = file.path(arguments$output_dir, "plot_observed_fitted.png"),
  profiles     = file.path(arguments$output_dir, "plot_profiles.png"),
  residuals    = file.path(arguments$output_dir, "plot_residuals.png")
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
input_files <- unlist(output_paths[c(
  "observations",
  "forcing",
  "bulk_density"
)])
checksums <- as.list(as.character(tools::md5sum(input_files)))
names(checksums) <- basename(input_files)
silo_metadata <- jsonlite::fromJSON(attr(climate, "metadata_path"))
metadata <- list(
  reference_case = paste(site$id, site$soil, site$herbicide, sep = " / "),
  generated_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
  software = list(
    package_version = unname(description[1, "Version"]),
    r_version       = R.version.string
  ),
  source_workbook = normalizePath(arguments$workbook, mustWork = TRUE),
  concentration = list(
    unit        = "ug/kg dry soil",
    unit_status = "provisional; inferred from the sampled-data structure"
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
    source             = silo_metadata$source,
    request_latitude   = site$latitude,
    request_longitude  = site$longitude,
    returned_latitude  = silo_metadata$grid_latitude,
    returned_longitude = silo_metadata$grid_longitude,
    cache_file         = basename(attr(climate, "cache_path"))
  ),
  slga = list(
    product          = "SLGA Bulk Density (whole earth)",
    product_version  = "v2",
    latitude         = site$latitude,
    longitude        = site$longitude,
    cache_file       = basename(attr(bulk_density, "cache_path")),
    source_status    = unique(bulk_density$source),
    depth_bands_mm   = bulk_density[c("depth_top_mm", "depth_bottom_mm")],
    top_layer_g_cm3  = unname(top_density),
    bottom_layer_g_cm3 = unname(bottom_density)
  ),
  model = list(
    target_quantity        = "layer-average resident concentration",
    top_thickness_mm       = top_thickness_mm,
    bottom_thickness_mm    = bottom_thickness_mm,
    effective_porosity     = effective_porosity,
    degradation_clock      = "total elapsed time",
    water_balance          = "max(rain + irrigation - PET, 0) accumulated daily",
    et_factor              = 1,
    irrigation_mm          = 0,
    convolution_method     = convolution_method,
    convolution_steps      = convolution_steps
  ),
  calibration = list(
    objective          = "replicate-level root mean squared log residual",
    objective_value    = unname(fit$objective),
    convergence        = fit$convergence,
    message            = fit$message,
    selected_start     = fit$start_index,
    bounds             = parameter_table[c("parameter", "lower", "upper")],
    starts             = as.data.frame(fit$starts),
    bound_hits         = as.list(fit$bound_hit),
    transport_scales   = as.list(fit$transport_scales),
    identifiability_note = fit$identifiability_note
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
  "Wrote SA Minnipa Heavy/Imazapic reference outputs to ",
  normalizePath(arguments$output_dir, mustWork = TRUE),
  "\n",
  "Objective: ",
  format(fit$objective, digits = 8),
  "\n",
  sep = ""
)

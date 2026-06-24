#!/usr/bin/env Rscript
# Script: prepare_shared_observations.R
# Objective: Prepare normalized NSW and SA replicate-level observation inputs.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Herbicide Dissipation 2024 Excel workbook.
# Outputs: Shared NSW Griffith and SA Minnipa observation CSV files.
# Usage: Rscript examples/R/prepare_shared_observations.R --workbook FILE
# Dependencies: pkgload, cltf, readxl

script_argument <- grep(
  "^--file=",
  commandArgs(trailingOnly = FALSE),
  value = TRUE
)
script_path <- normalizePath(
  sub("^--file=", "", script_argument[1]),
  mustWork = TRUE
)
repository_root <- normalizePath(
  file.path(dirname(script_path), "..", ".."),
  mustWork = TRUE
)

parse_arguments <- function(arguments) {
  if (any(arguments %in% c("-h", "--help"))) {
    cat(
      paste(
        "Usage:",
        "Rscript examples/R/prepare_shared_observations.R",
        "--workbook FILE\n"
      )
    )
    quit(status = 0)
  }
  workbook_index <- match("--workbook", arguments)
  if (is.na(workbook_index) || workbook_index == length(arguments)) {
    stop("--workbook FILE is required.", call. = FALSE)
  }
  list(workbook = arguments[workbook_index + 1L])
}

write_case <- function(
  observations,
  site_id,
  soil_group,
  herbicide,
  output_path
) {
  selected <- observations$site_id == site_id &
    observations$soil_group == soil_group &
    observations$herbicide == herbicide
  case <- observations[selected, ]
  if (nrow(case) == 0L) {
    stop(
      "No observations found for ",
      site_id,
      " / ",
      soil_group,
      " / ",
      herbicide,
      ".",
      call. = FALSE
    )
  }
  case$used_for_calibration <- !case$is_t0 &
    is.finite(case$analysis_concentration_ug_kg) &
    case$analysis_concentration_ug_kg > 0
  dir.create(dirname(output_path), recursive = TRUE, showWarnings = FALSE)
  utils::write.csv(case, output_path, row.names = FALSE, na = "")
}

arguments <- parse_arguments(commandArgs(trailingOnly = TRUE))
if (!file.exists(arguments$workbook)) {
  stop("Workbook does not exist: ", arguments$workbook, call. = FALSE)
}

pkgload::load_all(file.path(repository_root, "R"), quiet = TRUE)
observations <- read_herbicide_workbook(
  arguments$workbook,
  sheets = c("NSW", "SA")
)

write_case(
  observations,
  site_id     = "NSW_Griffith",
  soil_group  = "Heavy",
  herbicide   = "Imazapic",
  output_path = file.path(
    repository_root,
    "examples",
    "data",
    "nsw_griffith_heavy_imazapic",
    "observations.csv"
  )
)
write_case(
  observations,
  site_id     = "SA_Minnipa",
  soil_group  = "Heavy",
  herbicide   = "Imazapic",
  output_path = file.path(
    repository_root,
    "examples",
    "data",
    "sa_minnipa_heavy_imazapic",
    "observations.csv"
  )
)

#!/usr/bin/env Rscript
# Script: prepare_shared_climate.R
# Objective: Normalize existing SILO grid-cell climate into shared case inputs.
# Author: Yi Yu
# Created: 2026-06-24
# Last updated: 2026-06-24
# Inputs: Existing workbench daily_climate.csv and shared site/case JSON.
# Outputs: Data Drill-compatible SILO CSV and metadata for NSW and SA.
# Usage: Rscript examples/R/prepare_shared_climate.R
# Dependencies: jsonlite, utils

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
data_root <- file.path(repository_root, "examples", "data")
source_path <- file.path(
  repository_root,
  "apps",
  "herbicide_workbench",
  "sample_data",
  "daily_climate.csv"
)

if (!file.exists(source_path)) {
  stop("Climate source does not exist: ", source_path, call. = FALSE)
}

source <- utils::read.csv(source_path, stringsAsFactors = FALSE)
required <- c("site_id", "date", "rain_mm", "Tmax", "Tmin")
missing_columns <- setdiff(required, names(source))
if (length(missing_columns) > 0L) {
  stop(
    "Climate source is missing columns: ",
    paste(missing_columns, collapse = ", "),
    call. = FALSE
  )
}
source$date <- as.Date(source$date)
sites <- jsonlite::fromJSON(file.path(data_root, "sites.json"))

write_case <- function(case_name) {
  case_dir <- file.path(data_root, case_name)
  case <- jsonlite::fromJSON(file.path(case_dir, "case.json"))
  site <- sites[sites$site_id == case$site_id, ]
  if (nrow(site) != 1L) {
    stop("Site registry match is not unique for ", case$site_id, call. = FALSE)
  }

  start_date <- as.Date(case$application_date)
  end_date <- as.Date(case$final_date)
  selected <- source$site_id == case$site_id &
    source$date >= start_date &
    source$date <= end_date
  climate <- source[selected, ]
  expected_rows <- as.integer(end_date - start_date) + 1L
  if (nrow(climate) != expected_rows) {
    stop(
      "Climate source does not fully cover ",
      case_name,
      ".",
      call. = FALSE
    )
  }

  normalized <- data.frame(
    Date  = format(climate$date, "%Y%m%d"),
    T.Max = climate$Tmax,
    T.Min = climate$Tmin,
    Rain  = climate$rain_mm,
    check.names = FALSE
  )
  utils::write.csv(
    normalized,
    file.path(case_dir, "silo.csv"),
    row.names = FALSE,
    quote = FALSE
  )

  metadata <- list(
    source = paste(
      "Existing 2024 SILO gridded-archive extraction normalized",
      "to the shared CLTF cache schema"
    ),
    source_file       = "apps/herbicide_workbench/sample_data/daily_climate.csv",
    request_latitude  = site$latitude,
    request_longitude = site$longitude,
    grid_latitude     = site$silo_latitude,
    grid_longitude    = site$silo_longitude,
    start_date        = case$application_date,
    end_date          = case$final_date,
    raw_cache_file    = "silo.csv"
  )
  jsonlite::write_json(
    metadata,
    file.path(case_dir, "silo_metadata.json"),
    pretty     = TRUE,
    auto_unbox = TRUE,
    digits     = 16
  )
}

write_case("nsw_griffith_heavy_imazapic")
write_case("sa_minnipa_heavy_imazapic")

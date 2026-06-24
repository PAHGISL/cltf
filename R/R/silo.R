# Script: silo.R
# Objective: Retrieve and parse cached SILO point climate data.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Coordinates, date range, SILO credentials, and cache directory.
# Outputs: Daily rainfall and temperature forcing with source metadata.
# Usage: Use fetch_silo_point() or parse_silo_csv() after library(rclt).
# Dependencies: jsonlite, utils

#' Round a coordinate to the SILO 0.05-degree grid
#'
#' @param value Decimal-degree coordinate.
#' @return Rounded coordinate.
#' @export
round_silo_coordinate <- function(value) {
  if (length(value) != 1L || !is.finite(value)) {
    stop("value must be one finite coordinate.", call. = FALSE)
  }
  round(value / 0.05) * 0.05
}

#' Parse a SILO Data Drill CSV
#'
#' @param path Path to a SILO CSV response.
#' @return Data frame with standard RCLT climate fields.
#' @export
parse_silo_csv <- function(path) {
  if (!file.exists(path)) {
    stop("SILO CSV does not exist: ", path, call. = FALSE)
  }
  raw <- utils::read.csv(
    path,
    check.names  = FALSE,
    comment.char = "#",
    stringsAsFactors = FALSE
  )
  date_column <- intersect(c("Date", "YYYYMMDD", "date"), names(raw))[1]
  tmax_column <- intersect(c("T.Max", "Tmax", "max_temp"), names(raw))[1]
  tmin_column <- intersect(c("T.Min", "Tmin", "min_temp"), names(raw))[1]
  rain_column <- intersect(c("Rain", "rain", "rain_mm"), names(raw))[1]
  required <- c(date_column, tmax_column, tmin_column, rain_column)
  if (any(is.na(required))) {
    stop("SILO CSV is missing required date, temperature, or rain columns.", call. = FALSE)
  }

  date <- as.Date(as.character(raw[[date_column]]), format = "%Y%m%d")
  result <- data.frame(
    date    = date,
    jdays   = as.integer(format(date, "%j")),
    rain_mm = as.numeric(raw[[rain_column]]),
    Tmax    = as.numeric(raw[[tmax_column]]),
    Tmin    = as.numeric(raw[[tmin_column]])
  )
  if (any(!is.finite(unlist(result[-1]))) || any(is.na(result$date))) {
    stop("SILO CSV contains invalid or missing forcing values.", call. = FALSE)
  }
  result[order(result$date), ]
}

silo_coordinate_tag <- function(value) {
  prefix <- if (value < 0) "m" else "p"
  digits <- gsub("\\.", "p", sprintf("%.2f", abs(value)))
  paste0(prefix, digits)
}

silo_cache_paths <- function(
  cache_dir,
  latitude,
  longitude,
  start_date,
  end_date
) {
  stem <- paste(
    "silo",
    silo_coordinate_tag(latitude),
    silo_coordinate_tag(longitude),
    format(start_date, "%Y%m%d"),
    format(end_date, "%Y%m%d"),
    sep = "_"
  )
  list(
    csv      = file.path(cache_dir, paste0(stem, ".csv")),
    metadata = file.path(cache_dir, paste0(stem, ".json"))
  )
}

silo_request_url <- function(
  latitude,
  longitude,
  start_date,
  end_date,
  username,
  password
) {
  query <- c(
    username = username,
    password = password,
    start    = format(start_date, "%Y%m%d"),
    finish   = format(end_date, "%Y%m%d"),
    lat      = sprintf("%.2f", latitude),
    lon      = sprintf("%.2f", longitude),
    format   = "csv",
    comment  = "RXN"
  )
  encoded <- paste(
    names(query),
    vapply(
      query,
      utils::URLencode,
      character(1),
      reserved = TRUE
    ),
    sep      = "=",
    collapse = "&"
  )
  paste0(
    "https://www.longpaddock.qld.gov.au/cgi-bin/silo/",
    "DataDrillDataset.php?",
    encoded
  )
}

#' Retrieve cached SILO point climate data
#'
#' @param latitude,longitude Requested decimal-degree coordinates.
#' @param start_date,end_date Inclusive date range.
#' @param cache_dir Directory for immutable raw responses and metadata.
#' @param refresh Force a new request when `TRUE`.
#' @param username,password SILO credentials, defaulting to environment variables.
#' @param downloader Download function compatible with [utils::download.file()].
#' @return Parsed climate data with cache paths stored as attributes.
#' @export
fetch_silo_point <- function(
  latitude,
  longitude,
  start_date,
  end_date,
  cache_dir,
  refresh    = FALSE,
  username   = Sys.getenv("SILO_USERNAME"),
  password   = Sys.getenv("SILO_PASSWORD"),
  downloader = utils::download.file
) {
  coordinates <- c(latitude, longitude)
  if (any(!is.finite(coordinates))) {
    stop("SILO coordinates must be finite.", call. = FALSE)
  }
  start_date <- as.Date(start_date)
  end_date <- as.Date(end_date)
  if (is.na(start_date) || is.na(end_date) || end_date < start_date) {
    stop("SILO date range is invalid.", call. = FALSE)
  }

  grid_latitude <- round_silo_coordinate(latitude)
  grid_longitude <- round_silo_coordinate(longitude)
  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
  paths <- silo_cache_paths(
    cache_dir,
    grid_latitude,
    grid_longitude,
    start_date,
    end_date
  )

  if (!refresh && file.exists(paths$csv) && file.exists(paths$metadata)) {
    result <- parse_silo_csv(paths$csv)
    attr(result, "cache_path") <- paths$csv
    attr(result, "metadata_path") <- paths$metadata
    return(result)
  }
  if (!nzchar(username) || !nzchar(password)) {
    stop(
      "SILO_USERNAME and SILO_PASSWORD are required for a cache miss.",
      call. = FALSE
    )
  }

  url <- silo_request_url(
    grid_latitude,
    grid_longitude,
    start_date,
    end_date,
    username,
    password
  )
  temporary <- tempfile("silo-", tmpdir = cache_dir, fileext = ".csv")
  on.exit(unlink(temporary), add = TRUE)
  status <- downloader(url, temporary, quiet = TRUE, mode = "wb")
  if (!(isTRUE(status) || identical(status, 0L))) {
    stop("SILO download failed with status: ", status, call. = FALSE)
  }
  parse_silo_csv(temporary)
  if (!file.rename(temporary, paths$csv)) {
    stop("Could not move SILO response into the cache.", call. = FALSE)
  }

  metadata <- list(
    source              = "SILO Data Drill API",
    request_latitude    = latitude,
    request_longitude   = longitude,
    grid_latitude       = grid_latitude,
    grid_longitude      = grid_longitude,
    start_date          = as.character(start_date),
    end_date            = as.character(end_date),
    retrieved_at_utc    = format(Sys.time(), tz = "UTC", usetz = TRUE),
    raw_cache_file      = basename(paths$csv)
  )
  jsonlite::write_json(
    metadata,
    paths$metadata,
    pretty      = TRUE,
    auto_unbox  = TRUE
  )

  result <- parse_silo_csv(paths$csv)
  attr(result, "cache_path") <- paths$csv
  attr(result, "metadata_path") <- paths$metadata
  result
}

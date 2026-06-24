# Script: observations.R
# Objective: Prepare replicate-level herbicide observations for RCLT analysis.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-23
# Inputs: Herbicide workbooks or tidy concentration vectors.
# Outputs: Explicit depth intervals, non-detect fields, summaries, and inferred application rates.
# Usage: Use exported functions after library(rclt).
# Dependencies: readxl

#' Map workbook depth labels to sampling intervals
#'
#' @param sheet Workbook sheet or jurisdiction label.
#' @param depth_label Workbook depth label.
#' @return Numeric vector containing top and bottom depths in millimetres.
#' @export
depth_interval_mm <- function(sheet, depth_label) {
  key <- paste(
    toupper(trimws(sheet)),
    gsub("\\s+", "", tolower(trimws(depth_label))),
    sep = ":"
  )
  intervals <- list(
    "SA:10cm"  = c(0, 100),
    "SA:30cm"  = c(100, 300),
    "NSW:15cm" = c(0, 150),
    "NSW:30cm" = c(150, 300),
    "QLD:10cm" = c(0, 100),
    "QLD:30cm" = c(100, 300)
  )
  result <- intervals[[key]]
  if (is.null(result)) {
    stop("Unsupported sheet/depth combination: ", key, call. = FALSE)
  }
  result
}

#' Prepare observations with explicit non-detect handling
#'
#' @param concentration_ug_kg Reported concentrations.
#' @param is_non_detect Logical non-detect indicators.
#' @param detection_limit_ug_kg Detection limits in micrograms per kilogram.
#' @return Data frame containing analysis concentrations and handling flags.
#' @export
prepare_non_detects <- function(
  concentration_ug_kg,
  is_non_detect,
  detection_limit_ug_kg
) {
  lengths <- c(
    length(concentration_ug_kg),
    length(is_non_detect),
    length(detection_limit_ug_kg)
  )
  if (length(unique(lengths)) != 1L) {
    stop("Non-detect input vectors must have equal lengths.", call. = FALSE)
  }
  if (any(!is.finite(concentration_ug_kg))) {
    stop("Reported concentrations must be finite.", call. = FALSE)
  }
  if (any(is.na(is_non_detect))) {
    stop("is_non_detect cannot contain missing values.", call. = FALSE)
  }

  substituted <- is_non_detect &
    is.finite(detection_limit_ug_kg) &
    detection_limit_ug_kg > 0
  excluded_zero <- concentration_ug_kg <= 0 & !substituted
  analysis <- concentration_ug_kg
  analysis[substituted] <- detection_limit_ug_kg[substituted] / 2
  analysis[excluded_zero] <- NA_real_

  data.frame(
    analysis_concentration_ug_kg = analysis,
    lod_substituted              = substituted,
    excluded_zero                = excluded_zero
  )
}

#' Calculate grouped geometric concentration summaries
#'
#' @param data Data frame containing `analysis_concentration_ug_kg`.
#' @param group_columns Character vector of grouping columns.
#' @return Data frame with counts, geometric means, and geometric standard deviations.
#' @export
geometric_concentration <- function(data, group_columns) {
  if (!"analysis_concentration_ug_kg" %in% names(data)) {
    stop("data must contain analysis_concentration_ug_kg.", call. = FALSE)
  }
  if (!all(group_columns %in% names(data)) || length(group_columns) == 0L) {
    stop("group_columns must identify columns in data.", call. = FALSE)
  }

  key <- interaction(data[group_columns], drop = TRUE, lex.order = TRUE)
  split_data <- split(data, key)
  rows <- lapply(split_data, function(group) {
    values <- group$analysis_concentration_ug_kg
    values <- values[is.finite(values) & values > 0]
    first <- group[1, group_columns, drop = FALSE]
    first$n <- length(values)
    first$geometric_mean_ug_kg <- if (length(values)) {
      exp(mean(log(values)))
    } else {
      NA_real_
    }
    first$geometric_sd <- if (length(values) > 1L) {
      exp(stats::sd(log(values)))
    } else {
      NA_real_
    }
    first
  })
  result <- do.call(rbind, rows)
  rownames(result) <- NULL
  result
}

normalize_sample_date <- function(value) {
  if (inherits(value, "POSIXt") || inherits(value, "Date")) {
    return(as.Date(value))
  }
  if (is.numeric(value)) {
    return(as.Date(value, origin = "1899-12-30"))
  }
  as.Date(value)
}

column_or_default <- function(data, column, default) {
  if (column %in% names(data)) data[[column]] else rep(default, nrow(data))
}

prepare_workbook_sheet <- function(path, sheet) {
  raw <- as.data.frame(
    readxl::read_excel(path, sheet = sheet, .name_repair = "unique"),
    stringsAsFactors = FALSE
  )
  identifier_columns <- intersect(
    c(
      "Soil",
      "Irrigation",
      "Timepoint",
      "Crop_2024",
      "Depth",
      "Sample_date"
    ),
    names(raw)
  )
  herbicide_columns <- setdiff(names(raw), identifier_columns)
  site_id <- switch(
    toupper(sheet),
    SA  = "SA_Minnipa",
    NSW = "NSW_Griffith",
    QLD = "QLD_Wellcamp",
    stop("Unsupported workbook sheet: ", sheet, call. = FALSE)
  )

  frames <- lapply(herbicide_columns, function(herbicide) {
    concentration <- suppressWarnings(as.numeric(raw[[herbicide]]))
    keep <- is.finite(concentration)
    if (!any(keep)) {
      return(NULL)
    }
    data.frame(
      site_id             = site_id,
      source_sheet        = sheet,
      source_row          = which(keep) + 1L,
      soil_group          = trimws(as.character(raw$Soil[keep])),
      treatment           = trimws(as.character(
        column_or_default(raw, "Irrigation", "All")[keep]
      )),
      crop_2024           = trimws(as.character(
        column_or_default(raw, "Crop_2024", NA_character_)[keep]
      )),
      timepoint           = trimws(as.character(raw$Timepoint[keep])),
      depth_label         = trimws(as.character(raw$Depth[keep])),
      sample_date         = normalize_sample_date(raw$Sample_date[keep]),
      herbicide           = herbicide,
      concentration_ug_kg = concentration[keep],
      stringsAsFactors    = FALSE
    )
  })
  frames <- Filter(Negate(is.null), frames)
  if (!length(frames)) {
    stop("No herbicide concentrations found in sheet ", sheet, ".", call. = FALSE)
  }
  do.call(rbind, frames)
}

#' Read the herbicide dissipation workbook
#'
#' @param path Path to the source Excel workbook.
#' @param sheets Workbook sheets to import.
#' @return Replicate-level tidy observations with explicit depth intervals.
#' @export
read_herbicide_workbook <- function(
  path,
  sheets = c("SA", "NSW", "Qld")
) {
  if (!requireNamespace("readxl", quietly = TRUE)) {
    stop("Package 'readxl' is required to import workbooks.", call. = FALSE)
  }
  if (!file.exists(path)) {
    stop("Observation workbook does not exist: ", path, call. = FALSE)
  }

  observations <- do.call(
    rbind,
    lapply(sheets, function(sheet) prepare_workbook_sheet(path, sheet))
  )
  intervals <- t(vapply(
    seq_len(nrow(observations)),
    function(index) {
      depth_interval_mm(
        observations$source_sheet[index],
        observations$depth_label[index]
      )
    },
    numeric(2)
  ))
  observations$depth_top_mm <- intervals[, 1]
  observations$depth_bottom_mm <- intervals[, 2]
  observations$is_t0 <- toupper(observations$timepoint) == "T0"

  application_group <- interaction(
    observations[c("site_id", "soil_group", "treatment")],
    drop      = TRUE,
    lex.order = TRUE
  )
  application_dates <- tapply(
    as.numeric(observations$sample_date[observations$is_t0]),
    application_group[observations$is_t0],
    min
  )
  observations$application_date <- as.Date(
    unname(application_dates[as.character(application_group)]),
    origin = "1970-01-01"
  )
  if (any(is.na(observations$application_date))) {
    stop("At least one observation group has no T0 application date.", call. = FALSE)
  }
  observations$days_since_application <- as.integer(
    observations$sample_date - observations$application_date
  )

  replicate_group <- interaction(
    observations[
      c(
        "site_id",
        "soil_group",
        "treatment",
        "herbicide",
        "depth_top_mm",
        "depth_bottom_mm",
        "sample_date"
      )
    ],
    drop      = TRUE,
    lex.order = TRUE
  )
  observations$replicate_id <- stats::ave(
    seq_len(nrow(observations)),
    replicate_group,
    FUN = seq_along
  )
  observations$is_non_detect <- FALSE
  observations$detection_limit_ug_kg <- NA_real_
  observations$is_zero_reported <- observations$concentration_ug_kg <= 0
  non_detects <- prepare_non_detects(
    observations$concentration_ug_kg,
    observations$is_non_detect,
    observations$detection_limit_ug_kg
  )
  observations <- cbind(observations, non_detects)
  observations$unit_status <- "inferred_from_application_rate"

  observations[order(
    observations$site_id,
    observations$soil_group,
    observations$treatment,
    observations$herbicide,
    observations$sample_date,
    observations$depth_top_mm,
    observations$replicate_id
  ), ]
}

#' Infer applied mass from top-layer T0 concentration
#'
#' @param t0_concentration_ug_kg Positive T0 replicate concentrations.
#' @param depth_top_mm,depth_bottom_mm T0 layer bounds.
#' @param bulk_density_g_cm3 Whole-earth bulk density.
#' @return Inferred application rate in grams per hectare.
#' @export
infer_application_rate_g_ha <- function(
  t0_concentration_ug_kg,
  depth_top_mm,
  depth_bottom_mm,
  bulk_density_g_cm3
) {
  if (!length(t0_concentration_ug_kg) ||
      any(!is.finite(t0_concentration_ug_kg)) ||
      any(t0_concentration_ug_kg <= 0)) {
    stop("T0 concentrations must be finite and greater than zero.", call. = FALSE)
  }
  soil_mass <- soil_mass_kg_ha(
    depth_top_mm,
    depth_bottom_mm,
    bulk_density_g_cm3
  )
  exp(mean(log(t0_concentration_ug_kg))) * soil_mass / 1e6
}

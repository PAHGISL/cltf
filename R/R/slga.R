# Script: slga.R
# Objective: Retrieve, normalize, and depth-weight SLGA whole-earth bulk density.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Coordinates, TERN API credentials, cached JSON, or manual overrides.
# Outputs: Standard bulk-density bands and depth-weighted estimates in g/cm3.
# Usage: Use fetch_slga_bulk_density() and weight_bulk_density() after library(cltf).
# Dependencies: jsonlite; terra is optional for direct COG fallback.

slga_standard_depths <- function() {
  data.frame(
    depth_top_mm    = c(0, 50, 150),
    depth_bottom_mm = c(50, 150, 300)
  )
}

validate_slga_bands <- function(bands) {
  required <- c(
    "depth_top_mm",
    "depth_bottom_mm",
    "estimate_g_cm3",
    "lower_g_cm3",
    "upper_g_cm3",
    "source"
  )
  missing_columns <- setdiff(required, names(bands))
  if (length(missing_columns) > 0L) {
    stop(
      "Bulk-density data are missing columns: ",
      paste(missing_columns, collapse = ", "),
      call. = FALSE
    )
  }
  numeric_columns <- setdiff(required, "source")
  if (any(!is.finite(unlist(bands[numeric_columns])))) {
    stop("Bulk-density values and depths must be finite.", call. = FALSE)
  }
  if (any(bands$depth_bottom_mm <= bands$depth_top_mm)) {
    stop("Bulk-density depth bands must have positive thickness.", call. = FALSE)
  }
  bands[order(bands$depth_top_mm), required]
}

#' Parse normalized SLGA whole-earth bulk density
#'
#' @param path Path to a normalized SLGA JSON cache.
#' @return Data frame containing depth bands and density estimates in g/cm3.
#' @export
parse_slga_bulk_density <- function(path) {
  if (!file.exists(path)) {
    stop("SLGA cache does not exist: ", path, call. = FALSE)
  }
  payload <- jsonlite::fromJSON(path, simplifyDataFrame = TRUE)
  values <- payload$values
  if (is.null(values) || !is.data.frame(values)) {
    stop("SLGA cache does not contain a tabular values field.", call. = FALSE)
  }

  source <- if ("source" %in% names(values)) {
    as.character(values$source)
  } else {
    rep("SLGA whole-earth bulk density", nrow(values))
  }
  bands <- data.frame(
    depth_top_mm    = 10 * as.numeric(values$depth_top_cm),
    depth_bottom_mm = 10 * as.numeric(values$depth_bottom_cm),
    estimate_g_cm3  = as.numeric(values$estimate_g_cm3),
    lower_g_cm3     = as.numeric(values$lower_g_cm3),
    upper_g_cm3     = as.numeric(values$upper_g_cm3),
    source           = source,
    stringsAsFactors = FALSE
  )
  validate_slga_bands(bands)
}

#' Calculate a depth-weighted bulk density
#'
#' @param bands Standard bulk-density bands from [parse_slga_bulk_density()].
#' @param depth_top_mm,depth_bottom_mm Target depth interval in millimetres.
#' @return One-row data frame with overlap-weighted density estimates.
#' @export
weight_bulk_density <- function(bands, depth_top_mm, depth_bottom_mm) {
  bands <- validate_slga_bands(bands)
  target <- c(depth_top_mm, depth_bottom_mm)
  if (
    length(target) != 2L ||
      any(!is.finite(target)) ||
      depth_bottom_mm <= depth_top_mm
  ) {
    stop("Target depth interval must have positive finite thickness.", call. = FALSE)
  }

  overlap_mm <- pmax(
    0,
    pmin(bands$depth_bottom_mm, depth_bottom_mm) -
      pmax(bands$depth_top_mm, depth_top_mm)
  )
  target_thickness_mm <- depth_bottom_mm - depth_top_mm
  if (abs(sum(overlap_mm) - target_thickness_mm) > 1e-8) {
    stop(
      "Bulk-density bands do not fully cover the requested depth interval.",
      call. = FALSE
    )
  }

  weighted <- function(column) {
    sum(column * overlap_mm) / target_thickness_mm
  }
  data.frame(
    depth_top_mm    = depth_top_mm,
    depth_bottom_mm = depth_bottom_mm,
    estimate_g_cm3  = weighted(bands$estimate_g_cm3),
    lower_g_cm3     = weighted(bands$lower_g_cm3),
    upper_g_cm3     = weighted(bands$upper_g_cm3),
    source           = paste(unique(bands$source), collapse = "; "),
    stringsAsFactors = FALSE
  )
}

normalize_bulk_density_override <- function(manual_override) {
  if (is.data.frame(manual_override)) {
    return(validate_slga_bands(manual_override))
  }
  if (!is.numeric(manual_override) || !length(manual_override) %in% c(1L, 3L)) {
    stop(
      "manual_override must be one value, three standard-band values, or a data frame.",
      call. = FALSE
    )
  }
  if (length(manual_override) == 1L) {
    manual_override <- rep(manual_override, 3L)
  }
  if (any(!is.finite(manual_override)) || any(manual_override <= 0)) {
    stop("Manual bulk-density values must be finite and positive.", call. = FALSE)
  }

  depths <- slga_standard_depths()
  data.frame(
    depths,
    estimate_g_cm3 = manual_override,
    lower_g_cm3    = manual_override,
    upper_g_cm3    = manual_override,
    source          = rep("manual_override", 3L),
    stringsAsFactors = FALSE
  )
}

slga_cache_path <- function(cache_dir, latitude, longitude) {
  stem <- paste(
    "slga_bulk_density",
    silo_coordinate_tag(latitude),
    silo_coordinate_tag(longitude),
    sep = "_"
  )
  file.path(cache_dir, paste0(stem, ".json"))
}

slga_query_url <- function(endpoint, query) {
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
    "https://esoil.io/TERNLandscapes/RasterProductsAPI/",
    endpoint,
    "?",
    encoded
  )
}

slga_find_data_frames <- function(object) {
  if (is.data.frame(object)) {
    return(list(object))
  }
  if (!is.list(object)) {
    return(list())
  }
  unlist(
    lapply(object, slga_find_data_frames),
    recursive = FALSE
  )
}

slga_product_table <- function(payload) {
  candidates <- slga_find_data_frames(payload)
  if (is.data.frame(payload)) {
    candidates <- c(list(payload), candidates)
  }
  if (length(candidates) == 0L) {
    stop("SLGA ProductInfo response contains no tabular product records.", call. = FALSE)
  }
  scores <- vapply(
    candidates,
    function(candidate) {
      normalized <- gsub("[^a-z0-9]", "", tolower(names(candidate)))
      sum(grepl("cog|path|url|model", normalized))
    },
    numeric(1)
  )
  candidates[[which.max(scores)]]
}

slga_match_column <- function(table, aliases, required = TRUE) {
  normalized_names <- gsub("[^a-z0-9]", "", tolower(names(table)))
  normalized_aliases <- gsub("[^a-z0-9]", "", tolower(aliases))
  index <- match(normalized_aliases, normalized_names, nomatch = 0L)
  index <- index[index > 0L]
  if (length(index) == 0L) {
    if (required) {
      stop(
        "SLGA ProductInfo response is missing: ",
        paste(aliases, collapse = " / "),
        call. = FALSE
      )
    }
    return(NULL)
  }
  names(table)[index[1]]
}

slga_depth_from_text <- function(text) {
  text <- as.character(text)
  matched <- regexec("([0-9]{3})[_-]([0-9]{3})", text)
  pieces <- regmatches(text, matched)
  result <- matrix(NA_real_, nrow = length(text), ncol = 2L)
  for (index in seq_along(pieces)) {
    if (length(pieces[[index]]) == 3L) {
      result[index, ] <- 10 * as.numeric(pieces[[index]][2:3])
    }
  }
  result
}

slga_select_products <- function(payload) {
  products <- slga_product_table(payload)
  cog_column <- slga_match_column(
    products,
    c("COGPath", "COGsPath", "COG", "CloudOptimizedGeoTIFF", "URL", "FilePath")
  )
  component_column <- slga_match_column(
    products,
    c("Component", "ComponentName", "Statistic"),
    required = FALSE
  )
  model_column <- slga_match_column(
    products,
    c("Model", "ModelName", "ModelID", "RasterName"),
    required = FALSE
  )

  cog_path <- as.character(products[[cog_column]])
  model_text <- if (is.null(model_column)) {
    cog_path
  } else {
    paste(products[[model_column]], cog_path)
  }
  depths <- slga_depth_from_text(model_text)
  component_text <- if (is.null(component_column)) {
    model_text
  } else {
    paste(products[[component_column]], model_text)
  }
  component_text <- tolower(component_text)
  statistic <- ifelse(
    grepl("lower|_05_|p05", component_text),
    "lower_g_cm3",
    ifelse(
      grepl("upper|_95_|p95", component_text),
      "upper_g_cm3",
      "estimate_g_cm3"
    )
  )

  selected <- data.frame(
    depth_top_mm    = depths[, 1],
    depth_bottom_mm = depths[, 2],
    statistic       = statistic,
    cog_path        = cog_path,
    stringsAsFactors = FALSE
  )
  expected_depths <- c("0_50", "50_150", "150_300")
  selected$depth_key <- paste(
    selected$depth_top_mm,
    selected$depth_bottom_mm,
    sep = "_"
  )
  selected <- selected[
    selected$depth_key %in% expected_depths &
      nzchar(selected$cog_path),
  ]
  selected <- selected[!duplicated(selected[c("depth_key", "statistic")]), ]
  if (nrow(selected) != 9L) {
    stop(
      "SLGA ProductInfo did not resolve all three estimates for three depth bands.",
      call. = FALSE
    )
  }
  selected
}

slga_extract_numeric_value <- function(payload) {
  if (is.numeric(payload) && length(payload) == 1L && is.finite(payload)) {
    return(as.numeric(payload))
  }
  if (is.data.frame(payload)) {
    payload <- as.list(payload)
  }
  if (!is.list(payload)) {
    stop("SLGA Drill response contains no numeric raster value.", call. = FALSE)
  }

  preferred_names <- c(
    "value",
    "rastervalue",
    "pixelvalue",
    "bandvalue",
    "result"
  )
  normalized_names <- gsub("[^a-z0-9]", "", tolower(names(payload)))
  for (preferred_name in preferred_names) {
    index <- which(normalized_names == preferred_name)
    for (candidate_index in index) {
      candidate <- suppressWarnings(as.numeric(payload[[candidate_index]]))
      if (length(candidate) == 1L && is.finite(candidate)) {
        return(candidate)
      }
    }
  }
  for (candidate in payload) {
    result <- tryCatch(
      slga_extract_numeric_value(candidate),
      error = function(...) NULL
    )
    if (!is.null(result)) {
      return(result)
    }
  }
  stop("SLGA Drill response contains no numeric raster value.", call. = FALSE)
}

slga_read_cog <- function(cog_path, latitude, longitude, api_key) {
  if (!requireNamespace("terra", quietly = TRUE)) {
    stop(
      "SLGA Drill failed and optional package 'terra' is unavailable for COG fallback.",
      call. = FALSE
    )
  }
  header_path <- tempfile("tern-header-", fileext = ".txt")
  writeLines(paste("x-api-key:", api_key), header_path)
  on.exit(unlink(header_path), add = TRUE)

  previous_header <- Sys.getenv("GDAL_HTTP_HEADER_FILE", unset = NA_character_)
  Sys.setenv(GDAL_HTTP_HEADER_FILE = header_path)
  on.exit({
    if (is.na(previous_header)) {
      Sys.unsetenv("GDAL_HTTP_HEADER_FILE")
    } else {
      Sys.setenv(GDAL_HTTP_HEADER_FILE = previous_header)
    }
  }, add = TRUE)

  raster <- terra::rast(paste0("/vsicurl/", cog_path))
  extracted <- terra::extract(
    raster,
    matrix(c(longitude, latitude), ncol = 2L)
  )
  values <- unlist(extracted[, -1, drop = FALSE], use.names = FALSE)
  values <- values[is.finite(values)]
  if (length(values) == 0L) {
    stop("SLGA COG contains no value at the requested point.", call. = FALSE)
  }
  as.numeric(values[1])
}

slga_read_product_value <- function(
  product,
  latitude,
  longitude,
  api_key,
  drill_reader
) {
  url <- slga_query_url(
    "Drill",
    c(
      format     = "json",
      verbose    = "false",
      TERNapiKey = api_key,
      COGPath    = product$cog_path,
      latitude   = format(latitude, scientific = FALSE, trim = TRUE),
      longitude  = format(longitude, scientific = FALSE, trim = TRUE)
    )
  )
  tryCatch(
    slga_extract_numeric_value(drill_reader(url)),
    error = function(...) {
      slga_read_cog(product$cog_path, latitude, longitude, api_key)
    }
  )
}

slga_write_cache <- function(path, latitude, longitude, bands) {
  values <- data.frame(
    depth_top_cm    = bands$depth_top_mm / 10,
    depth_bottom_cm = bands$depth_bottom_mm / 10,
    estimate_g_cm3  = bands$estimate_g_cm3,
    lower_g_cm3     = bands$lower_g_cm3,
    upper_g_cm3     = bands$upper_g_cm3,
    source           = bands$source,
    stringsAsFactors = FALSE
  )
  payload <- list(
    latitude         = latitude,
    longitude        = longitude,
    attribute        = "Bulk Density (whole earth)",
    units            = "g/cm3",
    retrieved_at_utc = format(Sys.time(), tz = "UTC", usetz = TRUE),
    values            = values
  )
  jsonlite::write_json(
    payload,
    path,
    pretty     = TRUE,
    auto_unbox = TRUE,
    dataframe  = "rows"
  )
}

#' Retrieve SLGA whole-earth bulk density
#'
#' @param latitude,longitude Requested decimal-degree coordinates.
#' @param cache_dir Directory for normalized JSON responses.
#' @param manual_override Optional scalar, three standard-band values, or standard
#'   bulk-density data frame. Overrides never access the network.
#' @param refresh Force a new request when `TRUE`.
#' @param api_key TERN Landscapes API key, defaulting to `TERN_API_KEY`.
#' @param metadata_reader JSON reader for ProductInfo responses.
#' @param drill_reader JSON reader for Drill responses.
#' @return Standard 0--5, 5--15, and 15--30 cm bulk-density bands in g/cm3.
#' @export
fetch_slga_bulk_density <- function(
  latitude,
  longitude,
  cache_dir,
  manual_override = NULL,
  refresh         = FALSE,
  api_key         = Sys.getenv("TERN_API_KEY"),
  metadata_reader = jsonlite::fromJSON,
  drill_reader    = jsonlite::fromJSON
) {
  if (!is.null(manual_override)) {
    return(normalize_bulk_density_override(manual_override))
  }
  coordinates <- c(latitude, longitude)
  if (length(coordinates) != 2L || any(!is.finite(coordinates))) {
    stop("SLGA coordinates must be finite.", call. = FALSE)
  }

  dir.create(cache_dir, recursive = TRUE, showWarnings = FALSE)
  cache_path <- slga_cache_path(cache_dir, latitude, longitude)
  if (!refresh && file.exists(cache_path)) {
    result <- parse_slga_bulk_density(cache_path)
    attr(result, "cache_path") <- cache_path
    return(result)
  }
  if (!nzchar(api_key)) {
    stop("TERN_API_KEY is required for an SLGA cache miss.", call. = FALSE)
  }

  metadata_url <- slga_query_url(
    "ProductInfo",
    c(
      format           = "json",
      attribute        = "Bulk Density (whole earth)",
      product          = "SLGA",
      isCurrentVersion = "1"
    )
  )
  products <- slga_select_products(metadata_reader(metadata_url))
  products$value <- vapply(
    seq_len(nrow(products)),
    function(index) {
      slga_read_product_value(
        products[index, ],
        latitude,
        longitude,
        api_key,
        drill_reader
      )
    },
    numeric(1)
  )

  depths <- slga_standard_depths()
  bands <- data.frame(
    depths,
    estimate_g_cm3 = NA_real_,
    lower_g_cm3    = NA_real_,
    upper_g_cm3    = NA_real_,
    source          = rep(
      "credentialed SLGA v2 whole-earth bulk density retrieval",
      3L
    ),
    stringsAsFactors = FALSE
  )
  for (index in seq_len(nrow(products))) {
    band_index <- match(
      products$depth_key[index],
      paste(bands$depth_top_mm, bands$depth_bottom_mm, sep = "_")
    )
    bands[band_index, products$statistic[index]] <- products$value[index]
  }
  bands <- validate_slga_bands(bands)
  slga_write_cache(cache_path, latitude, longitude, bands)
  attr(bands, "cache_path") <- cache_path
  bands
}

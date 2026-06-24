# Script: plots.R
# Objective: Produce base-R diagnostic plots for CLTF inputs, fits, and mass balance.
# Author: Yi Yu
# Created: 2026-06-23
# Last updated: 2026-06-24
# Inputs: Climate, soil, prediction, simulation, and objective-profile tables.
# Outputs: Graphics on the active R device.
# Usage: Open a graphics device, call an exported plot function, then close the device.
# Dependencies: grDevices, graphics

cltf_plot_family <- function() {
  fonts <- names(grDevices::pdfFonts())
  if ("Arial" %in% fonts) "Arial" else "sans"
}

with_cltf_par <- function(code) {
  old <- graphics::par(no.readonly = TRUE)
  on.exit(graphics::par(old), add = TRUE)
  graphics::par(
    family = cltf_plot_family(),
    mar    = c(4.2, 4.5, 1.2, 1.0),
    las    = 1
  )
  force(code)
}

require_plot_columns <- function(data, columns, object_name) {
  missing_columns <- setdiff(columns, names(data))
  if (length(missing_columns) > 0L) {
    stop(
      object_name,
      " is missing columns: ",
      paste(missing_columns, collapse = ", "),
      call. = FALSE
    )
  }
}

cltf_layer_label <- function(depth_top_mm, depth_bottom_mm) {
  paste0(depth_top_mm, "\u2013", depth_bottom_mm, " mm")
}

#' Plot daily climate and infiltration forcing
#'
#' @param forcing Data frame containing rain, PET, daily infiltration, cumulative
#'   infiltration, and either dates or elapsed time.
#' @return The input data, invisibly.
#' @export
plot_climate_forcing <- function(forcing) {
  require_plot_columns(
    forcing,
    c(
      "rain_mm",
      "pet_mm",
      "daily_infiltration_mm",
      "cumulative_infiltration_mm"
    ),
    "forcing"
  )
  x <- if ("date" %in% names(forcing)) forcing$date else forcing$time_days
  if (is.null(x)) {
    stop("forcing must contain date or time_days.", call. = FALSE)
  }

  with_cltf_par({
    graphics::par(mfrow = c(2, 1), mar = c(3.2, 4.5, 1.2, 1.0))
    water_limit <- range(
      c(0, forcing$rain_mm, forcing$pet_mm),
      finite = TRUE
    )
    graphics::plot(
      x,
      forcing$rain_mm,
      type = "h",
      lwd  = 4,
      col  = "#0072B2",
      ylim = water_limit,
      xlab = "",
      ylab = "Daily water (mm)"
    )
    graphics::lines(x, forcing$pet_mm, col = "#D55E00", lwd = 1.8)
    graphics::legend(
      "topright",
      legend = c("Rain", "PET"),
      col    = c("#0072B2", "#D55E00"),
      lty    = 1,
      lwd    = c(4, 1.8),
      bty    = "n"
    )

    cumulative_limit <- range(
      c(0, forcing$cumulative_infiltration_mm),
      finite = TRUE
    )
    graphics::plot(
      x,
      forcing$cumulative_infiltration_mm,
      type = "l",
      lwd  = 2,
      col  = "#009E73",
      ylim = cumulative_limit,
      xlab = if (inherits(x, "Date")) "Date" else "Elapsed time (days)",
      ylab = "Cumulative infiltration (mm)"
    )
    positive <- forcing$daily_infiltration_mm > 0
    graphics::points(
      x[positive],
      forcing$cumulative_infiltration_mm[positive],
      pch = 16,
      cex = 0.65,
      col = "#009E73"
    )
  })
  invisible(forcing)
}

geometric_plot_summary <- function(predictions) {
  usable <- is.finite(predictions$analysis_concentration_ug_kg) &
    predictions$analysis_concentration_ug_kg > 0
  data <- predictions[usable, , drop = FALSE]
  key <- interaction(
    data[
      c(
        "days_since_application",
        "depth_top_mm",
        "depth_bottom_mm"
      )
    ],
    drop      = TRUE,
    lex.order = TRUE
  )
  groups <- split(data, key)
  rows <- lapply(groups, function(group) {
    data.frame(
      days_since_application = group$days_since_application[1],
      depth_top_mm           = group$depth_top_mm[1],
      depth_bottom_mm        = group$depth_bottom_mm[1],
      geometric_mean_ug_kg   = exp(mean(
        log(group$analysis_concentration_ug_kg)
      ))
    )
  })
  do.call(rbind, rows)
}

#' Plot replicate observations, geometric means, and fitted concentrations
#'
#' @param predictions Fit prediction table returned by [fit_cltf()].
#' @return The input data, invisibly.
#' @export
plot_observed_fitted <- function(predictions) {
  require_plot_columns(
    predictions,
    c(
      "days_since_application",
      "depth_top_mm",
      "depth_bottom_mm",
      "analysis_concentration_ug_kg",
      "predicted_concentration_ug_kg"
    ),
    "predictions"
  )
  positive <- c(
    predictions$analysis_concentration_ug_kg,
    predictions$predicted_concentration_ug_kg
  )
  positive <- positive[is.finite(positive) & positive > 0]
  if (length(positive) == 0L) {
    stop("predictions contain no positive concentrations to plot.", call. = FALSE)
  }
  layer <- cltf_layer_label(
    predictions$depth_top_mm,
    predictions$depth_bottom_mm
  )
  layers <- unique(layer)
  colors <- rep(c("#0072B2", "#D55E00", "#009E73", "#CC79A7"), length.out = length(layers))
  names(colors) <- layers
  geometric <- geometric_plot_summary(predictions)

  with_cltf_par({
    graphics::plot(
      range(predictions$days_since_application, finite = TRUE),
      range(positive, finite = TRUE),
      type = "n",
      log  = "y",
      xlab = "Days since application",
      ylab = "Resident concentration (\u00b5g/kg)"
    )
    for (current_layer in layers) {
      selected <- layer == current_layer
      fitted <- unique(predictions[
        selected,
        c("days_since_application", "predicted_concentration_ug_kg")
      ])
      fitted <- fitted[order(fitted$days_since_application), ]
      fitted <- fitted[
        is.finite(fitted$predicted_concentration_ug_kg) &
          fitted$predicted_concentration_ug_kg > 0,
      ]
      graphics::lines(
        fitted$days_since_application,
        fitted$predicted_concentration_ug_kg,
        col = colors[current_layer],
        lwd = 2
      )
      usable <- selected &
        is.finite(predictions$analysis_concentration_ug_kg) &
        predictions$analysis_concentration_ug_kg > 0
      graphics::points(
        predictions$days_since_application[usable],
        predictions$analysis_concentration_ug_kg[usable],
        pch = 1,
        col = colors[current_layer]
      )

      geometric_layer <- cltf_layer_label(
        geometric$depth_top_mm,
        geometric$depth_bottom_mm
      ) == current_layer
      graphics::points(
        geometric$days_since_application[geometric_layer],
        geometric$geometric_mean_ug_kg[geometric_layer],
        pch = 16,
        col = colors[current_layer]
      )
    }
    graphics::legend(
      "topright",
      legend = c(
        paste(layers, "fit"),
        "Replicate",
        "Geometric mean"
      ),
      col = c(colors[layers], "#333333", "#333333"),
      lty = c(rep(1, length(layers)), NA, NA),
      lwd = c(rep(2, length(layers)), NA, NA),
      pch = c(rep(NA, length(layers)), 1, 16),
      bty = "n",
      cex = 0.85
    )
  })
  invisible(predictions)
}

#' Plot log residuals against fitted concentration
#'
#' @param predictions Fit prediction table returned by [fit_cltf()].
#' @return The input data, invisibly.
#' @export
plot_residuals <- function(predictions) {
  require_plot_columns(
    predictions,
    c(
      "depth_top_mm",
      "depth_bottom_mm",
      "analysis_concentration_ug_kg",
      "predicted_concentration_ug_kg"
    ),
    "predictions"
  )
  residual <- if ("log_residual" %in% names(predictions)) {
    predictions$log_residual
  } else {
    log(predictions$analysis_concentration_ug_kg) -
      log(predictions$predicted_concentration_ug_kg)
  }
  usable <- is.finite(residual) &
    is.finite(predictions$predicted_concentration_ug_kg) &
    predictions$predicted_concentration_ug_kg > 0
  if (!any(usable)) {
    stop("predictions contain no finite log residuals.", call. = FALSE)
  }
  layer <- cltf_layer_label(
    predictions$depth_top_mm,
    predictions$depth_bottom_mm
  )
  layers <- unique(layer[usable])
  colors <- rep(c("#0072B2", "#D55E00", "#009E73", "#CC79A7"), length.out = length(layers))
  names(colors) <- layers

  with_cltf_par({
    graphics::plot(
      predictions$predicted_concentration_ug_kg[usable],
      residual[usable],
      log  = "x",
      pch  = 16,
      col  = colors[layer[usable]],
      xlab = "Fitted concentration (\u00b5g/kg, log scale)",
      ylab = "Log(observed) - log(fitted)"
    )
    graphics::abline(h = 0, lty = 2, col = "#666666")
    graphics::legend(
      "topright",
      legend = layers,
      col    = colors[layers],
      pch    = 16,
      bty    = "n"
    )
  })
  invisible(predictions)
}

#' Plot CLTF mass fractions through time
#'
#' @param simulation Simulation table returned by [simulate_cltf()].
#' @return The input data, invisibly.
#' @export
plot_mass_fractions <- function(simulation) {
  mass_columns <- c(
    "mass_top",
    "mass_bottom",
    "mass_below",
    "mass_degraded"
  )
  require_plot_columns(
    simulation,
    c("time_days", mass_columns),
    "simulation"
  )
  colors <- c("#0072B2", "#D55E00", "#009E73", "#777777")

  with_cltf_par({
    graphics::matplot(
      simulation$time_days,
      simulation[mass_columns],
      type = "l",
      lty  = 1,
      lwd  = 2,
      col  = colors,
      ylim = c(0, 1),
      xlab = "Days since application",
      ylab = "Applied-mass fraction"
    )
    graphics::legend(
      "right",
      legend = c("Top layer", "Bottom layer", "Below profile", "Degraded"),
      col    = colors,
      lty    = 1,
      lwd    = 2,
      bty    = "n"
    )
  })
  invisible(simulation)
}

#' Plot numerical mass balance through time
#'
#' @inheritParams plot_mass_fractions
#' @return The input data, invisibly.
#' @export
plot_mass_balance <- function(simulation) {
  mass_columns <- c(
    "mass_top",
    "mass_bottom",
    "mass_below",
    "mass_degraded"
  )
  require_plot_columns(
    simulation,
    c("time_days", mass_columns),
    "simulation"
  )
  total <- rowSums(simulation[mass_columns])
  deviation <- total - 1
  limit <- max(abs(deviation), 1e-12)

  with_cltf_par({
    graphics::plot(
      simulation$time_days,
      deviation,
      type = "l",
      lwd  = 1.8,
      col  = "#0072B2",
      ylim = c(-limit, limit),
      xlab = "Days since application",
      ylab = "Mass-balance error"
    )
    graphics::abline(h = 0, lty = 2, col = "#666666")
  })
  invisible(simulation)
}

#' Plot one or more objective profiles
#'
#' @param profile Profile table returned by [profile_cltf_parameter()].
#' @return The input data, invisibly.
#' @export
plot_objective_profile <- function(profile) {
  require_plot_columns(
    profile,
    c("parameter", "parameter_value", "objective"),
    "profile"
  )
  parameters <- unique(as.character(profile$parameter))

  with_cltf_par({
    graphics::par(
      mfrow = grDevices::n2mfrow(length(parameters)),
      mar   = c(4.2, 5.2, 1.2, 1.0)
    )
    for (parameter in parameters) {
      selected <- profile$parameter == parameter
      values <- profile[selected, ]
      values <- values[order(values$parameter_value), ]
      graphics::plot(
        values$parameter_value,
        values$objective,
        type = "b",
        pch  = 16,
        col  = "#0072B2",
        xlab = parameter,
        ylab = "Log-RMSE objective"
      )
      minimum <- which.min(values$objective)
      graphics::abline(
        v   = values$parameter_value[minimum],
        lty = 2,
        col = "#D55E00"
      )
    }
  })
  invisible(profile)
}

#' Plot SLGA bulk density by depth
#'
#' @param bulk_density Standard bulk-density band table.
#' @return The input data, invisibly.
#' @export
plot_bulk_density <- function(bulk_density) {
  require_plot_columns(
    bulk_density,
    c(
      "depth_top_mm",
      "depth_bottom_mm",
      "estimate_g_cm3",
      "lower_g_cm3",
      "upper_g_cm3"
    ),
    "bulk_density"
  )
  x_limit <- range(
    c(bulk_density$lower_g_cm3, bulk_density$upper_g_cm3),
    finite = TRUE
  )
  y_limit <- rev(range(
    c(bulk_density$depth_top_mm, bulk_density$depth_bottom_mm),
    finite = TRUE
  ))

  with_cltf_par({
    graphics::plot(
      x_limit,
      y_limit,
      type = "n",
      xlab = expression(paste("Bulk density (g/", cm^3, ")")),
      ylab = "Depth (mm)"
    )
    for (index in seq_len(nrow(bulk_density))) {
      graphics::rect(
        bulk_density$lower_g_cm3[index],
        bulk_density$depth_top_mm[index],
        bulk_density$upper_g_cm3[index],
        bulk_density$depth_bottom_mm[index],
        col    = grDevices::adjustcolor("#0072B2", alpha.f = 0.18),
        border = "#0072B2"
      )
      graphics::segments(
        bulk_density$estimate_g_cm3[index],
        bulk_density$depth_top_mm[index],
        bulk_density$estimate_g_cm3[index],
        bulk_density$depth_bottom_mm[index],
        col = "#D55E00",
        lwd = 2.5
      )
    }
    graphics::legend(
      "bottomright",
      legend = c("Estimate", "SLGA interval"),
      col    = c("#D55E00", "#0072B2"),
      lwd    = c(2.5, 8),
      bty    = "n"
    )
  })
  invisible(bulk_density)
}

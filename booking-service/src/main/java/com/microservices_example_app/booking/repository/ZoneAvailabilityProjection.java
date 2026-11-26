package com.microservices_example_app.booking.repository;

import com.microservices_example_app.booking.model.Zone;

import java.math.BigDecimal;

/**
 * Aggregated active-ticket counts per zone for a single event.
 */
public interface ZoneAvailabilityProjection {
    Zone getZone();

    Long getSeatsLeft();

    BigDecimal getMinPrice();
}

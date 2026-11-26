package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.Zone;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.io.Serializable;
import java.math.BigDecimal;

/**
 * Active seats and the cheapest price inside a single event zone.
 */
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ZoneAvailabilityDto implements Serializable {
    private static final long serialVersionUID = 1L;
    private Zone zone;
    private Long seatsLeft;
    private BigDecimal minPrice;
}

package com.microservices_example_app.booking.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.io.Serializable;
import java.util.List;

/**
 * Exact, party-aware availability of an event.
 *
 * <p>Read-only snapshot: active tickets grouped by zone plus the venue
 * capacity. {@code party} is not echoed back; callers pass it as a query
 * parameter.</p>
 */
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class EventAvailabilityResponseDto implements Serializable {
    private static final long serialVersionUID = 1L;
    private Long eventId;
    private AvailabilityStatus status;
    private Integer capacity;
    private List<ZoneAvailabilityDto> zones;
}

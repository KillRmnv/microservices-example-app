package com.microservices_example_app.booking.dto;

import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Locale;

/**
 * Coarse, party-aware availability of an event.
 *
 * <p>Serialized in lower snake case ({@code available}, {@code few_left},
 * {@code insufficient}, {@code sold_out}) because the assistant and the
 * frontend consume those exact values. An unknown event is reported as HTTP
 * 404 (ProblemDetail {@code not_found}) instead of a status value.</p>
 */
public enum AvailabilityStatus {
    AVAILABLE,
    FEW_LEFT,
    INSUFFICIENT,
    SOLD_OUT;

    @JsonValue
    public String value() {
        return name().toLowerCase(Locale.ROOT);
    }
}

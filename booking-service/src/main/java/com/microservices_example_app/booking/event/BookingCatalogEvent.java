package com.microservices_example_app.booking.event;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

/**
 * One row of the searchable catalog stream.
 *
 * <p>Published to {@code booking.catalog} on every create/update/delete and
 * replayed in full on startup, so the collector can rebuild its search index
 * from Kafka alone. Timestamps are ISO-8601 in UTC because booking stores
 * naive {@code TIMESTAMP} values filled by {@code CURRENT_TIMESTAMP}.</p>
 */
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class BookingCatalogEvent {

    private Long id;
    private String title;
    private String startsAt;
    private String endsAt;
    private Long venueId;
    private String venuePlace;
    private Long townId;
    private String townName;
    private String category;
    private String admissionMode;
    private boolean deleted;
}

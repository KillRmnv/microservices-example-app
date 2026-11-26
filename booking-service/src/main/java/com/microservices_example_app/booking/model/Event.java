package com.microservices_example_app.booking.model;

import jakarta.persistence.*;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.experimental.SuperBuilder;

import java.time.LocalDateTime;

@Entity
@Table(name = "events")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
public class Event extends BaseEntity {

    @Column(nullable = false)
    private String title;

    @Column(nullable = false)
    private LocalDateTime startsAt;

    @Column(nullable = false)
    private LocalDateTime endsAt;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "venue_id", nullable = false)
    private Venue venue;

    @Column(nullable = false, length = 32)
    @Builder.Default
    private String category = "other";

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private EventAdmissionMode admissionMode;
}
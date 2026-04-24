package com.microservices_example_app.booking.model;

import jakarta.persistence.*;
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

    @Enumerated(EnumType.STRING)
    @Column(nullable = false)
    private EventAdmissionMode admissionMode;
}
package com.microservices_example_app.booking.model;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.experimental.SuperBuilder;

@Entity
@Table(name = "seats")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
public class Seat extends BaseEntity {

    @Column(nullable = false)
    private String sector;

    @Column(name = "row_label", nullable = false)
    private String row;

    @Column(name = "seat_number", nullable = false)
    private String number;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "venue_id", nullable = false)
    private Venue venue;
}
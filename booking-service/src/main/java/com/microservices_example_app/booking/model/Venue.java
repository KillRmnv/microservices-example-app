package com.microservices_example_app.booking.model;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import lombok.experimental.SuperBuilder;

@Entity
@Table(name = "venues")
@Getter
@Setter
@SuperBuilder
@NoArgsConstructor
public class Venue extends BaseEntity {

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "town_id", nullable = false)
    private Town town;

    @Column(nullable = false)
    private String place;

    @Column(nullable = false)
    private Integer capacity;
}
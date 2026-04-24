package com.microservices_example_app.booking.model;

import jakarta.persistence.Entity;

@Entity
public class Seat extends BaseEntity {
    private String sector;
    private String row;
    private String number;
    private Venue venue;
}

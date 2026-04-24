package com.microservices_example_app.booking.model;

import java.time.LocalDateTime;

public class Event extends BaseEntity {
    private String title;
    private LocalDateTime startsAt;
    private LocalDateTime endsAt;
    private Venue venue;
    private EventAdmissionMode admissionMode;
}

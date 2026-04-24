package com.microservices_example_app.booking.model;

import java.math.BigDecimal;

public class Ticket extends BaseEntity {
    private Event event;
    private Zone zone;
    private BigDecimal price;
    private boolean isActive;
    private int userId;
}

package com.microservices_example_app.booking.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;

@AllArgsConstructor
@Getter
@Setter
public class VenueSearchRequestDto {
    private Integer townId;
    private String place;
    private Integer minCapacity;
    private Integer maxCapacity;
}

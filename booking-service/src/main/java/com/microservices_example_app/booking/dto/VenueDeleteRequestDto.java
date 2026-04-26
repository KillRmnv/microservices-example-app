package com.microservices_example_app.booking.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@AllArgsConstructor
@NoArgsConstructor
@Setter
@Getter
public class VenueDeleteRequestDto {
    private Integer townId;
    private String place;
    private Integer minCapacity;
    private Integer maxCapacity;
}

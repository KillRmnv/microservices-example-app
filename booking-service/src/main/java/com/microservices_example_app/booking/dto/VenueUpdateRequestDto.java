package com.microservices_example_app.booking.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
public class VenueUpdateRequestDto {
    private Integer id;
    private Integer townId;
    private String place;
    private Integer capacity;
}

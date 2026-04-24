package com.microservices_example_app.booking.dto;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class VenueResponseDto {
    private Integer id;
    private Integer townId;
    private String townName;
    private String place;
    private Integer capacity;
}
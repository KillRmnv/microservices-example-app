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
public class SeatResponseDto {
    private Integer id;
    private String sector;
    private String row;
    private String number;
    private Integer venueId;
    private String venuePlace;
}
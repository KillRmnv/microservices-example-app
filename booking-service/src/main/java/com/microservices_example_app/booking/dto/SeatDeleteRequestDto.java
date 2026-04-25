package com.microservices_example_app.booking.dto;

import lombok.*;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class SeatDeleteRequestDto {
    private String sector;
    private String row;
    private String number;
    private Integer venueId;
}

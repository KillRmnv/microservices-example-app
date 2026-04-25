package com.microservices_example_app.booking.dto;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class SeatUpdateRequestDto {
    private Integer id;
    private String sector;
    private String row;
    private String number;
    private Integer venueId;
}

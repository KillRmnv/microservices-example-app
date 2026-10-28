package com.microservices_example_app.booking.dto;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "Request to update an existing seat")
public class SeatUpdateRequestDto {
    private Integer id;
    private String sector;
    private String row;
    private String number;
    private Integer venueId;
}

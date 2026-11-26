package com.microservices_example_app.booking.dto;

import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@NoArgsConstructor
@AllArgsConstructor
@Getter
@Setter
@Schema(description = "Request to update an existing venue")
public class VenueUpdateRequestDto {
    private Long id;
    private Long townId;
    private String place;
    private Integer capacity;
}

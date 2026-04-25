package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.Zone;

import java.math.BigDecimal;
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
public class SeatableTicketUpdateRequestDto {
    private Integer id;
    private Integer eventId;
    private Integer seatId;
    private Zone zone;
    private BigDecimal price;
    private Boolean active;
    private Integer userId;
    private String sector;
    private String row;
    private String number;
}

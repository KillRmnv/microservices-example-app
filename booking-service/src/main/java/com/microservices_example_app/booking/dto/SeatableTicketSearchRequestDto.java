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
public class SeatableTicketSearchRequestDto {
    private Long eventId;
    private Long seatId;
    private Zone zone;
    private BigDecimal minPrice;
    private BigDecimal maxPrice;
    private Boolean active;
    private Long userId;
    private String sector;
    private String row;
    private String number;
}

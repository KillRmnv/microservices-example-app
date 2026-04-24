package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.Zone;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.math.BigDecimal;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class TicketSearchRequestDto {
    private Integer eventId;
    private Integer userId;
    private Zone zone;
    private Boolean active;
    private BigDecimal maxPrice;
}
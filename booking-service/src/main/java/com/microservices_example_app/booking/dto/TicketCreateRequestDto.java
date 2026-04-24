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
public class TicketCreateRequestDto {
    private Integer eventId;
    private Zone zone;
    private BigDecimal price;
    private Boolean active;
    private Integer userId;
}
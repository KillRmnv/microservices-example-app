package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.Zone;

import java.math.BigDecimal;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class TicketUpdateRequestDto {
    private Integer id;
    private Integer eventId;
    private String eventTitle;
    private Zone zone;
    private BigDecimal price;
    private Boolean active;
    private Integer userId;
}

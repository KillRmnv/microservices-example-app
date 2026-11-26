package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.Zone;
import io.swagger.v3.oas.annotations.media.Schema;
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
@Schema(description = "Request to create a general-admission ticket")
public class TicketCreateRequestDto {
    private Long eventId;
    private Zone zone;
    private BigDecimal price;
    private Boolean active;
    private Long userId;
}
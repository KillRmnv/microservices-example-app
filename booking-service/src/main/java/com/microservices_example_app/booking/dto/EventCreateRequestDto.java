package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.EventAdmissionMode;
import io.swagger.v3.oas.annotations.media.Schema;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

import java.time.LocalDateTime;

@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
@Schema(description = "Request to create a new event")
public class EventCreateRequestDto {
    private String title;
    private LocalDateTime startsAt;
    private LocalDateTime endsAt;
    private Long venueId;
    private String category;
    private EventAdmissionMode admissionMode;
}
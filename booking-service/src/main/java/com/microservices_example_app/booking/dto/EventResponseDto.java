package com.microservices_example_app.booking.dto;

import com.microservices_example_app.booking.model.EventAdmissionMode;
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
public class EventResponseDto {
    private Integer id;
    private String title;
    private LocalDateTime startsAt;
    private LocalDateTime endsAt;
    private Integer venueId;
    private String venuePlace;
    private EventAdmissionMode admissionMode;
}